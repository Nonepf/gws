"""
记忆层 — Working Memory + Long-term Memory

设计原则：
- 工作记忆：容量有限，快速衰减，高频访问
- 长期记忆：持久存储，情绪调制编码，支持遗忘
- 情绪影响记忆的编码权重和提取偏向
"""

import json
import math
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class MemoryType(Enum):
    EPISODIC = "episodic"      # 事件/经历
    SEMANTIC = "semantic"      # 事实/知识
    PROCEDURAL = "procedural"  # 技能/方法
    EMOTIONAL = "emotional"    # 情绪相关
    INSIGHT = "insight"        # 洞察/灵感


@dataclass
class EmotionState:
    """情绪向量 — 基于 PAD 模型（Pleasure-Arousal-Dominance）"""
    valence: float = 0.0      # 效价 [-1, 1] 负面↔正面
    arousal: float = 0.0      # 唤醒 [-1, 1] 平静↔兴奋
    dominance: float = 0.0    # 支配 [-1, 1] 被动↔主动

    def to_dict(self) -> dict:
        return {"valence": self.valence, "arousal": self.arousal, "dominance": self.dominance}

    @classmethod
    def from_dict(cls, d: dict) -> "EmotionState":
        return cls(**{k: v for k, v in d.items() if k in ("valence", "arousal", "dominance")})

    @property
    def intensity(self) -> float:
        """情绪强度 — 用于调制记忆编码"""
        return math.sqrt(self.valence**2 + self.arousal**2 + self.dominance**2) / math.sqrt(3)


