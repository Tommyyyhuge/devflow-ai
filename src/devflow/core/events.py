"""轻量级事件总线"""

from enum import Enum, auto
from typing import Callable, Any


class EventType(Enum):
    """事件类型"""
    LLM_CALL_START = auto()
    LLM_CALL_END = auto()
    TOOL_EXECUTE = auto()
    FILE_CHANGED = auto()
    TASK_COMPLETE = auto()


class EventBus:
    """轻量级事件总线（单例模式）"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._listeners: dict[EventType, list[Callable]] = {}
        return cls._instance
    
    def on(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        """订阅事件"""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)
    
    def emit(self, event_type: EventType, data: Any) -> None:
        """触发事件"""
        handlers = self._listeners.get(event_type, [])
        for handler in handlers:
            handler(data)
    
    def off(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        """取消订阅"""
        handlers = self._listeners.get(event_type, [])
        if callback in handlers:
            handlers.remove(callback)
