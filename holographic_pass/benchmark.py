import time
import statistics
import hashlib
from .core import CryptoContext, PrimeRegistry
from .scopes import ParallelScope

class HolographicBenchmark:
    """
    [Phase 5] 极限压力测试
    """
    def __init__(self, context, registry_ref):
        self.ctx = context
        self.reg = registry_ref
        self.timings = []
        self.collision_set = set()
        
    def _simulate_op(self, t_curr, agent_name, depth):
        start = time.perf_counter()
        p = self.reg.register_agent(agent_name)
        
        path_term = pow(t_curr, p, self.ctx.M)
        depth_hash = int(hashlib.sha256(str(depth).encode()).hexdigest(), 16)
        depth_term = pow(self.ctx.G, depth_hash, self.ctx.M)
        t_next = (path_term * depth_term) % self.ctx.M
        
        self.timings.append((time.perf_counter() - start) * 1000)
        return t_next

    def run(self, iterations=100):
        print(f"🔥 [Benchmark] Start N={iterations} | Bits={self.ctx.M.bit_length()}")
        start_time = time.time()
        
        for i in range(iterations):
            # 模拟：Root -> Parallel(3 branches) -> End
            curr_t = 2 + i
            depth = 0
            curr_t = self._simulate_op(curr_t, "Root_Node", depth)
            depth += 1
            
            # Parallel
            scope = ParallelScope(self.ctx, self.reg, curr_t, depth)
            scope.add_branch_result("Worker_A")
            scope.add_branch_result("Worker_B")
            scope.add_branch_result("Worker_C")
            curr_t, depth = scope.merge()
            
            if curr_t in self.collision_set:
                print("💥 Collision detected!")
            self.collision_set.add(curr_t)
            
        print(f"✅ Benchmark Finished. Total Time: {time.time() - start_time:.4f}s")
        if self.timings:
            print(f"   Avg Latency: {statistics.mean(self.timings):.4f} ms")