@dataclass
class MemoryEntry:
    """单条记忆"""
    id: str
    content: str
    memory_type: MemoryType
    emotion: EmotionState
    created_at: float
    last_accessed: float
    access_count: int = 0
    strength: float = 1.0              # 记忆强度 [0, 1]
    tags: list[str] = field(default_factory=list)
    source: str = ""                    # 来源：哪个层/agent产生的

    def to_dict(self) -> dict:
        d = asdict(self)
        d["memory_type"] = self.memory_type.value
        d["emotion"] = self.emotion.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryEntry":
        d = dict(d)
        d["memory_type"] = MemoryType(d["memory_type"])
        d["emotion"] = EmotionState.from_dict(d["emotion"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class WorkingMemory:
    """
    工作记忆 — 容量有限，快速衰减

    类似人类的工作记忆：只能hold少量信息，
    不被关注的内容快速衰减消失。
    """

    def __init__(self, capacity: int = 20, half_life: float = 1800):
        self.capacity = capacity
        self.half_life = half_life  # 半衰期（秒）
        self.entries: list[MemoryEntry] = []

    def add(self, entry: MemoryEntry):
        """添加到工作记忆，满了则移除最弱的"""
        self.entries.append(entry)
        self._decay_all()
        if len(self.entries) > self.capacity:
            # 移除强度最低的
            self.entries.sort(key=lambda e: e.strength)
            self.entries = self.entries[-(self.capacity):]

    def get_all(self) -> list[MemoryEntry]:
        """获取所有条目并衰减"""
        self._decay_all()
        return self.entries

    def _decay_all(self):
        """对所有条目应用时间衰减"""
        now = time.time()
        for entry in self.entries:
            elapsed = now - entry.last_accessed
            entry.strength *= math.exp(-0.693 * elapsed / self.half_life)  # 0.693 ≈ ln(2)
            entry.last_accessed = now
        # 移除太弱的
        self.entries = [e for e in self.entries if e.strength > 0.01]

    def peek(self) -> list[MemoryEntry]:
        """查看但不衰减"""
        return list(self.entries)

    def clear(self):
        self.entries.clear()


class LongTermMemory:
    """
    长期记忆 — 持久化存储，情绪调制，支持遗忘

    特性：
    - 情绪强度高的记忆编码权重更大
    - 每次访问轻微衰减，但高频访问维持强度
    - 支持按类型、标签、情绪偏向检索
    """

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.entries: list[MemoryEntry] = []
        self._load()

    def encode(
        self,
        content: str,
        memory_type: MemoryType,
        emotion: EmotionState,
        tags: list[str] = None,
        source: str = "",
    ) -> MemoryEntry:
        """
        编码新记忆 — 受情绪调制

        高唤醒情绪 → 更强的初始编码
        """
        import uuid
        now = time.time()
        # 情绪对编码的增强
        emotional_boost = 1.0 + (emotion.intensity * 0.5)  # 最高 1.5x
        entry = MemoryEntry(
            id=str(uuid.uuid4())[:8],
            content=content,
            memory_type=memory_type,
            emotion=emotion,
            created_at=now,
            last_accessed=now,
            strength=min(1.0, emotional_boost),
            tags=tags or [],
            source=source,
        )
        self.entries.append(entry)
        self._save()
        return entry

    def retrieve(
        self,
        query: str = "",
        memory_type: Optional[MemoryType] = None,
        tags: list[str] = None,
        emotion_bias: Optional[EmotionState] = None,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """
        检索记忆 — 支持情绪偏向的回忆

        emotion_bias 模拟人类的 mood-congruent recall：
        当前情绪状态会影响能回忆起什么
        """
        candidates = self.entries

        # 按类型过滤
        if memory_type:
            candidates = [e for e in candidates if e.memory_type == memory_type]

        # 按标签过滤
        if tags:
            tag_set = set(tags)
            candidates = [e for e in candidates if tag_set & set(e.tags)]

        # 按内容匹配（优先语义检索，回退到简单匹配）
        if query:
            try:
                from .retrieval import semantic_search
                candidates = semantic_search(query, candidates, limit * 2, emotion_bias)
            except ImportError:
                query_lower = query.lower()
                candidates = [e for e in candidates if query_lower in e.content.lower()]

        # 衰减 + 重新评分
        now = time.time()
        scored = []
        for entry in candidates:
            # 时间衰减
            elapsed = now - entry.last_accessed
            decay = math.exp(-0.693 * elapsed / 86400)  # 1天半衰期
            score = entry.strength * decay

            # 情绪偏向加成
            if emotion_bias:
                # 计算情绪相似度（简单余弦）
                e_vec = [entry.emotion.valence, entry.emotion.arousal, entry.emotion.dominance]
                b_vec = [emotion_bias.valence, emotion_bias.arousal, emotion_bias.dominance]
                dot = sum(a * b for a, b in zip(e_vec, b_vec))
                mag_e = math.sqrt(sum(x**2 for x in e_vec)) or 1
                mag_b = math.sqrt(sum(x**2 for x in b_vec)) or 1
                similarity = dot / (mag_e * mag_b)
                score *= 1.0 + similarity * 0.3  # 情绪相似时最高 +30%

            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [e for _, e in scored[:limit]]

        # 标记访问
        for entry in results:
            entry.last_accessed = now
            entry.access_count += 1

        self._save()
        return results

    def forget(self, min_strength: float = 0.05):
        """遗忘 — 移除强度过低的记忆"""
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.strength > min_strength]
        forgotten = before - len(self.entries)
        if forgotten:
            self._save()
        return forgotten

    def _save(self):
        """持久化到磁盘"""
        data = [e.to_dict() for e in self.entries]
        path = self.storage_path / "long_term.json"
        text = json.dumps(data, ensure_ascii=False, indent=2)
        # 清除 LLM 可能产生的非法 UTF-8 surrogate 字符
        text = text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')
        path.write_text(text, encoding='utf-8')

    def _load(self):
        """从磁盘加载"""
        path = self.storage_path / "long_term.json"
        if path.exists():
            raw = path.read_text(encoding='utf-8')
            # 处理可能的非法 UTF-8
            clean = raw.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='replace')
            data = json.loads(clean)
            self.entries = [MemoryEntry.from_dict(d) for d in data]

    def stats(self) -> dict:
        """记忆统计"""
        if not self.entries:
            return {"total": 0}
        types = {}
        for e in self.entries:
            t = e.memory_type.value
            types[t] = types.get(t, 0) + 1
        avg_strength = sum(e.strength for e in self.entries) / len(self.entries)
        return {
            "total": len(self.entries),
            "by_type": types,
            "avg_strength": round(avg_strength, 3),
        }
