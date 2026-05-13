"""基础规划器 — 任务 → 步骤拆解

Week 1 简化版：使用 LLM 将自然语言任务拆解为可执行步骤。
Week 2 升级：使用 JSON mode 替代正则解析，更健壮。
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
        """将任务拆解为步骤列表（使用 JSON mode 确保结构化输出）"""
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
        chat_response = self.llm.chat_for_planning(messages)

        # 优先从 JSON 解析，fallback 到正则
        content = chat_response.data.get("choices", [{}])[0].get("message", {}).get("content", "")
        steps = self._parse_steps_json(content)
        if not steps:
            steps = self._parse_steps_legacy(content)

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
4. 返回格式必须是 JSON：

```json
{{
  "steps": [
    {{"index": 1, "type": "read", "description": "读取 src/api/__init__.py 了解路由结构"}},
    {{"index": 2, "type": "write", "description": "创建 src/api/health.py 实现健康检查端点"}},
    {{"index": 3, "type": "write", "description": "修改 src/api/__init__.py 注册路由"}},
    {{"index": 4, "type": "verify", "description": "运行 curl 验证端点返回 status ok"}}
  ]
}}
```
"""

    def _parse_steps_json(self, text: str) -> list[Step]:
        """尝试从 JSON 解析步骤（更健壮）"""
        import json
        import re

        steps = []

        # 提取 JSON 代码块
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

        # 尝试解析 JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "steps" in data:
                for item in data["steps"]:
                    step_type = StepType.WRITE
                    try:
                        step_type = StepType(item.get("type", "write").lower())
                    except ValueError:
                        pass

                    steps.append(Step(
                        index=item.get("index", len(steps) + 1),
                        type=step_type,
                        description=item.get("description", ""),
                        expected_output=item.get("expected_output", ""),
                    ))
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

        return steps

    def _parse_steps_legacy(self, text: str) -> list[Step]:
        """从 LLM 响应中解析步骤列表（fallback：正则解析）"""
        import re

        steps = []
        pattern = re.compile(r'(\d+)\s*[\.\)]\s*\[(\w+)\]\s*(.+)', re.IGNORECASE)
        matches = pattern.findall(text)

        for num, stype, desc in matches:
            try:
                step_type = StepType(stype.lower())
            except ValueError:
                step_type = StepType.WRITE

            steps.append(Step(
                index=int(num),
                type=step_type,
                description=desc.strip(),
            ))

        if not steps:
            steps.append(Step(
                index=1,
                type=StepType.WRITE,
                description=text.strip() or "执行任务",
            ))

        return steps
