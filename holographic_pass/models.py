from dataclasses import dataclass, field
from typing import List, Any

@dataclass
class HolographicMeta:
    """
    [Phase 2.1] 全息元数据结构
    """
    trace_t: int = 2          # 当前代数指纹 (T)
    depth: int = 0            # 当前深度 (d)
    segment_id: int = 0       # 当前折叠片段 ID
    path_log: List[str] = field(default_factory=list) # 仅用于人类可读审计，不做验证依据

@dataclass
class AgentState:
    """
    [Phase 2.1] 全局状态容器
    """
    task_id: str
    payload: Any              # 业务数据
    meta: HolographicMeta = field(default_factory=HolographicMeta)
    
    def summary(self):
        return f"[State] Depth: {self.meta.depth} | T: {str(self.meta.trace_t)[:10]}..."
