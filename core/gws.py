"""
GWS — Global Workspace System 主协调器

将所有层连接在一起：
- 记忆层 (Memory)
- 情绪层 (Emotion)
- 潜意识层 (Subconscious)
- 思考层 / 全局工作空间 (Workspace)
- 语言层 (Language → 由外部 LLM 提供)

这是核心的运行时，独立于任何特定平台。
"""

import json
import time
from pathlib import Path
from typing import Optional

from .memory import LongTermMemory, WorkingMemory, MemoryType, EmotionState as MemEmotion
from .emotion import EmotionEngine, EmotionState
from .subconscious import SubconsciousLayer
from .workspace import GlobalWorkspace


class GWS:
    """
    Global Workspace System — 主系统

    用法：
        gws = GWS(workspace_dir="./data")
        gws.start()

        # 主循环（或由外部驱动）
        while True:
            gws.tick()          # 推进潜意识
            gws.on_input(text)  # 处理外部输入
            gws.get_output()    # 获取意识层输出
    """

    def __init__(
        self,
        workspace_dir: str,
        # 记忆层参数
        working_memory_capacity: int = 20,
        working_memory_half_life: float = 1800,
        # 情绪层参数
        emotion_decay: float = 0.98,
        # 潜意识层参数
        cycle_seconds: int = 3600,
        burst_agents: int = 4,
        burst_duration: int = 1200,
        # 工作空间参数
        workspace_capacity: int = 5,
        promotion_threshold: float = 0.5,
    ):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # === 初始化各层 ===

        # 记忆层
        self.working_memory = WorkingMemory(
            capacity=working_memory_capacity,
            half_life=working_memory_half_life,
        )
        self.long_term_memory = LongTermMemory(
            storage_path=self.workspace_dir / "long_term"
        )

        # 情绪层
        self.emotion_engine = EmotionEngine(decay_rate=emotion_decay)

        # 潜意识层
        self.subconscious = SubconsciousLayer(
            memory=self.long_term_memory,
            emotion_engine=self.emotion_engine,
            cycle_seconds=cycle_seconds,
            burst_agents=burst_agents,
            burst_duration=burst_duration,
        )

        # 思考层 / 全局工作空间
        self.workspace = GlobalWorkspace(
            memory=self.long_term_memory,
            emotion_engine=self.emotion_engine,
            capacity=workspace_capacity,
            promotion_threshold=promotion_threshold,
        )

        # LLM 组件（可选，有 API key 时启用）
        self.llm_client = None
        self.llm_emotion_extractor = None
        self.language_layer = None

        # 状态
        self._started = False
        self._tick_count = 0
        self._input_count = 0

    def enable_llm(self, provider: str = "openrouter", api_key: str = "", model: str = ""):
        """启用 LLM 驱动的组件"""
        from .llm import LLMClient, LLMConfig
        from .emotion_llm import LLMEmotionExtractor
        from .language import LanguageLayer

        config = LLMConfig(
            provider=provider,
            api_key=api_key,
            model=model,
        )
        self.llm_client = LLMClient(config)
        self.llm_emotion_extractor = LLMEmotionExtractor(self.llm_client)
        self.language_layer = LanguageLayer(self.llm_client)

    def start(self):
        """启动系统"""
        self._started = True
        # 编码启动记忆
        self.long_term_memory.encode(
            content="GWS 系统启动",
            memory_type=MemoryType.EPISODIC,
            emotion=MemEmotion(0.3, 0.4, 0.2),
            tags=["system", "startup"],
            source="gws",
        )

    def tick(self) -> dict:
        """
        推进一个时间步（由外部定期调用）

        返回本轮的状态摘要
        """
        self._tick_count += 1

        # 1. 推进潜意识层
        subconscious_outputs = self.subconscious.tick()

        # 2. 如果有产出，送入工作空间
        if subconscious_outputs:
            self.workspace.receive(subconscious_outputs)

        # 3. 获取潜意识队列中的产出
        pending = self.subconscious.drain_outputs()
        if pending:
            self.workspace.receive(pending)

        # 4. 思考层处理
        conscious = self.workspace.think()

        # 5. 情绪自然衰减（在 EmotionEngine 中自动处理）

        return {
            "tick": self._tick_count,
            "subconscious": self.subconscious.status(),
            "workspace": self.workspace.status(),
            "new_conscious": len(conscious),
            "emotion": self.emotion_engine.get_influence(),
        }

    def on_input(self, text: str, source: str = "user") -> dict:
        """
        处理外部输入（用户对话等）

        输入会影响情绪，写入工作记忆，触发思考
        """
        self._input_count += 1

        # 1. 更新情绪（LLM 优先，回退到规则）
        if self.llm_emotion_extractor:
            extracted = self.llm_emotion_extractor.extract(text)
            self.emotion_engine.set_emotion(extracted, blend_weight=0.4)
        else:
            self.emotion_engine.update_from_text(text)

        # 2. 写入工作记忆
        from .memory import MemoryEntry
        entry = MemoryEntry(
            id=f"input-{self._input_count}",
            content=text,
            memory_type=MemoryType.EPISODIC,
            emotion=MemEmotion(
                self.emotion_engine.state.valence,
                self.emotion_engine.state.arousal,
                self.emotion_engine.state.dominance,
            ),
            created_at=time.time(),
            last_accessed=time.time(),
            source=source,
        )
        self.working_memory.add(entry)

        # 3. 有意义的输入写入长期记忆
        if self.emotion_engine.state.intensity > 0.1 or len(text) > 20:
            self.long_term_memory.encode(
                content=text,
                memory_type=MemoryType.EPISODIC,
                emotion=MemEmotion(
                    self.emotion_engine.state.valence,
                    self.emotion_engine.state.arousal,
                    self.emotion_engine.state.dominance,
                ),
                tags=["input", source],
                source=source,
            )

        return {
            "emotion": self.emotion_engine.state.to_dict(),
            "emotion_label": self.emotion_engine.state.label,
            "working_memory_size": len(self.working_memory.get_all()),
        }

    def get_output(self) -> Optional[list[dict]]:
        """
        获取意识层的内容（待语言层表达）

        消费后清空
        """
        conscious = self.workspace.get_consciousness()
        if not conscious:
            return None
        return conscious

    def think_about(self, query: str) -> dict:
        """
        主动思考某个话题

        从长期记忆检索相关内容，注入工作空间
        """
        # 检索相关记忆
        memories = self.long_term_memory.retrieve(
            query=query,
            emotion_bias=self.emotion_engine.state,
            limit=5,
        )

        # 包装为潜意识产出，注入工作空间
        from .subconscious import SubAgentOutput, AgentRole
        output = SubAgentOutput(
            id=f"think-{int(time.time())}",
            agent_role=AgentRole.EXPLORER,
            content=f"关于「{query}」的思考：找到了 {len(memories)} 条相关记忆",
            confidence=0.6,
            emotion=self.emotion_engine.state,
            timestamp=time.time(),
            related_memories=[m.id for m in memories],
            tags=["active_thinking", "query"],
        )
        self.workspace.receive([output])
        conscious = self.workspace.think()

        return {
            "query": query,
            "memories_found": len(memories),
            "conscious_output": conscious,
        }

    def get_status(self) -> dict:
        """系统整体状态"""
        return {
            "uptime_ticks": self._tick_count,
            "inputs_processed": self._input_count,
            "emotion": self.emotion_engine.get_influence(),
            "subconscious": self.subconscious.status(),
            "workspace": self.workspace.status(),
            "working_memory": len(self.working_memory.get_all()),
            "long_term_memory": self.long_term_memory.stats(),
        }

    def speak(self, user_message: str = None) -> str:
        """
        系统说话 — 用语言层表达意识层内容

        如果有 user_message，则回应用户
        否则表达当前的内部思考
        """
        if not self.language_layer:
            return "[语言层未启用: 需要调用 enable_llm()]"

        conscious = self.workspace.get_consciousness()
        influence = self.emotion_engine.get_influence()

        if user_message:
            # 先处理输入
            self.on_input(user_message)
            conscious = self.workspace.get_consciousness()
            influence = self.emotion_engine.get_influence()

            # 获取相关记忆
            memories = self.long_term_memory.retrieve(
                query=user_message,
                emotion_bias=self.emotion_engine.state,
                limit=3,
            )
            memory_context = [m.content for m in memories]

            return self.language_layer.respond_to_user(
                user_message=user_message,
                conscious_outputs=conscious,
                emotion_influence=influence,
                memory_context=memory_context,
            )
        else:
            return self.language_layer.express(
                conscious_outputs=conscious,
                emotion_influence=influence,
                working_memory_count=len(self.working_memory.get_all()),
            )

    def export_state(self) -> str:
        """导出完整状态（用于持久化或调试）"""
        return json.dumps(self.get_status(), ensure_ascii=False, indent=2)
