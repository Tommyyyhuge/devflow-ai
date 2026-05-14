"""EventBus 测试"""

import pytest
from devflow.core.events import EventBus, EventType


class TestEventBus:
    def test_subscribe_and_emit(self):
        """测试订阅和触发事件"""
        bus = EventBus()
        received = []
        
        def handler(data):
            received.append(data)
        
        bus.on(EventType.LLM_CALL_END, handler)
        bus.emit(EventType.LLM_CALL_END, {"cost": 0.01})
        
        assert len(received) == 1
        assert received[0]["cost"] == 0.01
    
    def test_multiple_handlers(self):
        """测试多个处理器"""
        bus = EventBus()
        results = []
        
        bus.on(EventType.TOOL_EXECUTE, lambda x: results.append("A"))
        bus.on(EventType.TOOL_EXECUTE, lambda x: results.append("B"))
        bus.emit(EventType.TOOL_EXECUTE, {})
        
        assert results == ["A", "B"]
    
    def test_unsubscribe(self):
        """测试取消订阅"""
        bus = EventBus()
        received = []
        
        def handler(data):
            received.append(data)
        
        bus.on(EventType.FILE_CHANGED, handler)
        bus.off(EventType.FILE_CHANGED, handler)
        bus.emit(EventType.FILE_CHANGED, {})
        
        assert len(received) == 0
