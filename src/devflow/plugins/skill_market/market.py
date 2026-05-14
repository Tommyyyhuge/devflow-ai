"""技能市场管理器"""

import importlib.util
import shutil
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from devflow.plugins.skill_market.skill import Skill


@runtime_checkable
class SkillProtocol(Protocol):
    name: str
    description: str
    version: str
    author: str
    tags: list[str]
    
    def execute(self, context: dict) -> str: ...
    def validate(self) -> bool: ...


class SkillMarket:
    """技能市场管理器"""
    
    def __init__(self, skills_dir: str = "~/.devflow/skills"):
        self.skills_dir = Path(skills_dir).expanduser()
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, SkillProtocol] = {}
        self._skill_paths: dict[str, Path] = {}
        self._load_all_skills()
    
    def _load_all_skills(self) -> None:
        """重新扫描 skills_dir 加载所有技能"""
        if not self.skills_dir.exists():
            return
        
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "skill.py").exists():
                try:
                    skill = self._load_skill_from_dir(skill_dir)
                    self._skills[skill.name] = skill
                except Exception as e:
                    print(f"⚠️ 加载技能失败 {skill_dir.name}: {e}")
    
    def _load_skill_from_dir(self, skill_dir: Path) -> SkillProtocol:
        """从目录加载技能"""
        skill_file = skill_dir / "skill.py"
        
        spec = importlib.util.spec_from_file_location("skill", skill_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, "name"):
            raise ValueError(f"技能 {skill_dir.name} 缺少 name 属性")
        if not hasattr(module, "execute"):
            raise ValueError(f"技能 {skill_dir.name} 缺少 execute 函数")
        
        self._skill_paths[module.name] = skill_dir
        return module
    
    def load_skill(self, path: str) -> SkillProtocol:
        """从本地路径加载技能"""
        skill_dir = Path(path)
        skill = self._load_skill_from_dir(skill_dir)
        self._skills[skill.name] = skill
        self._skill_paths[skill.name] = skill_dir
        return skill
    
    def install_from_git(self, repo_url: str, name: str | None = None) -> SkillProtocol:
        """从 Git 仓库安装技能"""
        if name is None:
            name = repo_url.split("/")[-1].replace(".git", "")
        
        target_dir = self.skills_dir / name
        
        subprocess.run(
            ["git", "clone", repo_url, str(target_dir)],
            check=True,
            capture_output=True,
        )
        
        return self.load_skill(str(target_dir))
    
    def install_from_local(self, local_path: str, name: str | None = None) -> SkillProtocol:
        """从本地目录安装技能"""
        src_dir = Path(local_path)
        if name is None:
            name = src_dir.name
        
        target_dir = self.skills_dir / name
        
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(src_dir, target_dir)
        
        return self.load_skill(str(target_dir))
    
    def list_skills(self) -> list[SkillProtocol]:
        """列出所有已安装技能（重新扫描磁盘确保最新）"""
        self._load_all_skills()
        return list(self._skills.values())
    
    def uninstall(self, name: str) -> bool:
        """卸载技能"""
        if name not in self._skills:
            return False
        
        del self._skills[name]
        
        skill_dir = self._skill_paths.pop(name, None)
        if skill_dir and skill_dir.exists():
            shutil.rmtree(skill_dir)
        
        return True
    
    def get_skill(self, name: str) -> SkillProtocol | None:
        """获取指定技能"""
        return self._skills.get(name)
    
    def execute_skill(self, name: str, context: dict) -> str:
        """执行指定技能"""
        skill = self.get_skill(name)
        if skill is None:
            raise ValueError(f"技能不存在: {name}")
        
        return skill.execute(context)
