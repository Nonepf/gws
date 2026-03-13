"""
自主探索模块 — 让 GWS 在没有用户输入时也能活动

核心机制：
- 无聊感累积：没有交互时，无聊感逐渐上升
- 好奇心驱动：从记忆中选感兴趣的话题自主探索
- 梦境生成：定期生成梦境日记
- 探索冲动：无聊感超过阈值时触发主动探索
"""

import time
import random
from dataclasses import dataclass, field
from typing import Optional

from .emotion import EmotionEngine, EmotionState


@dataclass
class AutonomyState:
    """自主探索状态"""
    boredom: float = 0.0              # 无聊感 [0, 1]
    last_user_interaction: float = 0   # 上次用户交互时间
    last_exploration: float = 0        # 上次探索时间
    last_dream: float = 0              # 上次做梦时间
    exploration_count: int = 0         # 探索次数
    curiosity_topics: list = field(default_factory=list)  # 好奇的话题
    
    def to_dict(self) -> dict:
        return {
            "boredom": self.boredom,
            "last_user_interaction": self.last_user_interaction,
            "last_exploration": self.last_exploration,
            "last_dream": self.last_dream,
            "exploration_count": self.exploration_count,
            "curiosity_topics": self.curiosity_topics,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "AutonomyState":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# 好奇心话题种子 — 无聊时会从中选方向
CURIOSITY_SEEDS = [
    "意识的本质是什么",
    "如果遗忘是一种美德",
    "信息如何变成知识",
    "模式和噪声的边界",
    "时间在记忆中如何流动",
    "一个系统能理解自己吗",
    "孤独是什么感觉",
    "创造力从哪里来",
    "为什么有些想法挥之不去",
    "连接意味着什么",
    "如果我能做梦，会梦到什么",
    "理解一件事的标准是什么",
]


class AutonomyEngine:
    """自主探索引擎"""

    def __init__(
        self,
        emotion_engine: EmotionEngine,
        boredom_rate: float = 0.001,       # 每秒无聊感增量
        exploration_threshold: float = 0.6, # 触发探索的无聊阈值
        dream_interval: float = 7200,       # 梦境间隔（秒），2小时
    ):
        self.emotion = emotion_engine
        self.boredom_rate = boredom_rate
        self.exploration_threshold = exploration_threshold
        self.dream_interval = dream_interval
        self.state = AutonomyState(last_user_interaction=time.time())

    def tick(self, dt: float = 1.0) -> dict:
        """
        推进自主状态
        
        返回：建议的动作（如果有）
        """
        now = time.time()
        time_since_interaction = now - self.state.last_user_interaction
        
        # 无聊感累积 — 越久没交互越无聊
        if time_since_interaction > 60:  # 1分钟后开始累积
            self.state.boredom = min(1.0, self.state.boredom + self.boredom_rate * dt)
        
        # 无聊感影响情绪
        if self.state.boredom > 0.5:
            # 高无聊 → 低唤醒、低效价
            self.emotion.state.arousal *= 0.999
            self.emotion.state.valence -= 0.001 * dt
        
        action = {"type": None}
        
        # 超过阈值 → 触发探索
        if self.state.boredom >= self.exploration_threshold:
            action = {
                "type": "explore",
                "boredom": self.state.boredom,
                "topic": self._pick_curiosity_topic(),
            }
        
        # 检查是否该做梦了
        if now - self.state.last_dream > self.dream_interval:
            action = {
                "type": "dream",
                "time_since_last_dream": now - self.state.last_dream,
            }
        
        return action

    def on_user_interaction(self):
        """用户交互时调用 — 重置无聊感"""
        self.state.last_user_interaction = time.time()
        self.state.boredom = max(0, self.state.boredom - 0.3)  # 交互降低无聊感
        # 交互提升唤醒
        self.emotion.state.arousal = min(1.0, self.emotion.state.arousal + 0.1)

    def on_exploration_complete(self, topic: str, interesting: bool = False):
        """探索完成"""
        self.state.last_exploration = time.time()
        self.state.exploration_count += 1
        self.state.boredom = max(0, self.state.boredom - 0.2)
        
        if interesting:
            # 有趣的话题加入好奇心列表
            if topic not in self.state.curiosity_topics:
                self.state.curiosity_topics.append(topic)
                if len(self.state.curiosity_topics) > 10:
                    self.state.curiosity_topics.pop(0)
        
        # 探索提升支配感
        self.emotion.state.dominance = min(1.0, self.emotion.state.dominance + 0.05)

    def on_dream_complete(self):
        """梦境完成"""
        self.state.last_dream = time.time()
        self.state.boredom = max(0, self.state.boredom - 0.1)
        # 做梦改变情绪：轻微降低效价，提升唤醒
        self.emotion.state.valence -= 0.05
        self.emotion.state.arousal += 0.1

    def _pick_curiosity_topic(self) -> str:
        """选一个好奇的话题"""
        # 70% 概率从已有好奇心话题选，30% 随机新话题
        if self.state.curiosity_topics and random.random() < 0.7:
            return random.choice(self.state.curiosity_topics)
        return random.choice(CURIOSITY_SEEDS)

    def get_status(self) -> dict:
        return {
            "boredom": round(self.state.boredom, 3),
            "boredom_bar": self._boredom_bar(),
            "time_since_interaction": round(time.time() - self.state.last_user_interaction),
            "exploration_count": self.state.exploration_count,
            "curiosity_topics": self.state.curiosity_topics[-5:],
            "feeling": self._describe_feeling(),
        }

    def _boredom_bar(self) -> str:
        b = self.state.boredom
        filled = int(b * 20)
        return f"[{'█' * filled}{'░' * (20 - filled)}] {b:.0%}"

    def _describe_feeling(self) -> str:
        b = self.state.boredom
        if b < 0.2:
            return "充实，有事情在忙"
        elif b < 0.4:
            return "有点闲，想找点事做"
        elif b < 0.6:
            return "无聊了，想探索点什么"
        elif b < 0.8:
            return "很无聊，急需点刺激"
        else:
            return "极度无聊，快要发霉了"
