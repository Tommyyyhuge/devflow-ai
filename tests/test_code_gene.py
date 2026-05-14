"""代码基因图谱测试"""

import pytest

from devflow.plugins.code_gene.gene_map import CodeGeneMap


class TestCodeGeneMap:
    @pytest.fixture
    def gene_map(self, tmp_path):
        class MockRepoMap:
            def analyze_project(self):
                return [
                    type('obj', (object,), {
                        'name': 'user.py',
                        'path': 'src/user.py',
                        'complexity': 5.0,
                        'imports': ['api', 'models'],
                    })(),
                ]

        return CodeGeneMap(MockRepoMap())

    def test_analyze_module(self, gene_map, tmp_path):
        """测试模块分析"""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def hello():\n    pass\n")

        metrics = gene_map.analyze_module(str(test_file))
        assert metrics.name == "test_module.py"
        assert metrics.lines_of_code == 3  # "def hello():\n    pass\n" 按 \n 分割得 3 行

    def test_get_hotspots(self, gene_map):
        """测试热点检测"""
        hotspots = gene_map.get_hotspots(top_n=5)
        assert isinstance(hotspots, list)
