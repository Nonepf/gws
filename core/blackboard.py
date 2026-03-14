"""
AWARE 黑板 (Blackboard) - 潜意识层的共享工作区

潜意识的 sub-agent 不直接输出到聊天，
而是写入黑板。思考层从黑板中挑选有意义的内容。
黑板也包含"灵感池"供创作使用。
"""

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .events import EventBus, Event, EventType


class EntryType(Enum):
    """黑板条目类型"""
    EXPLORATION = "exploration"     # 探索发现
    PATTERN = "pattern"             # 模式识别
    ASSOCIATION = "association"     # 联想碰撞
    DREAM = "dream"                 # 梦境碎片
    INSIGHT = "insight"             # 洞察（从其他类型升级）
    INSPIRATION = "inspiration"     # 灵感（创作种子）


@dataclass
class BlackboardEntry:
    """黑板条目"""
    id: str
    entry_type: EntryType
    content: str
    agent_role: str               # 哪个 sub-agent 产生的
    confidence: float             # 置信度 [0, 1]
    emotion: dict                 # 产生时的情绪状态
    timestamp: float
    related_memories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # 黑板特有字段
    salience: float = 0.5         # 显著性 [0, 1]，随时间衰减
    promoted: bool = False        # 是否已被思考层拾取
    promotion_count: int = 0      # 被拾取次数

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.entry_type.value,
            "content": self.content,
            "agent_role": self.agent_role,
            "confidence": self.confidence,
            "emotion": self.emotion,
            "timestamp": self.timestamp,
            "salience": self.salience,
            "promoted": self.promoted,
            "tags": self.tags,
        }


@dataclass
class InspirationSeed:
    """灵感池中的创作种子"""
    id: str
    content: str
    source: str                   # 来源：assoc / dream / exploration
    energy: float = 1.0           # 能量，随时间衰减
    timestamp: float = field(default_factory=time.time)
    developed: bool = False       # 是否已被展开

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source,
            "energy": self.energy,
            "developed": self.developed,
        }


