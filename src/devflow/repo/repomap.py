"""RepoMap — 项目地图构建

结构化项目索引，包含符号摘要和依赖关系。
支持基于文件修改时间的增量更新缓存。
用于为 LLM 构建精简的项目上下文。
"""

import json
import re
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
        """根据任务构建 LLM 上下文（基于 RepoMap 符号和关键词匹配）"""
        import re

        repomap = self.build()

        # 提取任务关键词
        keywords = self._extract_keywords(task)
        keywords_lower = [k.lower() for k in keywords]

        # 基于关键词给 entry 打分
        scored_entries: list[tuple[float, FileEntry]] = []
        for entry in repomap.entries:
            score = 0.0
            path_lower = entry.path.lower()
            summary_lower = entry.summary.lower()

            for kw in keywords_lower:
                if kw in path_lower:
                    score += 3.0  # 路径匹配权重高
                if kw in summary_lower:
                    score += 2.0  # 符号摘要匹配
                if any(kw in imp.lower() for imp in entry.imports):
                    score += 1.0  # 导入匹配

            if score > 0:
                scored_entries.append((score, entry))

        # 按分数排序
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        # 构建上下文文本
        parts = [f"项目: {self.root.name}", f"文件数: {len(repomap.entries)}"]

        if repomap.total_symbols > 0:
            parts.append(f"符号数: {repomap.total_symbols}")

        # 相关文件的符号摘要
        shown = 0
        for score, entry in scored_entries:
            parts.append(f"\n{entry.path} ({entry.language}, score={score:.1f})")
            if entry.summary:
                parts.append(entry.summary)
            shown += 1
            if shown >= max_files:
                remaining = len(scored_entries) - shown
                if remaining > 0:
                    parts.append(f"\n... 还有 {remaining} 个相关文件")
                break

        # 如果没有关键词匹配，展示前几个文件
        if shown == 0 and repomap.entries:
            parts.append("\n主要文件:")
            for entry in repomap.entries[:max_files]:
                parts.append(f"\n{entry.path} ({entry.language})")
                if entry.summary:
                    parts.append(entry.summary)

        # 依赖关系（如果有）
        if repomap.dependencies:
            parts.append("\n文件依赖:")
            for file, deps in list(repomap.dependencies.items())[:5]:
                parts.append(f"  {file} -> {', '.join(deps[:3])}")

        return "\n".join(parts)

    @staticmethod
    def _extract_keywords(task: str) -> list[str]:
        """从任务描述中提取关键词"""
        words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', task)
        stopwords = {
            "src", "api", "the", "and", "for", "that", "this", "with", "from",
            "create", "add", " implement", "fix", "update", "delete", "remove",
        }
        keywords = []
        for w in words:
            w_lower = w.lower()
            if len(w) >= 3 and w_lower not in stopwords:
                keywords.append(w)
        return keywords[:20]
