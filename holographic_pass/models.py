from dataclasses import dataclass, field
from typing import List, Any
import time
import secrets

@dataclass
class HolographicMeta:
    trace_t: int = 2          
    depth: int = 0            
    segment_id: int = 0       
    path_log: List[str] = field(default_factory=list)
    # [Security Fix #2] 记录路径总算力消耗，用于 DoS 审计
    total_op_count: int = 0

@dataclass
class AgentState:
    task_id: str
    payload: Any
    meta: HolographicMeta = field(default_factory=HolographicMeta)
    
    nonce: str = field(default_factory=lambda: secrets.token_hex(16))
    timestamp: float = field(default_factory=time.time)
    
    def summary(self):
        return f"[State] Depth: {self.meta.depth} | Ops: {self.meta.total_op_count} | T: {str(self.meta.trace_t)[:10]}..."
