import hashlib
from functools import reduce

class SwarmScope:
    """
    [Phase 2.2] 分级索引管理器 (Local Tracker)
    """
    def __init__(self, swarm_name, parent_context, registry_ref):
        self.swarm_name = swarm_name
        self.ctx = parent_context
        self.reg = registry_ref
        
        self.local_t = 2 
        self.local_depth = 0
        self.swarm_prime = self.reg.register_agent(swarm_name)

    def track_sub_task(self, sub_agent_name):
        p_sub = self.reg.register_agent(sub_agent_name)
        
        path_term = pow(self.local_t, p_sub, self.ctx.M)
        depth_term = pow(self.ctx.G, self.local_depth + 1, self.ctx.M)
        
        self.local_t = (path_term * depth_term) % self.ctx.M
        self.local_depth += 1

    def seal_and_export(self):
        proof_payload = f"{self.swarm_name}:{self.local_t}:{self.local_depth}"
        work_proof_hash = int(hashlib.sha256(proof_payload.encode()).hexdigest(), 16)
        
        return {
            "swarm_prime": self.swarm_prime,
            "work_proof": work_proof_hash,
            "complexity": self.local_depth
        }

def update_global_with_swarm(global_acc, swarm_result):
    """
    将 Swarm 结果注入全局主链
    """
    current_global_t = global_acc.current_T
    p_swarm = swarm_result['swarm_prime']
    
    # 身份项
    term_identity = pow(current_global_t, p_swarm, global_acc.ctx.M)
    
    # 扰动项 (Proof注入)
    proof = swarm_result['work_proof']
    effective_depth = global_acc.depth + swarm_result['complexity']
    term_perturbation = pow(global_acc.ctx.G, (proof + effective_depth), global_acc.ctx.M)
    
    new_global_t = (term_identity * term_perturbation) % global_acc.ctx.M
    
    global_acc.current_T = new_global_t
    global_acc.depth += 1
    return new_global_t

class ParallelScope:
    """
    [Phase 2.3] 并行路径合并算子 (Merging Operator)
    """
    def __init__(self, context, registry_ref, base_t, current_depth):
        self.ctx = context
        self.reg = registry_ref
        self.base_t = base_t
        self.base_depth = current_depth
        self.branch_factors = []
        
    def add_branch_result(self, agent_name):
        p_agent = self.reg.register_agent(agent_name)
        self.branch_factors.append(p_agent)

    def merge(self):
        if not self.branch_factors:
            return self.base_t, self.base_depth

        # 计算 P_total = P1 * P2 * ... * Pn (乘法交换律)
        p_total = reduce(lambda x, y: x * y, self.branch_factors)
        
        # T_new = (T_base ^ P_total * G ^ H(d+1)) mod M
        term_path = pow(self.base_t, p_total, self.ctx.M)
        
        next_depth = self.base_depth + 1
        depth_hash = int(hashlib.sha256(str(next_depth).encode()).hexdigest(), 16)
        term_depth = pow(self.ctx.G, depth_hash, self.ctx.M)
        
        t_final = (term_path * term_depth) % self.ctx.M
        
        return t_final, next_depth
