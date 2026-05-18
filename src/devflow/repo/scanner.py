"""简化项目理解 — 文件扫描 + 内容搜索 + 上下文构建

纯文件系统操作，为 LLM 构建项目上下文（文件树、语言统计、搜索结果）。
"""

import fnmatch
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# 默认排除模式
DEFAULT_EXCLUDES: list[str] = [
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "*.pyc", "*.pyo", "*.so", "*.dll", "*.dylib",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "*.egg-info",
]


@dataclass
class FileInfo:
    """文件元信息"""
    path: Path
    relative: str
    size: int
    extension: str
    is_text: bool


@dataclass
class SearchMatch:
    """搜索结果"""
    file: str
    line: int
    content: str


@dataclass
class ProjectContext:
    """项目上下文 — 用于 LLM 理解项目结构"""
    root: Path
    files: list[FileInfo] = field(default_factory=list)
    total_files: int = 0
    languages: dict[str, int] = field(default_factory=dict)  # .py: 23, .ts: 8
    structure: str = ""  # 文件树文本表示
    relevant_files: list[FileInfo] = field(default_factory=list)


class ProjectScanner:
    """项目文件扫描器"""

    def __init__(
        self,
        root: Path,
        excludes: list[str] | None = None,
        max_file_size: int = 512 * 1024,  # 512KB
        max_depth: int = 10,
    ):
        self.root = Path(root).resolve()
        self.excludes = excludes or DEFAULT_EXCLUDES
        self.max_file_size = max_file_size
        self.max_depth = max_depth

    def scan(self) -> ProjectContext:
        """扫描整个项目，返回 ProjectContext"""
        ctx = ProjectContext(root=self.root)
        files: list[FileInfo] = []

        for entry in self.root.rglob("*"):
            if entry.is_file():
                if self._should_skip(entry):
                    continue
                info = self._file_info(entry)
                if info:
                    files.append(info)

        ctx.files = sorted(files, key=lambda f: f.relative)
        ctx.total_files = len(ctx.files)
        ctx.languages = self._count_languages(ctx.files)
        ctx.structure = self._build_tree(ctx.files)
        return ctx

    def _should_skip(self, path: Path) -> bool:
        """检查文件/目录是否应被排除"""
        rel = str(path.relative_to(self.root))

        # 检查路径深度
        parts = Path(rel).parts
        if len(parts) > self.max_depth:
            return True

        # 检查父目录是否被排除
        for parent in path.parents:
            try:
                parent_rel = str(parent.relative_to(self.root))
            except ValueError:
                continue
            if parent_rel in {".git", "__pycache__", "node_modules", ".venv", "venv"}:
                return True

        # 检查文件名匹配排除模式
        for pattern in self.excludes:
            if fnmatch.fnmatch(path.name, pattern):
                return True
            if fnmatch.fnmatch(rel, pattern):
                return True

        # 跳过二进制文件
        if path.suffix in {".exe", ".dll", ".so", ".dylib", ".bin"}:
            return True

        return False

    def _file_info(self, path: Path) -> FileInfo | None:
        """构建文件信息"""
        try:
            stat = path.stat()
            size = stat.st_size
            if size > self.max_file_size:
                return None
        except OSError:
            return None

        return FileInfo(
            path=path,
            relative=str(path.relative_to(self.root)),
            size=size,
            extension=path.suffix,
            is_text=self._is_text_file(path),
        )

    @staticmethod
    def _is_text_file(path: Path) -> bool:
        """简单检测文本文件"""
        text_extensions = {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs",
            ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".hpp",
            ".json", ".yaml", ".yml", ".toml", ".xml", ".html", ".css",
            ".md", ".txt", ".sh", ".bat", ".ps1", ".env", ".cfg", ".ini",
            ".sql", ".graphql", ".proto",
        }
        if path.suffix in text_extensions:
            return True
        # 无后缀文件也尝试（如 Dockerfile, Makefile）
        if not path.suffix:
            return True
        return False

    @staticmethod
    def _count_languages(files: list[FileInfo]) -> dict[str, int]:
        """统计各语言文件数"""
        counter: Counter = Counter()
        for f in files:
            if f.extension:
                counter[f.extension] += 1
        return dict(counter.most_common(15))

    @staticmethod
    def _build_tree(files: list[FileInfo], max_display: int = 60) -> str:
        """生成简化的文件树文本"""
        lines = []
        dirs_seen: set[str] = set()
        for f in files[:max_display]:
            parent = str(Path(f.relative).parent)
            if parent not in dirs_seen and parent != ".":
                lines.append(f"  📁 {parent}/")
                dirs_seen.add(parent)
            lines.append(f"    📄 {f.relative}")
        if len(files) > max_display:
            lines.append(f"  ... 还有 {len(files) - max_display} 个文件")
        return "\n".join(lines)


class GrepSearch:
    """内容搜索封装"""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def search(
        self,
        pattern: str,
        include: str = "*",
        max_results: int = 50,
        case_sensitive: bool = False,
    ) -> list[SearchMatch]:
        """在项目文件中搜索文本模式"""
        matches: list[SearchMatch] = []
        flags = 0 if case_sensitive else re.IGNORECASE

        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            return [SearchMatch(file="", line=0, content=f"正则错误: {e}")]

        scanner = ProjectScanner(self.root)
        ctx = scanner.scan()

        for f in ctx.files:
            if not fnmatch.fnmatch(f.relative, include):
                continue
            if not f.is_text:
                continue

            try:
                content = f.path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for line_no, line in enumerate(content.splitlines(), 1):
                if compiled.search(line):
                    matches.append(SearchMatch(
                        file=f.relative,
                        line=line_no,
                        content=line.strip()[:200],
                    ))
                    if len(matches) >= max_results:
                        return matches

        return matches


class ContextBuilder:
    """上下文构建器 — 根据任务描述找到相关文件"""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.scanner = ProjectScanner(self.root)
        self.grep = GrepSearch(self.root)

    def build(self, task: str) -> ProjectContext:
        """根据任务构建项目上下文"""
        ctx = self.scanner.scan()

        # 提取任务中的关键词
        keywords = self._extract_keywords(task)

        # 基于关键词打分，选出相关文件
        relevant: list[FileInfo] = []
        for f in ctx.files:
            score = self._relevance_score(f, keywords)
            if score > 0:
                relevant.append(f)

        # 按相关性排序，取 top-10
        relevant.sort(key=lambda f: self._relevance_score(f, keywords), reverse=True)
        ctx.relevant_files = relevant[:10]

        # Fallback：如果没有匹配到相关文件，返回所有代码文件
        if not ctx.relevant_files:
            ctx.relevant_files = [f for f in ctx.files if f.is_text][:10]

        return ctx

    @staticmethod
    def _extract_keywords(task: str) -> list[str]:
        """从任务描述中提取关键词"""
        # 提取驼峰/蛇形命名的词和常见编程术语
        words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', task)
        # 过滤太短的词和常见停用词
        stopwords = {"src", "api", "the", "and", "for", "that", "this", "with", "from"}
        keywords = []
        for w in words:
            w_lower = w.lower()
            if len(w) >= 3 and w_lower not in stopwords:
                keywords.append(w)
        return keywords[:20]

    @staticmethod
    def _relevance_score(f: FileInfo, keywords: list[str]) -> int:
        """计算文件与关键词的相关性得分"""
        score = 0
        rel_lower = f.relative.lower()
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in rel_lower:
                score += 3  # 路径匹配权重高
            if kw_lower in f.extension.lower():
                score += 1
        return score
