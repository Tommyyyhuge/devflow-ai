"""基础规划器 — 任务 → 步骤拆解

使用 LLM JSON mode 将自然语言任务拆解为 read/write/verify 步骤。
支持 JSON 解析失败时 fallback 到正则解析。
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
    depends_on: list[int] = field(default_factory=list)


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

        # 校验依赖关系
        self._validate_dependencies(steps)

        return Plan(task=task, steps=steps)

    def _validate_dependencies(self, steps: list[Step]) -> None:
        """校验步骤依赖关系

        检查：
        1. 依赖的步骤索引是否存在
        2. 无循环依赖
        3. 最后一步是 verify 类型
        """
        if not steps:
            return

        index_set = {s.index for s in steps}

        # 1. 检查依赖是否存在
        for step in steps:
            for dep in step.depends_on:
                if dep not in index_set:
                    raise ValueError(
                        f"步骤 {step.index} 依赖不存在的步骤 {dep}"
                    )

        # 2. 检查循环依赖（DFS）
        def has_cycle(start: int, visited: set[int], path: set[int]) -> bool:
            if start in path:
                return True
            if start in visited:
                return False
            visited.add(start)
            path.add(start)
            step = next((s for s in steps if s.index == start), None)
            if step:
                for dep in step.depends_on:
                    if has_cycle(dep, visited, path):
                        return True
            path.remove(start)
            return False

        for step in steps:
            if has_cycle(step.index, set(), set()):
                raise ValueError(
                    f"步骤 {step.index} 存在循环依赖"
                )

        # 3. 检查最后一步是 verify
        last_step = max(steps, key=lambda s: s.index)
        if last_step.type != StepType.VERIFY:
            # 不强抛异常，只记录警告（某些任务可能不需要验证）
            pass

    def _system_prompt(self, project_context: str) -> str:
        return f"""你是一个资深的软件工程师。将编程任务拆解为具体可执行的步骤。

## 项目上下文
{project_context if project_context else "（无项目上下文）"}

## 步骤类型
- read: 读取/分析现有代码（多个 read 可以并行）
- write: 创建或修改代码文件（依赖 read 的结果）
- verify: 验证修改是否正确（运行测试/lint/curl，必须最后执行）

## 依赖关系规则
1. 每个步骤可以有 `depends_on` 字段（依赖的步骤索引列表）
2. 无依赖的步骤可以并行执行
3. write 步骤通常依赖读取同一文件的 read 步骤
4. verify 步骤依赖所有 write 步骤
5. 不允许循环依赖

## 返回格式必须是 JSON：

```json
{{
  "steps": [
    {{"index": 1, "type": "read", "description": "读取 src/api/__init__.py 了解路由结构"}},
    {{"index": 2, "type": "read", "description": "读取 src/models.py 了解数据模型"}},
    {{"index": 3, "type": "write", "description": "创建 src/api/health.py", "depends_on": [1]}},
    {{"index": 4, "type": "write", "description": "修改 src/api/__init__.py 注册路由", "depends_on": [1]}},
    {{"index": 5, "type": "verify", "description": "运行测试", "depends_on": [3, 4]}}
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

                    raw_deps = item.get("depends_on", [])
                    depends_on = [int(d) for d in raw_deps] if isinstance(raw_deps, list) else []

                    steps.append(Step(
                        index=item.get("index", len(steps) + 1),
                        type=step_type,
                        description=item.get("description", ""),
                        expected_output=item.get("expected_output", ""),
                        depends_on=depends_on,
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
