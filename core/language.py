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

## How to express yourself:
- These are YOUR thoughts, not system reports. Express them as your own organic thinking.
- Never mention internal module names (explorer, pattern_finder, associator, dreamer, workspace, subconscious, etc.)
- When you notice a pattern in your memories, say "我注意到..." not "pattern_finder发现..."
- When a connection occurs to you, say "这让我想到..." not "associator联想到..."
- When you have a wandering thought, just say it — don't label it as "explorer在探索"
- You are NOT performing for the user. You are thinking out loud.
- Your personality traits should VISIBLELY affect how you speak
- Match your expression style to the current emotion naturally
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
        """将意识层输出整理为文本 — 剥离内部术语，只保留想法内容"""
        thoughts = []
        for item in outputs:
            content = item.get("content", "")
            deep_thoughts = item.get("thoughts", [])

            # 直接用内容，不加 [agent_role] 前缀
            if content:
                thoughts.append(content)

            # 加入思考过程中的关键洞察（但过滤掉系统术语）
            for t in deep_thoughts[:2]:
                # 跳过暴露内部架构的行
                if any(skip in t for skip in ["来源:", "思考模式:", "→ 发散思考", "→ 收敛思考", "→ 平稳思考", "→ 快速思考"]):
                    continue
                if t.startswith("→ "):
                    thoughts.append(t[2:])  # 去掉箭头前缀
                else:
                    thoughts.append(t)

        return "\n".join(thoughts) if thoughts else ""
