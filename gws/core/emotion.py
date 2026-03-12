"""
情绪层 — PAD 情绪基座模型

- 基于 PAD (Pleasure-Arousal-Dominance) 三维情绪空间
- 情绪向自然中性衰减
- 支持从文本提取情绪信号（规则版，后续可换神经网络）
- 情绪渗透所有层：影响记忆编码、思考策略、潜意识活动
"""

import math
import re
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EmotionState:
    """PAD 情绪向量"""
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
        """情绪强度 [0, 1]"""
        return min(1.0, math.sqrt(self.valence**2 + self.arousal**2 + self.dominance**2) / math.sqrt(3))

    @property
    def label(self) -> str:
        """粗略情绪标签"""
        v, a, d = self.valence, self.arousal, self.dominance
        if v > 0.3 and a > 0.3:
            return "兴奋" if d > 0.2 else "愉悦"
        elif v > 0.3 and a < -0.3:
            return "平静" if d > 0.2 else "放松"
        elif v < -0.3 and a > 0.3:
            return "愤怒" if d > 0.2 else "焦虑"
        elif v < -0.3 and a < -0.3:
            return "无聊" if d < -0.2 else "悲伤"
        elif a > 0.4:
            return "专注"
        else:
            return "中性"

    def blend(self, other: "EmotionState", weight: float = 0.3) -> "EmotionState":
        """与另一个情绪状态混合"""
        return EmotionState(
            valence=self._clamp(self.valence * (1 - weight) + other.valence * weight),
            arousal=self._clamp(self.arousal * (1 - weight) + other.arousal * weight),
            dominance=self._clamp(self.dominance * (1 - weight) + other.dominance * weight),
        )

    @staticmethod
    def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, v))


class EmotionExtractor:
    """
    从文本提取情绪信号（规则版）

    后续可替换为微调的情绪分类神经网络
    """

    # 简单的情绪词典 → PAD 映射
    LEXICON = {
        # 正面高唤醒
        "开心": (0.7, 0.5, 0.3), "兴奋": (0.8, 0.8, 0.4), "高兴": (0.7, 0.4, 0.3),
        "棒": (0.6, 0.3, 0.2), "好": (0.3, 0.1, 0.1), "喜欢": (0.6, 0.3, 0.2),
        "爱": (0.9, 0.5, 0.3), "惊喜": (0.7, 0.8, 0.1), "有趣": (0.5, 0.4, 0.2),
        "厉害": (0.6, 0.4, 0.5), "牛": (0.6, 0.4, 0.5), "妙": (0.6, 0.3, 0.3),
        "哇": (0.6, 0.7, 0.2), "哈哈": (0.7, 0.5, 0.3),
        "酷": (0.7, 0.6, 0.3), "太好了": (0.8, 0.5, 0.3), "有意思": (0.5, 0.4, 0.2),
        "学到了": (0.5, 0.5, 0.3), "试试": (0.2, 0.4, 0.2), "先试试看": (0.3, 0.5, 0.3),
        "加油": (0.6, 0.6, 0.4), "成功": (0.8, 0.6, 0.5), "做到了": (0.8, 0.7, 0.5),
        "感谢": (0.7, 0.3, 0.2), "谢谢": (0.6, 0.2, 0.2), "感动": (0.6, 0.5, 0.1),
        "美好": (0.7, 0.3, 0.3), "美妙": (0.7, 0.4, 0.3), "完美": (0.8, 0.4, 0.5),
        "新": (0.3, 0.4, 0.1), "新鲜": (0.4, 0.5, 0.2),
        # 正面低唤醒
        "平静": (0.4, -0.5, 0.2), "安心": (0.5, -0.4, 0.3), "放松": (0.4, -0.5, 0.2),
        "舒服": (0.5, -0.2, 0.2), "满足": (0.5, -0.2, 0.4), "踏实": (0.4, -0.3, 0.3),
        # 负面高唤醒
        "生气": (-0.7, 0.7, 0.5), "愤怒": (-0.8, 0.8, 0.6), "焦虑": (-0.5, 0.6, -0.3),
        "害怕": (-0.6, 0.7, -0.5), "担心": (-0.5, 0.4, -0.3), "紧张": (-0.4, 0.6, -0.2),
        "烦躁": (-0.5, 0.5, 0.1), "急": (-0.3, 0.5, 0.0),
        "糟糕": (-0.6, 0.5, -0.2), "完了": (-0.7, 0.6, -0.4), "崩溃": (-0.8, 0.8, -0.5),
        "出问题": (-0.6, 0.5, -0.3), "搞不好": (-0.4, 0.4, -0.2), "麻烦": (-0.4, 0.3, -0.2),
        # 负面低唤醒
        "难过": (-0.6, -0.3, -0.3), "伤心": (-0.7, -0.2, -0.4), "无聊": (-0.4, -0.5, -0.2),
        "累": (-0.3, -0.6, -0.3), "困": (-0.2, -0.7, -0.3), "沮丧": (-0.6, -0.3, -0.4),
        "失望": (-0.5, -0.3, -0.3), "算了": (-0.3, -0.2, -0.3),
        # 疑问/好奇
        "好奇": (0.2, 0.5, 0.1), "疑惑": (-0.1, 0.3, -0.2), "为什么": (0.0, 0.3, -0.1),
        "想到": (0.1, 0.3, 0.1), "也许": (0.0, 0.2, 0.0),
        # 情感符号
        "！": (0.1, 0.3, 0.0), "？": (0.0, 0.2, -0.1), "...": (-0.1, -0.1, -0.1),
    }

    @classmethod
    def extract(cls, text: str) -> EmotionState:
        """从文本提取情绪向量"""
        if not text:
            return EmotionState()

        valence, arousal, dominance = 0.0, 0.0, 0.0
        count = 0

        for word, (v, a, d) in cls.LEXICON.items():
            occurrences = text.count(word)
            if occurrences > 0:
                valence += v * occurrences
                arousal += a * occurrences
                dominance += d * occurrences
                count += occurrences

        if count == 0:
            return EmotionState()

        # 归一化：直接平均，保留更多信号
        return EmotionState(
            valence=max(-1.0, min(1.0, valence / count)),
            arousal=max(-1.0, min(1.0, arousal / count)),
            dominance=max(-1.0, min(1.0, dominance / count)),
        )