class Blackboard:
    """
    潜意识黑板 - sub-agent 的共享输出区

    设计原则：
    - 写入快，读取也快
    - 条目有显著性评分，随时间衰减
    - 思考层"拾取"高显著性的条目
    - 灵感池独立管理，供创作动力使用
    """

    def __init__(
        self,
        max_entries: int = 100,
        max_inspirations: int = 30,
        salience_decay: float = 0.95,   # 每次 tick 衰减
        event_bus: Optional[EventBus] = None,
    ):
        self.max_entries = max_entries
        self.max_inspirations = max_inspirations
        self.salience_decay = salience_decay
        self.events = event_bus

        # 主黑板
        self.entries: deque[BlackboardEntry] = deque(maxlen=max_entries)

        # 灵感池
        self.inspirations: deque[InspirationSeed] = deque(maxlen=max_inspirations)

        # 统计
        self._total_written = 0
        self._total_promoted = 0

    def write(self, entry: BlackboardEntry) -> BlackboardEntry:
        """写入黑板（相似度去重）"""
        # 去重：基于内容相似度（简化版：前30字符匹配或完全相同id）
        entry_preview = entry.content[:30]
        for existing in self.entries:
            if existing.id == entry.id:
                return existing
            # 简单相似度：前30字符相同超过25字符
            existing_preview = existing.content[:30]
            if len(entry_preview) > 10 and len(existing_preview) > 10:
                common = sum(1 for a, b in zip(entry_preview, existing_preview) if a == b)
                if common > min(len(entry_preview), len(existing_preview)) * 0.85:
                    return existing

        self.entries.append(entry)
        self._total_written += 1

        # 如果是高显著性或有创意标签，同时加入灵感池
        if entry.confidence > 0.6 or "creative" in entry.tags:
            self._add_inspiration(entry)

        # 发射事件
        if self.events:
            self.events.emit(Event(
                type=EventType.BLACKBOARD_UPDATED,
                data={"entry": entry.to_dict(), "total_entries": len(self.entries)},
                source="blackboard",
            ))

        return entry

    def _add_inspiration(self, entry: BlackboardEntry):
        """将高潜力条目加入灵感池"""
        seed = InspirationSeed(
            id=str(uuid.uuid4())[:8],
            content=entry.content[:200],
            source=entry.agent_role,
        )
        self.inspirations.append(seed)

        if self.events:
            self.events.emit(Event(
                type=EventType.INSPIRATION_ADDED,
                data={"seed": seed.to_dict(), "pool_size": len(self.inspirations)},
                source="blackboard",
            ))

    def pick_salient(self, limit: int = 5, min_salience: float = 0.3) -> list[BlackboardEntry]:
        """
        思考层调用：拾取高显著性且未被拾取的条目

        返回按显著性排序的条目列表
        """
        candidates = [
            e for e in self.entries
            if not e.promoted and e.salience >= min_salience
        ]
        candidates.sort(key=lambda e: e.salience * e.confidence, reverse=True)

        picked = candidates[:limit]

        # 标记为已拾取
        for entry in picked:
            entry.promoted = True
            entry.promotion_count += 1
            self._total_promoted += 1

        return picked

    def pick_inspirations(self, limit: int = 3, min_energy: float = 0.3) -> list[InspirationSeed]:
        """拾取高能量的灵感种子"""
        candidates = [
            s for s in self.inspirations
            if not s.developed and s.energy >= min_energy
        ]
        candidates.sort(key=lambda s: s.energy, reverse=True)

        picked = candidates[:limit]
        for seed in picked:
            seed.developed = True

        return picked

    def tick_decay(self, mood=None, drives=None):
        """时间步衰减 — 降低所有条目的显著性，可选心境和驱动力调制"""
        for entry in self.entries:
            entry.salience *= self.salience_decay

            # 心境调制：如果条目情绪与当前心境共鸣，衰减更慢
            if mood and isinstance(entry.emotion, dict):
                ev = entry.emotion.get("valence", 0)
                mv = mood.valence if hasattr(mood, 'valence') else 0
                if ev * mv > 0:  # 同号 = 共鸣
                    entry.salience *= 1.02  # 减缓衰减

        for seed in self.inspirations:
            seed.energy *= self.salience_decay

    def get_all(self, limit: int = 50) -> list[BlackboardEntry]:
        """获取所有条目（按时间倒序）"""
        items = list(self.entries)
        items.reverse()
        return items[:limit]

    def get_by_type(self, entry_type: EntryType, limit: int = 20) -> list[BlackboardEntry]:
        """按类型获取条目"""
        items = [e for e in self.entries if e.entry_type == entry_type]
        items.reverse()
        return items[:limit]

    def get_recent(self, seconds: float = 300, limit: int = 20) -> list[BlackboardEntry]:
        """获取最近 N 秒内的条目"""
        cutoff = time.time() - seconds
        items = [e for e in self.entries if e.timestamp >= cutoff]
        items.reverse()
        return items[:limit]

    def clear_promoted(self):
        """清理已拾取的旧条目，释放空间"""
        self.entries = deque(
            [e for e in self.entries if not e.promoted or e.promotion_count < 3],
            maxlen=self.max_entries,
        )

    def cleanup_expired(self, max_age_seconds: float = 3600):
        """清理过期条目（默认 1 小时）"""
        cutoff = time.time() - max_age_seconds
        self.entries = deque(
            [e for e in self.entries if e.timestamp > cutoff or e.promoted],
            maxlen=self.max_entries,
        )

    def status(self) -> dict:
        return {
            "total_entries": len(self.entries),
            "total_inspirations": len(self.inspirations),
            "total_written": self._total_written,
            "total_promoted": self._total_promoted,
            "unpromoted": sum(1 for e in self.entries if not e.promoted),
            "avg_salience": round(
                sum(e.salience for e in self.entries) / max(len(self.entries), 1), 3
            ),
            "inspiration_energy": round(
                sum(s.energy for s in self.inspirations) / max(len(self.inspirations), 1), 3
            ),
        }
