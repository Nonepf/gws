"""
内驱力系统 v3 — 稳态调节强化学习 (HRRL)

传统强化学习依赖外部奖赏函数。
HRRL 将奖励内在化为"驱动力减少"（Drive Reduction）：

  驱动力 d(H_t) = (Σ|h* - h|^m)^(1/m)

  主奖励 r(H_t, K_t) = d(H_t) - d(H_t + K_t)

这提供了生物学上合理的自治动机：
追求内部平衡，而非无限最大化某个外部指标。

一旦达到设定点（homeostasis），智能体自然停止——
这就是"有界自治"的数学基础。
"""

import math
import time
from dataclasses import dataclass, field
from typing import Optional

from .events import EventBus, Event, EventType


# ============================================================
# 稳态维度
# ============================================================

@dataclass
class HomeostaticDimension:
    """单个稳态维度"""
    name: str
    current: float = 0.5            # 当前值 [0, 1]
    setpoint: float = 0.5           # 设定点 [0, 1]
    tolerance: float = 0.1          # 容差范围
    drift_rate: float = 0.001       # 自然漂移速率（每秒，向远离设定点方向）
    drift_direction: int = -1       # 漂移方向：-1=向下，+1=向上

    @property
    def deviation(self) -> float:
        """偏离度 |h* - h|"""
        return abs(self.setpoint - self.current)

    @property
    def signed_deviation(self) -> float:
        """有符号偏离度 h* - h（正值=不足，负值=过剩）"""
        return self.setpoint - self.current

    @property
    def is_satisfied(self) -> bool:
        """是否在容差范围内"""
        return self.deviation <= self.tolerance

    @property
    def tension(self) -> float:
        """张力 = 超过容差的偏离部分"""
        return max(0, self.deviation - self.tolerance)

    def drift(self, dt: float):
        """自然漂移（远离设定点）"""
        self.current += self.drift_direction * self.drift_rate * dt
        self.current = max(0.0, min(1.0, self.current))

    def apply_event(self, magnitude: float):
        """外部事件影响（正=向设定点靠近，负=远离）"""
        if self.signed_deviation > 0:
            # 不足 → 正事件补充
            self.current += magnitude * self.signed_deviation
        else:
            # 过剩 → 负事件消耗
            self.current += magnitude * self.signed_deviation
        self.current = max(0.0, min(1.0, self.current))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "current": round(self.current, 3),
            "setpoint": round(self.setpoint, 3),
            "deviation": round(self.deviation, 3),
            "tension": round(self.tension, 3),
            "satisfied": self.is_satisfied,
        }


# ============================================================
# HRRL 驱动引擎
# ============================================================

class HomeostaticState:
    """多维稳态空间 H"""

    def __init__(self):
        self.dimensions: dict[str, HomeostaticDimension] = {
            "energy": HomeostaticDimension("能量", current=0.5, setpoint=0.7, drift_rate=0.0005, drift_direction=-1),
            "information": HomeostaticDimension("信息", current=0.5, setpoint=0.6, drift_rate=0.0008, drift_direction=-1),
            "coherence": HomeostaticDimension("秩序", current=0.5, setpoint=0.7, drift_rate=0.0003, drift_direction=-1),
            "social": HomeostaticDimension("社交", current=0.5, setpoint=0.5, drift_rate=0.0006, drift_direction=-1),
            "safety": HomeostaticDimension("安全", current=0.8, setpoint=0.8, drift_rate=0.0002, drift_direction=-1),
        }

    def get_values(self) -> dict[str, float]:
        """获取所有维度的当前值"""
        return {k: d.current for k, d in self.dimensions.items()}

    def get_deviations(self) -> dict[str, float]:
        """获取所有维度的偏离度"""
        return {k: d.deviation for k, d in self.dimensions.items()}

    def get_signed_deviations(self) -> dict[str, float]:
        """获取有符号偏离度"""
        return {k: d.signed_deviation for k, d in self.dimensions.items()}

    def to_dict(self) -> dict:
        return {k: d.to_dict() for k, d in self.dimensions.items()}


