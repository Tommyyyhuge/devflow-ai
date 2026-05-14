"""沙盒模块——安全执行环境"""

import shutil
import subprocess
import tempfile
from pathlib import Path


class Sandbox:
    """沙盒执行环境"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="devflow_sandbox_")
        self._original_dir = None

    def copy_project(self, project_path: str, ignore_patterns: list[str] | None = None) -> None:
        """复制项目文件到沙盒"""
        self._original_dir = Path(project_path).resolve()

        if ignore_patterns is None:
            ignore_patterns = ['.git', '__pycache__', '.pytest_cache', '*.pyc', '.sisyphus']

        def ignore_func(dir, files):
            return [f for f in files if any(
                f.endswith(pat.replace('*', '')) if '*' in pat else f == pat or f.endswith(pat)
                for pat in ignore_patterns
            )]

        shutil.copytree(project_path, self.temp_dir, dirs_exist_ok=True, ignore=ignore_func)

    def execute(self, command: str, timeout: int = 30) -> dict:
        """在沙盒中执行命令"""
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=self.temp_dir,
            timeout=timeout,
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    def get_changes(self) -> dict:
        """获取文件变化（新增、修改、删除）"""
        if not self._original_dir:
            return {"added": [], "modified": [], "deleted": []}

        added = []
        modified = []
        deleted = []

        # 遍历沙盒目录，对比原始目录
        for item in Path(self.temp_dir).rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(self.temp_dir)
                orig_file = self._original_dir / rel_path

                if not orig_file.exists():
                    added.append(str(rel_path))
                elif item.stat().st_mtime != orig_file.stat().st_mtime:
                    modified.append(str(rel_path))

        # 检查删除的文件
        for item in self._original_dir.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(self._original_dir)
                sandbox_file = Path(self.temp_dir) / rel_path
                if not sandbox_file.exists():
                    deleted.append(str(rel_path))

        return {"added": added, "modified": modified, "deleted": deleted}

    def apply_changes(self) -> None:
        """将沙盒中的修改应用到原始项目"""
        if not self._original_dir:
            raise ValueError("没有原始项目路径")

        changes = self.get_changes()

        # 应用新增和修改的文件
        for file_path in changes["added"] + changes["modified"]:
            src = Path(self.temp_dir) / file_path
            dst = self._original_dir / file_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        # 删除原始项目中已删除的文件
        for file_path in changes["deleted"]:
            (self._original_dir / file_path).unlink(missing_ok=True)

    def cleanup(self) -> None:
        """清理临时目录"""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
