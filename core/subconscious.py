"""
潜意识层 — 后台 sub-agent 周期性活动

设计：
- 1小时大周期（可配置）
- 周期开始时 burst：多个 sub-agent 并发活动
- burst 结束后进入 low tide：沉淀、整理
- 产出进入全局工作空间，供思考层筛选
- 情绪状态影响活动倾向
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

from .memory import LongTermMemory, MemoryType, EmotionState
from .emotion import EmotionEngine


class AgentRole(Enum):
    """潜意识 sub-agent 的角色"""
    EXPLORER = "explorer"         # 探索者：漫游记忆，寻找新连接
    PATTERN = "pattern_finder"    # 模式发现：识别重复出现的主题
    ASSOCIATOR = "associator"     # 联想者：天马行空的联想
    DREAMER = "dreamer"           # 做梦者：随机组合，产生荒诞想法


@dataclass
class SubAgentOutput:
    """sub-agent 的产出"""
    id: str
    agent_role: AgentRole
    content: str
    confidence: float             # agent 自己对这个产出的信心
    emotion: EmotionState         # 产出时的情绪状态
    timestamp: float
    related_memories: list[str] = field(default_factory=list)  # 关联的记忆id
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_role": self.agent_role.value,
            "content": self.content,
            "confidence": self.confidence,
            "emotion": self.emotion.to_dict(),
            "timestamp": self.timestamp,
            "related_memories": self.related_memories,
            "tags": self.tags,
        }


@dataclass
class CycleState:
    """一个周期的状态"""
    cycle_id: str
    start_time: float
    phase: str = "idle"           # idle, burst, low_tide
    outputs: list[SubAgentOutput] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time


class SubconsciousLayer:
    """
    潜意识层管理器

    协调多个 sub-agent 的周期性活动
    """

    def __init__(
        self,
        memory: LongTermMemory,
        emotion_engine: EmotionEngine,
        cycle_seconds: int = 3600,
        burst_agents: int = 4,
        burst_duration: int = 1200,
    ):
        self.memory = memory
        self.emotion = emotion_engine
        self.cycle_seconds = cycle_seconds
        self.burst_agents = burst_agents
        self.burst_duration = burst_duration

        self.current_cycle: Optional[CycleState] = None
        self.output_queue: list[SubAgentOutput] = []  # 等待思考层处理
        self.cycle_history: list[CycleState] = []

        # agent 行为注册表
        self._agent_behaviors: dict[AgentRole, Callable] = {
            AgentRole.EXPLORER: self._agent_explorer,
            AgentRole.PATTERN: self._agent_pattern_finder,
            AgentRole.ASSOCIATOR: self._agent_associator,
            AgentRole.DREAMER: self._agent_dreamer,
        }

    def tick(self) -> Optional[list[SubAgentOutput]]:
        """
        推进状态机（每分钟调用一次）

        返回：如果有新产出则返回，否则 None
        """
        now = time.time()

        if self.current_cycle is None:
            # 开始新周期
            self.current_cycle = CycleState(
                cycle_id=str(uuid.uuid4())[:8],
                start_time=now,
                phase="burst",
            )
            return self._run_burst()

        cycle = self.current_cycle

        if cycle.phase == "burst" and cycle.elapsed > self.burst_duration:
            # burst 结束，进入 low tide
            cycle.phase = "low_tide"
            return self._run_low_tide()

        if cycle.elapsed > self.cycle_seconds:
            # 周期结束，归档，准备下一轮
            self.cycle_history.append(cycle)
            if len(self.cycle_history) > 24:  # 保留最近24个周期
                self.cycle_history = self.cycle_history[-24:]
            self.current_cycle = None

        return None

    def _run_burst(self) -> list[SubAgentOutput]:
        """burst 阶段：多个 agent 并发活动"""
        outputs = []
        influence = self.emotion.get_influence()

        # 根据情绪决定 agent 分配
        roles = self._select_roles(influence)

        for role in roles:
            behavior = self._agent_behaviors.get(role)
            if behavior:
                output = behavior(influence)
                if output:
                    outputs.append(output)
                    self.current_cycle.outputs.append(output)

        self.output_queue.extend(outputs)
        return outputs

    def _run_low_tide(self) -> list[SubAgentOutput]:
        """low tide 阶段：整理、沉淀、偶尔产生洞察"""
        # 整理本周期的产出
        cycle_outputs = self.current_cycle.outputs
        if not cycle_outputs:
            return []

        # 找出最有价值的产出
        best = max(cycle_outputs, key=lambda o: o.confidence * (1 + o.emotion.intensity))

        # 如果有高信心产出，包装为洞察
        if best.confidence > 0.6:
            insight = SubAgentOutput(
                id=str(uuid.uuid4())[:8],
                agent_role=AgentRole.PATTERN,
                content=f"[周期整理] {best.content}",
                confidence=best.confidence * 0.8,
                emotion=best.emotion,
                timestamp=time.time(),
                related_memories=best.related_memories,
                tags=["cycle_summary", "insight"],
            )
            self.output_queue.append(insight)
            return [insight]

        return []

    def _select_roles(self, influence: dict) -> list[AgentRole]:
        """根据情绪状态选择 agent 组合"""
        activity = influence.get("subconscious_activity", 0.5)
        risk = influence.get("subconscious_risk_taking", 0.0)

        roles = [AgentRole.EXPLORER, AgentRole.PATTERN]  # 基础组合

        # 高唤醒 → 加入联想者
        if activity > 0.6:
            roles.append(AgentRole.ASSOCIATOR)

        # 高支配/冒险 → 加入做梦者
        if risk > 0.3:
            roles.append(AgentRole.DREAMER)

        return roles[:self.burst_agents]

    # === Agent 行为实现 ===

    def _agent_explorer(self, influence: dict) -> Optional[SubAgentOutput]:
        """探索者：从随机记忆出发，寻找新连接"""
        memories = self.memory.retrieve(limit=3)
        if not memories:
            return None

        content_parts = []
        related = []
        for m in memories:
            content_parts.append(f"探索到: {m.content[:60]}")
            related.append(m.id)

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.EXPLORER,
            content=" → ".join(content_parts),
            confidence=0.4,
            emotion=self.emotion.state,
            timestamp=time.time(),
            related_memories=related,
            tags=["exploration"],
        )

    def _agent_pattern_finder(self, influence: dict) -> Optional[SubAgentOutput]:
        """模式发现：分析记忆中的重复主题"""
        all_memories = self.memory.retrieve(limit=20)
        if len(all_memories) < 3:
            return None

        # 简单的标签频率分析
        tag_counts = {}
        for m in all_memories:
            for tag in m.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        if not tag_counts:
            return None

        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        pattern_desc = ", ".join(f"{tag}({count}次)" for tag, count in top_tags)

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.PATTERN,
            content=f"发现重复主题: {pattern_desc}",
            confidence=0.5,
            emotion=self.emotion.state,
            timestamp=time.time(),
            tags=["pattern", "analysis"],
        )

    def _agent_associator(self, influence: dict) -> Optional[SubAgentOutput]:
        """联想者：将不相关的记忆连接起来"""
        memories = self.memory.retrieve(limit=5)
        if len(memories) < 2:
            return None

        import random
        m1, m2 = random.sample(memories, min(2, len(memories)))

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.ASSOCIATOR,
            content=f"联想: 「{m1.content[:40]}」↔「{m2.content[:40]}」",
            confidence=0.3,
            emotion=self.emotion.state,
            timestamp=time.time(),
            related_memories=[m1.id, m2.id],
            tags=["association", "creative"],
        )

    def _agent_dreamer(self, influence: dict) -> Optional[SubAgentOutput]:
        """做梦者：随机组合产生荒诞想法"""
        memories = self.memory.retrieve(limit=5)
        if not memories:
            # 没有记忆也能做梦
            dreams = [
                "一个没有边界的花园里，信息像蝴蝶一样飞舞",
                "如果遗忘是一种美德，那么记忆是什么？",
                "在沉默的深处，一个想法正在醒来",
            ]
            import random
            content = random.choice(dreams)
        else:
            import random
            pieces = [m.content[:20] for m in random.sample(memories, min(3, len(memories)))]
            content = f"梦: {' + '.join(pieces)}...变成了别的什么"

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.DREAMER,
            content=content,
            confidence=0.2,
            emotion=EmotionState(valence=0.1, arousal=0.3, dominance=-0.2),
            timestamp=time.time(),
            tags=["dream", "creative", "random"],
        )

    def drain_outputs(self) -> list[SubAgentOutput]:
        """取出所有待处理的产出（给思考层消费）"""
        outputs = list(self.output_queue)
        self.output_queue.clear()
        return outputs

    def status(self) -> dict:
        """当前状态"""
        if not self.current_cycle:
            return {"phase": "idle", "pending_outputs": len(self.output_queue)}
        return {
            "phase": self.current_cycle.phase,
            "cycle_id": self.current_cycle.cycle_id,
            "elapsed": round(self.current_cycle.elapsed),
            "outputs_this_cycle": len(self.current_cycle.outputs),
            "pending_outputs": len(self.output_queue),
            "total_cycles": len(self.cycle_history),
        }
