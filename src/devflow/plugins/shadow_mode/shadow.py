"""影子模式——AI 结对编程伙伴"""

from dataclasses import dataclass
from typing import Callable
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


@dataclass
class CodeChangeImpact:
    """代码变更影响分析"""
    changed_file: str
    change_type: str
    affected_tests: list[str]
    affected_modules: list[str]
    impact_score: float
    suggestion: str


class ShadowMode:
    """影子模式——静默观察，适时建议"""
    
    def __init__(
        self,
        agent,
        repomap,
        callback: Callable[[CodeChangeImpact], None] | None = None,
        impact_threshold: float = 0.7,
    ):
        if not HAS_WATCHDOG:
            raise ImportError("shadow mode requires 'watchdog'. Run: pip install watchdog")
        
        self.agent = agent
        self.repomap = repomap
        self.callback = callback or self._default_callback
        self.impact_threshold = impact_threshold
        self.observer = None
        self.is_running = False
    
    def start(self, watch_path: str = ".") -> None:
        """启动影子模式"""
        if self.is_running:
            return
        
        event_handler = ShadowEventHandler(self._on_file_changed)
        self.observer = Observer()
        self.observer.schedule(event_handler, watch_path, recursive=True)
        self.observer.start()
        self.is_running = True
        print(f"👥 影子模式已启动，监听: {watch_path}")
    
    def stop(self) -> None:
        """停止影子模式"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.is_running = False
            print("👥 影子模式已停止")
    
    def _on_file_changed(self, event):
        """文件变化回调"""
        if event.is_directory:
            return
        
        file_path = event.src_path
        if not self._is_source_file(file_path):
            return
        
        impact = self._analyze_impact(file_path)
        if self._should_trigger(impact):
            self.callback(impact)
    
    def _analyze_impact(self, file_path: str) -> CodeChangeImpact:
        """分析变更影响"""
        raw_impact = self.repomap.analyze_impact(file_path)
        impact = CodeChangeImpact(
            changed_file=file_path,
            change_type="modified",
            affected_tests=getattr(raw_impact, 'affected_tests', []),
            affected_modules=getattr(raw_impact, 'affected_modules', []),
            impact_score=getattr(raw_impact, 'score', 0.0),
            suggestion="",
        )
        impact.suggestion = self.agent.suggest_follow_up(impact)
        return impact
    
    def _should_trigger(self, impact: CodeChangeImpact) -> bool:
        """判断是否触发建议"""
        return impact.impact_score >= self.impact_threshold
    
    def _is_source_file(self, file_path: str) -> bool:
        """检查是否是源码文件"""
        source_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.md'}
        return Path(file_path).suffix in source_extensions
    
    def _default_callback(self, impact: CodeChangeImpact) -> None:
        """默认通知方式"""
        print(f"\n💡 影子模式建议:")
        print(f"   你修改了: {impact.changed_file}")
        print(f"   影响度: {impact.impact_score:.0%}")
        print(f"   建议: {impact.suggestion}")
        print()


class ShadowEventHandler(FileSystemEventHandler):
    """文件系统事件处理器"""
    
    def __init__(self, callback):
        self.callback = callback
    
    def on_modified(self, event):
        self.callback(event)
    
    def on_created(self, event):
        self.callback(event)
