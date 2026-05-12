"""RepoMap — 项目地图构建

Week 2 Day 3-4：结构化项目索引，包含符号摘要和依赖关系。
用于为 LLM 构建精简的项目上下文。
"""

from dataclasses import dataclass, field
from pathlib import Path

from devflow.repo.parser import LanguageProvider, LanguageRegistry, Symbol
from devflow.repo.scanner import FileInfo, ProjectScanner


@dataclass
class FileEntry:
    """单个文件的 RepoMap 条目"""
    path: str
    language: str
    symbols: list = field(default_factory=list)  # list[Symbol]
    summary: str = ""           # <100 tokens 结构摘要
    token_count: int = 0
    imports: list[str] = field(default_factory=list)  # 导入的模块名


@dataclass
class RepoMap:
    """项目结构化地图"""
    root: Path
    entries: list[FileEntry] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    total_symbols: int = 0
    total_tokens: int = 0


class RepoMapBuilder:
    """RepoMap 构建器"""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.scanner = ProjectScanner(self.root)
        self._cache: dict[str, FileEntry] = {}  # 路径缓存

    def build(self, force: bool = False) -> RepoMap:
        """构建完整的 RepoMap"""
        ctx = self.scanner.scan()
        repomap = RepoMap(root=self.root)

        for f in ctx.files:
            if not f.is_text:
                continue

            provider = LanguageRegistry.detect(Path(f.relative))
            if not provider:
                continue  # 跳过不支持的语言

            entry = self._build_entry(f, provider, force)
            repomap.entries.append(entry)
            repomap.total_symbols += len(entry.symbols)
            repomap.total_tokens += entry.token_count

        # 构建依赖图
        repomap.dependencies = self._build_deps(repomap.entries)
        return repomap

    def _build_entry(self, f: FileInfo, provider: LanguageProvider,
                     force: bool) -> FileEntry:
        """构建单个文件条目（带缓存）"""
        cache_key = str(f.relative)

        # 检查缓存（基于文件修改时间）
        if not force and cache_key in self._cache:
            return self._cache[cache_key]

        # 解析文件
        result = provider.parse_file(self.root / f.relative)

        # 提取导入模块名
        import_modules = list(set(
            imp.module.split(".")[0] for imp in result.imports
        ))

        # 生成摘要（<100 tokens）
        summary = self._summarize(result.symbols)

        entry = FileEntry(
            path=f.relative,
            language=result.language,
            symbols=result.symbols,
            summary=summary,
            token_count=f.size // 4,  # 估算 token 数
            imports=import_modules,
        )

        self._cache[cache_key] = entry
        return entry

    @staticmethod
    def _summarize(symbols: list[Symbol], max_items: int = 8) -> str:
        """生成文件结构摘要"""
        if not symbols:
            return "(空文件)"

        lines = []
        for sym in symbols[:max_items]:
            lines.append(sym.signature)

        summary = "\n".join(lines)
        if len(symbols) > max_items:
            summary += f"\n... 还有 {len(symbols) - max_items} 个符号"
        return summary

    @staticmethod
    def _build_deps(entries: list[FileEntry]) -> dict[str, list[str]]:
        """构建文件依赖图（基于 import 关系）"""
        deps: dict[str, list[str]] = {}
        for entry in entries:
            # 文件名（去掉路径和扩展名）
            module_name = Path(entry.path).stem

            dependents = []
            for other in entries:
                if other.path == entry.path:
                    continue
                # 检查 other 是否导入了 entry 的模块
                if module_name in other.imports:
                    dependents.append(other.path)

            if dependents:
                deps[entry.path] = dependents
        return deps

    def get_context_for_task(self, task: str, max_files: int = 10) -> str:
        """根据任务构建 LLM 上下文（精简版）"""
        repomap = self.build()
        from devflow.repo.scanner import ContextBuilder

        # 先用关键词筛选相关文件
        cb = ContextBuilder(self.root)
        ctx = cb.build(task)
        relevant_paths = {f.relative for f in ctx.relevant_files}

        # 构建上下文文本
        parts = [f"项目: {self.root.name}", f"文件数: {len(repomap.entries)}"]

        # 相关文件的符号摘要
        shown = 0
        for entry in repomap.entries:
            if entry.path in relevant_paths or shown < 5:
                parts.append(f"\n📄 {entry.path} ({entry.language})")
                if entry.summary:
                    parts.append(entry.summary)
                shown += 1
                if shown >= max_files:
                    parts.append(f"\n... 还有 {len(repomap.entries) - shown} 个文件")
                    break

        # 依赖关系（如果有）
        if repomap.dependencies:
            parts.append("\n文件依赖:")
            for file, deps in list(repomap.dependencies.items())[:5]:
                parts.append(f"  {file} → {', '.join(deps[:3])}")

        return "\n".join(parts)
