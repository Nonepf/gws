"""
桥接模块 — GWS 记忆层 ↔ OpenClaw Memory

让 GWS 可以读取和写入 OpenClaw 的 memory 文件，
同时保持自己更丰富的结构化记忆。
"""

import json
from datetime import datetime
from pathlib import Path

from .memory import EmotionState, LongTermMemory, MemoryType


class OpenClawBridge:
    """连接 GWS 和 OpenClaw 的记忆系统"""

    def __init__(self, workspace: Path, ltm: LongTermMemory):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_file = workspace / "MEMORY.md"
        self.ltm = ltm

    def import_daily_notes(self, date: str = None):
        """
        从 OpenClaw 的每日笔记导入记忆

        date: YYYY-MM-DD 格式，默认今天
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        daily_file = self.memory_dir / f"{date}.md"
        if not daily_file.exists():
            return 0

        content = daily_file.read_text(encoding="utf-8")
        # 按段落分割作为独立记忆
        blocks = [b.strip() for b in content.split("\n\n") if b.strip() and not b.strip().startswith("#")]

        count = 0
        for block in blocks:
            # 跳过太短的
            if len(block) < 10:
                continue
            # 检查是否已导入（简单去重）
            existing = self.ltm.retrieve(query=block[:30])
            if existing:
                continue

            # 简单判断记忆类型
            mem_type = MemoryType.EPISODIC
            if any(kw in block.lower() for kw in ["学到", "发现", "原理", "概念"]):
                mem_type = MemoryType.SEMANTIC
            if any(kw in block.lower() for kw in ["灵感", "想法", "突然想到"]):
                mem_type = MemoryType.INSIGHT

            self.ltm.encode(
                content=block,
                memory_type=mem_type,
                emotion=EmotionState(0.0, 0.0, 0.0),  # 默认中性，后续可由情绪层调整
                tags=["imported", date],
                source="opencclaw-daily",
            )
            count += 1

        return count

    def export_insight(self, content: str, emotion: EmotionState = None):
        """
        将 GWS 产生的洞察写回 OpenClaw 的每日笔记
        """
        date = datetime.now().strftime("%Y-%m-%d")
        daily_file = self.memory_dir / f"{date}.md"

        emotion_str = ""
        if emotion:
            emotion_str = f" [情绪: val={emotion.valence:.1f} aro={emotion.arousal:.1f}]"

        entry = f"\n> 💡 GWS 洞察{emotion_str}\n> {content}\n"

        with open(daily_file, "a", encoding="utf-8") as f:
            f.write(entry)

    def get_recent_context(self, days: int = 3) -> list[str]:
        """获取最近几天的记忆内容作为上下文"""
        contexts = []
        today = datetime.now()

        for i in range(days):
            date = (today - __import__("datetime").timedelta(days=i)).strftime("%Y-%m-%d")
            daily_file = self.memory_dir / f"{date}.md"
            if daily_file.exists():
                content = daily_file.read_text(encoding="utf-8")
                contexts.append(f"[{date}]\n{content}")

        return contexts