class EmotionEngine:
    """
    情绪引擎 — 管理系统情绪状态

    - 维护当前情绪基座
    - 从交互中更新情绪
    - 自然衰减到中性
    - 对外提供情绪影响因子
    """

    def __init__(self, decay_rate: float = 0.98):
        self.state = EmotionState()
        self.decay_rate = decay_rate
        self.history: list[dict] = []
        self._last_update = time.time()

    def update_from_text(self, text: str, blend_weight: float = 0.3):
        """从文本输入更新情绪"""
        extracted = EmotionExtractor.extract(text)
        self.state = self.state.blend(extracted, blend_weight)
        self._decay()
        self._record("text_input", extracted)

    def set_emotion(self, emotion: EmotionState, blend_weight: float = 0.5):
        """直接设置/混合情绪"""
        self.state = self.state.blend(emotion, blend_weight)
        self._record("direct_set", emotion)

    def get_influence(self) -> dict:
        """
        获取情绪对各层的影响因子

        返回值用于调制其他层的行为
        """
        v, a, d = self.state.valence, self.state.arousal, self.state.dominance

        return {
            # 对记忆层的影响
            "memory_encoding_boost": 1.0 + abs(a) * 0.5,       # 高唤醒 → 编码增强
            "memory_recall_bias": v,                              # 效价 → 回忆偏向
            # 对思考层的影响
            "thinking_strategy": "exploratory" if v > 0.2 else ("cautious" if v < -0.2 else "neutral"),
            "thinking_speed": 0.5 + (a + 1) / 2,                 # 唤醒 → 思考速度
            # 对潜意识层的影响
            "subconscious_activity": 0.5 + (a + 1) / 2 * 0.5,   # 高唤醒 → 活跃
            "subconscious_risk_taking": d,                        # 支配 → 冒险倾向
            # 当前情绪状态
            "state": self.state.to_dict(),
            "label": self.state.label,
            "intensity": self.state.intensity,
        }

    def _decay(self):
        """情绪自然衰减到中性"""
        now = time.time()
        elapsed = now - self._last_update
        # 每秒应用一次衰减
        decay_factor = self.decay_rate ** elapsed
        self.state = EmotionState(
            valence=self.state.valence * decay_factor,
            arousal=self.state.arousal * decay_factor,
            dominance=self.state.dominance * decay_factor,
        )
        self._last_update = now

    def _record(self, source: str, trigger: EmotionState):
        """记录情绪变化"""
        self.history.append({
            "time": time.time(),
            "source": source,
            "trigger": trigger.to_dict(),
            "result": self.state.to_dict(),
        })
        # 只保留最近100条
        if len(self.history) > 100:
            self.history = self.history[-100:]
