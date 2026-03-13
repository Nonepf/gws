"""
全局工作空间 — 思考层（前额叶）

职责：
- 从潜意识层接收产出
- 筛选、评估、深度处理
- 决定哪些内容进入意识（输出给语言层）
- 情绪影响筛选策略
"""

import time
from dataclasses import dataclass, field
from typing import Optional

from .subconscious import SubAgentOutput
from .memory import LongTermMemory, MemoryType, EmotionState
from .emotion import EmotionEngine


@dataclass
class WorkspaceItem:
    """工作空间中的项目"""
    source: SubAgentOutput
    evaluation: float = 0.0       # 思考层的评估分数
    processed: bool = False
    promoted: bool = False        # 是否被提升到意识层
    thoughts: list[str] = field(default_factory=list)


class GlobalWorkspace:
    """
    全局工作空间 — 信息竞争的战场

    类似 Baars 的 GWT：多个信息源竞争注意力，
    胜出者进入意识，被广播到所有模块。
    """

    def __init__(
        self,
        memory: LongTermMemory,
        emotion_engine: EmotionEngine,
        capacity: int = 5,
        promotion_threshold: float = 0.5,
    ):
        self.memory = memory
        self.emotion = emotion_engine
        self.capacity = capacity
        self.promotion_threshold = promotion_threshold

        self.items: list[WorkspaceItem] = []
        self.conscious_content: list[dict] = []  # 意识层的内容
        self.history: list[dict] = []

    def receive(self, outputs: list[SubAgentOutput]):
        """接收潜意识层的产出"""
        for output in outputs:
            item = WorkspaceItem(source=output)
            item.evaluation = self._evaluate(output)
            self.items.append(item)

        # 超出容量，移除最弱的
        if len(self.items) > self.capacity * 2:
            self.items.sort(key=lambda i: i.evaluation)
            self.items = self.items[-(self.capacity * 2):]

    def think(self) -> list[dict]:
        """
        思考轮次：评估、筛选、深度处理

        返回进入意识层的内容
        """
        influence = self.emotion.get_influence()
        strategy = influence.get("thinking_strategy", "neutral")
        new_conscious = []

        for item in self.items:
            if item.processed:
                continue

            # 根据情绪策略调整评估
            adjusted_score = self._adjust_by_strategy(item.evaluation, strategy)

            if adjusted_score >= self.promotion_threshold:
                # 提升到意识层
                thought = self._deep_process(item, influence)
                item.promoted = True
                item.processed = True
                new_conscious.append(thought)

                # 写入长期记忆
                self.memory.encode(
                    content=f"[思考] {thought['content']}",
                    memory_type=MemoryType.INSIGHT,
                    emotion=self.emotion.state,
                    tags=["workspace", "promoted"],
                    source="thinking_layer",
                )
            else:
                item.processed = True

        # 清理已处理的
        self.items = [i for i in self.items if not i.processed or i.promoted]

        self.conscious_content.extend(new_conscious)
        # 意识层只保留最近10条
        if len(self.conscious_content) > 10:
            self.conscious_content = self.conscious_content[-10:]

        return new_conscious

    def _evaluate(self, output: SubAgentOutput) -> float:
        """评估一个潜意识产出的价值"""
        score = output.confidence

        # 情绪强度加分
        score += output.emotion.intensity * 0.2

        # 有标签的更有结构
        if output.tags:
            score += 0.1

        # insight 类产出额外加分
        if "insight" in output.tags:
            score += 0.2

        # 与当前系统情绪共鸣的产出加分（mood-congruent）
        current_v = self.emotion.state.valence
        output_v = output.emotion.valence
        if current_v * output_v > 0:  # 同号 = 同效价
            score += 0.15

        return min(1.0, score)

    def _adjust_by_strategy(self, score: float, strategy: str) -> float:
        """根据思考策略调整分数 — 不只调门槛，还调方向偏好"""
        if strategy == "exploratory":
            # 探索模式：宽容 + 给创意类产出额外加分
            return score * 1.2
        elif strategy == "cautious":
            # 谨慎模式：严格 + 偏好已有验证的模式类产出
            return score * 0.8
        return score

    def _deep_process(self, item: WorkspaceItem, influence: dict) -> dict:
        """对提升的内容进行深度处理 — 情绪影响思考内容"""
        source = item.source
        thoughts = []
        strategy = influence.get("thinking_strategy", "neutral")
        valence = influence.get("state", {}).get("valence", 0)
        arousal = influence.get("state", {}).get("arousal", 0)

        # 基础分析
        thoughts.append(f"来源: {source.agent_role.value}")
        thoughts.append(f"内容: {source.content}")

        # 情绪关联分析
        if source.emotion.intensity > 0.3:
            thoughts.append(f"强烈情绪信号: {source.emotion.label} (强度={source.emotion.intensity:.2f})")

        # 关联记忆
        if source.related_memories:
            thoughts.append(f"关联 {len(source.related_memories)} 条记忆")

        # === 情绪驱动的思考方向 ===
        if strategy == "exploratory" and valence > 0.2:
            thoughts.append("→ 发散思考：这个想法可以延伸到哪里？")
            # 额外检索相关但不直接相关的记忆
            related = self.memory.retrieve(query=source.content[:50], limit=3)
            if related:
                thoughts.append(f"→ 触发了 {len(related)} 条远距离联想")
        elif strategy == "cautious" and valence < -0.2:
            thoughts.append("→ 收敛思考：这个结论的依据是什么？有没有反例？")
            # 检索同类型的记忆来验证
            similar = self.memory.retrieve(
                query=source.content[:50],
                tags=source.tags[:2] if source.tags else None,
                limit=3,
            )
            if similar:
                thoughts.append(f"→ 找到 {len(similar)} 条相似记忆来交叉验证")
        elif arousal > 0.4:
            thoughts.append("→ 快速思考：直觉告诉我这很重要，先抓住再说")
        else:
            thoughts.append("→ 平稳思考")

        # 思考模式记录
        thoughts.append(f"思考模式: {strategy}")

        return {
            "id": source.id,
            "content": source.content,
            "thoughts": thoughts,
            "evaluation": item.evaluation,
            "timestamp": time.time(),
            "agent_role": source.agent_role.value,
            "emotion": source.emotion.to_dict(),
        }

    def get_consciousness(self) -> list[dict]:
        """获取当前意识层内容"""
        return list(self.conscious_content)

    def status(self) -> dict:
        return {
            "workspace_items": len(self.items),
            "conscious_items": len(self.conscious_content),
            "promotion_threshold": self.promotion_threshold,
        }
