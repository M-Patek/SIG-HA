import hashlib
import json
import time
from .models import AgentState

class StateSealer:
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
        
        anchor_raw = f"{current_t}|{payload_hash}|{metrics_str}|{state.nonce}|{state.timestamp}|{state.meta.total_op_count}"
        
        integrity_seal = hashlib.sha256(anchor_raw.encode()).hexdigest()
        
        return {
            "version": "v4.0-hardened",
            "header": {
                "trace_t": str(current_t),
                "integrity_seal": integrity_seal,
                "nonce": state.nonce,
                "timestamp": state.timestamp,
                "ops": state.meta.total_op_count
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
        
        recalc_anchor_raw = f"{header['trace_t']}|{recalc_payload_hash}|{metrics_str}|{header['nonce']}|{header['timestamp']}|{header['ops']}"
        
        recalc_seal = hashlib.sha256(recalc_anchor_raw.encode()).hexdigest()
        return recalc_seal == header['integrity_seal']

class TraceInspector:
    def __init__(self, context, registry_ref):
        self.ctx = context
        self.reg = registry_ref
        self.MAX_CLOCK_DRIFT = 300 

    def verify_path(self, target_t, claimed_witness_list, envelope_header=None):
        if envelope_header:
            ts = float(envelope_header.get('timestamp', 0))
            now = time.time()
            if abs(now - ts) > self.MAX_CLOCK_DRIFT:
                return False, f"Timestamp rejected: Drift {abs(now - ts):.2f}s > {self.MAX_CLOCK_DRIFT}s"

        simulated_t = 2
        simulated_depth = 0
        ops_counter = 0
        
        for agent_name in claimed_witness_list:
            p = self.reg.get_prime(agent_name)
            if not p: return False, f"Unknown agent: {agent_name}"
            
            # [Security Fix #4] 使用 ctx.fast_pow (Rust FFI) 加速验证
            # 原生的 pow(a,b,m) 在 2048 位下太慢，易遭 DoS
            path_term = self.ctx.fast_pow(simulated_t, p)
            ops_counter += 1
            
            depth_hash = int(hashlib.sha256(str(simulated_depth).encode()).hexdigest(), 16)
            depth_term = self.ctx.fast_pow(self.ctx.G, depth_hash)
            ops_counter += 1
            
            simulated_t = (path_term * depth_term) % self.ctx.M
            simulated_depth += 1
            
            if ops_counter > 5000: 
                return False, "DoS Protection: Verification Complexity Threshold Exceeded"
            
        if envelope_header and 'ops' in envelope_header:
             claimed_ops = int(envelope_header['ops'])
             if claimed_ops != ops_counter:
                 return False, f"Ops Integrity Violation: Claimed {claimed_ops} != Actual {ops_counter}"

        return str(simulated_t) == str(target_t), "Verification Passed"