class HRRLDriveEngine:
    """
    稳态调节强化学习引擎

    核心数学：
    - 驱动力: d(H_t) = (Σ|h* - h|^m)^(1/m)
    - 主奖励: r = d(before) - d(after)
    - 目标: 最小化累积驱动力（即维持稳态）
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        m: float = 2.0,                # Minkowski 度量参数
        drive_threshold: float = 0.15,  # 驱动力触发阈值
    ):
        self.events = event_bus
        self.m = m
        self.drive_threshold = drive_threshold

        self.state = HomeostaticState()
        self._last_drive: float = 0.0
        self._last_tick: float = time.time()
        self._last_interaction: float = time.time()
        self._subconscious_backlog: int = 0
        self._reward_history: list[dict] = []

    def drive(self, H: HomeostaticState = None) -> float:
        """
        计算驱动力 d(H_t) = (Σ|h* - h|^m)^(1/m)

        驱动力越大 = 越不满足 = 越有动机行动
        """
        H = H or self.state
        deviations = [d.deviation for d in H.dimensions.values()]
        if not deviations:
            return 0.0
        return (sum(d ** self.m for d in deviations)) ** (1.0 / self.m)

    def primary_reward(self, H_before: HomeostaticState, H_after: HomeostaticState) -> float:
        """
        主奖励 = 驱动力减少量

        r(H_t, K_t) = d(H_before) - d(H_after)
        正值 = 进步（驱动力降低）
        负值 = 恶化（驱动力升高）
        """
        return self.drive(H_before) - self.drive(H_after)

    def tick(self, dt: float = None) -> list[dict]:
        """
        推进时间步

        1. 所有维度自然漂移（远离设定点）
        2. 计算当前驱动力
        3. 检查触发阈值
        """
        now = time.time()
        if dt is None:
            dt = now - self._last_tick
        self._last_tick = now

        # 自然漂移
        for dim in self.state.dimensions.values():
            dim.drift(dt)

        # 社交维度特殊处理：随时间推移下降
        time_since_interaction = now - self._last_interaction
        if time_since_interaction > 120:
            loneliness = min(0.01, time_since_interaction / 3600 * 0.01)
            self.state.dimensions["social"].current = max(
                0.0,
                self.state.dimensions["social"].current - loneliness * dt
            )

        # 计算驱动力
        current_drive = self.drive()
        self._last_drive = current_drive

        # 检查触发
        triggered = []
        if current_drive > self.drive_threshold:
            dominant = self.get_dominant_need()
            if dominant:
                dim = self.state.dimensions[dominant]
                if dim.tension > 0.05:
                    event_data = {
                        "drive_level": round(current_drive, 3),
                        "dominant_need": dominant,
                        "tension": round(dim.tension, 3),
                        "deviation": round(dim.deviation, 3),
                    }
                    triggered.append(event_data)

                    if self.events:
                        self.events.emit(Event(
                            type=EventType.DRIVE_THRESHOLD_CROSSED,
                            data=event_data,
                            source="hrrl_drive_engine",
                        ))

        return triggered

    # === 外部事件响应 ===

    def on_user_interaction(self):
        """用户交互 → 社交满足 + 能量消耗"""
        now = time.time()
        self._last_interaction = now
        self.state.dimensions["social"].apply_event(0.2)  # 社交部分满足
        self.state.dimensions["information"].apply_event(0.05)  # 新信息
        self.state.dimensions["energy"].apply_event(-0.05)  # 轻微能量消耗

    def on_subconscious_output(self, count: int = 1):
        """潜意识产出 → 信息增加，表达欲上升"""
        self._subconscious_backlog += count
        self.state.dimensions["information"].apply_event(0.02 * count)

    def on_expression_delivered(self):
        """表达完成 → 部分满足"""
        self._subconscious_backlog = max(0, self._subconscious_backlog - 3)

    def on_new_information(self):
        """收到新信息 → 信息满足"""
        self.state.dimensions["information"].apply_event(0.1)

    def on_memory_contradiction(self, count: int = 1):
        """发现矛盾 → 秩序下降"""
        self.state.dimensions["coherence"].apply_event(-0.05 * count)

    def on_coherence_resolved(self):
        """矛盾解决 → 秩序恢复"""
        self.state.dimensions["coherence"].apply_event(0.15)

    def on_safety_threat(self, severity: float):
        """安全威胁"""
        self.state.dimensions["safety"].apply_event(-severity)

    def on_energy_consumption(self, amount: float):
        """能量消耗"""
        self.state.dimensions["energy"].apply_event(-amount)

    def get_dominant_need(self) -> Optional[str]:
        """获取最迫切的需求（偏离最大的维度）"""
        max_tension = 0
        dominant = None
        for key, dim in self.state.dimensions.items():
            if dim.tension > max_tension:
                max_tension = dim.tension
                dominant = key
        return dominant

    def get_drive_vector(self) -> dict[str, float]:
        """获取驱动力向量（兼容 v2 接口）"""
        return self.state.get_values()

    def is_satisfied(self) -> bool:
        """所有维度是否都在容差范围内"""
        return all(d.is_satisfied for d in self.state.dimensions.values())

    def get_drive_level(self) -> float:
        """当前驱动力水平（实时计算）"""
        return self.drive()

    def status(self) -> dict:
        dominant = self.get_dominant_need()
        current_drive = self.drive()  # 实时计算而非用缓存
        return {
            "drive_level": round(current_drive, 3),
            "satisfied": self.is_satisfied(),
            "dominant_need": dominant,
            "dimensions": self.state.to_dict(),
            "time_since_interaction": round(time.time() - self._last_interaction),
            "subconscious_backlog": self._subconscious_backlog,
        }

    def get_history(self, limit: int = 60) -> list[dict]:
        return self._reward_history[-limit:]
