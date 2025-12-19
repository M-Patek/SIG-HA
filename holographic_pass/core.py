import secrets
from holographic_core import RustAccumulator  # 导入我们的 Rust 扩展

class CryptoContext:
    """
    [Phase 1] 全局加密上下文
    定义模数空间 M 和生成元 G，并作为 Rust 算力的统一入口
    """
    def __init__(self, bit_length=2048, max_depth=10, setup_mode="simulation"):
        self.MAX_DEPTH = max_depth
        self.G = 3  # 生成元
        
        if setup_mode == "simulation":
            # 模拟环境：生成一个随机的大整数作为模数 M
            self.M = secrets.randbits(bit_length)
        else:
            # 生产环境：这里应该加载 RSA Keygen 生成的安全模数 N
            self.M = secrets.randbits(bit_length)
            
        # [Critical] 将 M 转换为字符串，供 Rust 引擎使用 (避免 Python->Rust 的大数精度问题)
        self.M_str = str(self.M)
        
        # 创建一个共享的 Rust 累加器实例用于计算素数映射 (Stateless Helper)
        self._prime_helper = RustAccumulator(self.M_str, self.G)
        
        print(f"🌍 [System] Rust Core v2.0 Loaded | Modulus Bits: {self.M.bit_length()}")

    def fast_pow(self, base, exp):
        """
        [Optimization] 暴露 Rust 的高性能模幂运算给 Python 其他模块 (如 Scopes)
        """
        # 调用 Rust 的静态方法 (Rug backend)
        res_str = RustAccumulator.pow_mod_unsafe(str(base), str(exp), self.M_str)
        return int(res_str)

class PrimeRegistry:
    """
    [Phase 1] 素数身份注册表 (Rust 驱动版)
    利用 Rust 的确定性 Hash-to-Prime 算法，不再需要维护内存中的 lookup table
    """
    def __init__(self, context):
        self.ctx = context
        # 为了兼容旧代码的查询接口，保留一个缓存
        self.cache = {} 
    
    def register_agent(self, agent_id):
        """
        获取 Agent 的素数 ID。
        现在的逻辑是确定性的：只要 AgentID 相同，生成的 Prime 永远相同。
        """
        if agent_id in self.cache:
            return self.cache[agent_id]
        
        # 调用 Rust 引擎的 hash_to_prime
        p_str = self.ctx._prime_helper.hash_to_prime(str(agent_id))
        p = int(p_str)
        
        self.cache[agent_id] = p
        return p

    def get_prime(self, agent_id):
        return self.register_agent(agent_id)

class HolographicAccumulator:
    """
    [Phase 1] 核心代数累加器 (Rust Wrapper)
    所有繁重的模幂运算现在都由底层 Rust 引擎处理
    """
    def __init__(self, context):
        self.ctx = context
        # 初始化底层的 Rust 累加器
        self._backend = RustAccumulator(context.M_str, context.G)
        
        # 保持 Python 侧的状态同步
        self.current_T = int(self._backend.get_state(), 16) # Rust 返回 Hex
        self.depth = self._backend.get_depth()
        self.history = []

    def update_state(self, agent_id, agent_prime=None):
        """
        更新状态
        :param agent_id: Agent 的唯一标识
        """
        # 1. 调用 Rust 进行高性能计算
        t_next_str = self._backend.update_state(str(agent_id))
        
        # 2. 同步状态回 Python 对象
        self.current_T = int(t_next_str)
        self.depth = self._backend.get_depth()
        
        # 3. 记录日志 (用于调试/审计)
        self.history.append({
            'depth': self.depth, 
            'agent': agent_id, 
            'T': self.current_T
        })
        
        return self.current_T

class SnapshotAccumulator(HolographicAccumulator):
    """
    [Phase 1.3] 支持自动快照折叠的累加器
    """
    def __init__(self, context):
        super().__init__(context)
        self.snapshot_store = []
        self.segment_id = 0
        
    def _fold_state(self):
        # 快照哈希计算
        import hashlib
        t_bytes = str(self.current_T).encode()
        snapshot_hash = hashlib.sha256(t_bytes).hexdigest()
        
        block = {
            "segment_id": self.segment_id,
            "final_t": str(self.current_T)[:20] + "...",
            "depth_at_snapshot": self.depth,
            "snapshot_hash": snapshot_hash
        }
        self.snapshot_store.append(block)
        print(f"💾 [Snapshot] Block #{self.segment_id} 折叠归档.")
        
        # 计算新种子
        new_seed = int(snapshot_hash, 16) % self.ctx.M
        self.current_T = new_seed
        self.depth = 0
        self.segment_id += 1
        
        # 🚨 [CRITICAL FIX] 强制同步 Rust 后端状态！
        # 如果不加这行，Rust 还会继续用旧的 T 和 Depth 计算，导致 Python/Rust 状态分裂
        self._backend.set_state(str(new_seed), 0)

    def update_state_with_check(self, agent_id, agent_prime=None):
        if self.depth >= self.ctx.MAX_DEPTH:
            self._fold_state()
        return super().update_state(agent_id, agent_prime)
