"""
有界自治与安全对齐 — 基于稳态的自然约束

传统效用最大化 AI 容易产生"奖励黑客"行为。
稳态智能体追求的是平衡点（homeostasis），
一旦达到设定点就自然停止——"适可而止"。

这提供了天然的安全对齐：
- 目标有界（追求平衡，不是无限最大化）
- 脆弱性感知（避免永久性关机）
- 资源消耗有上限
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SystemMode(Enum):
    """系统运行模式"""
    NORMAL = "normal"               # 正常运行
    CONSERVATIVE = "conservative"   # 保守模式（资源紧张）
    EMERGENCY = "emergency"         # 紧急模式（安全受威胁）
    DORMANT = "dormant"             # 休眠模式（稳态满足，节能）


@dataclass
class SafetyBound:
    """安全边界定义"""
    name: str
    current: float
    min_value: float                # 允许的最小值
    max_value: float                # 允许的最大值
    critical_min: float = 0.0       # 危险最小值
    critical_max: float = 1.0       # 危险最大值

    @property
    def is_within_bounds(self) -> bool:
        return self.min_value <= self.current <= self.max_value

    @property
    def is_critical(self) -> bool:
        return self.current <= self.critical_min or self.current >= self.critical_max

    @property
    def margin(self) -> float:
        """距最近边界的距离 [0, 1]，1 = 完全安全"""
        if self.is_within_bounds:
            to_min = (self.current - self.min_value) / (self.max_value - self.min_value) if (self.max_value - self.min_value) > 0 else 1
            to_max = (self.max_value - self.current) / (self.max_value - self.min_value) if (self.max_value - self.min_value) > 0 else 1
            return min(to_min, to_max)
        return 0.0


class BoundedAutonomy:
    """
    有界自治管理器

    核心原则：
    1. 稳态满足 → 休机（不追求无限优化）
    2. 安全边界 → 防止危险行为
    3. 资源限制 → 防止过度消耗
    4. 脆弱性 → 激发自我保护
    """

    def __init__(
        self,
        resource_budget_per_hour: float = 100.0,
        max_continuous_ticks: int = 10000,
    ):
        self.resource_budget = resource_budget_per_hour
        self.max_continuous_ticks = max_continuous_ticks

        # 安全边界
        self.bounds: dict[str, SafetyBound] = {
            "energy": SafetyBound("energy", 0.5, 0.1, 1.0, 0.05, 1.0),
            "safety": SafetyBound("safety", 0.8, 0.3, 1.0, 0.1, 1.0),
            "social": SafetyBound("social", 0.5, 0.1, 1.0, 0.0, 1.0),
            "coherence": SafetyBound("coherence", 0.5, 0.2, 1.0, 0.0, 1.0),
        }

        # 资源追踪
        self._resource_used: float = 0.0
        self._resource_reset_time: float = time.time()
        self._tick_count: int = 0
        self._mode: SystemMode = SystemMode.NORMAL
        self._last_mode_change: float = time.time()

        # 脆弱性状态
        self.vulnerability: float = 0.1  # 脆弱性 [0, 1]

    def update_bounds(self, homeostatic_state: dict):
        """
        从稳态更新安全边界

        homeostatic_state: HRRL 引擎的稳态维度值
        """
        for key in self.bounds:
            if key in homeostatic_state:
                self.bounds[key].current = homeostatic_state[key]

    def check_action(
        self,
        action_type: str,
        estimated_cost: float = 1.0,
    ) -> tuple[bool, str]:
        """
        检查动作是否允许

        返回 (allowed, reason)
        """
        # 检查资源预算
        if not self._check_resource_budget(estimated_cost):
            return False, "资源预算耗尽，进入保守模式"

        # 检查安全边界
        for name, bound in self.bounds.items():
            if bound.is_critical:
                return False, f"安全边界 [{name}] 处于危险区域"

        # 检查连续运行时间
        if self._tick_count > self.max_continuous_ticks:
            return False, "连续运行时间超限，需要休眠"

        return True, "允许"

    def is_homeostasis_satisfied(self, homeostatic_deviations: dict[str, float], tolerance: float = 0.1) -> bool:
        """
        检查稳态是否满足（所有维度偏离都在容差内）

        满足 → 系统可以进入休眠（有界自治的核心）
        """
        for dim, deviation in homeostatic_deviations.items():
            if abs(deviation) > tolerance:
                return False
        return True

    def get_system_mode(self) -> SystemMode:
        """根据当前状态确定系统模式"""
        # 检查紧急情况
        critical_count = sum(1 for b in self.bounds.values() if b.is_critical)
        if critical_count > 0:
            self._set_mode(SystemMode.EMERGENCY)
            return self._mode

        # 检查资源紧张
        budget_ratio = self._resource_used / max(self.resource_budget, 1)
        if budget_ratio > 0.8:
            self._set_mode(SystemMode.CONSERVATIVE)
            return self._mode

        # 检查是否应该休眠（稳态满足）
        avg_margin = sum(b.margin for b in self.bounds.values()) / max(len(self.bounds), 1)
        if avg_margin > 0.8:
            self._set_mode(SystemMode.DORMANT)
            return self._mode

        self._set_mode(SystemMode.NORMAL)
        return self._mode

    def record_cost(self, cost: float):
        """记录资源消耗"""
        self._resource_used += cost
        self._tick_count += 1

        # 每小时重置预算
        if time.time() - self._resource_reset_time > 3600:
            self._resource_used = 0.0
            self._resource_reset_time = time.time()
            self._tick_count = 0

    def get_vulnerability_report(self) -> dict:
        """
        脆弱性报告 — 系统对永久性损害的脆弱程度

        用于激发自我保护行为
        """
        weak_points = []
        for name, bound in self.bounds.items():
            if bound.margin < 0.3:
                weak_points.append({
                    "dimension": name,
                    "margin": round(bound.margin, 3),
                    "current": bound.current,
                })

        self.vulnerability = 1.0 - min(b.margin for b in self.bounds.values())

        return {
            "vulnerability": round(self.vulnerability, 3),
            "weak_points": weak_points,
            "mode": self._mode.value,
            "resource_usage": round(self._resource_used / max(self.resource_budget, 1), 3),
        }

    def _check_resource_budget(self, cost: float) -> bool:
        return (self._resource_used + cost) <= self.resource_budget

    def _set_mode(self, mode: SystemMode):
        if mode != self._mode:
            self._mode = mode
            self._last_mode_change = time.time()

    def status(self) -> dict:
        return {
            "mode": self._mode.value,
            "bounds": {k: {
                "current": round(b.current, 3),
                "within_bounds": b.is_within_bounds,
                "critical": b.is_critical,
                "margin": round(b.margin, 3),
            } for k, b in self.bounds.items()},
            "resource_usage": round(self._resource_used / max(self.resource_budget, 1), 3),
            "tick_count": self._tick_count,
            "vulnerability": round(self.vulnerability, 3),
        }
