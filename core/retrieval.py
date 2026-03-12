"""
语义检索引擎 — 替代简单字符串匹配

使用 TF-IDF + 余弦相似度实现轻量级语义搜索，
不需要额外依赖或 API 调用。
"""

import math
import re
from collections import Counter
from typing import Optional

from .memory import MemoryEntry, EmotionState


class SemanticRetriever:
    """
    基于 TF-IDF 的语义检索

    特性：
    - 中英文分词（简单版）
    - TF-IDF 加权
    - 余弦相似度排序
    - 情绪偏向调制
    """

    def __init__(self):
        self.idf_cache: dict[str, float] = {}
        self.doc_count: int = 0

    def _tokenize(self, text: str) -> list[str]:
        """简单分词：中文逐字 + 英文按空格"""
        text = text.lower()
        # 提取英文单词
        english_words = re.findall(r'[a-z]+', text)
        # 提取中文字符（作为单字 token）
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        # 提取数字
        numbers = re.findall(r'\d+', text)
        return english_words + chinese_chars + numbers

    def _compute_tf(self, tokens: list[str]) -> dict[str, float]:
        """词频"""
        counts = Counter(tokens)
        total = len(tokens) if tokens else 1
        return {word: count / total for word, count in counts.items()}

    def _compute_idf(self, all_docs: list[list[str]]) -> dict[str, float]:
        """逆文档频率"""
        n = len(all_docs)
        df = Counter()
        for doc in all_docs:
            unique = set(doc)
            for word in unique:
                df[word] += 1
        return {word: math.log(n / (1 + freq)) + 1 for word, freq in df.items()}

    def _cosine_similarity(self, vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
        """余弦相似度"""
        common = set(vec_a.keys()) & set(vec_b.keys())
        if not common:
            return 0.0

        dot = sum(vec_a[w] * vec_b[w] for w in common)
        mag_a = math.sqrt(sum(v**2 for v in vec_a.values())) or 1
        mag_b = math.sqrt(sum(v**2 for v in vec_b.values())) or 1
        return dot / (mag_a * mag_b)

    def index(self, memories: list[MemoryEntry]):
        """建立索引"""
        self.doc_count = len(memories)
        if not memories:
            return

        all_tokens = [self._tokenize(m.content) for m in memories]
        self.idf_cache = self._compute_idf(all_tokens)

    def search(
        self,
        query: str,
        memories: list[MemoryEntry],
        top_k: int = 5,
        emotion_bias: Optional[EmotionState] = None,
    ) -> list[tuple[float, MemoryEntry]]:
        """
        语义搜索

        返回 [(score, memory)] 列表，按分数降序
        """
        if not memories:
            return []

        # 建立索引
        self.index(memories)

        # 查询向量
        query_tokens = self._tokenize(query)
        query_tf = self._compute_tf(query_tokens)
        query_vec = {word: tf * self.idf_cache.get(word, 1.0) for word, tf in query_tf.items()}

        results = []
        for memory in memories:
            # 文档向量
            doc_tokens = self._tokenize(memory.content)
            doc_tf = self._compute_tf(doc_tokens)
            doc_vec = {word: tf * self.idf_cache.get(word, 1.0) for word, tf in doc_tf.items()}

            # 基础相似度
            score = self._cosine_similarity(query_vec, doc_vec)

            # 情绪偏向
            if emotion_bias and memory.emotion:
                e_vec = [memory.emotion.valence, memory.emotion.arousal, memory.emotion.dominance]
                b_vec = [emotion_bias.valence, emotion_bias.arousal, emotion_bias.dominance]
                dot = sum(a * b for a, b in zip(e_vec, b_vec))
                mag_e = math.sqrt(sum(x**2 for x in e_vec)) or 1
                mag_b = math.sqrt(sum(x**2 for x in b_vec)) or 1
                emotion_sim = dot / (mag_e * mag_b)
                score *= 1.0 + emotion_sim * 0.2  # 情绪相似度最高 +20%

            # 强度衰减加权
            score *= memory.strength

            results.append((score, memory))

        results.sort(key=lambda x: x[0], reverse=True)

        # 去重（基于内容前50字符）
        seen = set()
        unique = []
        for score, memory in results:
            key = memory.content[:50]
            if key not in seen:
                seen.add(key)
                unique.append((score, memory))
            if len(unique) >= top_k:
                break

        return unique


# 全局单例
_retriever = SemanticRetriever()


def semantic_search(
    query: str,
    memories: list[MemoryEntry],
    top_k: int = 5,
    emotion_bias: Optional[EmotionState] = None,
) -> list[MemoryEntry]:
    """便捷函数"""
    results = _retriever.search(query, memories, top_k, emotion_bias)
    return [m for _, m in results]
