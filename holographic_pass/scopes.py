import hashlib
from holographic_core import RustAccumulator

class SwarmScope:
    def __init__(self, swarm_name, parent_context, registry_ref):
        self.swarm_name = swarm_name
        self.ctx = parent_context
        self.reg = registry_ref
        self._backend = RustAccumulator(self.ctx.M_str, self.ctx.G_str, self.ctx.MAX_DEPTH)
        self.swarm_prime = self.reg.register_agent(swarm_name)

    def track_sub_task(self, sub_agent_name):
        # 任何错误 (FFI Validation, DoS) 都会在这里抛出
        self._backend.update_state(str(sub_agent_name))

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
    """
    [Phase 2.3] 并行路径合并算子 (Safe Rust Version with Complexity Tracking)
    """
    def __init__(self, context, registry_ref, base_t, current_depth):
        self.ctx = context
        self.reg = registry_ref
        self.base_t = base_t
        self.base_depth = current_depth
        self.branch_ids = []
        # 借用 Context 的 helper 进行计算
        self._computer = self.ctx._prime_helper 

    def add_branch_result(self, agent_name):
        self.branch_ids.append(agent_name)

    def merge(self):
        """
        返回: (new_t, new_depth, ops_cost)
        """
        if not self.branch_ids:
            return self.base_t, self.base_depth, 0

        primes_str = []
        for agent in self.branch_ids:
            p = self.reg.register_agent(agent)
            primes_str.append(str(p))
            
        # [Security Fix #1] 获取 Rust 返回的精确 Ops Cost
        t_final_str, next_depth, ops_cost = self._computer.safe_merge_branches(
            str(self.base_t), 
            primes_str, 
            self.base_depth
        )
        
        return int(t_final_str), next_depth, ops_cost
