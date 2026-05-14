"""代码基因图谱——可视化项目健康状况"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class RepoMapProtocol(Protocol):
    """RepoMap 接口协议"""
    def analyze_project(self): ...


@dataclass
class ModuleMetrics:
    """模块健康指标"""
    name: str
    file_path: str
    lines_of_code: int
    complexity: float
    coupling_score: float
    debt_score: float
    test_coverage: float
    last_modified: str = ""
    authors: list[str] = None


@dataclass
class ProjectHealth:
    """项目整体健康度"""
    overall_score: float
    module_count: int
    total_lines: int
    avg_complexity: float
    avg_coupling: float
    hotspots: list[ModuleMetrics]
    trends: dict


class CodeGeneMap:
    """代码基因图谱生成器"""

    def __init__(self, repomap: RepoMapProtocol):
        self.repomap = repomap

    def analyze(self) -> ProjectHealth:
        """分析整个项目健康度"""
        modules = self._analyze_all_modules()

        if not modules:
            return ProjectHealth(
                overall_score=100.0,
                module_count=0,
                total_lines=0,
                avg_complexity=0.0,
                avg_coupling=0.0,
                hotspots=[],
                trends={},
            )

        avg_complexity = sum(m.complexity for m in modules) / len(modules)
        avg_coupling = sum(m.coupling_score for m in modules) / len(modules)
        overall_score = self._calculate_overall_score(modules)
        hotspots = sorted(modules, key=lambda m: m.debt_score, reverse=True)[:5]

        return ProjectHealth(
            overall_score=overall_score,
            module_count=len(modules),
            total_lines=sum(m.lines_of_code for m in modules),
            avg_complexity=avg_complexity,
            avg_coupling=avg_coupling,
            hotspots=hotspots,
            trends={},
        )

    def analyze_module(self, file_path: str) -> ModuleMetrics:
        """分析单个模块"""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")

        return ModuleMetrics(
            name=path.name,
            file_path=file_path,
            lines_of_code=len(lines),
            complexity=self._calculate_complexity(content),
            coupling_score=0.5,
            debt_score=0.3,
            test_coverage=0.0,
        )

    def generate_html(self, output_path: str = "code_gene.html") -> str:
        """生成交互式 HTML 报告"""
        health = self.analyze()
        html_content = self._render_html(health)
        Path(output_path).write_text(html_content, encoding="utf-8")
        return output_path

    def get_hotspots(self, top_n: int = 5) -> list[ModuleMetrics]:
        """返回技术债务最严重的模块"""
        health = self.analyze()
        return health.hotspots[:top_n]

    def _analyze_all_modules(self) -> list[ModuleMetrics]:
        """分析所有模块"""
        modules = []
        src_path = Path("src")

        if src_path.exists():
            for py_file in src_path.rglob("*.py"):
                if "__pycache__" not in str(py_file):
                    modules.append(self.analyze_module(str(py_file)))

        return modules

    def _calculate_complexity(self, content: str) -> float:
        """计算圈复杂度（简化版）"""
        branches = content.count("if ") + content.count("for ") + content.count("while ")
        branches += content.count("except") + content.count("with ")
        return max(1.0, float(branches))

    def _calculate_overall_score(self, modules: list[ModuleMetrics]) -> float:
        """计算项目综合健康分"""
        if not modules:
            return 100.0

        scores = []
        for m in modules:
            score = 100.0
            score -= m.complexity * 2
            score -= m.coupling_score * 20
            score -= m.debt_score * 30
            scores.append(max(0.0, score))

        return sum(scores) / len(scores)

    def _render_html(self, health: ProjectHealth) -> str:
        """渲染 HTML 模板"""
        hotspots_html = ""
        for h in health.hotspots:
            color = "red" if h.debt_score > 0.7 else "orange" if h.debt_score > 0.3 else "green"
            hotspots_html += f'<div style="color:{color}">{h.name}: 债务 {h.debt_score:.0%}</div>'

        return f"""
<!DOCTYPE html>
<html>
<head><title>Code Gene Map</title></head>
<body>
    <h1>项目健康度报告</h1>
    <div>综合评分: {health.overall_score:.1f}/100</div>
    <div>模块数: {health.module_count}</div>
    <div>代码行数: {health.total_lines}</div>
    <h2>热点模块</h2>
    {hotspots_html}
</body>
</html>
        """
