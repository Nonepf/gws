"""
LLM 情绪提取器 — 替代规则词典

调用 LLM 从文本中提取 PAD 情绪向量，
比规则词典准确得多，能理解语境和隐含情绪。
"""

import json
from .emotion import EmotionState, EmotionExtractor
from .llm import LLMClient


SYSTEM_PROMPT = """You are an emotion analysis system. Given a text, extract the emotional state using the PAD (Pleasure-Arousal-Dominance) model.

Return ONLY a JSON object with this exact format:
{
  "valence": <float between -1 and 1>,
  "arousal": <float between -1 and 1>,
  "dominance": <float between -1 and 1>
}

Guidelines:
- valence: -1 (very negative) to +1 (very positive)
- arousal: -1 (very calm/sleepy) to +1 (very excited/alert)
- dominance: -1 (helpless/passive) to +1 (in control/dominant)
- Consider context, irony, implicit emotions
- Chinese text is common, analyze accordingly"""


class LLMEmotionExtractor:
    """
    用 LLM 提取情绪 — 比规则词典准确

    用法：
        extractor = LLMEmotionExtractor(llm_client)
        emotion = extractor.extract("今天心情不错，虽然有点累")
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def extract(self, text: str) -> EmotionState:
        """从文本提取 PAD 情绪向量"""
        if not text or len(text.strip()) < 2:
            return EmotionState()

        result = self.llm.chat_json(
            messages=[{"role": "user", "content": f"Analyze the emotion in this text:\n\n{text}"}],
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,
        )

        if "error" in result:
            # LLM 失败，回退到规则词典
            return EmotionExtractor.extract(text)

        try:
            return EmotionState(
                valence=max(-1.0, min(1.0, float(result.get("valence", 0)))),
                arousal=max(-1.0, min(1.0, float(result.get("arousal", 0)))),
                dominance=max(-1.0, min(1.0, float(result.get("dominance", 0)))),
            )
        except (ValueError, TypeError):
            return EmotionExtractor.extract(text)

    def extract_batch(self, texts: list[str]) -> list[EmotionState]:
        """批量提取（可以优化为单次调用）"""
        return [self.extract(t) for t in texts]
