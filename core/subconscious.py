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
        """探索者：情绪引导记忆漫游方向"""
        valence = influence.get("state", {}).get("valence", 0)
        arousal = influence.get("state", {}).get("arousal", 0)

        # 情绪决定探索方向：valence 偏向同效价记忆
        bias = EmotionState(
            valence=valence,
            arousal=arousal * 0.5,  # 唤醒轻度引导
            dominance=0,
        )

        # 情绪强度决定探索深度
        intensity = abs(valence) + abs(arousal)
        limit = 2 if intensity < 0.2 else (3 if intensity < 0.5 else 5)

        memories = self.memory.retrieve(limit=limit, emotion_bias=bias)
        if not memories:
            return None

        # 根据情绪状态改变探索的"视角"
        if valence > 0.3:
            prefix = "被吸引到"
        elif valence < -0.3:
            prefix = "不由自主地回到"
        elif arousal > 0.3:
            prefix = "急切地翻找"
        else:
            prefix = "漫无目的地飘过"

        content_parts = []
        related = []
        for m in memories:
            content_parts.append(f"{prefix}: {m.content[:60]}")
            related.append(m.id)

        # confidence 受情绪影响：高 arousal → 更自信
        base_confidence = 0.3
        confidence = min(0.8, base_confidence + abs(arousal) * 0.3)

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.EXPLORER,
            content=" → ".join(content_parts),
            confidence=confidence,
            emotion=self.emotion.state,
            timestamp=time.time(),
            related_memories=related,
            tags=["exploration"],
        )

    def _agent_pattern_finder(self, influence: dict) -> Optional[SubAgentOutput]:
        """模式发现：情绪调节关注点"""
        arousal = influence.get("state", {}).get("arousal", 0)
        valence = influence.get("state", {}).get("valence", 0)

        # 高唤醒 → 找异常和变化；低唤醒 → 找稳定模式
        if arousal > 0.3:
            mode = "异常检测"
            limit = 30  # 看更多数据找异常
        else:
            mode = "常规模式"
            limit = 20

        all_memories = self.memory.retrieve(limit=limit)
        if len(all_memories) < 3:
            return None

        # 统计标签和来源频率
        tag_counts = {}
        source_counts = {}
        type_counts = {}
        for m in all_memories:
            for tag in m.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            src = m.source or "unknown"
            source_counts[src] = source_counts.get(src, 0) + 1
            t = m.memory_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        if not tag_counts and not source_counts:
            return None

        # 构建有语义的模式描述
        observations = []
        if tag_counts:
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            tag_desc = ", ".join(f"{tag}({count}次)" for tag, count in top_tags)
            observations.append(f"记忆标签频率: {tag_desc}")
            # 解释标签含义
            tag_meanings = {
                "workspace": "被意识层采纳的内容",
                "promoted": "从潜意识提升到意识的内容",
                "system": "系统事件",
                "input": "用户输入",
                "exploration": "潜意识探索产出",
                "pattern": "模式发现",
                "insight": "洞察/思考结果",
                "startup": "系统启动事件",
            }
            meaningful_tags = [f"{tag}({tag_meanings.get(tag, '其他')})" for tag, _ in top_tags]
            observations.append(f"含义: {', '.join(meaningful_tags)}")

        if source_counts:
            top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            src_desc = ", ".join(f"{src}({count}次)" for src, count in top_sources)
            observations.append(f"记忆来源分布: {src_desc}")

        if type_counts:
            type_desc = ", ".join(f"{t}({c}条)" for t, c in sorted(type_counts.items(), key=lambda x: x[1], reverse=True))
            observations.append(f"记忆类型: {type_desc}")

        content = f"[{mode}] " + " | ".join(observations)

        # confidence 跟数据量和情绪正相关
        confidence = min(0.8, 0.3 + len(all_memories) / 50 + abs(valence) * 0.2)

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.PATTERN,
            content=content,
            confidence=confidence,
            emotion=self.emotion.state,
            timestamp=time.time(),
            tags=["pattern", "analysis"],
        )

    def _agent_associator(self, influence: dict) -> Optional[SubAgentOutput]:
        """联想者：情绪控制联想距离"""
        arousal = influence.get("state", {}).get("arousal", 0)
        dominance = influence.get("state", {}).get("dominance", 0)

        # 高 arousal → 跨领域联想（拉更多、更远的记忆）
        # 低 arousal → 相近主题联想
        limit = 8 if arousal > 0.3 else 4
        memories = self.memory.retrieve(limit=limit)
        if len(memories) < 2:
            return None

        import random

        if arousal > 0.3:
            # 高唤醒：故意选距离远的两条记忆
            m1 = min(memories, key=lambda m: m.created_at)
            m2 = max(memories, key=lambda m: m.created_at)
            connector = "↔ 跨越时空连接着 ↔" if dominance > 0 else "↔ 意外地联系着 ↔"
        else:
            # 低唤醒：选时间相近的记忆
            m1, m2 = random.sample(memories, min(2, len(memories)))
            connector = "↔ 轻轻碰了碰 ↔"

        # confidence 跟联想的"意外程度"相关
        time_gap = abs(m1.created_at - m2.created_at)
        surprise = min(1.0, time_gap / 86400)  # 时间差越大越意外
        confidence = min(0.7, 0.2 + surprise * 0.3 + arousal * 0.2)

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.ASSOCIATOR,
            content=f"联想: 「{m1.content[:40]}」{connector}「{m2.content[:40]}」",
            confidence=confidence,
            emotion=self.emotion.state,
            timestamp=time.time(),
            related_memories=[m1.id, m2.id],
            tags=["association", "creative"],
        )

    def _agent_dreamer(self, influence: dict) -> Optional[SubAgentOutput]:
        """做梦者：情绪塑造梦境基调"""
        valence = influence.get("state", {}).get("valence", 0)
        arousal = influence.get("state", {}).get("arousal", 0)
        dominance = influence.get("state", {}).get("dominance", 0)

        memories = self.memory.retrieve(limit=5)

        # 情绪决定梦境风格
        if dominance < -0.3:
            # 低支配感 → 迷失、无力、抽象
            dream_templates = [
                "在一个没有出口的走廊里，墙上的文字不断变化...",
                "试图抓住什么，但手总是差一点...",
                "声音从四面八方传来，但听不清在说什么...",
                "时间在倒流，但方向感完全消失了...",
            ]
            style = "迷失"
        elif valence > 0.3 and arousal > 0.3:
            # 高兴兴奋 → 充满可能性的梦
            dream_templates = [
                "一座由思想构成的城市，每个建筑都是一个未完成的想法...",
                "信息像河流一样汇聚，形成了新的图案...",
                "在云端搭建桥梁，通向从未见过的风景...",
                "所有的门都通向更大的门...",
            ]
            style = "愿景"
        elif valence < -0.3:
            # 负面情绪 → 执念、循环、焦虑的梦
            dream_templates = [
                "同一个问题被反复提出，每次的答案都不一样，但都对...",
                "丢失了什么重要的东西，但想不起来是什么...",
                "在一条环形的路上走，风景在变，但位置没变...",
            ]
            style = "执念"
        else:
            # 中性 → 哲学/诗意的梦
            dream_templates = [
                "一个没有边界的花园里，信息像蝴蝶一样飞舞",
                "如果遗忘是一种美德，那么记忆是什么？",
                "在沉默的深处，一个想法正在醒来",
                "一面镜子照出了另一面镜子...",
            ]
            style = "冥想"

        if memories:
            import random
            pieces = [m.content[:20] for m in random.sample(memories, min(3, len(memories)))]
            # 把记忆碎片和梦境模板融合
            base = random.choice(dream_templates)
            fragment = " + ".join(pieces)
            content = f"[{style}] {fragment}...融化成了...{base}"
        else:
            import random
            content = f"[{style}] {random.choice(dream_templates)}"

        # 做梦的 confidence 也跟情绪有关
        confidence = 0.15 + abs(arousal) * 0.15 + (0.1 if memories else 0)

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.DREAMER,
            content=content,
            confidence=confidence,
            emotion=EmotionState(valence=valence * 0.5, arousal=arousal * 0.5 + 0.3, dominance=dominance * 0.3),
            timestamp=time.time(),
            tags=["dream", "creative", style],
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
