"""技能市场测试"""

import tempfile
from pathlib import Path

import pytest

from devflow.plugins.skill_market.market import SkillMarket
from devflow.plugins.skill_market.skill import Skill


class TestSkillMarket:
    @pytest.fixture
    def market(self, tmp_path):
        return SkillMarket(skills_dir=str(tmp_path))
    
    def test_load_skill_from_local(self, market, tmp_path):
        """测试从本地加载技能"""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "skill.py").write_text('''
name = "Test Skill"
description = "A test skill"
version = "1.0.0"
author = "test"
tags = ["test"]

def execute(context):
    return f"Hello {context.get('name', 'world')}"

def validate():
    return True
''')
        
        skill = market.load_skill(str(skill_dir))
        assert skill.name == "Test Skill"
        result = skill.execute({"name": "DevFlow"})
        assert result == "Hello DevFlow"
    
    def test_list_skills(self, market, tmp_path):
        """测试列出技能"""
        for name in ["skill_a", "skill_b"]:
            skill_dir = tmp_path / name
            skill_dir.mkdir()
            (skill_dir / "skill.py").write_text(f'''
name = "{name}"
description = "desc"
version = "1.0"
author = "test"
tags = []

def execute(context): return ""
def validate(): return True
''')
        
        skills = market.list_skills()
        assert len(skills) == 2
    
    def test_uninstall_skill(self, market, tmp_path):
        """测试卸载技能"""
        skill_dir = tmp_path / "to_remove"
        skill_dir.mkdir()
        (skill_dir / "skill.py").write_text('''
name = "Remove Me"
description = ""
version = "1.0"
author = "test"
tags = []

def execute(context): return ""
def validate(): return True
''')
        
        market.load_skill(str(skill_dir))
        assert len(market.list_skills()) == 1
        
        market.uninstall("Remove Me")
        assert len(market.list_skills()) == 0
