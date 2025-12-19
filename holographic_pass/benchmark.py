import time
import statistics
import hashlib
from .core import CryptoContext, PrimeRegistry
from .scopes import ParallelScope

class HolographicBenchmark:
    """
    [Phase 5] 极限压力测试 (适配 Rust 核心版)
    """
    def __init__(self, context, registry_ref):
        self.ctx = context
        self.reg = registry_ref
        self.timings = []
        self.collision_set = set()
        
    def _simulate_op(self, t_curr, agent_name, depth):
        # 这里的模拟操作用于验证数学正确性，因此保留 Python 原生实现逻辑
        # 但调用了确定性的 PrimeRegistry (基于 Rust)
        start = time.perf_counter()
        p = self.reg.register_agent(agent_name)
        
        # 注意：这里我们依然用 Python 的 pow 进行对比测试
        # 如果想测试纯 Rust 链路，请参考 run_system_test
        path_term = pow(t_curr, p, self.ctx.M)
        depth_hash = int(hashlib.sha256(str(depth).encode()).hexdigest(), 16)
        depth_term = pow(self.ctx.G, depth_hash, self.ctx.M)
        t_next = (path_term * depth_term) % self.ctx.M
        
        self.timings.append((time.perf_counter() - start) * 1000)
        return t_next

    def run_system_test(self, iterations=100):
        """
        [New] 系统级测试：直接调用 Rust 封装好的累加器，测试真实的生产环境性能
        """
        from .core import HolographicAccumulator
        
        print(f"🔥 [System Test] Start N={iterations} | Rust Backend Active")
        acc = HolographicAccumulator(self.ctx)
        
        start_time = time.time()
        latencies = []
        
        for i in range(iterations):
            t0 = time.perf_counter()
            # 直接调用 Rust 封装接口
            acc.update_state(f"Agent_{i}")
            latencies.append((time.perf_counter() - t0) * 1000)
            
        total_time = time.time() - start_time
        print(f"✅ System Test Finished. Total Time: {total_time:.4f}s")
        print(f"   Avg Latency (Rust): {statistics.mean(latencies):.4f} ms")
        print(f"   Throughput: {iterations / total_time:.2f} ops/sec")

    def run(self, iterations=100):
        print(f"⚠️ [Simulation] Running Python-side validation logic (Slower)...")
        print(f"🔥 [Benchmark] Start N={iterations} | Bits={self.ctx.M.bit_length()}")
        start_time = time.time()
        
        for i in range(iterations):
            # 模拟：Root -> Parallel(3 branches) -> End
            curr_t = 2 + i
            depth = 0
            curr_t = self._simulate_op(curr_t, "Root_Node", depth)
            depth += 1
            
            # Parallel Scope
            # 这里的 scope.merge() 已经使用了 Rust 加速
            scope = ParallelScope(self.ctx, self.reg, curr_t, depth)
            scope.add_branch_result("Worker_A")
            scope.add_branch_result("Worker_B")
            scope.add_branch_result("Worker_C")
            curr_t, depth = scope.merge()
            
            if curr_t in self.collision_set:
                print("💥 Collision detected!")
            self.collision_set.add(curr_t)
            
        print(f"✅ Simulation Finished. Total Time: {time.time() - start_time:.4f}s")
        if self.timings:
            print(f"   Avg Latency (Python logic): {statistics.mean(self.timings):.4f} ms")
