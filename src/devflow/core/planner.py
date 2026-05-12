"""基础规划器 — 任务 → 步骤拆解

Week 1 简化版：使用 LLM 将自然语言任务拆解为可执行步骤。
"""

from dataclasses import dataclass, field
from enum import Enum


class StepType(str, Enum):
    READ = "read"
    WRITE = "write"
    VERIFY = "verify"


@dataclass
class Step:
    """单个执行步骤"""
    index: int
    type: StepType
    description: str
    expected_output: str = ""


@dataclass
class Plan:
    """执行计划"""
    task: str
    steps: list[Step]
    dependencies: dict[int, list[int]] = field(default_factory=dict)


class Planner:
    """基础规划器 — 用 LLM 拆解任务"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def plan(self, task: str, project_context: str = "") -> Plan:
        """将任务拆解为步骤列表"""
        messages = [
            {
                "role": "system",
                "content": self._system_prompt(project_context),
            },
            {
                "role": "user",
                "content": f"请将以下任务拆解为可执行步骤：\n\n{task}",
            },
        ]
        response = self.llm.chat_for_planning(messages)

        # 从 LLM 响应中解析步骤（简化版：按数字序号分割）
        steps = self._parse_steps(response.get("choices", [{}])[0]
                                  .get("message", {}).get("content", ""))
        return Plan(task=task, steps=steps)

    def _system_prompt(self, project_context: str) -> str:
        return f"""你是一个资深的软件工程师。将编程任务拆解为具体可执行的步骤。

## 项目上下文
{project_context if project_context else "（无项目上下文）"}

## 步骤类型
- read: 读取/分析现有代码
- write: 创建或修改代码文件
- verify: 验证修改是否正确（运行测试/lint/curl）

## 要求
1. 最后一步必须是 verify 类型
2. 每个步骤只做一件事
3. 用明确的文件路径
4. 返回格式：
1. [read] 读取 src/api/__init__.py 了解路由结构
2. [write] 创建 src/api/health.py 实现健康检查端点
3. [write] 修改 src/api/__init__.py 注册路由
4. [verify] 运行 curl 验证端点
"""

    def _parse_steps(self, text: str) -> list[Step]:
        """从 LLM 响应中解析步骤列表"""
        import re

        steps = []
        # 匹配 "1. [type] description" 格式
        pattern = re.compile(r'(\d+)\s*[\.\)]\s*\[(\w+)\]\s*(.+)', re.IGNORECASE)
        matches = pattern.findall(text)

        for num, stype, desc in matches:
            try:
                step_type = StepType(stype.lower())
            except ValueError:
                step_type = StepType.WRITE  # 未知类型默认 WRITE

            steps.append(Step(
                index=int(num),
                type=step_type,
                description=desc.strip(),
            ))

        if not steps:
            # 如果没有解析到结构化步骤，创建单个 WRITE 步骤
            steps.append(Step(
                index=1,
                type=StepType.WRITE,
                description=text[:500],
            ))

        return steps
