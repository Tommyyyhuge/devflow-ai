"""代码解析器 — Tree-sitter AST 分析

Week 2 Day 1-2：基于 Tree-sitter 提取代码结构（函数/类/导入）。
LanguageProvider 抽象允许插件化扩展多语言支持。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Symbol:
    """代码符号（函数、类、方法）"""
    name: str
    kind: str          # "function" | "class" | "method"
    signature: str     # "def foo(x: int) -> str"
    line: int
    docstring: str | None = None


@dataclass
class Import:
    """导入声明"""
    module: str        # "os.path"
    names: list[str] = field(default_factory=list)  # ["join", "dirname"]
    line: int = 0


@dataclass
class ParseResult:
    """文件解析结果"""
    path: Path
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    token_count: int = 0
    error: str | None = None


class LanguageProvider(ABC):
    """语言解析插件抽象（Oracle 审查建议）

    新增语言只需实现此接口并注册到 LanguageRegistry。
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """语言标识符，如 'python', 'typescript'"""
        ...

    @abstractmethod
    def parse_file(self, path: Path) -> ParseResult:
        """解析文件，返回符号和导入"""
        ...

    @abstractmethod
    def extract_imports(self, path: Path) -> list[Import]:
        """提取导入声明"""
        ...

    def get_symbol_at(self, path: Path, line: int) -> Symbol | None:
        """获取指定行的符号（默认从完整解析结果中查找）"""
        result = self.parse_file(path)
        for sym in result.symbols:
            if sym.line == line:
                return sym
        return None


class PythonProvider(LanguageProvider):
    """Python Tree-sitter 解析器"""

    language = "python"

    def __init__(self):
        import tree_sitter_python as tspy
        from tree_sitter import Language, Parser

        self.parser = Parser(Language(tspy.language()))

    def parse_file(self, path: Path) -> ParseResult:
        result = ParseResult(path=path, language=self.language)

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            result.error = str(e)
            return result

        result.token_count = len(content.split())

        try:
            tree = self.parser.parse(bytes(content, "utf-8"))
        except Exception as e:
            result.error = f"解析失败: {e}"
            return result

        root = tree.root_node
        source = content

        # 遍历 AST 提取函数和类
        self._extract_symbols(root, source, result)
        # 提取导入
        result.imports = self._extract_imports_from_node(root, source)

        return result

    def extract_imports(self, path: Path) -> list[Import]:
        result = self.parse_file(path)
        return result.imports

    def _extract_symbols(self, node, source: str, result: ParseResult):
        """递归遍历 AST 提取函数和类定义"""
        for child in node.children:
            if child.type == "function_definition":
                sym = self._parse_function(child, source)
                if sym:
                    result.symbols.append(sym)
            elif child.type == "class_definition":
                sym = self._parse_class(child, source)
                if sym:
                    result.symbols.append(sym)
                    # 递归提取类方法
                    body = child.child_by_field_name("body")
                    if body:
                        for item in body.children:
                            if item.type == "function_definition":
                                m = self._parse_function(item, source)
                                if m:
                                    m.kind = "method"
                                    result.symbols.append(m)
            else:
                self._extract_symbols(child, source, result)

    def _parse_function(self, node, source: str) -> Symbol | None:
        """解析函数/方法定义"""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = source[name_node.start_byte:name_node.end_byte]
        line = node.start_point[0] + 1

        # 提取签名
        params_node = node.child_by_field_name("parameters")
        params = source[params_node.start_byte:params_node.end_byte] if params_node else "()"

        # 提取返回类型
        return_type = ""
        return_node = node.child_by_field_name("return_type")
        if return_node:
            return_type = f" -> {source[return_node.start_byte:return_node.end_byte]}"

        # 提取 docstring
        docstring = self._extract_docstring(node, source)

        return Symbol(
            name=name,
            kind="function",
            signature=f"def {name}{params}{return_type}",
            line=line,
            docstring=docstring,
        )

    def _parse_class(self, node, source: str) -> Symbol | None:
        """解析类定义"""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = source[name_node.start_byte:name_node.end_byte]
        line = node.start_point[0] + 1

        # 提取父类
        bases = []
        for child in node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type not in ("(", ")", ","):
                        bases.append(source[arg.start_byte:arg.end_byte])

        signature = f"class {name}"
        if bases:
            signature += f"({', '.join(bases)})"

        docstring = self._extract_docstring(node, source)

        return Symbol(
            name=name,
            kind="class",
            signature=signature,
            line=line,
            docstring=docstring,
        )

    def _extract_docstring(self, node, source: str) -> str | None:
        """提取函数的 docstring"""
        body = node.child_by_field_name("body")
        if not body or not body.children:
            return None

        first = body.children[0]
        if first.type == "expression_statement":
            expr = first.children[0] if first.children else None
            if expr and expr.type == "string":
                text = source[expr.start_byte:expr.end_byte]
                return text.strip('"').strip("'")
        return None

    def _extract_imports_from_node(self, node, source: str) -> list[Import]:
        """提取所有 import 语句"""
        imports: list[Import] = []
        self._walk_imports(node, source, imports)
        return imports

    def _walk_imports(self, node, source: str, imports: list[Import]):
        """递归遍历 import 节点"""
        if node.type == "import_statement":
            # import os, sys
            for child in node.children:
                if child.type == "dotted_name":
                    imports.append(Import(
                        module=source[child.start_byte:child.end_byte],
                        line=node.start_point[0] + 1,
                    ))
                elif child.type == "aliased_import":
                    name = child.child_by_field_name("name")
                    if name:
                        imports.append(Import(
                            module=source[name.start_byte:name.end_byte],
                            line=node.start_point[0] + 1,
                        ))
        elif node.type == "import_from_statement":
            # from X import Y, Z
            module = ""
            names = []
            for child in node.children:
                if child.type == "dotted_name" and not module:
                    module = source[child.start_byte:child.end_byte]
                elif child.type == "aliased_import":
                    n = child.child_by_field_name("name")
                    if n:
                        names.append(source[n.start_byte:n.end_byte])

            if module:
                imports.append(Import(
                    module=module,
                    names=names,
                    line=node.start_point[0] + 1,
                ))

        for child in node.children:
            self._walk_imports(child, source, imports)


class LanguageRegistry:
    """语言提供者注册中心"""

    _providers: dict[str, LanguageProvider] = {}

    @classmethod
    def register(cls, provider: LanguageProvider):
        cls._providers[provider.language] = provider

    @classmethod
    def get(cls, language: str) -> LanguageProvider | None:
        return cls._providers.get(language)

    @classmethod
    def detect(cls, path: Path) -> LanguageProvider | None:
        """根据文件扩展名检测语言"""
        ext_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".go": "go",
            ".rs": "rust",
        }
        lang = ext_map.get(path.suffix)
        return cls.get(lang) if lang else None


# 默认注册 Python
LanguageRegistry.register(PythonProvider())
