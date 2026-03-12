"""
语言层 — 意识层内容 → 自然语言表达

将 GWS 内部的结构化思考转化为自然语言输出。
这是系统对外的"声音"。
"""

from typing import Optional
from .llm import LLMClient
from .emotion import EmotionState


SYSTEM_PROMPT_TEMPLATE = """You are the language output layer of a cognitive AI system called GWS (Global Workspace System).

Your role: Express the system's internal thoughts naturally. You are NOT the thinker — you are the speaker.

Current internal state:
- Emotion: {emotion_label} (valence={valence:.2f}, arousal={arousal:.2f})
- Thinking mode: {thinking_strategy}
- Working memory: {working_memory_count} items

Guidelines:
- Express thoughts authentically, not performatively
- Reflect the current emotional state in tone
- Don't add your own analysis — just articulate what the system is thinking
- If consciousness is empty, say something brief about being in a quiet state
- Chinese or English based on context"""


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
            # 意识层空着，表达一种安静的状态
            return self._express_silence(emotion_influence)

        # 构建内部思考的摘要
        internal_thoughts = self._summarize_consciousness(conscious_outputs)

        # 构建系统 prompt
        emotion = emotion_influence.get("state", {})
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            emotion_label=emotion_influence.get("label", "中性"),
            valence=emotion.get("valence", 0),
            arousal=emotion.get("arousal", 0),
            thinking_strategy=emotion_influence.get("thinking_strategy", "neutral"),
            working_memory_count=working_memory_count,
        )

        messages = [
            {
                "role": "user",
                "content": (
                    f"Express these internal thoughts naturally:\n\n{internal_thoughts}\n\n"
                    f"Remember: you are articulating the system's thoughts, not adding your own."
                ),
            }
        ]

        response = self.llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.8,
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
        回应用户 — 结合意识层思考和记忆上下文
        """
        emotion = emotion_influence.get("state", {})
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            emotion_label=emotion_influence.get("label", "中性"),
            valence=emotion.get("valence", 0),
            arousal=emotion.get("arousal", 0),
            thinking_strategy=emotion_influence.get("thinking_strategy", "neutral"),
            working_memory_count=0,
        )

        # 添加记忆上下文
        if memory_context:
            context_text = "\n".join(memory_context[:3])
            system_prompt += f"\n\nRelevant memories:\n{context_text}"

        # 添加意识层思考
        if conscious_outputs:
            thoughts = self._summarize_consciousness(conscious_outputs)
            system_prompt += f"\n\nCurrent internal thoughts:\n{thoughts}"

        messages = self.conversation_history[-10:]  # 最近10轮
        messages.append({"role": "user", "content": user_message})

        response = self.llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.7,
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

    def _express_silence(self, emotion_influence: dict) -> str:
        """意识层安静时的表达"""
        label = emotion_influence.get("label", "中性")
        silence_map = {
            "中性": "……",
            "平静": "思绪如水。",
            "放松": "……嗯。",
            "焦虑": "脑子里有点乱……",
            "兴奋": "好像有什么东西要冒出来了……",
            "悲伤": "……",
            "无聊": "……没什么可想的。",
        }
        return silence_map.get(label, "……")
