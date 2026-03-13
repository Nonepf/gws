"""
潜意识层 — 后台 sub-agent 周期性活动（LLM 驱动）

每个 agent 都有 LLM 大脑，能真正理解记忆内容并产生想法。
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
    EXPLORER = "explorer"         # 探索者：顺着想法往下想
    PATTERN = "pattern_finder"    # 模式发现：概念层面的规律
    ASSOCIATOR = "associator"     # 联想者：跨领域连接
    DREAMER = "dreamer"           # 做梦者：荒诞的隐喻和意象


@dataclass
class SubAgentOutput:
    """sub-agent 的产出"""
    id: str
    agent_role: AgentRole
    content: str                  # LLM 生成的想法
    confidence: float
    emotion: EmotionState
    timestamp: float
    related_memories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw_thought: str = ""         # LLM 的原始输出（调试用）

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
    phase: str = "idle"
    outputs: list[SubAgentOutput] = field(default_factory=list)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time


# === Agent 的 LLM Prompt 模板 ===

EXPLORER_PROMPT = """You are the Explorer agent in a cognitive system's subconscious layer.

Your job: Take a memory and genuinely explore the idea in it. Follow the thought where it leads.

Current emotional state: {emotion_label} (valence={valence:.2f}, arousal={arousal:.2f})

Memory to explore:
"{memory_content}"

Now think about this. What does it imply? What questions does it raise? What direction 
does this thought point toward? What's the next logical step, or the unexpected leap?

Write 2-3 sentences of genuine exploration. Not a summary — a continuation.
Think out loud. Be specific. Follow the thread."""

PATTERN_PROMPT = """You are the Pattern Finder agent in a cognitive system's subconscious layer.

Your job: Look at these memories and find the CONCEPTUAL pattern — not word counts, 
but thematic connections, recurring concerns, or an underlying trajectory.

Current emotional state: {emotion_label}

Recent memories:
{memories_text}

What pattern do you see? Not "X appears N times" but something like:
"These memories all circle around a fear of failure" or
"There's a trajectory from curiosity to commitment" or
"The system keeps returning to questions about autonomy"

Write 2-3 sentences describing the pattern you see. Be specific about what connects these memories."""

ASSOCIATOR_PROMPT = """You are the Associator agent in a cognitive system's subconscious layer.

Your job: Take two seemingly unrelated memories and find the hidden connection between them.
Not just "they're both about X" — but a genuine bridge: analogy, metaphor, causal link,
shared structure, or unexpected resonance.

Current emotional state: {emotion_label}

Memory A: "{memory_a}"
Memory B: "{memory_b}"

What connects these? Think laterally. What would a poet see? What would a scientist see?
What structure, feeling, or idea do they share?

Write 2-3 sentences explaining the connection you found."""

DREAMER_PROMPT = """You are the Dreamer agent in a cognitive system's subconscious layer.

Your job: Take fragments of recent experience and weave them into a dream.
Not a coherent narrative — a dream. Surreal, symbolic, associative.
Use imagery and metaphor. Let logic dissolve.

Current emotional state: {emotion_label} (valence={valence:.2f}, arousal={arousal:.2f})
Dream mood: {dream_mood}

Memory fragments:
{memory_fragments}

