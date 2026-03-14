"""
认知协调器 v3 — CognitiveOrchestrator

整合所有认知模块的主协调器：
- OCC 认知评估 → 情感产生
- PAD 心境缓冲器 + 神经递质调制
- HRRL 稳态内驱力
- GWT 全局工作空间（显著性竞争 + 点火 + 广播）
- 潜意识层（4 Agent 并行）
- 有界自治安全层
- 黑板 + 意图生成 + 表达欲

这是 GWS v3 的"大脑皮层"——协调一切。
"""

import json
import time
import uuid
from pathlib import Path
from typing import Optional

from .memory import LongTermMemory, WorkingMemory, MemoryType, MemoryEntry
from .emotion import EmotionEngine, EmotionState
from .subconscious import SubconsciousLayer, AgentRole, SubAgentOutput
from .workspace import GlobalWorkspace
from .state import StateManager
from .events import EventBus, Event, EventType
from .blackboard import Blackboard, BlackboardEntry, EntryType
from .drives import HRRLDriveEngine
from .intentions import IntentionGenerator
from .urge import UrgeToSpeak
from .occ import OCCEngine
from .neurotransmitter import NeurotransmitterEngine
from .safety import BoundedAutonomy


class CognitiveOrchestrator:
    """
    v3 认知协调器

    增强的 tick 流程：
    1. 神经递质 tick
    2. 潜意识推进 → 黑板
    3. OCC 评估（如有新输入）
    4. PAD 心境更新 + 神经递质调制
    5. 驱动力 HRRL 更新
    6. 黑板显著性竞争
    7. 工作空间点火检查 → 广播
    8. 安全边界检查
    9. 意图生成
    10. 表达欲更新
    """

    def __init__(
        self,
        workspace_dir: str,
        working_memory_capacity: int = 20,
        working_memory_half_life: float = 1800,
        emotion_decay: float = 0.98,
        cycle_seconds: int = 3600,
        burst_agents: int = 2,
        burst_duration: int = 1200,
        workspace_capacity: int = 5,
        ignition_threshold: float = 0.45,
        urge_threshold: float = 0.6,
        urge_cooldown: float = 120,
    ):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # === 事件总线 ===
        self.event_bus = EventBus()

        # === 神经递质 ===
        self.neurotransmitter = NeurotransmitterEngine()

        # === OCC 评估引擎 ===
        self.occ_engine = OCCEngine()

        # === 记忆层 ===
        self.working_memory = WorkingMemory(
            capacity=working_memory_capacity,
            half_life=working_memory_half_life,
        )
        self.long_term_memory = LongTermMemory(
            storage_path=self.workspace_dir / "long_term"
        )

        # === 情绪层（带心境缓冲器） ===
        self.emotion_engine = EmotionEngine(
            decay_rate=emotion_decay,
            event_bus=self.event_bus,
        )
        self.emotion_engine.set_neurotransmitter(self.neurotransmitter)

        # === HRRL 稳态内驱力 ===
        self.drives = HRRLDriveEngine(event_bus=self.event_bus)

        # === 黑板 ===
        self.blackboard = Blackboard(event_bus=self.event_bus)

        # === 潜意识层 ===
        self.subconscious = SubconsciousLayer(
            memory=self.long_term_memory,
            emotion_engine=self.emotion_engine,
            cycle_seconds=cycle_seconds,
            burst_agents=burst_agents,
            burst_duration=burst_duration,
        )

        # === GWT 全局工作空间 ===
        self.workspace = GlobalWorkspace(
            memory=self.long_term_memory,
            emotion_engine=self.emotion_engine,
            capacity=workspace_capacity,
            ignition_threshold=ignition_threshold,
        )

        # === 有界自治 ===
        self.safety = BoundedAutonomy()

        # === 意图生成器 ===
        self.intentions = IntentionGenerator(event_bus=self.event_bus)

        # === 表达欲 ===
        self.urge = UrgeToSpeak(
            event_bus=self.event_bus,
            threshold=urge_threshold,
            cooldown=urge_cooldown,
        )

        # === 状态持久化 ===
        self.state_manager = StateManager(self.workspace_dir / "state")

        # === LLM 组件 ===
        self.llm_client = None
        self.llm_emotion_extractor = None
        self.language_layer = None

        # === 状态 ===
        self._started = False
        self._tick_count = 0
        self._input_count = 0
        self._input_history: list[dict] = []
        self._last_occ_result = None

        self._setup_event_listeners()

    def _setup_event_listeners(self):
        """设置事件监听"""
        self.event_bus.subscribe(EventType.SUBCONSCIOUS_OUTPUT, self._on_subconscious_output)
        self.event_bus.subscribe(EventType.DRIVE_THRESHOLD_CROSSED, self._on_drive_triggered)

    def _on_subconscious_output(self, event: Event):
        """潜意识产出 → 黑板 + 驱动力"""
        data = event.data
        role_to_type = {
            "explorer": EntryType.EXPLORATION,
            "pattern_finder": EntryType.PATTERN,
            "associator": EntryType.ASSOCIATION,
            "dreamer": EntryType.DREAM,
        }
        agent_role = data.get("agent_role", "explorer")
        entry_type = role_to_type.get(agent_role, EntryType.EXPLORATION)

        entry = BlackboardEntry(
            id=data.get("id", str(uuid.uuid4())[:8]),
            entry_type=entry_type,
            content=data.get("content", ""),
            agent_role=agent_role,
            confidence=data.get("confidence", 0.5),
            emotion=data.get("emotion", {}),
            timestamp=data.get("timestamp", time.time()),
            related_memories=data.get("related_memories", []),
            tags=data.get("tags", []),
            salience=0.5 + data.get("confidence", 0.5) * 0.3,
        )
        self.blackboard.write(entry)
        self.drives.on_subconscious_output()

    def _on_drive_triggered(self, event: Event):
        """驱动力触发 → 生成意图"""
        self._generate_intentions()

    def enable_llm(self, provider: str = "openrouter", api_key: str = "", model: str = "", lightweight_model: str = ""):
        """启用 LLM 功能"""
        from .llm import LLMClient, LLMConfig
        from .emotion_llm import LLMEmotionExtractor
        from .language import LanguageLayer

        config = LLMConfig(provider=provider, api_key=api_key, model=model)
        self.llm_client = LLMClient(config)
        self.llm_emotion_extractor = LLMEmotionExtractor(self.llm_client)
        self.language_layer = LanguageLayer(self.llm_client)

        # 潜意识用轻量模型
        if lightweight_model:
            try:
                lw_config = LLMConfig(provider=provider, api_key=api_key, model=lightweight_model)
                self.subconscious.set_llm(LLMClient(lw_config))
            except Exception:
                self.subconscious.set_llm(self.llm_client)
        else:
            self.subconscious.set_llm(self.llm_client)

    def start(self):
        """系统启动"""
        self._started = True
        restored = self.state_manager.restore(self)
        if restored:
            self.long_term_memory.encode(
                content="GWS v3 系统重启",
                memory_type=MemoryType.EPISODIC,
                emotion=EmotionState(0.2, 0.3, 0.2),
                tags=["system", "restart"],
                source="orchestrator",
            )
        else:
            self.long_term_memory.encode(
                content="GWS v3 系统启动",
                memory_type=MemoryType.EPISODIC,
                emotion=EmotionState(0.3, 0.4, 0.2),
                tags=["system", "startup"],
                source="orchestrator",
            )

    def tick(self) -> dict:
        """推进一个认知周期"""
        self._tick_count += 1
        tick_start = time.time()

        # 1. 神经递质 tick
        self.neurotransmitter.tick()

        # 2. 潜意识推进 → 黑板
        self.subconscious.tick()
        pending = self.subconscious.drain_outputs()
        for output in pending:
            self.event_bus.emit(Event(
                type=EventType.SUBCONSCIOUS_OUTPUT,
                data=output.to_dict(),
                source="subconscious",
            ))

        # 3. 黑板衰减
        self.blackboard.tick_decay()

        # 4. 驱动力 HRRL 更新
        self.drives.tick()

        # 5. 更新安全边界
        drive_values = self.drives.state.get_values()
        self.safety.update_bounds(drive_values)
        system_mode = self.safety.get_system_mode()

        # 6. 工作空间显著性竞争 + 点火
        salient = self.blackboard.pick_salient(limit=3, min_salience=0.25)
        if salient:
            ws_outputs = []
            for entry in salient:
                try:
                    role = AgentRole(entry.agent_role) if entry.agent_role in [r.value for r in AgentRole] else AgentRole.EXPLORER
                except (ValueError, KeyError):
                    role = AgentRole.EXPLORER
                ws_outputs.append(SubAgentOutput(
                    id=entry.id,
                    agent_role=role,
                    content=entry.content,
                    confidence=entry.confidence,
                    emotion=EmotionState.from_dict(entry.emotion) if isinstance(entry.emotion, dict) else self.emotion_engine.state,
                    timestamp=entry.timestamp,
                    related_memories=entry.related_memories,
                    tags=entry.tags + ["from_blackboard"],
                ))
            self.workspace.receive(ws_outputs)

        # 工作空间思考（含点火）
        conscious = self.workspace.think()

        # 7. 情绪衰减
        self.emotion_engine._decay()

        # 8. 意图生成
        self._generate_intentions()

        # 9. 表达欲更新
        influence = self.emotion_engine.get_influence()
        new_insights = len([e for e in self.blackboard.entries if not e.promoted])
        avg_salience = sum(e.salience for e in self.blackboard.entries) / max(len(self.blackboard.entries), 1)
        self.urge.update(
            arousal=influence["state"]["arousal"],
            new_insight_count=new_insights,
            insight_salience=avg_salience,
            expression_drive=drive_values.get("energy", 0.5),
        )

        # 10. 资源消耗记录
        elapsed_ms = (time.time() - tick_start) * 1000
        self.safety.record_cost(elapsed_ms / 1000)

        return {
            "tick": self._tick_count,
            "subconscious": self.subconscious.status(),
            "blackboard": self.blackboard.status(),
            "drives": self.drives.status(),
            "neurotransmitter": self.neurotransmitter.status(),
            "safety": self.safety.status(),
            "intentions": self.intentions.status(),
            "urge": self.urge.status(),
            "workspace": self.workspace.status(),
            "emotion": influence,
            "conscious_items": len(conscious),
            "system_mode": system_mode.value,
            "elapsed_ms": round(elapsed_ms),
        }

    def on_input(self, text: str, source: str = "user") -> dict:
        """处理外部输入"""
        self._input_count += 1
        now = time.time()

        self.drives.on_user_interaction()
        self.urge.on_user_interaction()

        # OCC 评估
        occ_result = self.occ_engine.appraise_from_text(text)
        self._last_occ_result = occ_result

        # 通过 OCC 更新情绪
        self.emotion_engine.update_from_occ(
            occ_pad=occ_result.pad_vector,
            intensity=occ_result.intensity,
            blend_weight=0.5,
        )

        # LLM 情绪提取（如果可用，作为补充）
        if self.llm_emotion_extractor:
            extracted = self.llm_emotion_extractor.extract(text)
            self.emotion_engine.set_emotion(extracted, blend_weight=0.3)

        # 神经递质更新
        self.neurotransmitter.update_from_pad(
            self.emotion_engine.state.valence,
            self.emotion_engine.state.arousal,
            self.emotion_engine.state.dominance,
        )

        # 工作记忆
        entry = MemoryEntry(
            id=f"input-{self._input_count}",
            content=text,
            memory_type=MemoryType.EPISODIC,
            emotion=self.emotion_engine.state,
            created_at=now,
            last_accessed=now,
            source=source,
            affective_tag={
                "occ_category": occ_result.category.value,
                "occ_intensity": occ_result.intensity,
            },
        )
        self.working_memory.add(entry)

        # 长期记忆（带躯体标记）
        if self.emotion_engine.state.intensity > 0.05 or len(text) > 10:
            self.long_term_memory.encode(
                content=text,
                memory_type=MemoryType.EPISODIC,
                emotion=self.emotion_engine.state,
                tags=["input", source],
                source=source,
                affective_tag={
                    "occ_category": occ_result.category.value,
                    "occ_intensity": occ_result.intensity,
                },
            )

        self.event_bus.emit(Event(
            type=EventType.USER_INPUT,
            data={
                "text": text,
                "source": source,
                "emotion": self.emotion_engine.state.to_dict(),
                "occ_category": occ_result.category.value,
            },
            source="user",
        ))

        self._input_history.append({
            "text": text,
            "time": now,
            "emotion": self.emotion_engine.state.label,
            "occ": occ_result.category.value,
        })

        return {
            "emotion": self.emotion_engine.state.to_dict(),
            "emotion_label": self.emotion_engine.state.label,
            "occ_category": occ_result.category.value,
            "coping_strategy": self.emotion_engine.mood_buffer.get_coping_strategy().value,
            "working_memory_size": len(self.working_memory.get_all()),
        }

    def _generate_intentions(self):
        """生成意图"""
        influence = self.emotion_engine.get_influence()
        drive_vector = self.drives.get_drive_vector()
        drive_status = self.drives.status()

        self.intentions.generate(
            drives=drive_vector,
            drive_states=drive_status.get("dimensions", {}),
            emotion=influence,
            dominant_drive=self.drives.get_dominant_need(),
        )

    def speak(self, user_message: str = None, proactive: bool = False) -> str:
        """系统说话"""
        if not self.language_layer:
            return "[语言层未启用]"

        bb_context = [e.to_dict() for e in self.blackboard.get_recent(seconds=300)]
        conscious = self.workspace.get_consciousness()
        influence = self.emotion_engine.get_influence()

        if user_message:
            self.on_input(user_message)
            conscious = self.workspace.get_consciousness()
            influence = self.emotion_engine.get_influence()
            memories = self.long_term_memory.retrieve(
                query=user_message,
                emotion_bias=self.emotion_engine.state,
                limit=3,
            )
            memory_context = [m.content for m in memories]

            response = self.language_layer.respond_to_user(
                user_message=user_message,
                conscious_outputs=conscious,
                emotion_influence=influence,
                memory_context=memory_context,
                blackboard_context=bb_context,
            )
        else:
            if proactive:
                top_intention = self.intentions.get_top_intention()
                if top_intention:
                    conscious = list(conscious) if conscious else []
                    conscious.append({"content": f"[想做] {top_intention.description}", "thoughts": []})

            response = self.language_layer.express(
                conscious_outputs=conscious,
                emotion_influence=influence,
                working_memory_count=len(self.working_memory.get_all()),
                blackboard_context=bb_context,
            )

        self.urge.on_speech_delivered()
        self.drives.on_expression_delivered()
        return response

    def get_output(self):
        return self.workspace.get_consciousness()

    def get_status(self) -> dict:
        return {
            "version": "v3",
            "uptime_ticks": self._tick_count,
            "inputs_processed": self._input_count,
            "emotion": self.emotion_engine.get_influence(),
            "subconscious": self.subconscious.status(),
            "blackboard": self.blackboard.status(),
            "drives": self.drives.status(),
            "neurotransmitter": self.neurotransmitter.status(),
            "safety": self.safety.status(),
            "intentions": self.intentions.status(),
            "urge": self.urge.status(),
            "workspace": self.workspace.status(),
            "working_memory": len(self.working_memory.get_all()),
            "long_term_memory": self.long_term_memory.stats(),
            "events": self.event_bus.get_stats(),
            "state_restored": self.state_manager.exists(),
            "occ": self.occ_engine.status(),
        }

    def get_dashboard_data(self) -> dict:
        """获取 Dashboard 所需的完整数据"""
        return {
            "version": "v3",
            "emotion": {
                **self.emotion_engine.get_influence(),
                "time_series": self.emotion_engine.get_time_series(),
            },
            "drives": {
                **self.drives.status(),
            },
            "neurotransmitter": self.neurotransmitter.status(),
            "safety": self.safety.status(),
            "intentions": self.intentions.get_intention_radar(),
            "urge": self.urge.status(),
            "blackboard": {
                "status": self.blackboard.status(),
                "recent": [e.to_dict() for e in self.blackboard.get_recent(seconds=600)],
                "inspirations": [s.to_dict() for s in list(self.blackboard.inspirations)[-10:]],
            },
            "subconscious": self.subconscious.status(),
            "workspace": self.workspace.status(),
            "memory": {
                "working": len(self.working_memory.get_all()),
                "long_term": self.long_term_memory.stats(),
                "recent": [
                    {
                        "content": m.content[:100],
                        "type": m.memory_type.value,
                        "strength": round(m.strength, 2),
                        "somatic_marker": round(m.somatic_marker, 2),
                    }
                    for m in self.long_term_memory.retrieve(limit=15)
                ],
            },
            "events": {
                "stats": self.event_bus.get_stats(),
                "recent": [e.to_dict() for e in self.event_bus.get_history(limit=30)],
            },
            "system": {
                "uptime_ticks": self._tick_count,
                "inputs_processed": self._input_count,
                "has_llm": self.language_layer is not None,
                "system_mode": self.safety.get_system_mode().value,
            },
        }

    def save_state(self) -> dict:
        return self.state_manager.save(self)

    def think_about(self, query: str) -> dict:
        """主动思考某个话题"""
        memories = self.long_term_memory.retrieve(
            query=query,
            emotion_bias=self.emotion_engine.state,
            limit=5,
        )
        output = SubAgentOutput(
            id=f"think-{int(time.time())}",
            agent_role=AgentRole.EXPLORER,
            content=f"关于「{query}」：从 {len(memories)} 条记忆中寻找线索",
            confidence=0.6,
            emotion=self.emotion_engine.state,
            timestamp=time.time(),
            related_memories=[m.id for m in memories],
            tags=["active_thinking"],
        )
        self.workspace.receive([output])
        conscious = self.workspace.think()
        return {"query": query, "memories_found": len(memories), "conscious_output": conscious}

    def autonomous_tick(self) -> dict:
        """自主活动 tick"""
        now = time.time()
        time_since = now - self.drives._last_interaction

        # 检查系统模式
        mode = self.safety.get_system_mode()
        if mode.value == "dormant":
            return {"action": "dormant", "reason": "稳态满足，节能模式"}

        # 好奇心驱动探索
        dominant = self.drives.get_dominant_need()
        if dominant == "information" and self.drives.state.dimensions["information"].tension > 0.1:
            import random
            topic = random.choice(["意识的本质", "遗忘与记忆", "模式与噪声", "系统自我理解"])
            result = self.think_about(topic)
            self.drives.on_new_information()
            return {"action": "explored", "topic": topic, **result}

        # 表达欲驱动主动说话
        if self.urge.state.is_triggering and self.language_layer:
            return {"action": "proactive_speech"}

        return {"action": "idle"}
