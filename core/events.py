"""
AWARE 事件总线 — 异步认知架构的核心通信机制

所有层通过事件总线通信，而非直接方法调用。
支持同步和异步事件处理。
"""

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Any


class EventType(Enum):
    """系统事件类型"""
    # 输入事件
    USER_INPUT = "user_input"
    INTERNAL_TRIGGER = "internal_trigger"
    
    # 潜意识事件
    SUBCONSCIOUS_OUTPUT = "subconscious_output"
    SUBCONSCIOUS_CYCLE_START = "subconscious_cycle_start"
    SUBCONSCIOUS_CYCLE_END = "subconscious_cycle_end"
    
    # 黑板事件
    BLACKBOARD_UPDATED = "blackboard_updated"
    INSPIRATION_ADDED = "inspiration_added"
    
    # 思考层事件
    THOUGHT_PRODUCED = "thought_produced"
    EVALUATION_COMPLETE = "evaluation_complete"
    
    # 意图事件
    INTENTION_GENERATED = "intention_generated"
    INTENTION_COMPLETED = "intention_completed"
    
    # 情绪事件
    EMOTION_CHANGED = "emotion_changed"
    
    # 内驱力事件
    DRIVE_THRESHOLD_CROSSED = "drive_threshold_crossed"
    
    # 语言/输出事件
    EXPRESSION_READY = "expression_ready"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END = "stream_end"
    
    # 主动交互事件
    URGE_TO_SPEAK_CHANGED = "urge_to_speak_changed"
    PROACTIVE_SPEECH_TRIGGERED = "proactive_speech_triggered"
    
    # 系统事件
    SYSTEM_TICK = "system_tick"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"


@dataclass
class Event:
    """系统事件"""
    type: EventType
    data: dict = field(default_factory=dict)
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp,
        }


# 类型别名
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]


class EventBus:
    """
    事件总线 — 支持同步和异步订阅
    
    所有系统组件通过事件总线通信，
    实现松耦合的异步认知架构。
    """
    
    def __init__(self):
        # 同步处理器
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        # 异步处理器
        self._async_handlers: dict[EventType, list[AsyncEventHandler]] = defaultdict(list)
        # 通配符处理器（接收所有事件）
        self._wildcard_handlers: list[EventHandler] = []
        # 事件历史（最近 N 条）
        self._history: list[Event] = []
        self._max_history = 200
        # 统计
        self._stats: dict[str, int] = defaultdict(int)
    
    def subscribe(self, event_type: EventType, handler: EventHandler):
        """订阅特定类型的事件（同步）"""
        self._handlers[event_type].append(handler)
    
    def subscribe_all(self, handler: EventHandler):
        """订阅所有事件"""
        self._wildcard_handlers.append(handler)
    
    def subscribe_async(self, event_type: EventType, handler: AsyncEventHandler):
        """订阅异步事件"""
        self._async_handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        """取消订阅"""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
    
    def emit(self, event: Event):
        """发射事件（同步）"""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        
        self._stats[event.type.value] += 1
        
        # 通配符处理器
        for handler in self._wildcard_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus] Wildcard handler error: {e}")
        
        # 类型特定处理器
        for handler in self._handlers.get(event.type, []):
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus] Handler error for {event.type.value}: {e}")
    
    async def emit_async(self, event: Event):
        """发射事件（异步）"""
        # 先同步处理
        self.emit(event)
        
        # 再异步处理
        for handler in self._async_handlers.get(event.type, []):
            try:
                await handler(event)
            except Exception as e:
                print(f"[EventBus] Async handler error for {event.type.value}: {e}")
    
    def get_history(self, event_type: Optional[EventType] = None, limit: int = 50) -> list[Event]:
        """获取事件历史"""
        if event_type:
            filtered = [e for e in self._history if e.type == event_type]
            return filtered[-limit:]
        return self._history[-limit:]
    
    def get_stats(self) -> dict:
        return dict(self._stats)
    
    def clear_history(self):
        self._history.clear()
