"""
OpenClaw 适配器 — 将 GWS 连接到 OpenClaw 的能力

映射关系：
- 潜意识 sub-agent → OpenClaw sessions_spawn
- 周期调度 → OpenClaw cron
- 语言层 → OpenClaw LLM session
- 记忆桥接 → OpenClaw memory files
"""

import sys
import json
from pathlib import Path

# GWS 核心
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.gws import GWS


class OpenClawAdapter:
    """
    GWS 在 OpenClaw 上的运行时适配器

    注意：这个适配器只在 OpenClaw 环境内使用。
    GWS 核心本身不依赖它。
    """

    def __init__(self, workspace_dir: str = None):
        if workspace_dir is None:
            workspace_dir = str(Path(__file__).parent.parent / "data")

        self.gws = GWS(workspace_dir)
        self.gws.start()

    def handle_message(self, text: str) -> dict:
        """
        处理来自 OpenClaw 的用户消息

        返回需要表达的内容
        """
        # 1. 让 GWS 处理输入
        input_result = self.gws.on_input(text)

        # 2. 推进系统
        tick_result = self.gws.tick()

        # 3. 获取意识层输出
        output = self.gws.get_output()

        return {
            "input": input_result,
            "tick": tick_result,
            "conscious_output": output,
            "status": self.gws.get_status(),
        }

    def autonomous_tick(self) -> dict:
        """
        自主推进（由 cron 定期调用）

        不需要用户输入，系统自己运行一个周期
        """
        tick_result = self.gws.tick()
        output = self.gws.get_output()

        return {
            "tick": tick_result,
            "conscious_output": output,
        }

    def get_system_prompt_addition(self) -> str:
        """
        生成附加到系统 prompt 的 GWS 状态信息

        让 LLM 语言层能感知内部状态
        """
        status = self.gws.get_status()
        emotion = status["emotion"]

        prompt = f"""
[GWS 内部状态]
情绪: {emotion['label']} (val={emotion['state']['valence']:.2f}, aro={emotion['state']['arousal']:.2f}, dom={emotion['state']['dominance']:.2f})
思考模式: {emotion['thinking_strategy']}
潜意识: {status['subconscious']['phase']}
工作记忆: {status['working_memory']} 条
长期记忆: {status['long_term_memory']['total']} 条
"""
        return prompt.strip()
