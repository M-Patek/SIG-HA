import hashlib
from functools import reduce
from holographic_core import RustAccumulator

class SwarmScope:
    """
    [Phase 2.2] 分级索引管理器 (Local Tracker) - Rust Accelerated
    """
    def __init__(self, swarm_name, parent_context, registry_ref):
        self.swarm_name = swarm_name
        self.ctx = parent_context
        self.reg = registry_ref
        
        # 优化：Swarm 内部也直接使用 Rust 引擎处理子任务
        self._backend = RustAccumulator(self.ctx.M_str, self.ctx.G)
        self.swarm_prime = self.reg.register_agent(swarm_name)

    def track_sub_task(self, sub_agent_name):
        # 调用 Rust 后端
        self._backend.update_state(str(sub_agent_name))

    def seal_and_export(self):
        # 从 Rust 后端获取结果
        local_t = int(self._backend.get_state(), 16)
        local_depth = self._backend.get_depth()
        
        proof_payload = f"{self.swarm_name}:{local_t}:{local_depth}"
        work_proof_hash = int(hashlib.sha256(proof_payload.encode()).hexdigest(), 16)
        
        return {
            "swarm_prime": self.swarm_prime,
            "work_proof": work_proof_hash,
            "complexity": local_depth
        }

def update_global_with_swarm(global_acc, swarm_result):
    """
    将 Swarm 结果注入全局主链 - Rust Accelerated
    """
    ctx = global_acc.ctx
    current_global_t = global_acc.current_T
    p_swarm = swarm_result['swarm_prime']
    
    # ⚡ [Optimization] 使用 Rust 加速大数模幂
    term_identity = ctx.fast_pow(current_global_t, p_swarm)
    
    # 扰动项
    proof = swarm_result['work_proof']
    effective_depth = global_acc.depth + swarm_result['complexity']
    
    # ⚡ [Optimization] 使用 Rust 加速
    term_perturbation = ctx.fast_pow(ctx.G, (proof + effective_depth))
    
    new_global_t = (term_identity * term_perturbation) % ctx.M
    
    # 手动更新 Python 侧状态
    global_acc.current_T = new_global_t
    global_acc.depth += 1
    
    # 🚨 [Sync] 必须同步状态回全局累加器的 Rust 后端
    global_acc._backend.set_state(str(new_global_t), global_acc.depth)
    
    return new_global_t

class ParallelScope:
    """
    [Phase 2.3] 并行路径合并算子 (Merging Operator) - Rust Accelerated
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

        # 计算 P_total = P1 * P2 * ... * Pn
        p_total = reduce(lambda x, y: x * y, self.branch_factors)
        
        # ⚡ [Optimization] 使用 Rust 加速核心计算: (T_base ^ P_total) mod M
        term_path = self.ctx.fast_pow(self.base_t, p_total)
        
        next_depth = self.base_depth + 1
        depth_hash = int(hashlib.sha256(str(next_depth).encode()).hexdigest(), 16)
        
        # ⚡ [Optimization] 使用 Rust 加速
        term_depth = self.ctx.fast_pow(self.ctx.G, depth_hash)
        
        t_final = (term_path * term_depth) % self.ctx.M
        
        return t_final, next_depth
