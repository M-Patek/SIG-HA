import hashlib
import json
import sympy
from .models import AgentState

class StateSealer:
    """
    [Phase 3.1] 状态锚定与数据锁定
    """
    @staticmethod
    def _compute_payload_hash(payload):
        if isinstance(payload, dict):
            s = json.dumps(payload, sort_keys=True)
        else:
            s = str(payload)
        return hashlib.sha256(s.encode()).hexdigest()

    @staticmethod
    def seal(state: AgentState, extra_metrics: dict = None):
        payload_hash = StateSealer._compute_payload_hash(state.payload)
        current_t = state.meta.trace_t
        metrics_str = json.dumps(extra_metrics) if extra_metrics else "{}"
        
        # Anchor String
        anchor_raw = f"{current_t}|{payload_hash}|{metrics_str}"
        integrity_seal = hashlib.sha256(anchor_raw.encode()).hexdigest()
        
        return {
            "version": "v1.0",
            "header": {
                "trace_t": str(current_t),
                "integrity_seal": integrity_seal,
            },
            "body": {
                "payload": state.payload,
                "metrics": extra_metrics
            }
        }

    @staticmethod
    def verify(envelope):
        header = envelope['header']
        body = envelope['body']
        
        recalc_payload_hash = StateSealer._compute_payload_hash(body['payload'])
        metrics_str = json.dumps(body['metrics']) if body['metrics'] else "{}"
        recalc_anchor_raw = f"{header['trace_t']}|{recalc_payload_hash}|{metrics_str}"
        recalc_seal = hashlib.sha256(recalc_anchor_raw.encode()).hexdigest()
        
        return recalc_seal == header['integrity_seal']

class TraceInspector:
    """
    [Phase 3.2] 全息侦探与验证
    """
    def __init__(self, context, registry_ref):
        self.ctx = context
        self.reg = registry_ref

    def verify_path(self, target_t, claimed_witness_list):
        simulated_t = 2
        simulated_depth = 0
        
        for agent_name in claimed_witness_list:
            p = self.reg.get_prime(agent_name)
            if not p: return False, f"Unknown agent: {agent_name}"
            
            path_term = pow(simulated_t, p, self.ctx.M)
            depth_hash = int(hashlib.sha256(str(simulated_depth).encode()).hexdigest(), 16)
            depth_term = pow(self.ctx.G, depth_hash, self.ctx.M)
            
            simulated_t = (path_term * depth_term) % self.ctx.M
            simulated_depth += 1
            
        return str(simulated_t) == str(target_t), "Verification Logic Completed"

class TopologyGuard:
    """
    [Phase 4.1] 拓扑合法性校验
    """
    def __init__(self, allowed_transitions):
        self.allowed_transitions = allowed_transitions
    
    def check_access(self, current_agent_name, state):
        history = state.meta.path_log
        last_agent = history[-1] if history else "Start_Node"
        allowed = self.allowed_transitions.get(last_agent, [])
        return current_agent_name in allowed

class HighSecurityGate:
    """
    [Phase 4.2] 高权限准入控制
    """
    def __init__(self, inspector_ref):
        self.inspector = inspector_ref
        
    def require_authority(self, state, required_role_name):
        # 1. Math Verification
        is_valid, _ = self.inspector.verify_path(state.meta.trace_t, state.meta.path_log)
        if not is_valid: return False
        
        # 2. Role Existence
        return required_role_name in state.meta.path_log
