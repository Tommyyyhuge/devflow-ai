"""影子模式测试"""

import pytest

from devflow.plugins.shadow_mode.shadow import ShadowMode, CodeChangeImpact


class TestShadowMode:
    @pytest.fixture
    def shadow(self):
        class MockAgent:
            def suggest_follow_up(self, impact):
                return f"建议更新测试: {impact.changed_file}"
        
        class MockRepoMap:
            def analyze_impact(self, file_path):
                return type('obj', (object,), {
                    'affected_tests': ['test_user.py'],
                    'affected_modules': ['api/routes.py'],
                    'score': 0.85,
                })()
        
        return ShadowMode(MockAgent(), MockRepoMap())
    
    def test_analyze_impact_high(self, shadow):
        """测试高影响变更分析"""
        impact = shadow._analyze_impact("user.py")
        assert impact.impact_score == 0.85
        assert len(impact.affected_tests) == 1
    
    def test_should_trigger_high_impact(self, shadow):
        """测试高影响时触发建议"""
        impact = CodeChangeImpact(
            changed_file="user.py",
            change_type="modified",
            affected_tests=["test_user.py"],
            affected_modules=["api/routes.py"],
            impact_score=0.85,
            suggestion="更新测试",
        )
        assert shadow._should_trigger(impact) is True
    
    def test_should_not_trigger_low_impact(self, shadow):
        """测试低影响时不触发"""
        impact = CodeChangeImpact(
            changed_file="README.md",
            change_type="modified",
            affected_tests=[],
            affected_modules=[],
            impact_score=0.3,
            suggestion="",
        )
        assert shadow._should_trigger(impact) is False
