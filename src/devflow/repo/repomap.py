"""RepoMap — 项目地图构建

Week 2 Day 3-4：结构化项目索引，包含符号摘要和依赖关系。
Week 2 升级：基于文件修改时间的增量更新缓存。
用于为 LLM 构建精简的项目上下文。
"""

import json
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
    mtime: float = 0.0          # 文件修改时间（用于缓存验证）


@dataclass
class RepoMap:
    """项目结构化地图"""
    root: Path
    entries: list[FileEntry] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    total_symbols: int = 0
    total_tokens: int = 0


class RepoMapBuilder:
    """RepoMap 构建器（带增量缓存）"""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.scanner = ProjectScanner(self.root)
        self._cache: dict[str, FileEntry] = {}  # 内存缓存
        self._cache_file = self.root / ".devflow" / "repomap_cache.json"
        self._load_cache()

    def _load_cache(self):
        """从磁盘加载缓存"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("entries", []):
                    entry = FileEntry(**item)
                    self._cache[entry.path] = entry
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

    def _save_cache(self):
        """保存缓存到磁盘"""
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [
                {
                    "path": e.path,
                    "language": e.language,
                    "symbols": [],  # 符号不持久化（太大）
                    "summary": e.summary,
                    "token_count": e.token_count,
                    "imports": e.imports,
                    "mtime": e.mtime,
                }
                for e in self._cache.values()
            ]
        }
        with open(self._cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _is_cache_valid(self, path: str, mtime: float) -> bool:
        """检查缓存是否有效（文件未修改且有 symbols）"""
        if path not in self._cache:
            return False
        entry = self._cache[path]
        # 如果缓存中没有 symbols（从磁盘加载的缓存），需要重新解析
        if not entry.symbols:
            return False
        return entry.mtime == mtime

    def build(self, force: bool = False) -> RepoMap:
        """构建完整的 RepoMap（增量更新）"""
        ctx = self.scanner.scan()
        repomap = RepoMap(root=self.root)
        cache_hits = 0
        cache_misses = 0

        for f in ctx.files:
            if not f.is_text:
                continue

            provider = LanguageRegistry.detect(Path(f.relative))
            if not provider:
                continue

            # 检查缓存有效性
            file_path = self.root / f.relative
            mtime = file_path.stat().st_mtime if file_path.exists() else 0

            if not force and self._is_cache_valid(f.relative, mtime):
                entry = self._cache[f.relative]
                cache_hits += 1
            else:
                entry = self._build_entry(f, provider, mtime)
                self._cache[f.relative] = entry
                cache_misses += 1

            repomap.entries.append(entry)
            repomap.total_symbols += len(entry.symbols)
            repomap.total_tokens += entry.token_count

        # 清理已删除文件的缓存
        current_files = {f.relative for f in ctx.files}
        for key in list(self._cache.keys()):
            if key not in current_files:
                del self._cache[key]

        # 构建依赖图
        repomap.dependencies = self._build_deps(repomap.entries)

        # 保存缓存
        self._save_cache()

        return repomap

    def _build_entry(self, f: FileInfo, provider: LanguageProvider,
                     mtime: float) -> FileEntry:
        """构建单个文件条目"""
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
            token_count=f.size // 4,
            imports=import_modules,
            mtime=mtime,
        )

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
