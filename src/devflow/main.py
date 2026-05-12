"""CLI 入口 — devflow 命令"""

import sys

import click
from rich.console import Console

from devflow.config import load_config

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="devflow")
def main():
    """devflow-ai — 低成本的 AI 编程助手"""
    pass


@main.command()
def info():
    """显示项目信息（原 help 命令，避免与 Click --help 冲突）"""
    console.print(
        "[bold cyan]devflow-ai[/bold cyan] — 低成本的 AI 编程助手\n\n"
        "基于 DeepSeek V4 Flash，内置预算上限（$20/周 + $3.5/5h）\n\n"
        "使用方法:\n"
        "  devflow run \"你的编程任务\"   执行 AI 编程任务\n"
        "  devflow config show            显示当前配置\n"
        "  devflow budget show            显示预算使用情况\n"
    )


@main.group()
def config():
    """配置管理"""
    pass


@config.command("show")
def config_show():
    """显示当前配置"""
    cfg = load_config()
    console.print("[bold]LLM 配置[/bold]")
    console.print(f"  模型: {cfg.llm.model}")
    api_status = "已设置" if cfg.llm.api_key.get_secret_value() else "[red]未设置[/red]"
    console.print(f"  API Key: {api_status}")
    console.print(f"  Max Tokens: {cfg.llm.max_tokens_per_request}")
    console.print("[bold]Agent 配置[/bold]")
    console.print(f"  上下文预算: {cfg.agent.context_budget}")
    console.print(f"  代码上下文预算: {cfg.agent.code_context_budget}")
    console.print(f"  自动确认: {cfg.agent.auto_confirm}")
    console.print("[bold]预算配置[/bold]")
    console.print(f"  周预算: ${cfg.budget.weekly_budget}")
    console.print(f"  5小时预算: ${cfg.budget.budget_per_5h}")
    console.print("[bold]日志[/bold]")
    console.print(f"  级别: {cfg.log_level}")


@main.command()
@click.argument("task", required=False)
def run(task: str | None):
    """执行 AI 编程任务（开发中）"""
    if not task:
        console.print("[yellow]请提供任务描述。示例: devflow run \"创建 hello.py\"[/yellow]")
        return
    try:
        cfg = load_config()
    except Exception as e:
        console.print(f"[red]配置加载失败: {e}[/red]")
        sys.exit(1)
    if not cfg.llm.api_key.get_secret_value():
        console.print("[red]错误: 请设置 DEEPSEEK_API_KEY 环境变量[/red]")
        sys.exit(1)
    console.print(f"[bold]🚀 执行任务:[/bold] {task}")
    _run_task(task, cfg)


@main.command()
def web():
    """启动 Web UI"""
    import uvicorn
    console.print("[bold]🌐 启动 Web UI: http://localhost:8000[/bold]")
    uvicorn.run("devflow.api.server:app", host="0.0.0.0", port=8000, reload=True)


def _run_task(task: str, cfg):
    """执行 AI 编程任务"""
    import asyncio
    from pathlib import Path

    from devflow.core.agent import Agent
    from devflow.llm import DeepSeekClient
    from devflow.tools.base import create_tool_registry, set_safe_root

    repo_path = Path(".").resolve()
    set_safe_root(repo_path)

    # 初始化组件
    client = DeepSeekClient(cfg.llm)
    tools = create_tool_registry()
    agent = Agent(client, tools, config=cfg)

    # 执行
    async def _run():
        return await agent.run(task, repo_path)

    with console.status("[bold green]Agent 工作中..."):
        result = asyncio.run(_run())

    # 输出结果
    if result.success:
        console.print("\n[bold green]✅ 任务完成[/bold green]")
    else:
        console.print(f"\n[bold red]❌ 任务失败[/bold red]: {result.error}")

    if result.plan:
        console.print(f"\n[bold]执行计划:[/bold] {len(result.plan.steps)} 个步骤")
        for sr in result.step_results:
            status = "✅" if sr.success else "❌"
            console.print(f"  {status} 步骤 {sr.step.index}: {sr.step.description[:80]}")

    if result.files_modified:
        console.print("\n[bold]修改文件:[/bold]")
        for f in result.files_modified:
            console.print(f"  📄 {f}")

    if result.verify_result and result.verify_result.errors:
        console.print("\n[bold red]验证错误:[/bold red]")
        for e in result.verify_result.errors:
            loc = f"{e.file}:{e.line}" if e.line else e.file
            console.print(f"  ❌ {loc}: {e.message}")


@main.command()
@click.argument("project_path", type=click.Path(exists=True), default=".")
@click.option("--search", "-s", default=None, help="在项目中搜索文本模式")
def analyze(project_path: str, search: str | None):
    """分析项目结构（Day 2 实现）"""
    from pathlib import Path

    from devflow.repo.scanner import ContextBuilder, GrepSearch, ProjectScanner

    root = Path(project_path).resolve()
    console.print(f"\n[bold]📊 分析项目:[/bold] {root}")

    # 扫描文件
    scanner = ProjectScanner(root)
    ctx = scanner.scan()

    console.print(f"\n[bold]文件统计:[/bold] {ctx.total_files} 个文件")
    for ext, count in ctx.languages.items():
        console.print(f"  {ext}: {count}")

    console.print("\n[bold]文件树:[/bold]")
    console.print(ctx.structure)

    # 搜索（如果指定）
    if search:
        console.print(f"\n[bold]🔍 搜索:[/bold] '{search}'")
        gs = GrepSearch(root)
        matches = gs.search(search)
        for m in matches[:20]:
            console.print(f"  [cyan]{m.file}:{m.line}[/cyan] {m.content}")
        if len(matches) > 20:
            console.print(f"  ... 还有 {len(matches) - 20} 个结果")

    # 上下文构建
    if search:
        builder = ContextBuilder(root)
        task_ctx = builder.build(search)
        if task_ctx.relevant_files:
            console.print(f"\n[bold]🎯 相关文件 (Top {len(task_ctx.relevant_files)}):[/bold]")
            for f in task_ctx.relevant_files:
                console.print(f"  📄 {f.relative} ({f.size:,} bytes)")