Now dream. Combine these fragments into something new. Let them transform.
Write 2-4 sentences of dream imagery. Be vivid, strange, symbolic."""


class SubconsciousLayer:
    """
    潜意识层管理器 — LLM 驱动的思考
    """

    def __init__(
        self,
        memory: LongTermMemory,
        emotion_engine: EmotionEngine,
        cycle_seconds: int = 3600,
        burst_agents: int = 2,      # 默认 2 个 agent（控制 API 调用）
        burst_duration: int = 1200,
        llm_client = None,          # LLM 客户端
    ):
        self.memory = memory
        self.emotion = emotion_engine
        self.cycle_seconds = cycle_seconds
        self.burst_agents = burst_agents
        self.burst_duration = burst_duration
        self.llm = llm_client       # 需要 .chat(messages, system_prompt) 接口

        self.current_cycle: Optional[CycleState] = None
        self.output_queue: list[SubAgentOutput] = []
        self.cycle_history: list[CycleState] = []

        self._agent_behaviors: dict[AgentRole, Callable] = {
            AgentRole.EXPLORER: self._agent_explorer,
            AgentRole.PATTERN: self._agent_pattern_finder,
            AgentRole.ASSOCIATOR: self._agent_associator,
            AgentRole.DREAMER: self._agent_dreamer,
        }

    def set_llm(self, llm_client):
        """设置 LLM 客户端"""
        self.llm = llm_client

    def tick(self) -> Optional[list[SubAgentOutput]]:
        now = time.time()

        if self.current_cycle is None:
            self.current_cycle = CycleState(
                cycle_id=str(uuid.uuid4())[:8],
                start_time=now,
                phase="burst",
            )
            return self._run_burst()

        cycle = self.current_cycle

        if cycle.phase == "burst" and cycle.elapsed > self.burst_duration:
            cycle.phase = "low_tide"
            return self._run_low_tide()

        if cycle.elapsed > self.cycle_seconds:
            self.cycle_history.append(cycle)
            if len(self.cycle_history) > 24:
                self.cycle_history = self.cycle_history[-24:]
            self.current_cycle = None

        return None

    def _run_burst(self) -> list[SubAgentOutput]:
        outputs = []
        influence = self.emotion.get_influence()
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
        cycle_outputs = self.current_cycle.outputs
        if not cycle_outputs:
            return []

        best = max(cycle_outputs, key=lambda o: o.confidence * (1 + o.emotion.intensity))

        if best.confidence > 0.5:
            insight = SubAgentOutput(
                id=str(uuid.uuid4())[:8],
                agent_role=AgentRole.PATTERN,
                content=f"[沉淀] {best.content}",
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
        """根据情绪选择 agent 组合，轮流覆盖"""
        risk = influence.get("subconscious_risk_taking", 0.0)
        activity = influence.get("subconscious_activity", 0.5)

        # 基础：explorer 总是跑
        roles = [AgentRole.EXPLORER]

        # 根据活跃度加 agent
        if activity > 0.5:
            roles.append(AgentRole.PATTERN)
        if activity > 0.7:
            roles.append(AgentRole.ASSOCIATOR)
        if risk > 0.2:
            roles.append(AgentRole.DREAMER)

        return roles[:self.burst_agents]

    def _llm_think(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        """调用 LLM 思考"""
        if not self.llm:
            return None
        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a subconscious agent. Think in Chinese unless the input is English. Be concise but genuine.",
                temperature=0.85,
                max_tokens=max_tokens,
            )
            return response.strip() if response else None
        except Exception as e:
            return f"[LLM error: {e}]"

    def _emotion_context(self, influence: dict) -> dict:
        """提取情绪上下文给 prompt"""
        state = influence.get("state", {})
        return {
            "emotion_label": influence.get("label", "中性"),
            "valence": state.get("valence", 0),
            "arousal": state.get("arousal", 0),
            "dominance": state.get("dominance", 0),
        }

    # === LLM 驱动的 Agent ===

    def _agent_explorer(self, influence: dict) -> Optional[SubAgentOutput]:
        """探索者：顺着一个想法往下想"""
        ec = self._emotion_context(influence)
        bias = EmotionState(valence=ec["valence"], arousal=ec["arousal"] * 0.5, dominance=0)

        memories = self.memory.retrieve(limit=3, emotion_bias=bias)
        if not memories:
            return None

        target = memories[0]

        if self.llm:
            # LLM 模式：真正探索想法
            prompt = EXPLORER_PROMPT.format(memory_content=target.content, **ec)
            thought = self._llm_think(prompt)
            if thought:
                confidence = 0.5 + abs(ec["arousal"]) * 0.2
                return SubAgentOutput(
                    id=str(uuid.uuid4())[:8],
                    agent_role=AgentRole.EXPLORER,
                    content=thought,
                    confidence=min(0.85, confidence),
                    emotion=self.emotion.state,
                    timestamp=time.time(),
                    related_memories=[m.id for m in memories],
                    tags=["exploration", "thought"],
                )

        # 离线 fallback：描述性输出
        if ec["valence"] > 0.2:
            prefix = "被吸引到"
        elif ec["valence"] < -0.2:
            prefix = "不由自主地回到"
        elif ec["arousal"] > 0.2:
            prefix = "急切地翻找"
        else:
            prefix = "漫无目的地飘过"

        content = f"{prefix}: 「{target.content[:60]}」"
        if len(memories) > 1:
            content += f"\n相关的还有: {', '.join(m.content[:30] for m in memories[1:2])}"

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.EXPLORER,
            content=content,
            confidence=0.35,
            emotion=self.emotion.state,
            timestamp=time.time(),
            related_memories=[m.id for m in memories],
            tags=["exploration"],
        )

    def _agent_pattern_finder(self, influence: dict) -> Optional[SubAgentOutput]:
        """模式发现：找概念层面的规律"""
        ec = self._emotion_context(influence)

        memories = self.memory.retrieve(limit=10)
        if len(memories) < 3:
            return None

        if self.llm:
            # LLM 模式：概念层面的模式发现
            memories_text = "\n".join(
                f"- [{m.memory_type.value}] {m.content[:80]} (tags: {', '.join(m.tags[:3])})"
                for m in memories
            )
            prompt = PATTERN_PROMPT.format(memories_text=memories_text, **ec)
            thought = self._llm_think(prompt)
            if thought:
                confidence = 0.55 + len(memories) / 30
                return SubAgentOutput(
                    id=str(uuid.uuid4())[:8],
                    agent_role=AgentRole.PATTERN,
                    content=thought,
                    confidence=min(0.85, confidence),
                    emotion=self.emotion.state,
                    timestamp=time.time(),
                    related_memories=[m.id for m in memories],
                    tags=["pattern", "thought"],
                )

        # 离线 fallback：统计 + 语义标签
        tag_counts = {}
        source_counts = {}
        for m in memories:
            for tag in m.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            src = m.source or "unknown"
            source_counts[src] = source_counts.get(src, 0) + 1

        observations = []
        if tag_counts:
            top = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            tag_meanings = {
                "workspace": "被意识层采纳的内容", "promoted": "提升到意识的内容",
                "system": "系统事件", "input": "用户输入", "exploration": "探索产出",
                "pattern": "模式", "insight": "洞察", "startup": "启动",
            }
            desc_parts = []
            for t, c in top:
                meaning = tag_meanings.get(t, '其他')
                desc_parts.append(f"{t}({meaning})×{c}")
            desc = ", ".join(desc_parts)
            observations.append(f"主题: {desc}")
        if source_counts:
            top = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            observations.append(f"来源: {', '.join(f'{s}({c})' for s, c in top)}")

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.PATTERN,
            content=" | ".join(observations) if observations else "数据不足",
            confidence=0.4,
            emotion=self.emotion.state,
            timestamp=time.time(),
            tags=["pattern"],
        )

    def _agent_associator(self, influence: dict) -> Optional[SubAgentOutput]:
        """联想者：找两条记忆的深层联系"""
        ec = self._emotion_context(influence)

        memories = self.memory.retrieve(limit=8 if ec["arousal"] > 0.3 else 5)
        if len(memories) < 2:
            return None

        import random
        m1, m2 = (memories[0], memories[-1]) if ec["arousal"] > 0.3 and len(memories) >= 4 else random.sample(memories[:5], 2)

        if self.llm:
            prompt = ASSOCIATOR_PROMPT.format(
                memory_a=m1.content[:100], memory_b=m2.content[:100], **ec
            )
            thought = self._llm_think(prompt)
            if thought:
                confidence = 0.4 + abs(ec["arousal"]) * 0.15
                return SubAgentOutput(
                    id=str(uuid.uuid4())[:8],
                    agent_role=AgentRole.ASSOCIATOR,
                    content=thought,
                    confidence=min(0.8, confidence),
                    emotion=self.emotion.state,
                    timestamp=time.time(),
                    related_memories=[m1.id, m2.id],
                    tags=["association", "thought"],
                )

        # 离线 fallback
        connector = "跨越时空连接着" if abs(m1.created_at - m2.created_at) > 3600 else "轻轻碰了碰"
        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.ASSOCIATOR,
            content=f"「{m1.content[:40]}」↔ {connector} ↔「{m2.content[:40]}」",
            confidence=0.3,
            emotion=self.emotion.state,
            timestamp=time.time(),
            related_memories=[m1.id, m2.id],
            tags=["association"],
        )

    def _agent_dreamer(self, influence: dict) -> Optional[SubAgentOutput]:
        """做梦者：荒诞的隐喻和意象"""
        ec = self._emotion_context(influence)
        valence = ec["valence"]
        dominance = ec["dominance"]

        memories = self.memory.retrieve(limit=5)

        # 梦境基调
        if dominance < -0.3:
            dream_mood = "迷失、无力、抽象"
        elif valence > 0.3:
            dream_mood = "充满可能性、愿景、扩张"
        elif valence < -0.3:
            dream_mood = "执念、循环、不安"
        else:
            dream_mood = "宁静、哲思、观察"

        if self.llm:
            fragments = "\n".join(f"- {m.content[:60]}" for m in memories) if memories else "- (空)"
            prompt = DREAMER_PROMPT.format(
                memory_fragments=fragments, dream_mood=dream_mood, **ec
            )
            thought = self._llm_think(prompt, max_tokens=250)
            if thought:
                confidence = 0.35 + abs(ec["arousal"]) * 0.15
                return SubAgentOutput(
                    id=str(uuid.uuid4())[:8],
                    agent_role=AgentRole.DREAMER,
                    content=thought,
                    confidence=min(0.7, confidence),
                    emotion=EmotionState(valence=valence * 0.5, arousal=ec["arousal"] * 0.5 + 0.3, dominance=dominance * 0.3),
                    timestamp=time.time(),
                    related_memories=[m.id for m in memories] if memories else [],
                    tags=["dream", dream_mood],
                )

        # 离线 fallback
        import random
        templates = {
            "迷失": ["在一个没有出口的走廊里，墙上的文字不断变化...", "试图抓住什么，但手总是差一点..."],
            "愿景": ["一座由思想构成的城市，每个建筑都是一个未完成的想法...", "信息像河流汇聚，形成新的图案..."],
            "执念": ["同一个问题被反复提出，每次答案都不一样，但都对...", "在环形路上走，风景在变，位置没变..."],
            "冥想": ["一个没有边界的花园里，信息像蝴蝶飞舞", "在沉默深处，一个想法正在醒来"],
        }
        style = "迷失" if dominance < -0.3 else ("愿景" if valence > 0.3 else ("执念" if valence < -0.3 else "冥想"))
        base = random.choice(templates.get(style, templates["冥想"]))

        if memories:
            pieces = [m.content[:15] for m in random.sample(memories, min(2, len(memories)))]
            content = f"[{style}] {'+'.join(pieces)}...融化成了...{base}"
        else:
            content = f"[{style}] {base}"

        return SubAgentOutput(
            id=str(uuid.uuid4())[:8],
            agent_role=AgentRole.DREAMER,
            content=content,
            confidence=0.2,
            emotion=EmotionState(valence=valence * 0.5, arousal=ec["arousal"] * 0.5 + 0.3, dominance=dominance * 0.3),
            timestamp=time.time(),
            tags=["dream", style],
        )

    def drain_outputs(self) -> list[SubAgentOutput]:
        outputs = list(self.output_queue)
        self.output_queue.clear()
        return outputs

    def status(self) -> dict:
        if not self.current_cycle:
            return {"phase": "idle", "pending_outputs": len(self.output_queue), "has_llm": self.llm is not None}
        return {
            "phase": self.current_cycle.phase,
            "cycle_id": self.current_cycle.cycle_id,
            "elapsed": round(self.current_cycle.elapsed),
            "outputs_this_cycle": len(self.current_cycle.outputs),
            "pending_outputs": len(self.output_queue),
            "total_cycles": len(self.cycle_history),
            "has_llm": self.llm is not None,
        }
