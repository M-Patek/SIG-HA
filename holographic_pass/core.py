import secrets
import hashlib
import sympy

class CryptoContext:
    """
    [Phase 1] 全局加密上下文
    定义模数空间 M 和生成元 G
    """
    def __init__(self, bit_length=2048, max_depth=10):
        # 生产环境请使用 RSA Keygen 生成 N = p*q
        # 这里模拟一个足够大的安全整数空间
        self.M = secrets.randbits(bit_length)
        self.G = 3  # 生成元
        self.MAX_DEPTH = max_depth
        print(f"🌍 [System] 全局模数空间 M 已初始化 (BitLength: {self.M.bit_length()})")

class PrimeRegistry:
    """
    [Phase 1] 素数身份注册表
    维护 AgentID <-> Prime 的双向映射
    """
    def __init__(self):
        self.registry = {}         # {agent_id: prime}
        self.reverse_registry = {} # {prime: agent_id}
        self.used_primes = set()
    
    def _generate_candidate_prime(self, bits=256):
        while True:
            candidate = secrets.randbits(bits) | 1 
            if sympy.isprime(candidate):
                return candidate

    def register_agent(self, agent_id):
        if agent_id in self.registry:
            return self.registry[agent_id]
        
        while True:
            p = self._generate_candidate_prime()
            if p not in self.used_primes:
                self.used_primes.add(p)
                self.registry[agent_id] = p
                self.reverse_registry[p] = agent_id
                # print(f"🐱 [Registry] Agent '{agent_id}' 绑定素数: {str(p)[:8]}...")
                return p

    def get_prime(self, agent_id):
        return self.registry.get(agent_id)

class HolographicAccumulator:
    """
    [Phase 1] 核心代数累加器
    公式: T_next = (T_prev ^ P_agent * G ^ H(depth)) mod M
    """
    def __init__(self, context):
        self.ctx = context
        self.current_T = 2
        self.depth = 0
        self.history = []

    def _hash_depth(self, depth):
        depth_bytes = str(depth).encode()
        return int(hashlib.sha256(depth_bytes).hexdigest(), 16)

    def update_state(self, agent_id, agent_prime):
        path_term = pow(self.current_T, agent_prime, self.ctx.M)
        depth_term = pow(self.ctx.G, self._hash_depth(self.depth), self.ctx.M)
        
        T_next = (path_term * depth_term) % self.ctx.M
        
        self.history.append({'depth': self.depth, 'agent': agent_id, 'T': T_next})
        self.current_T = T_next
        self.depth += 1
        return T_next

class SnapshotAccumulator(HolographicAccumulator):
    """
    [Phase 1.3] 支持自动快照折叠的累加器
    """
    def __init__(self, context):
        super().__init__(context)
        self.snapshot_store = []
        self.segment_id = 0
        
    def _fold_state(self):
        # 计算快照哈希
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
        
        # 重置状态 (Reseeding)
        new_seed = int(snapshot_hash, 16) % self.ctx.M
        self.current_T = new_seed
        self.depth = 0
        self.segment_id += 1

    def update_state_with_check(self, agent_id, agent_prime):
        if self.depth >= self.ctx.MAX_DEPTH:
            self._fold_state()
        return super().update_state(agent_id, agent_prime)
