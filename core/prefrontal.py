"""
前额叶层 — 思维链 (Chain of Thought)

真正的思考不是"筛选然后输出"，而是：
1. 收到多个潜意识产出
2. 在它们之间建立联系
3. 形成连贯的推理链
4. 得出结论或新问题
5. 决定如何表达

这就是前额叶做的事——不是被动过滤，而是主动加工。
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Thought:
    """一个思维节点"""
    id: str
    content: str                    # 思考内容
    source_outputs: list = field(default_factory=list)  # 基于哪些潜意识产出
    thought_type: str = "observe"   # observe → connect → infer → conclude
    confidence: float = 0.5
    timestamp: float = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "thought_type": self.thought_type,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass  
class ThoughtChain:
    """一条完整的思维链"""
    id: str
    trigger: str                     # 什么触发了这条思考
    thoughts: list = field(default_factory=list)  # [Thought, ...]
    conclusion: str = ""
    new_questions: list = field(default_factory=list)
    timestamp: float = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "thoughts": [t.to_dict() for t in self.thoughts],
            "conclusion": self.conclusion,
            "new_questions": self.new_questions,
            "timestamp": self.timestamp,
        }


class PrefrontalCortex:
    """
    前额叶 — 主动思维加工
    
    不只是筛选，而是：
    - 观察潜意识产出
    - 在产出之间找联系
    - 推理和延伸
    - 形成结论
    - 产生新问题
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.thought_history: list[ThoughtChain] = []
        self.current_chain: Optional[ThoughtChain] = None
        self.max_history = 20

    def think(self, subconscious_outputs: list[dict], memory_context: list[str] = None,
              emotion_influence: dict = None) -> Optional[ThoughtChain]:
        """
        对潜意识产出进行思维链加工
        
        流程：观察 → 联系 → 推理 → 结论
        """
        if not subconscious_outputs:
            return None

        chain = ThoughtChain(
            id=str(uuid.uuid4())[:8],
            trigger=subconscious_outputs[0].get("content", "")[:80] if subconscious_outputs else "",
            timestamp=time.time(),
        )

        if self.llm:
            # LLM 驱动的思维链
            chain = self._llm_think(subconscious_outputs, memory_context, emotion_influence)
        else:
            # 离线思维链（基于规则）
            chain = self._offline_think(subconscious_outputs, emotion_influence)

        self.current_chain = chain
        self.thought_history.append(chain)
        if len(self.thought_history) > self.max_history:
            self.thought_history = self.thought_history[-self.max_history:]

        return chain

    def _offline_think(self, outputs: list[dict], emotion: dict) -> ThoughtChain:
        """离线思维链"""
        chain = ThoughtChain(
            id=str(uuid.uuid4())[:8],
            trigger=outputs[0].get("content", "")[:60] if outputs else "",
            timestamp=time.time(),
        )

        # Step 1: 观察每个产出
        for out in outputs:
            content = out.get("content", "")
            role = out.get("agent_role", "unknown")
            t = Thought(
                id=str(uuid.uuid4())[:8],
                content=f"[{role}] {content[:100]}",
                source_outputs=[out.get("id", "")],
                thought_type="observe",
                confidence=out.get("confidence", 0.3),
                timestamp=time.time(),
            )
            chain.thoughts.append(t)

        # Step 2: 尝试联系（如果有多个产出）
        if len(outputs) >= 2:
            roles = [o.get("agent_role", "") for o in outputs]
            contents = [o.get("content", "")[:40] for o in outputs]
            t = Thought(
                id=str(uuid.uuid4())[:8],
                content=f"这些想法之间可能有联系：{', '.join(roles)} 似乎都在指向某个共同的主题",
                thought_type="connect",
                confidence=0.3,
                timestamp=time.time(),
            )
            chain.thoughts.append(t)

        # Step 3: 结论
        if emotion:
            strategy = emotion.get("thinking_strategy", "neutral")
            if strategy == "exploratory":
                chain.conclusion = "值得进一步探索"
            elif strategy == "cautious":
                chain.conclusion = "需要更多证据"
            else:
                chain.conclusion = "继续观察"

        return chain

    def _llm_think(self, outputs: list[dict], memory_context: list[str],
                   emotion: dict) -> ThoughtChain:
        """LLM 驱动的思维链"""
        chain = ThoughtChain(
            id=str(uuid.uuid4())[:8],
            trigger="",
            timestamp=time.time(),
        )

        # 构建思维链 prompt
        outputs_text = "\n".join(
            f"- [{o.get('agent_role', '?')}] {o.get('content', '')[:150]}"
            for o in outputs
        )
        
        memory_text = "\n".join(f"- {m[:100]}" for m in (memory_context or [])[:5])
        if not memory_text:
            memory_text = "(无相关记忆)"

        emotion_text = ""
        if emotion:
            emotion_text = f"当前情绪: {emotion.get('label', '中性')} (策略: {emotion.get('thinking_strategy', 'neutral')})"

        prompt = f"""你是认知系统的前额叶层。你收到了来自潜意识的几个产出，需要将它们加工成连贯的思考。

{emotion_text}

潜意识产出:
{outputs_text}

相关记忆:
{memory_text}

请按以下步骤思考（每步1-2句话）：

1. **观察**：这些产出现在分别说了什么？
2. **联系**：它们之间有什么关联？和记忆有什么关联？
3. **推理**：从这些信息能推导出什么？
4. **结论**：当前最值得关注的是什么？产生了什么新问题？

用自然的内心独白风格，不是报告。简短、直接。"""

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="你是一个思维简洁的思考者。用短句，直接点。中文思考。",
                temperature=0.7,
                max_tokens=400,
            )

            if response:
                chain.conclusion = response[:500]
                chain.trigger = outputs[0].get("content", "")[:80] if outputs else ""

                # 将 LLM 的思考拆分为步骤
                for line in response.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if "观察" in line or "1." in line:
                        chain.thoughts.append(Thought(
                            id=str(uuid.uuid4())[:8], content=line,
                            thought_type="observe", timestamp=time.time(),
                        ))
                    elif "联系" in line or "2." in line:
                        chain.thoughts.append(Thought(
                            id=str(uuid.uuid4())[:8], content=line,
                            thought_type="connect", timestamp=time.time(),
                        ))
                    elif "推理" in line or "3." in line:
                        chain.thoughts.append(Thought(
                            id=str(uuid.uuid4())[:8], content=line,
                            thought_type="infer", timestamp=time.time(),
                        ))
                    elif "结论" in line or "4." in line or "新问题" in line:
                        chain.thoughts.append(Thought(
                            id=str(uuid.uuid4())[:8], content=line,
                            thought_type="conclude", timestamp=time.time(),
                        ))
        except Exception as e:
            chain.conclusion = f"[思考中断: {e}]"

        return chain

    def get_recent_thoughts(self, n: int = 5) -> list[dict]:
        """获取最近的思维链"""
        return [c.to_dict() for c in self.thought_history[-n:]]
