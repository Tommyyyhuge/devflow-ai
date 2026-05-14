"""技能接口协议"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Skill(Protocol):
    """技能接口协议"""
    name: str
    description: str
    version: str
    author: str
    tags: list[str]
    
    def execute(self, context: dict) -> str:
        """执行技能"""
        ...
    
    def validate(self) -> bool:
        """验证技能配置"""
        ...
