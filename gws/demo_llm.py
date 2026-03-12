#!/usr/bin/env python3
"""
GWS LLM 驱动 Demo — 接入外部 LLM 的完整认知系统

对比 demo.py：
- 情绪提取用 LLM（不是规则词典）
- 语言层用 LLM 输出自然语言
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.gws import GWS


def divider(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    divider("🌳 GWS — LLM 驱动 Demo")

    # === 初始化 ===
    demo_data = Path(__file__).parent / "demo_llm_data"
    if demo_data.exists():
        import shutil
        shutil.rmtree(demo_data)

    gws = GWS(
        workspace_dir=str(demo_data),
        cycle_seconds=30,
        burst_duration=10,
    )

    # 启用 LLM（从配置文件读取 key）
    import json as _json
    _cfg = _json.loads((Path(__file__).parent / "config" / "llm.json").read_text())
    gws.enable_llm(provider=_cfg["provider"], api_key=_cfg["api_key"], model=_cfg["model"])
    gws.start()
    print("✅ 系统启动，LLM 已连接")

    # === 1. LLM 情绪提取 ===
    divider("🎭 阶段一：LLM 情绪提取")

    test_texts = [
        "今天学到了一个很酷的东西！太开心了",
        "我有点担心这个方案会不会出问题",
        "算了不管了，先试试看吧！这个方向很有意思",
        "好累……什么都不想做",
    ]

    for text in test_texts:
        emotion = gws.llm_emotion_extractor.extract(text)
        print(f"\n📝 \"{text}\"")
        print(f"   PAD: val={emotion.valence:.2f} aro={emotion.arousal:.2f} dom={emotion.dominance:.2f}")
        print(f"   情绪: {emotion.label}")

    # === 2. 对话 + 情绪累积 ===
    divider("💬 阶段二：对话")

    conversations = [
        "你好！我今天发现了一个超酷的现象——树的根系通过真菌网络互相通信！",
        "我在想能不能把这种机制用到分布式AI系统里",
        "不过有点担心太复杂了，怕搞砸",
    ]

    for msg in conversations:
        print(f"\n🗣️ 用户: {msg}")
        result = gws.on_input(msg)
        print(f"   情绪: {result['emotion_label']} (val={gws.emotion_engine.state.valence:.2f}, aro={gws.emotion_engine.state.arousal:.2f})")

    # === 3. 推进系统 ===
    divider("🌊 阶段三：潜意识 + 思考")

    for i in range(3):
        result = gws.tick()
        if result["new_conscious"] > 0:
            print(f"\n⏰ Tick {i+1}: {result['new_conscious']} 条进入意识")

    # === 4. 语言层表达 ===
    divider("🗣️ 阶段四：语言层表达")

    print("\n【系统自发思考】")
    spoken = gws.speak()
    print(f"  {spoken}")

    # === 5. 与系统对话 ===
    divider("🤖 阶段五：与 GWS 对话")

    questions = [
        "你刚才在想什么？",
        "那个真菌网络的想法，你怎么看？",
    ]

    for q in questions:
        print(f"\n👤 Nonepf: {q}")
        response = gws.speak(q)
        print(f"🌳 栖云木: {response}")

    # === 6. 系统状态 ===
    divider("📊 系统状态")
    print(json.dumps(gws.get_status(), ensure_ascii=False, indent=2))

    divider("✅ LLM Demo 完成")


if __name__ == "__main__":
    main()
