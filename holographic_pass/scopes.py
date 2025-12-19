import hashlib
from holographic_core import RustAccumulator

class SwarmScope:
    def __init__(self, swarm_name, parent_context, registry_ref):
        self.swarm_name = swarm_name
        self.ctx = parent_context
        self.reg = registry_ref
        
        # [Update] 构造 RustAccumulator 需传入 Domain Context
        self._backend = RustAccumulator(self.ctx.M_str, self.ctx.G_str, self.ctx.MAX_DEPTH, self.ctx.DOMAIN)
        self.swarm_prime = self.reg.register_agent(swarm_name)

    def track_sub_task(self, sub_agent_name):
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
        # [Security Fix #2] 位置敏感合并 (Positional-Binding)
        # 强制并行分支具有顺序敏感性，修复 "伪交换性" 漏洞
        # 我们通过将索引绑定到 Agent 身份上，强制生成不同的素数
        for idx, agent in enumerate(self.branch_ids):
            # 构造虚拟的 "Positional Identity": AgentName#Index
            # 这样即使是 {A, B} 和 {B, A}，实际上会映射为 {A#0, B#1} 和 {B#0, A#1}
            # 从而生成完全不同的素数集合，打破阿贝尔交换律
            positional_id = f"{agent}#{idx}"
            
            p = self.reg.register_agent(positional_id)
            primes_str.append(str(p))
            
        t_final_str, next_depth, ops_cost = self._computer.safe_merge_branches(
            str(self.base_t), 
            primes_str, 
            self.base_depth
        )
        
        return int(t_final_str), next_depth, ops_cost
