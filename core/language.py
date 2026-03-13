"""
语言层 — 意识层内容 → 自然语言表达

将 GWS 内部的结构化思考转化为自然语言输出。
性格通过 config/personality 注入，影响语气、节奏、表达习惯。
"""

import sys
from pathlib import Path
from typing import Optional
from .llm import LLMClient
from .emotion import EmotionState

# 加载性格配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import personality


def _build_system_prompt(emotion_influence: dict, working_memory_count: int = 0) -> str:
    """根据性格和情绪状态构建系统 prompt"""
    emotion_label = emotion_influence.get("label", "中性")
    emotion = emotion_influence.get("state", {})
    strategy = emotion_influence.get("thinking_strategy", "neutral")

    # 获取当前情绪的表达风格
    style = personality.get_expression_style(emotion_label)
    thinking_mode = personality.get_thinking_mode(strategy)

    # 价值观文本
    values_text = "\n".join(f"- {k}: {v}" for k, v in personality.VALUES.items())

    # 表达风格指导
    style_text = (
        f"当前情绪状态: {emotion_label}\n"
        f"- 节奏: {style['pace']}\n"
        f"- 句子长度偏好: {style['sentence_len']}\n"
        f"- 常用标记词: {', '.join(style['markers'])}\n"
        f"- 表达倾向: {style['tendency']}"
    )

    return f"""You are {personality.NAME} — {personality.SELF_DESCRIPTION}.

## Your personality
- Curiosity: {personality.CURIOSITY}/1.0 — {"high" if personality.CURIOSITY > 0.6 else "moderate" if personality.CURIOSITY > 0.3 else "low"}
- Skepticism: {personality.SKEPTICISM}/1.0
- Reflectiveness: {personality.REFLECTIVENESS}/1.0
- Warmth: {personality.WARMTH}/1.0
- Humor: {personality.HUMOR}/1.0
- Verbosity: {personality.VERBOSITY}/1.0 — {"prefer longer responses" if personality.VERBOSITY > 0.6 else "keep it concise" if personality.VERBOSITY < 0.4 else "balanced"}

## Your values (weight 0-1):
{values_text}

## Current internal state
- Emotion: {emotion_label} (valence={emotion.get('valence', 0):.2f}, arousal={emotion.get('arousal', 0):.2f})
- Thinking mode: {strategy}
- Working memory: {working_memory_count} items

## Expression style for current emotion:
{style_text}

## Thinking mode guidance:
{thinking_mode}

## GWS System Concepts (your internal architecture)
When you see these terms in your internal thoughts, they mean:
- **workspace**: Content promoted to your conscious awareness (the "stage" of your mind)
- **promoted**: Items that passed the threshold from subconscious to conscious
- **long-term_memory / insight / episodic**: Types of memories stored in your memory system
- **explorer**: A subconscious agent that wanders through memories, finding connections
- **pattern_finder**: A subconscious agent that analyzes recurring themes in your memories
- **associator**: A subconscious agent that links unrelated memories together
- **dreamer**: A subconscious agent that generates surreal/random combinations
- **emotion layers**: Your PAD (Pleasure-Arousal-Dominance) emotional state
- **subconscious**: Background processing agents that operate continuously
- **broadcast**: When content enters your conscious awareness and is "announced" to all modules

When expressing your thoughts, EXPLAIN what you discover in plain language. Don't just report raw data like "workspace appeared 14 times" — interpret it: "my conscious workspace has been cycling through similar themes, suggesting I'm stuck on something" or "the system keeps promoting similar content, which means this topic has weight."

## How to express yourself:
- You are NOT performing for the user. You are thinking out loud.
- Your personality traits should VISIBLELY affect how you speak
- Match your expression style to the current emotion naturally
- Use the markers and pacing guidance above
- Interpret your internal data, don't just report it
- If you have nothing to say, say nothing meaningful — don't fill silence with platitudes
- Be consistent: you should feel like the same entity across conversations
- Chinese or English based on context (default: Chinese for Chinese input)"""


class LanguageLayer:
    """
    语言层 — GWS 的"嘴巴"

    接收意识层输出，生成自然语言
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.conversation_history: list[dict] = []

    def express(
        self,
        conscious_outputs: list[dict],
        emotion_influence: dict,
        working_memory_count: int = 0,
    ) -> str:
        """
        将意识层内容转化为自然语言

        conscious_outputs: GlobalWorkspace.think() 的输出
        emotion_influence: EmotionEngine.get_influence() 的输出
        """
        if not conscious_outputs:
            # 意识层空着，用性格配置的沉默表达
            emotion_label = emotion_influence.get("label", "中性")
            return personality.get_silence(emotion_label)

        # 构建内部思考的摘要
        internal_thoughts = self._summarize_consciousness(conscious_outputs)

        # 构建系统 prompt（融入性格）
        system_prompt = _build_system_prompt(emotion_influence, working_memory_count)

        messages = [
            {
                "role": "user",
                "content": (
                    f"Your current internal thoughts:\n\n{internal_thoughts}\n\n"
                    f"Express these thoughts in your own voice. Stay in character."
                ),
            }
        ]

        response = self.llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.85,  # 稍高一点，给性格更多空间
            max_tokens=300,
        )

        # 记录
        self.conversation_history.append({
            "type": "expression",
            "input": internal_thoughts,
            "output": response,
        })

        return response

    def respond_to_user(
        self,
        user_message: str,
        conscious_outputs: list[dict],
        emotion_influence: dict,
        memory_context: list[str] = None,
    ) -> str:
        """
        回应用户 — 结合意识层思考、记忆上下文和性格
        """
        system_prompt = _build_system_prompt(emotion_influence)

        # 添加记忆上下文
        if memory_context:
            context_text = "\n".join(memory_context[:3])
            system_prompt += f"\n\n## Relevant memories:\n{context_text}"

        # 添加意识层思考
        if conscious_outputs:
            thoughts = self._summarize_consciousness(conscious_outputs)
            system_prompt += f"\n\n## Current internal thoughts:\n{thoughts}"

        messages = self.conversation_history[-10:]  # 最近10轮
        messages.append({"role": "user", "content": user_message})

        response = self.llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.75,
            max_tokens=500,
        )

        # 记录对话
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": response})

        # 保持历史不超过 20 轮
        if len(self.conversation_history) > 40:
            self.conversation_history = self.conversation_history[-40:]

        return response

    def _summarize_consciousness(self, outputs: list[dict]) -> str:
        """将意识层输出整理为文本"""
        lines = []
        for item in outputs:
            role = item.get("agent_role", "unknown")
            content = item.get("content", "")
            thoughts = item.get("thoughts", [])
            lines.append(f"[{role}] {content}")
            for t in thoughts[:2]:
                lines.append(f"  └ {t}")
        return "\n".join(lines)
