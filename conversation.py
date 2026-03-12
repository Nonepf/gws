#!/usr/bin/env python3
"""
GWS 对话接口 — 与 GWS 系统进行自然语言对话

用法：
    python3 gws/conversation.py              # 交互模式
    python3 gws/conversation.py "你的消息"   # 单次对话
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.gws import GWS


def load_gws() -> GWS:
    """加载 GWS 实例"""
    gws_data = Path(__file__).parent / "data"
    llm_config_path = Path(__file__).parent / "config" / "llm.json"

    gws = GWS(workspace_dir=str(gws_data))

    if llm_config_path.exists():
        llm_cfg = json.loads(llm_config_path.read_text())
        gws.enable_llm(
            provider=llm_cfg.get("provider", "openrouter"),
            api_key=llm_cfg.get("api_key", ""),
            model=llm_cfg.get("model", ""),
        )

    gws.start()
    return gws


def chat_once(gws: GWS, message: str) -> str:
    """单次对话"""
    # 推进系统
    gws.tick()

    # 语言层回应
    if gws.language_layer:
        return gws.speak(message)
    else:
        # 无 LLM 时的回退
        result = gws.on_input(message)
        gws.tick()
        conscious = gws.get_output()
        if conscious:
            lines = [item["content"] for item in conscious]
            return "\n".join(lines)
        return f"[情绪: {result['emotion_label']}] 收到了，但语言层未启用。"


def main():
    gws = load_gws()

    if len(sys.argv) > 1:
        # 单次模式
        message = " ".join(sys.argv[1:])
        print(chat_once(gws, message))
    else:
        # 交互模式
        print("🌳 GWS 对话系统 (输入 'quit' 退出, 'status' 查看状态)")
        print("-" * 50)

        while True:
            try:
                user_input = input("\n你: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if user_input.lower() == "status":
                print(json.dumps(gws.get_status(), ensure_ascii=False, indent=2))
                continue

            response = chat_once(gws, user_input)
            print(f"\n🌳 {response}")

        print("\n再见 👋")


if __name__ == "__main__":
    main()
