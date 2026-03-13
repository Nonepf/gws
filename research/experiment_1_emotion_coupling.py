#!/usr/bin/env python3
"""
实验 1: 情绪-决策耦合度测量

目的: 量化情绪对 GWS 各层决策的实际影响

方法:
1. 给系统输入不同情绪色彩的文本
2. 记录潜意识角色分配、工作空间筛选、语言层输出
3. 计算情绪状态与行为的相关性

用法: python3 experiment_1_emotion_coupling.py
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "gws"))

from core.emotion import EmotionEngine, EmotionExtractor
from core.memory import LongTermMemory, MemoryType, EmotionState as MemEmotion, MemoryEntry
from core.subconscious import SubconsciousLayer
from core.workspace import GlobalWorkspace


# === 测试输入：同一话题，不同情绪 ===

TEST_INPUTS = {
    "positive_high": [
        "太棒了！这个想法简直天才！我们一定要马上试试看！",
        "兴奋得不行，今天发现了超级酷的东西！",
        "完美！这正是我一直想要的解决方案！",
    ],
    "positive_low": [
        "嗯，这个想法挺有意思的，值得慢慢想想。",
        "还不错，平静地接受这个结果。",
        "挺好的，没什么特别激动的，但感觉踏实。",
    ],
    "negative_high": [
        "完了完了，这下出大问题了！搞不好整个系统都崩了！",
        "焦虑得不行，总觉得哪里会出问题！",
        "太糟糕了，一切都乱套了！",
    ],
    "negative_low": [
        "唉，又失败了。算了，无所谓了。",
        "有点难过，但说不上来为什么。",
        "累了，不想再想了。",
    ],
    "neutral": [
        "今天天气不错，适合做点研究。",
        "这个算法的时间复杂度是 O(n log n)。",
        "需要检查一下系统日志。",
    ],
}


def run_experiment():
    print("=" * 70)
    print("  实验 1: 情绪-决策耦合度测量")
    print("=" * 70)
    print()

    results = {}

    for emotion_group, inputs in TEST_INPUTS.items():
        print(f"\n{'─' * 50}")
        print(f"  测试组: {emotion_group}")
        print(f"{'─' * 50}")

        group_results = []

        for text in inputs:
            # === 初始化各层 ===
            data_dir = Path("/tmp/gws_experiment_1") / emotion_group
            data_dir.mkdir(parents=True, exist_ok=True)

            emotion_engine = EmotionEngine()
            ltm = LongTermMemory(data_dir / "long_term")

            # 预填充一些记忆
            _seed_memories(ltm)

            subconscious = SubconsciousLayer(
                memory=ltm,
                emotion_engine=emotion_engine,
                cycle_seconds=60,
                burst_agents=4,
                burst_duration=30,
            )

            workspace = GlobalWorkspace(
                memory=ltm,
                emotion_engine=emotion_engine,
                capacity=5,
                promotion_threshold=0.5,
            )

            # === 处理输入 ===
            # 1. 情绪提取
            extracted = EmotionExtractor.extract(text)
            emotion_engine.update_from_text(text)

            # 2. 潜意识活动（tick 会自动启动周期并执行 burst）
            sc_outputs = subconscious.tick() or []
            # 取出产出队列中的内容
            sc_outputs = subconscious.drain_outputs()

            # 3. 工作空间处理
            workspace.receive(sc_outputs)
            conscious = workspace.think()

            # === 收集结果 ===
            result = {
                "input": text[:30],
                "emotion_state": {
                    "valence": round(emotion_engine.state.valence, 3),
                    "arousal": round(emotion_engine.state.arousal, 3),
                    "dominance": round(emotion_engine.state.dominance, 3),
                    "label": emotion_engine.state.label,
                    "intensity": round(emotion_engine.state.intensity, 3),
                },
                "extracted_emotion": {
                    "valence": round(extracted.valence, 3),
                    "arousal": round(extracted.arousal, 3),
                },
                "subconscious_roles": [o.agent_role.value for o in sc_outputs],
                "subconscious_confidence": [round(o.confidence, 3) for o in sc_outputs],
                "subconscious_count": len(sc_outputs),
                "conscious_promoted": len(conscious),
                "conscious_contents": [c.get("content", "")[:50] for c in conscious],
                "influence": {
                    "strategy": emotion_engine.get_influence()["thinking_strategy"],
                    "memory_boost": round(emotion_engine.get_influence()["memory_encoding_boost"], 3),
                    "sub_activity": round(emotion_engine.get_influence()["subconscious_activity"], 3),
                    "risk_taking": round(emotion_engine.get_influence()["subconscious_risk_taking"], 3),
                },
            }
            group_results.append(result)

            # 打印简要
            print(f"\n  输入: {text[:40]}...")
            print(f"  情绪: {result['emotion_state']['label']} "
                  f"(V={result['emotion_state']['valence']:.2f}, "
                  f"A={result['emotion_state']['arousal']:.2f}, "
                  f"D={result['emotion_state']['dominance']:.2f})")
            print(f"  潜意识: {result['subconscious_roles']}")
            print(f"  意识提升: {result['conscious_promoted']} 条")
            print(f"  思考策略: {result['influence']['strategy']}")

        results[emotion_group] = group_results

    # === 跨组对比分析 ===
    print(f"\n\n{'=' * 70}")
    print("  跨组对比分析")
    print(f"{'=' * 70}\n")

    for group, data in results.items():
        avg_valence = sum(r["emotion_state"]["valence"] for r in data) / len(data)
        avg_arousal = sum(r["emotion_state"]["arousal"] for r in data) / len(data)
        avg_intensity = sum(r["emotion_state"]["intensity"] for r in data) / len(data)
        avg_sc_count = sum(r["subconscious_count"] for r in data) / len(data)
        avg_conscious = sum(r["conscious_promoted"] for r in data) / len(data)
        strategies = set(r["influence"]["strategy"] for r in data)
        roles_used = set()
        for r in data:
            roles_used.update(r["subconscious_roles"])

        print(f"  {group}:")
        print(f"    平均情绪: V={avg_valence:.3f}, A={avg_arousal:.3f}, 强度={avg_intensity:.3f}")
        print(f"    潜意识产出: {avg_sc_count:.1f} 条/轮")
        print(f"    意识提升: {avg_conscious:.1f} 条/轮")
        print(f"    思考策略: {strategies}")
        print(f"    使用的角色: {roles_used}")
        print()

    # === 耦合度计算 ===
    print(f"{'=' * 70}")
    print("  耦合度分析")
    print(f"{'=' * 70}\n")

    # 计算不同情绪组之间的行为差异
    groups = list(results.keys())
    for i, g1 in enumerate(groups):
        for g2 in groups[i+1:]:
            roles1 = set()
            for r in results[g1]:
                roles1.update(r["subconscious_roles"])
            roles2 = set()
            for r in results[g2]:
                roles2.update(r["subconscious_roles"])

            strat1 = set(r["influence"]["strategy"] for r in results[g1])
            strat2 = set(r["influence"]["strategy"] for r in results[g2])

            role_diff = len(roles1.symmetric_difference(roles2))
            strat_diff = len(strat1.symmetric_difference(strat2))

            print(f"  {g1} vs {g2}:")
            print(f"    角色差异: {role_diff} 个不同角色")
            print(f"    策略差异: {strat_diff} 个不同策略")

    # 保存详细结果
    output_path = Path("/home/nonepf/.openclaw/workspace/research/experiment_1_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  详细结果已保存: {output_path}")


def _seed_memories(ltm: LongTermMemory):
    """预填充一些测试记忆"""
    seed_texts = [
        "分布式系统的设计需要考虑一致性问题",
        "树的根系通过真菌网络互相通信",
        "情绪在认知中扮演重要角色",
        "遗忘是一种美德",
        "AI 系统需要更多自主性",
    ]
    for text in seed_texts:
        ltm.encode(
            content=text,
            memory_type=MemoryType.EPISODIC,
            emotion=MemEmotion(0.1, 0.2, 0.1),
            tags=["seed"],
            source="experiment",
        )


if __name__ == "__main__":
    run_experiment()
