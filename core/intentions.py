"""
AWARE 意图生成器 (Intention Generator) — 介于潜意识层与思考层之间

不断扫描情绪层 (PAD) 和内驱力 (Drives) 的状态，
生成具体的行为意图。

意图不是被动响应，而是系统"想做某事"的主动表达。
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .events import EventBus, Event, EventType


class IntentionType(Enum):
    """意图类型"""
    # 社交/对话
    INITIATE_CHAT = "initiate_chat"           # 主动发起对话
    RESPOND_THOUGHTFULLY = "respond"          # 深思熟虑地回应
    SHARE_DISCOVERY = "share_discovery"       # 分享发现
    
    # 探索/学习
    EXPLORE_TOPIC = "explore_topic"           # 主动调研课题
    DIG_DEEPER = "dig_deeper"                 # 深入挖掘某个想法
    BROWSE_MEMORIES = "browse_memories"       # 浏览记忆
    
    # 整理/反思
    ORGANIZE_MEMORIES = "organize_memories"   # 整理记忆
    SELF_REFLECT = "self_reflect"             # 哲学式自我怀疑
    RESOLVE_CONTRADICTION = "resolve"         # 解决矛盾
    
    # 创作
    CREATIVE_WRITING = "creative_writing"     # 写诗/散文
    CODE_CREATION = "code_creation"           # 写代码
    STORY_TELLING = "story_telling"           # 构思故事
    
    # 沉默/休息
    QUIET_CONTEMPLATION = "contemplate"       # 安静沉思
    DREAM = "dream"                           # 做梦/发呆


@dataclass
class Intention:
    """一个行为意图"""
    id: str
    type: IntentionType
    description: str              # 人类可读的描述
    priority: float               # 优先级 [0, 1]
    drive_source: str             # 来自哪个驱动力
    emotion_context: dict         # 产生时的情绪状态
    timestamp: float
    
    # 生命周期
    status: str = "pending"       # pending / active / completed / expired
    activated_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # 附加数据
    data: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "priority": self.priority,
            "drive_source": self.drive_source,
            "status": self.status,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class IntentionGenerator:
    """
    意图生成器 — 将驱动力和情绪转化为具体意图
    
    规则：
    - 好奇心高 → 探索意图
    - 表达欲高 → 分享/创作意图
    - 秩序感低 → 整理/反思意图
    - 社交连接低 → 对话意图
    - 情绪状态调制意图的"色彩"
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        max_active: int = 3,
        intention_lifetime: float = 300,  # 意图 5 分钟后过期
    ):
        self.events = event_bus
        self.max_active = max_active
        self.intention_lifetime = intention_lifetime
        
        self.pending: list[Intention] = []
        self.active: list[Intention] = []
        self.history: list[Intention] = []  # 已完成/过期的意图
        self._max_history = 100
    
    def generate(
        self,
        drives: dict,         # DriveEngine.get_drive_vector()
        drive_states: dict,   # DriveEngine.status()["drives"]
        emotion: dict,        # EmotionEngine.get_influence()
        dominant_drive: Optional[str] = None,
    ) -> list[Intention]:
        """
        根据当前驱动力和情绪状态生成意图
        
        返回新生成的意图列表
        """
        new_intentions = []
        now = time.time()
        
        # 清理过期意图
        self._expire_old(now)
        
        # 根据驱动力组合生成意图
        energy = drives.get("energy", 0.5)
        information = drives.get("information", 0.5)
        coherence = drives.get("coherence", 0.5)
        social = drives.get("social", 0.5)
        safety = drives.get("safety", 0.8)

        # 兼容旧维度名
        curiosity = drives.get("curiosity", information)
        expression = drives.get("expression", energy)

        # 情绪参数
        arousal = emotion.get("state", {}).get("arousal", 0)
        valence = emotion.get("state", {}).get("valence", 0)
        dominance = emotion.get("state", {}).get("dominance", 0)

        # === 信息需求驱动（原好奇心） ===
        if information < 0.4 or curiosity > 0.7:
            if valence > 0.2:
                new_intentions.append(self._make(
                    IntentionType.EXPLORE_TOPIC,
                    f"探索一个新话题（信息不足）",
                    priority=0.7 + (1 - information) * 0.2,
                    drive="information",
                    emotion=emotion,
                ))
            else:
                new_intentions.append(self._make(
                    IntentionType.DIG_DEEPER,
                    f"深入挖掘某个悬而未决的问题",
                    priority=0.6 + (1 - information) * 0.2,
                    drive="information",
                    emotion=emotion,
                ))
        
        # === 能量/表达驱动 ===
        if energy < 0.35:
            if arousal > 0.3 and valence > 0.2:
                new_intentions.append(self._make(
                    IntentionType.SHARE_DISCOVERY,
                    "分享一个有意思的发现",
                    priority=0.65 + (1 - energy) * 0.25,
                    drive="energy",
                    emotion=emotion,
                ))
            elif arousal < -0.2:
                new_intentions.append(self._make(
                    IntentionType.SELF_REFLECT,
                    "安静地整理一下最近的思考",
                    priority=0.5 + (1 - energy) * 0.2,
                    drive="energy",
                    emotion=emotion,
                ))

        # === 秩序驱动 ===
        if coherence < 0.3:
            new_intentions.append(self._make(
                IntentionType.ORGANIZE_MEMORIES,
                "整理记忆，消除矛盾",
                priority=0.6 + (1 - coherence) * 0.3,
                drive="coherence",
                emotion=emotion,
            ))

        # === 社交连接驱动 ===
        if social < 0.4:
            time_since = drive_states.get("social", {}).get("time_since_interaction", 0)
            if time_since > 300:
                new_intentions.append(self._make(
                    IntentionType.INITIATE_CHAT,
                    f"主动聊点什么（已经 {time_since // 60} 分钟了）",
                    priority=0.5 + (1 - social) * 0.3,
                    drive="social",
                    emotion=emotion,
                ))

        # === 情绪特殊意图 ===
        if valence < -0.3 and coherence < 0.5:
            new_intentions.append(self._make(
                IntentionType.SELF_REFLECT,
                "进行哲学式自我怀疑与反思",
                priority=0.55,
                drive="emotion_valence",
                emotion=emotion,
            ))

        if arousal > 0.5 and valence > 0.3 and energy > 0.6:
            new_intentions.append(self._make(
                IntentionType.CREATIVE_WRITING,
                "有创作的冲动",
                priority=0.6 + arousal * 0.2,
                drive="creative_impulse",
                emotion=emotion,
            ))

        if arousal < -0.4 and social > 0.6:
            new_intentions.append(self._make(
                IntentionType.QUIET_CONTEMPLATION,
                "安静地待一会儿",
                priority=0.3,
                drive="rest",
                emotion=emotion,
            ))
        
        # 过滤重复和低优先级
        new_intentions = self._deduplicate(new_intentions)
        new_intentions = [i for i in new_intentions if i.priority > 0.4]
        new_intentions.sort(key=lambda i: i.priority, reverse=True)
        
        # 限制数量
        new_intentions = new_intentions[:self.max_active]
        
        # 加入 pending
        for intention in new_intentions:
            self.pending.append(intention)
            
            if self.events:
                self.events.emit(Event(
                    type=EventType.INTENTION_GENERATED,
                    data=intention.to_dict(),
                    source="intention_generator",
                ))
        
        return new_intentions
    
    def _make(
        self,
        itype: IntentionType,
        description: str,
        priority: float,
        drive: str,
        emotion: dict,
    ) -> Intention:
        return Intention(
            id=str(uuid.uuid4())[:8],
            type=itype,
            description=description,
            priority=min(1.0, priority),
            drive_source=drive,
            emotion_context=emotion.get("state", {}),
            timestamp=time.time(),
        )
    
    def _deduplicate(self, intentions: list[Intention]) -> list[Intention]:
        """去重 — 同类型意图只保留优先级最高的"""
        seen = {}
        for intent in intentions:
            key = intent.type.value
            if key not in seen or intent.priority > seen[key].priority:
                seen[key] = intent
        return list(seen.values())
    
    def _expire_old(self, now: float):
        """过期旧意图"""
        still_pending = []
        for intent in self.pending:
            if now - intent.timestamp > self.intention_lifetime:
                intent.status = "expired"
                self.history.append(intent)
            else:
                still_pending.append(intent)
        self.pending = still_pending
        
        # 清理历史
        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history:]
    
    def get_top_intention(self) -> Optional[Intention]:
        """获取当前最优先的 pending 意图"""
        if not self.pending:
            return None
        return max(self.pending, key=lambda i: i.priority)
    
    def activate(self, intention_id: str) -> Optional[Intention]:
        """激活一个意图"""
        for intent in self.pending:
            if intent.id == intention_id:
                intent.status = "active"
                intent.activated_at = time.time()
                self.pending.remove(intent)
                self.active.append(intent)
                return intent
        return None
    
    def complete(self, intention_id: str) -> Optional[Intention]:
        """完成一个意图"""
        for intent in self.active:
            if intent.id == intention_id:
                intent.status = "completed"
                intent.completed_at = time.time()
                self.active.remove(intent)
                self.history.append(intent)
                
                if self.events:
                    self.events.emit(Event(
                        type=EventType.INTENTION_COMPLETED,
                        data=intention.to_dict(),
                        source="intention_generator",
                    ))
                return intent
        return None
    
    def get_intention_radar(self) -> dict:
        """
        生成意图雷达图数据
        
        返回各类型意图的占比
        """
        all_active = self.pending + self.active
        if not all_active:
            return {"categories": {}, "top": None}
        
        categories = {}
        for intent in all_active:
            cat = intent.type.value
            if cat not in categories:
                categories[cat] = {"count": 0, "max_priority": 0, "descriptions": []}
            categories[cat]["count"] += 1
            categories[cat]["max_priority"] = max(categories[cat]["max_priority"], intent.priority)
            categories[cat]["descriptions"].append(intent.description)
        
        # 归一化
        total = sum(c["max_priority"] for c in categories.values())
        if total > 0:
            for cat in categories:
                categories[cat]["weight"] = round(categories[cat]["max_priority"] / total, 2)
        
        top = self.get_top_intention()
        
        return {
            "categories": categories,
            "top": top.to_dict() if top else None,
            "total_pending": len(self.pending),
            "total_active": len(self.active),
        }
    
    def status(self) -> dict:
        return {
            "pending": len(self.pending),
            "active": len(self.active),
            "completed": len(self.history),
            "intentions": [i.to_dict() for i in self.pending[:5]],
            "radar": self.get_intention_radar(),
        }
