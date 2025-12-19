import hashlib
from holographic_core import RustAccumulator

class SwarmScope:
    def __init__(self, swarm_name, parent_context, registry_ref):
        self.swarm_name = swarm_name
        self.ctx = parent_context
        self.reg = registry_ref
        
        self._backend = RustAccumulator(self.ctx.M_str, self.ctx.G_str, self.ctx.MAX_DEPTH, self.ctx.DOMAIN)
        self.swarm_prime = self.reg.register_agent(swarm_name)

    def track_sub_task(self, sub_agent_name):
        # [Security Fix #2] 获取当前 Rust 状态作为 expected_prev_t
        # 虽然这看起来是多余的（自己查自己），但在 FFI 边界这是一种良好的断言机制
        # 实际场景中，prev_t 可能来自客户端请求的 Proof
        current_state_hex = self._backend.get_state()
        current_t = int(current_state_hex, 16)
        
        self._backend.update_state(str(sub_agent_name), str(current_t))

    def seal_and_export(self):
        local_t = int(self._backend.get_state(), 16)
        local_depth = self._backend.get_depth()
        op_usage = self._backend.get_op_count()
        
        proof_payload = f"{self.swarm_name}:{local_t}:{local_depth}"
        work_proof_hash = int(hashlib.sha256(proof_payload.encode()).hexdigest(), 16)
        
        return {
            "swarm_prime": self.swarm_prime,
            "work_proof": work_proof_hash,
            "complexity": local_depth,
            "ops": op_usage
        }

class ParallelScope:
    def __init__(self, context, registry_ref, base_t, current_depth):
        self.ctx = context
        self.reg = registry_ref
        self.base_t = base_t
        self.base_depth = current_depth
        self.branch_ids = []
        self._computer = self.ctx._prime_helper 

    def add_branch_result(self, agent_name):
        self.branch_ids.append(agent_name)

    def merge(self):
        if not self.branch_ids:
            return self.base_t, self.base_depth, 0

        primes_str = []
        # [Security Fix #1] Positional Binding + Cascaded Merge
        # Python 侧依然保留 Position ID 以生成不同素数
        # Rust 侧现在执行级联模幂，因此传递的顺序至关重要
        for idx, agent in enumerate(self.branch_ids):
            positional_id = f"{agent}#{idx}"
            p = self.reg.register_agent(positional_id)
            primes_str.append(str(p))
            
        t_final_str, next_depth, ops_cost = self._computer.safe_merge_branches(
            str(self.base_t), 
            primes_str, 
            self.base_depth
        )
        
        return int(t_final_str), next_depth, ops_cost
