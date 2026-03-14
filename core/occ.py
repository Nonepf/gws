"""
OCC 认知评估引擎 — 基于 Ortony-Clore-Collins 情感模型

OCC 模型将情感分为三大类，基于结构化评估：
1. 事件后果评估 → 关于事件的情感（joy, distress, hope, fear...）
2. 行动规范评估 → 关于行动的情感（pride, shame, admiration, reproach...）
3. 对象吸引力评估 → 关于对象的情感（love, hate...）

每种情感都有明确的触发条件（appraisal dimensions），
而非简单的 PAD 映射——这是情感的"理性基础"。
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AppraisalDimension(Enum):
    """评估维度 — 决定产生何种情感"""
    GOAL_RELEVANCE = "goal_relevance"           # 事件是否与目标相关 [0, 1]
    GOAL_CONGRUENCE = "goal_congruence"         # 事件是否有利于目标 [-1, 1]
    EXPECTATION_CONFIRMATION = "expectation"     # 是否符合预期 [-1, 1]
    AGENCY_SELF = "agency_self"                 # 自己导致的 [0, 1]
    AGENCY_OTHER = "agency_other"               # 他人导致的 [0, 1]
    NORM_CONSISTENCY = "norm_consistency"        # 是否符合规范 [-1, 1]
    ATTRACTIVENESS = "attractiveness"            # 对象吸引力 [-1, 1]
    FAMILIARITY = "familiarity"                  # 熟悉度 [0, 1]


class EmotionCategory(Enum):
    """OCC 22 种情感分类"""

    # === 关于事件的情感（Event-based）===
    JOY = "joy"                         # 喜悦：有利事件发生
    DISTRESS = "distress"               # 痛苦：不利事件发生
    HAPPY_FOR = "happy_for"             # 为他人高兴：他人受益
    PITY = "pity"                       # 怜悯：他人受损
    GLOATING = "gloating"               # 幸灾乐祸：敌手受损
    RESENTMENT = "resentment"           # 愤恨：敌手受益
    HOPE = "hope"                       # 希望：预期有利事件
    FEAR = "fear"                       # 恐惧：预期不利事件
    SATISFACTION = "satisfaction"       # 满足：期望有利事件确认发生
    FEARS_CONFIRMED = "fears_confirmed" # 恐惧确认：预期不利事件确认发生
    RELIEF = "relief"                   # 解脱：预期不利事件未发生
    DISAPPOINTMENT = "disappointment"   # 失望：预期有利事件未发生

    # === 关于行动的情感（Agent-based）===
    PRIDE = "pride"                     # 自豪：自己做了值得称赞的事
    SHAME = "shame"                     # 羞愧：自己做了该受谴责的事
    ADMIRATION = "admiration"           # 钦佩：他人做了值得称赞的事
    REPROACH = "reproach"               # 责备：他人做了该受谴责的事
    GRATIFICATION = "gratification"     # 感激满足：自己做了好事且结果有利
    REMORSE = "remorse"                 # 悔恨：自己做了坏事且结果不利

    # === 关于对象的情感（Object-based）===
    LOVE = "love"                       # 喜爱：有吸引力的对象
    HATE = "hate"                       # 厌恶：无吸引力的对象
    GRATITUDE = "gratitude"             # 感激：感谢他人帮助
    ANGER = "anger"                     # 愤怒：因他人不当行为而愤怒


# OCC → PAD 映射表
# 每种 OCC 情感对应一个标准 PAD 向量
OCC_TO_PAD: dict[EmotionCategory, tuple[float, float, float]] = {
    # 事件情感
    EmotionCategory.JOY:              (0.6,  0.5,  0.3),
    EmotionCategory.DISTRESS:        (-0.6,  0.4, -0.3),
    EmotionCategory.HAPPY_FOR:       (0.5,   0.3,  0.1),
    EmotionCategory.PITY:            (-0.4,  0.2, -0.2),
    EmotionCategory.GLOATING:        (0.3,   0.4,  0.4),
    EmotionCategory.RESENTMENT:      (-0.4,  0.5, -0.3),
    EmotionCategory.HOPE:            (0.4,   0.6,  0.2),
    EmotionCategory.FEAR:            (-0.5,  0.7, -0.5),
    EmotionCategory.SATISFACTION:    (0.7,   0.3,  0.4),
    EmotionCategory.FEARS_CONFIRMED: (-0.7,  0.5, -0.5),
    EmotionCategory.RELIEF:          (0.5,  -0.2,  0.3),
    EmotionCategory.DISAPPOINTMENT:  (-0.5, -0.2, -0.3),
    # 行动情感
    EmotionCategory.PRIDE:           (0.6,   0.4,  0.5),
    EmotionCategory.SHAME:           (-0.6,  0.4, -0.5),
    EmotionCategory.ADMIRATION:      (0.5,   0.3, -0.1),
    EmotionCategory.REPROACH:        (-0.4,  0.3,  0.2),
    EmotionCategory.GRATIFICATION:   (0.7,   0.5,  0.4),
    EmotionCategory.REMORSE:         (-0.7,  0.4, -0.5),
    # 对象情感
    EmotionCategory.LOVE:            (0.7,   0.4,  0.2),
    EmotionCategory.HATE:            (-0.7,  0.5,  0.1),
    EmotionCategory.GRATITUDE:       (0.6,   0.3,  0.1),
    EmotionCategory.ANGER:           (-0.6,  0.7,  0.4),
}


@dataclass
class AppraisalResult:
    """评估结果"""
    category: EmotionCategory
    intensity: float                           # 强度 [0, 1]
    dimensions: dict[str, float]               # 各评估维度的值
    pad_vector: tuple[float, float, float]     # 映射到 PAD
    description: str = ""                      # 人类可读描述

    def to_emotion_state(self):
        """转换为 EmotionState"""
        from .emotion import EmotionState
        return EmotionState(
            valence=self.pad_vector[0] * self.intensity,
            arousal=self.pad_vector[1] * self.intensity,
            dominance=self.pad_vector[2] * self.intensity,
        )

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "intensity": round(self.intensity, 3),
            "dimensions": {k: round(v, 3) for k, v in self.dimensions.items()},
            "pad": [round(x, 3) for x in self.pad_vector],
            "description": self.description,
        }


class OCCEngine:
    """
    OCC 认知评估引擎

    根据事件、行动或对象的评估维度，
    确定产生的情感类别和强度。

    使用规则引擎（而非 LLM）确保快速、确定性的评估。
    """

    def __init__(self, goals: list[str] = None, standards: list[str] = None):
        self.goals = goals or []
        self.standards = standards or []
        self._history: list[AppraisalResult] = []

    def set_goals(self, goals: list[str]):
        """设置当前目标列表"""
        self.goals = goals

    def set_standards(self, standards: list[str]):
        """设置规范/标准列表"""
        self.standards = standards

    def appraise_event(
        self,
        description: str,
        valence_hint: float = 0.0,
        expected: Optional[bool] = None,
        affects_self: bool = True,
        affects_other: bool = False,
        other_is_friend: Optional[bool] = None,
    ) -> AppraisalResult:
        """
        评估事件 — 产生关于事件的情感

        参数:
        - description: 事件描述
        - valence_hint: 事件的正负面倾向 [-1, 1]
        - expected: 是否在预期中 (True/False/None)
        - affects_self: 是否影响自己
        - affects_other: 是否影响他人
        - other_is_friend: 受影响的他人是朋友/对手/无关
        """
        dimensions = {
            "goal_relevance": 0.8 if affects_self else 0.3,
            "goal_congruence": valence_hint,
            "expectation": 0.0 if expected is None else (0.5 if expected else -0.5),
        }

        # 确定情感类别
        if affects_self and not affects_other:
            category, intensity = self._event_self(valence_hint, expected)
        elif affects_other and not affects_self:
            category, intensity = self._event_other(valence_hint, other_is_friend)
        else:
            # 同时影响自己和他人
            category, intensity = self._event_self(valence_hint, expected)

        pad = OCC_TO_PAD.get(category, (0.0, 0.0, 0.0))
        result = AppraisalResult(
            category=category,
            intensity=min(1.0, intensity),
            dimensions=dimensions,
            pad_vector=pad,
            description=f"[事件评估] {description} → {category.value}",
        )
        self._history.append(result)
        return result

    def appraise_action(
        self,
        description: str,
        agent_is_self: bool,
        praiseworthy: bool,
        outcome_valence: float = 0.0,
    ) -> AppraisalResult:
        """
        评估行动 — 产生关于行动者的情感

        - agent_is_self: 行动者是自己还是他人
        - praiseworthy: 行动是否值得称赞
        - outcome_valence: 行动结果的好坏
        """
        dimensions = {
            "norm_consistency": 0.5 if praiseworthy else -0.5,
            "agency_self": 1.0 if agent_is_self else 0.0,
            "agency_other": 0.0 if agent_is_self else 1.0,
            "goal_congruence": outcome_valence,
        }

        if agent_is_self:
            if praiseworthy:
                if outcome_valence > 0.3:
                    category = EmotionCategory.GRATIFICATION
                else:
                    category = EmotionCategory.PRIDE
            else:
                if outcome_valence < -0.3:
                    category = EmotionCategory.REMORSE
                else:
                    category = EmotionCategory.SHAME
        else:
            if praiseworthy:
                category = EmotionCategory.ADMIRATION
            else:
                category = EmotionCategory.REPROACH

        intensity = 0.4 + abs(outcome_valence) * 0.4
        pad = OCC_TO_PAD.get(category, (0.0, 0.0, 0.0))

        result = AppraisalResult(
            category=category,
            intensity=min(1.0, intensity),
            dimensions=dimensions,
            pad_vector=pad,
            description=f"[行动评估] {description} → {category.value}",
        )
        self._history.append(result)
        return result

    def appraise_object(
        self,
        description: str,
        attractiveness: float,
        familiarity: float = 0.5,
    ) -> AppraisalResult:
        """
        评估对象 — 产生关于对象的情感

        - attractiveness: 吸引力 [-1, 1]
        - familiarity: 熟悉度 [0, 1]
        """
        dimensions = {
            "attractiveness": attractiveness,
            "familiarity": familiarity,
        }

        if attractiveness > 0.2:
            category = EmotionCategory.LOVE
        elif attractiveness < -0.2:
            category = EmotionCategory.HATE
        else:
            # 中性对象，产生微弱情感
            category = EmotionCategory.LOVE if familiarity > 0.7 else EmotionCategory.HATE

        intensity = min(1.0, 0.3 + abs(attractiveness) * 0.5)
        pad = OCC_TO_PAD.get(category, (0.0, 0.0, 0.0))

        result = AppraisalResult(
            category=category,
            intensity=intensity,
            dimensions=dimensions,
            pad_vector=pad,
            description=f"[对象评估] {description} → {category.value}",
        )
        self._history.append(result)
        return result

    def appraise_from_text(self, text: str, context: dict = None) -> AppraisalResult:
        """
        从文本自动推断评估（简化版规则引擎）

        用于快速评估用户输入的情感倾向
        """
        text_lower = text.lower()
        ctx = context or {}

        # 简单关键词匹配确定情感类别
        positive_events = ["成功", "完成", "好", "棒", "厉害", "喜欢", "开心", "thanks", "谢谢"]
        negative_events = ["失败", "问题", "bug", "错", "不好", "失望", "烦", "烂"]
        hope_signals = ["想", "希望", "如果", "能", "可以", "也许"]
        fear_signals = ["担心", "怕", "万一", "恐怕", "别"]

        valence = 0.0
        for word in positive_events:
            if word in text_lower:
                valence += 0.2
        for word in negative_events:
            if word in text_lower:
                valence -= 0.2
        valence = max(-1.0, min(1.0, valence))

        # 判断期望信号
        has_hope = any(w in text_lower for w in hope_signals)
        has_fear = any(w in text_lower for w in fear_signals)

        if has_hope and not has_fear:
            return self.appraise_event(text, valence_hint=max(0.1, valence), expected=None)
        elif has_fear and not has_hope:
            return self.appraise_event(text, valence_hint=min(-0.1, valence), expected=None)
        else:
            return self.appraise_event(text, valence_hint=valence)

    def blend_results(self, results: list[AppraisalResult]) -> tuple:
        """
        混合多个评估结果为单一 PAD 向量

        按强度加权平均
        """
        if not results:
            return (0.0, 0.0, 0.0)

        total_weight = sum(r.intensity for r in results)
        if total_weight == 0:
            return (0.0, 0.0, 0.0)

        v = sum(r.pad_vector[0] * r.intensity for r in results) / total_weight
        a = sum(r.pad_vector[1] * r.intensity for r in results) / total_weight
        d = sum(r.pad_vector[2] * r.intensity for r in results) / total_weight

        return (
            max(-1.0, min(1.0, v)),
            max(-1.0, min(1.0, a)),
            max(-1.0, min(1.0, d)),
        )

    def _event_self(self, valence: float, expected: Optional[bool]) -> tuple[EmotionCategory, float]:
        """事件影响自己时的情感"""
        intensity = 0.4 + abs(valence) * 0.5

        if expected is not None:
            if valence > 0:
                category = EmotionCategory.SATISFACTION if expected else EmotionCategory.JOY
            else:
                category = EmotionCategory.FEARS_CONFIRMED if expected else EmotionCategory.DISTRESS
        else:
            if valence > 0:
                category = EmotionCategory.HOPE if valence < 0.3 else EmotionCategory.JOY
            else:
                category = EmotionCategory.FEAR if valence > -0.3 else EmotionCategory.DISTRESS

        return category, intensity

    def _event_other(self, valence: float, is_friend: Optional[bool]) -> tuple[EmotionCategory, float]:
        """事件影响他人时的情感"""
        intensity = 0.3 + abs(valence) * 0.4

        if is_friend is True:
            category = EmotionCategory.HAPPY_FOR if valence > 0 else EmotionCategory.PITY
        elif is_friend is False:
            category = EmotionCategory.RESENTMENT if valence > 0 else EmotionCategory.GLOATING
        else:
            # 无关的人
            category = EmotionCategory.HAPPY_FOR if valence > 0 else EmotionCategory.PITY

        return category, intensity

    def get_history(self, limit: int = 20) -> list[dict]:
        return [r.to_dict() for r in self._history[-limit:]]

    def status(self) -> dict:
        return {
            "total_appraisals": len(self._history),
            "goals": self.goals,
            "standards": self.standards,
            "recent": self.get_history(5),
        }
