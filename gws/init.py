#!/usr/bin/env python3
"""
GWS 初始化 — 建立记忆层，导入现有记忆
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.memory import LongTermMemory, EmotionState, MemoryType
from core.bridge import OpenClawBridge

WORKSPACE = Path(__file__).parent.parent
GWS_DATA = Path(__file__).parent / "data"

def main():
    print("🌳 GWS 初始化...")
    print(f"   工作空间: {WORKSPACE}")
    print(f"   数据目录: {GWS_DATA}")

    # 创建长期记忆
    ltm = LongTermMemory(GWS_DATA / "long_term")
    print(f"   长期记忆: {ltm.stats()}")

    # 桥接 OpenClaw
    bridge = OpenClawBridge(WORKSPACE, ltm)

    # 导入今天的笔记
    count = bridge.import_daily_notes()
    print(f"   导入今日笔记: {count} 条新记忆")

    # 写入一条种子记忆
    seed = ltm.encode(
        content="GWS（Global Workspace System）项目启动。目标：构建一个有潜意识、思考层、情绪层的 AI 认知架构。记忆层是地基。",
        memory_type=MemoryType.EPISODIC,
        emotion=EmotionState(valence=0.7, arousal=0.6, dominance=0.3),
        tags=["gws", "项目", "启动"],
        source="init",
    )
    print(f"   种子记忆: {seed.id} — {seed.content[:40]}...")

    print(f"\n   记忆统计: {ltm.stats()}")
    print("✅ GWS 记忆层已就绪")

if __name__ == "__main__":
    main()
