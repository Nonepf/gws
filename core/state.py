"""
GWS 状态持久化 — 保存/恢复完整系统状态

解决"重启失忆"问题：
- 情绪状态
- 工作记忆
- 潜意识周期
- 探索历史
- 无聊感
"""

import json
import time
from pathlib import Path
from typing import Optional


class StateManager:
    """管理 GWS 的状态持久化"""

    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = state_dir / "gws_state.json"

    def save(self, gws) -> dict:
        """保存完整系统状态"""
        state = {
            "version": 1,
            "saved_at": time.time(),
            "saved_at_human": time.strftime("%Y-%m-%d %H:%M:%S"),
            
            # 情绪状态
            "emotion": {
                "valence": gws.emotion_engine.state.valence,
                "arousal": gws.emotion_engine.state.arousal,
                "dominance": gws.emotion_engine.state.dominance,
            },
            
            # 工作记忆
            "working_memory": [
                {
                    "id": e.id,
                    "content": e.content,
                    "strength": e.strength,
                    "created_at": e.created_at,
                }
                for e in gws.working_memory.get_all()
            ],
            
            # 潜意识状态
            "subconscious": {
                "phase": gws.subconscious.current_cycle.phase if gws.subconscious.current_cycle else "idle",
                "cycle_id": gws.subconscious.current_cycle.cycle_id if gws.subconscious.current_cycle else None,
                "total_cycles": len(gws.subconscious.cycle_history),
            },
            
            # 计数器
            "counters": {
                "uptime_ticks": gws._tick_count,
                "inputs_processed": gws._input_count,
            },
            
            # 无聊感和探索状态
            "autonomy": getattr(gws, '_autonomy_state', {
                "boredom": 0.0,
                "last_user_interaction": time.time(),
                "last_exploration": None,
                "exploration_count": 0,
            }),
        }
        
        self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        return state

    def load(self) -> Optional[dict]:
        """加载状态"""
        if not self.state_file.exists():
            return None
        try:
            return json.loads(self.state_file.read_text())
        except Exception:
            return None

    def restore(self, gws) -> bool:
        """恢复状态到 GWS 实例"""
        state = self.load()
        if not state:
            return False
        
        try:
            # 恢复情绪
            em = state.get("emotion", {})
            from core.emotion import EmotionState
            gws.emotion_engine.state = EmotionState(
                valence=em.get("valence", 0),
                arousal=em.get("arousal", 0),
                dominance=em.get("dominance", 0),
            )
            
            # 恢复工作记忆
            for item in state.get("working_memory", []):
                from core.memory import MemoryEntry, MemoryType
                entry = MemoryEntry(
                    id=item["id"],
                    content=item["content"],
                    memory_type=MemoryType.EPISODIC,
                    emotion=EmotionState(),
                    created_at=item.get("created_at", time.time()),
                    last_accessed=time.time(),
                    strength=item.get("strength", 0.5),
                )
                gws.working_memory.add(entry)
            
            # 恢复计数器
            counters = state.get("counters", {})
            gws._tick_count = counters.get("uptime_ticks", 0)
            gws._input_count = counters.get("inputs_processed", 0)
            
            # 恢复自主状态
            gws._autonomy_state = state.get("autonomy", {
                "boredom": 0.0,
                "last_user_interaction": time.time(),
                "last_exploration": None,
                "exploration_count": 0,
            })
            
            return True
        except Exception as e:
            print(f"State restore failed: {e}")
            return False

    def exists(self) -> bool:
        return self.state_file.exists()
