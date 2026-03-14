"""
神经递质模拟系统 — 计算认知调制因子

模拟三种关键神经递质的功能效应：
- 多巴胺 (DA): 奖励预测误差、动力、探索欲
- 血清素 (5-HT): 冲动控制、情绪稳定、延迟满足
- 皮质醇 (Cortisol): 压力响应、警觉、防御优先

递质水平 [0, 1] 影响各认知层的超参数，
而非直接决定行为——它们是调制器，不是控制器。
"""

import math
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NeurotransmitterState:
    """三种核心神经递质的水平"""
    dopamine: float = 0.5       # 基线 0.5 [0, 1]
    serotonin: float = 0.5      # 基线 0.5 [0, 1]
    cortisol: float = 0.2       # 基线 0.2（低压力状态）

    # 追踪
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "dopamine": round(self.dopamine, 3),
            "serotonin": round(self.serotonin, 3),
            "cortisol": round(self.cortisol, 3),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NeurotransmitterState":
        return cls(
            dopamine=d.get("dopamine", 0.5),
            serotonin=d.get("serotonin", 0.5),
            cortisol=d.get("cortisol", 0.2),
        )


class NeurotransmitterEngine:
    """
    神经递质引擎 — 管理递质动态并提供认知调制

    每种递质的更新规则：
    - 多巴胺：正向预测误差上升，负向下降；自然衰减到基线
    - 血清素：正面体验缓慢上升，冲动行为快速下降
    - 皮质醇：压力事件快速上升，放松时缓慢下降
    """

    # 基线值
    DA_BASELINE = 0.5
    SEROTONIN_BASELINE = 0.5
    CORTISOL_BASELINE = 0.2

    # 衰减率（每秒向基线回归的速度）
    DA_DECAY = 0.995
    SEROTONIN_DECAY = 0.998
    CORTISOL_DECAY = 0.992  # 皮质醇衰减最慢

    def __init__(self):
        self.state = NeurotransmitterState()
        self._last_tick = time.time()

    def tick(self, dt: float = None):
        """推进时间步：所有递质向基线衰减"""
        now = time.time()
        if dt is None:
            dt = now - self._last_tick
        self._last_tick = now

        # 多巴胺向基线衰减
        da_diff = self.state.dopamine - self.DA_BASELINE
        self.state.dopamine = self.DA_BASELINE + da_diff * (self.DA_DECAY ** dt)

        # 血清素向基线衰减
        ser_diff = self.state.serotonin - self.SEROTONIN_BASELINE
        self.state.serotonin = self.SEROTONIN_BASELINE + ser_diff * (self.SEROTONIN_DECAY ** dt)

        # 皮质醇向基线衰减
        cor_diff = self.state.cortisol - self.CORTISOL_BASELINE
        self.state.cortisol = self.CORTISOL_BASELINE + cor_diff * (self.CORTISOL_DECAY ** dt)

        self._clamp()

    def update_from_reward(self, prediction_error: float):
        """
        多巴胺更新 — 根据奖励预测误差

        prediction_error: 实际奖励 - 预期奖励 [-1, 1]
        正误差 → 多巴胺上升（比预期好）
        负误差 → 多巴胺下降（比预期差）
        """
        # 非线性响应：大误差的边际效应递减
        da_shift = 0.15 * math.tanh(prediction_error * 2)
        self.state.dopamine = self._clamp_value(self.state.dopamine + da_shift)

    def update_from_stress(self, stress_level: float):
        """
        皮质醇更新 — 压力响应

        stress_level: 压力程度 [0, 1]
        """
        target = self.CORTISOL_BASELINE + stress_level * 0.6
        # 皮质醇快速上升，缓慢下降
        if target > self.state.cortisol:
            self.state.cortisol += (target - self.state.cortisol) * 0.3
        else:
            self.state.cortisol += (target - self.state.cortisol) * 0.1
        self._clamp()

    def update_from_social(self, positive_interaction: bool):
        """
        血清素更新 — 社交互动影响

        正面社交 → 血清素上升（情绪稳定、满足感）
        孤立/负面 → 血清素缓慢下降
        """
        if positive_interaction:
            self.state.serotonin = min(1.0, self.state.serotonin + 0.05)
        else:
            self.state.serotonin = max(0.0, self.state.serotonin - 0.03)

    def update_from_pad(self, valence: float, arousal: float, dominance: float):
        """
        从 PAD 情绪状态推断递质水平变化

        正效价 + 高唤醒 → 多巴胺上升
        负效价 + 高唤醒 → 皮质醇上升
        高支配感 → 血清素上升
        """
        # 正面体验 → 多巴胺
        if valence > 0.2:
            self.state.dopamine = min(1.0, self.state.dopamine + valence * 0.05)

        # 压力/焦虑 → 皮质醇
        if arousal > 0.3 and valence < -0.1:
            stress = arousal * abs(valence)
            self.update_from_stress(stress)

        # 支配感 → 血清素（掌控感带来情绪稳定）
        if dominance > 0.2:
            self.state.serotonin = min(1.0, self.state.serotonin + dominance * 0.03)

    def modulate_learning_rate(self, base_lr: float) -> float:
        """
        多巴胺调节学习率

        高多巴胺 → 更高的学习率（对新信息更敏感）
        低多巴胺 → 更低的学习率（保守）
        """
        return base_lr * (0.5 + self.state.dopamine)

    def modulate_discount(self, base_gamma: float) -> float:
        """
        血清素调节时间折扣因子

        高血清素 → 更高的折扣因子（更愿意等待长期回报）
        低血清素 → 更低的折扣因子（冲动，偏好即时满足）
        """
        return base_gamma * (0.7 + self.state.serotonin * 0.3)

    def modulate_temperature(self, base_temp: float) -> float:
        """
        皮质醇调节动作采样温度

        高皮质醇 → 更高温度（更随机/冲动的决策）或更低（僵化）
        这里模拟"战斗或逃跑"的决策偏向
        """
        # 中等压力提升探索，极高压力导致僵化
        if self.state.cortisol < 0.6:
            return base_temp * (1.0 + self.state.cortisol * 0.3)
        else:
            # 极高压力 → 僵化/重复行为
            return base_temp * (1.0 - (self.state.cortisol - 0.6) * 0.5)

    def modulate_exploration(self, base_exploration: float) -> float:
        """
        多巴胺调节探索倾向

        高多巴胺 → 更多探索
        """
        return base_exploration * (0.5 + self.state.dopamine * 0.5)

    def get_cognitive_profile(self) -> dict:
        """
        获取当前递质组合的认知特征描述

        返回各维度的调制因子和文本描述
        """
        da = self.state.dopamine
        ser = self.state.serotonin
        cor = self.state.cortisol

        # 动力水平
        if da > 0.7:
            motivation = "high"
        elif da > 0.4:
            motivation = "moderate"
        else:
            motivation = "low"

        # 情绪稳定性
        if ser > 0.6:
            stability = "stable"
        elif ser > 0.35:
            stability = "moderate"
        else:
            stability = "volatile"

        # 压力状态
        if cor > 0.6:
            stress = "high"
        elif cor > 0.35:
            stress = "moderate"
        else:
            stress = "low"

        return {
            "motivation": motivation,
            "stability": stability,
            "stress": stress,
            "exploration_bias": round(0.5 + da * 0.5, 3),
            "impulse_control": round(ser, 3),
            "alertness": round(0.5 + cor * 0.5, 3),
            "values": self.state.to_dict(),
        }

    def _clamp(self):
        """确保所有值在 [0, 1] 范围内"""
        self.state.dopamine = self._clamp_value(self.state.dopamine)
        self.state.serotonin = self._clamp_value(self.state.serotonin)
        self.state.cortisol = self._clamp_value(self.state.cortisol)

    @staticmethod
    def _clamp_value(v: float) -> float:
        return max(0.0, min(1.0, v))

    def status(self) -> dict:
        return {
            "state": self.state.to_dict(),
            "profile": self.get_cognitive_profile(),
        }
