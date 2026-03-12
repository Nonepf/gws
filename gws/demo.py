#!/usr/bin/env python3
"""
GWS 完整 Demo — 模拟一个认知系统的一天

展示：
1. 系统启动与初始化
2. 用户对话 → 情绪变化 → 记忆编码
3. 潜意识周期活动
4. 思考层筛选与洞察产生
5. 情绪对所有层的影响
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.gws import GWS


def divider(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def show_emotion(gws: GWS):
    """显示当前情绪状态"""
    e = gws.emotion_engine
    state = e.state
    bar_v = "█" * int(abs(state.valence) * 10) + "░" * (10 - int(abs(state.valence) * 10))
    bar_a = "█" * int(abs(state.arousal) * 10) + "░" * (10 - int(abs(state.arousal) * 10))
    sign_v = "+" if state.valence >= 0 else "-"
    sign_a = "+" if state.arousal >= 0 else "-"
    print(f"  情绪: {e.state.label}")
    print(f"    效价 {sign_v}|{bar_v}| {state.valence:.2f}")
    print(f"    唤醒 {sign_a}|{bar_a}| {state.arousal:.2f}")
    print(f"    强度: {state.intensity:.2f}")


def main():
    divider("🌳 GWS — Global Workspace System Demo")

    # === 1. 初始化 ===
    print("\n初始化系统...")
    demo_data = Path(__file__).parent / "demo_data"
    if demo_data.exists():
        import shutil
        shutil.rmtree(demo_data)

    gws = GWS(
        workspace_dir=str(demo_data),
        cycle_seconds=30,       # Demo 用短周期
        burst_duration=10,      # 10秒 burst
        burst_agents=4,
    )
    gws.start()
    print("✅ 系统启动")
    show_emotion(gws)

    # === 2. 用户对话 ===
    divider("💬 阶段一：用户对话")

    conversations = [
        "你好！我今天学到了一个很酷的东西——树的根系其实是通过真菌网络互相通信的！",
        "这让我想到，也许分布式AI系统也可以用类似的方式协调？",
        "不过我也担心这样做会不会太复杂了，搞不好会出问题",
        "算了不管了，先试试看吧！我觉得这个方向很有意思",
    ]

    for i, msg in enumerate(conversations):
        print(f"\n🗣️ 用户: {msg}")
        result = gws.on_input(msg)
        print(f"  → 情绪: {result['emotion_label']} (强度={gws.emotion_engine.state.intensity:.2f})")
        print(f"  → 工作记忆: {result['working_memory_size']} 条")

    show_emotion(gws)

    # === 3. 潜意识活动 ===
    divider("🌊 阶段二：潜意识周期活动")

    print("\n模拟时间推进（潜意识 burst 阶段）...")
    for i in range(3):
        print(f"\n  ⏰ Tick {i+1}")
        result = gws.tick()
        sc = result["subconscious"]
        print(f"    潜意识阶段: {sc['phase']}")
        print(f"    本轮产出: {result['new_conscious']} 条进入意识")

        if result["new_conscious"] > 0:
            conscious = gws.get_output()
            if conscious:
                for item in conscious:
                    print(f"    💡 意识: {item['content'][:80]}")
                    for thought in item.get("thoughts", [])[:3]:
                        print(f"       └─ {thought}")
        time.sleep(1)

    # === 4. 主动思考 ===
    divider("🤔 阶段三：主动思考")

    topics = ["分布式系统", "AI自主性"]
    for topic in topics:
        print(f"\n思考话题: 「{topic}」")
        result = gws.think_about(topic)
        print(f"  找到 {result['memories_found']} 条相关记忆")
        for item in result.get("conscious_output", []):
            print(f"  💭 {item['content'][:80]}")

    # === 5. 系统状态总览 ===
    divider("📊 系统状态总览")

    status = gws.get_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))

    # === 6. 记忆层展示 ===
    divider("🧠 记忆层内容")

    print("\n【长期记忆】")
    all_memories = gws.long_term_memory.retrieve(limit=10)
    for m in all_memories:
        print(f"  [{m.memory_type.value}] {m.content[:60]} (强度: {m.strength:.2f})")

    print(f"\n【记忆统计】")
    stats = gws.long_term_memory.stats()
    print(f"  总计: {stats['total']} 条")
    print(f"  按类型: {stats.get('by_type', {})}")
    print(f"  平均强度: {stats.get('avg_strength', 0):.3f}")

    # === 7. 情绪影响展示 ===
    divider("🎭 情绪对系统的影响")

    influence = gws.emotion_engine.get_influence()
    print(f"  当前情绪: {influence['label']} (强度={influence['intensity']:.2f})")
    print(f"  思考策略: {influence['thinking_strategy']}")
    print(f"  记忆编码增强: {influence['memory_encoding_boost']:.2f}x")
    print(f"  潜意识活跃度: {influence['subconscious_activity']:.2f}")
    print(f"  冒险倾向: {influence['subconscious_risk_taking']:.2f}")

    divider("✅ Demo 完成")
    print("\nGWS 展示了:")
    print("  ✓ PAD 情绪模型 — 从对话中提取情绪，渗透所有层")
    print("  ✓ 记忆层 — 工作记忆(衰减) + 长期记忆(情绪调制)")
    print("  ✓ 潜意识层 — 多 agent 周期活动，探索/联想/做梦")
    print("  ✓ 思考层 — 筛选潜意识产出，提升到意识")
    print("  ✓ 情绪影响 — 调节记忆编码、思考策略、潜意识行为")
    print()


if __name__ == "__main__":
    main()
