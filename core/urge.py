"""
AWARE 表达欲水位线 (Urge to Speak) — 主动聊天触发系统

当系统的"想说话"欲望超过阈值时，主动向语言层发送指令。

公式: Urge = f(Arousal) + g(Subconscious_New_Insight) - h(Last_Interaction_Time)
"""

import math
import time
from dataclasses import dataclass, field
from typing import Optional

from .events import EventBus, Event, EventType


@dataclass
class UrgeState:
    """表达欲状态"""
    value: float = 0.0            # 当前水位 [0, 1]
    threshold: float = 0.65       # 触发阈值
    
    # 各贡献分量
    arousal_component: float = 0.0
    insight_component: float = 0.0
    social_component: float = 0.0
    drive_component: float = 0.0
    
    # 历史
    last_triggered: float = 0.0
    trigger_count: int = 0
    
    @property
    def is_triggering(self) -> bool:
        return self.value >= self.threshold
    
    def to_dict(self) -> dict:
        return {
            "value": round(self.value, 3),
            "threshold": self.threshold,
            "triggering": self.is_triggering,
            "components": {
                "arousal": round(self.arousal_component, 3),
                "insight": round(self.insight_component, 3),
                "social": round(self.social_component, 3),
                "drive": round(self.drive_component, 3),
            },
            "trigger_count": self.trigger_count,
        }


class UrgeToSpeak:
    """
    表达欲水位线 — 决定 AI 何时主动说话
    
    组成：
    1. 情绪唤醒 (Arousal) → 高唤醒 = 更想说话
    2. 新洞察 (New Insight) → 有新发现 = 想分享
    3. 社交间隔 (Time Gap) → 太久没说话 = 想聊天
    4. 内驱力 (Drives) → 表达欲驱动 = 想输出
    
    抑制因子：
    - 最近刚说过话 → 抑制
    - 用户正在输入 → 抑制
    - 系统忙碌 → 抑制
    """
    
    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        threshold: float = 0.65,
        cooldown: float = 120,           # 触发后冷却时间（秒）
        insight_decay: float = 0.98,     # 洞察贡献衰减
    ):
        self.events = event_bus
        self.state = UrgeState(threshold=threshold)
        self.cooldown = cooldown
        self.insight_decay = insight_decay
        
        # 状态追踪
        self._last_speech_time: float = 0.0
        self._last_interaction_time: float = time.time()
        self._recent_insights: list[dict] = []
        self._suppressed: bool = False
        self._history: list[dict] = []
    
    def update(
        self,
        arousal: float,
        new_insight_count: int = 0,
        insight_salience: float = 0.0,
        expression_drive: float = 0.3,
        user_active: bool = False,
    ) -> UrgeState:
        """
        更新表达欲水位
        
        参数:
        - arousal: 当前情绪唤醒度 [-1, 1]
        - new_insight_count: 最近新增的洞察数量
        insight_salience: 洞察的平均显著性
        - expression_drive: 内驱力中的表达欲分量 [0, 1]
        - user_active: 用户是否正在活跃
        """
        now = time.time()
        
        # 1. 情绪唤醒贡献 [0, 0.3]
        # 高唤醒 → 更想说话；低唤醒 → 安静
        self.state.arousal_component = max(0, (arousal + 1) / 2) * 0.3
        
        # 2. 新洞察贡献 [0, 0.3]
        if new_insight_count > 0:
            insight_boost = min(0.3, new_insight_count * 0.05 * (1 + insight_salience))
            self.state.insight_component = min(
                0.3,
                self.state.insight_component + insight_boost,
            )
        # 自然衰减
        self.state.insight_component *= self.insight_decay
        
        # 3. 社交间隔贡献 [0, 0.25]
        time_since_speech = now - self._last_speech_time if self._last_speech_time > 0 else 600
        time_since_interaction = now - self._last_interaction_time
        
        if time_since_interaction > 60:
            # 1 分钟后开始增长
            social_gap = min(0.25, (time_since_interaction - 60) / 1800 * 0.25)
            self.state.social_component = social_gap
        else:
            self.state.social_component = 0
        
        # 4. 内驱力贡献 [0, 0.15]
        self.state.drive_component = expression_drive * 0.15
        
        # 计算总表达欲
        raw_urge = (
            self.state.arousal_component +
            self.state.insight_component +
            self.state.social_component +
            self.state.drive_component
        )
        
        # 抑制因子
        if user_active:
            raw_urge *= 0.5  # 用户活跃时抑制
        
        if time_since_speech < self.cooldown:
            cooldown_factor = time_since_speech / self.cooldown
            raw_urge *= cooldown_factor
        
        if self._suppressed:
            raw_urge *= 0.3
        
        self.state.value = min(1.0, raw_urge)
        
        # 记录历史
        self._history.append({
            "time": now,
            "urge": self.state.value,
            "arousal_c": self.state.arousal_component,
            "insight_c": self.state.insight_component,
            "social_c": self.state.social_component,
            "drive_c": self.state.drive_component,
        })
        if len(self._history) > 300:
            self._history = self._history[-300:]
        
        return self.state
    
    def check_trigger(self) -> Optional[dict]:
        """
        检查是否应该触发主动说话
        
        返回触发信息或 None
        """
        now = time.time()
        
        # 冷却检查
        if self._last_speech_time > 0 and (now - self._last_speech_time) < self.cooldown:
            return None
        
        if self.state.is_triggering and not self._suppressed:
            self.state.last_triggered = now
            self.state.trigger_count += 1
            self._last_speech_time = now
            
            trigger_data = {
                "urge": self.state.value,
                "threshold": self.state.threshold,
                "components": self.state.to_dict()["components"],
                "timestamp": now,
            }
            
            if self.events:
                self.events.emit(Event(
                    type=EventType.PROACTIVE_SPEECH_TRIGGERED,
                    data=trigger_data,
                    source="urge_to_speak",
                ))
            
            # 触发后重置部分分量
            self.state.insight_component *= 0.3
            self.state.social_component *= 0.2
            
            return trigger_data
        
        return None
    
    def on_speech_delivered(self):
        """说话完成"""
        self._last_speech_time = time.time()
    
    def on_user_interaction(self):
        """用户交互"""
        self._last_interaction_time = time.time()
        # 交互降低社交分量
        self.state.social_component *= 0.3
    
    def suppress(self):
        """暂时抑制主动说话"""
        self._suppressed = True
    
    def unsuppress(self):
        """取消抑制"""
        self._suppressed = False
    
    def get_history(self, limit: int = 60) -> list[dict]:
        return self._history[-limit:]
    
    def status(self) -> dict:
        return {
            "state": self.state.to_dict(),
            "suppressed": self._suppressed,
            "time_since_speech": round(time.time() - self._last_speech_time) if self._last_speech_time > 0 else None,
            "time_since_interaction": round(time.time() - self._last_interaction_time),
            "history_points": len(self._history),
        }
