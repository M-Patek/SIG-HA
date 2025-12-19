import json
import secrets
import uuid
from cryptography.hazmat.primitives.asymmetric import rsa
from holographic_core import RustAccumulator

class CryptoContext:
    """
    [Phase 1] 全局加密上下文 (Security Hardened v3.0)
    """
    def __init__(self, bit_length=2048, max_depth=10, setup_mode="production", domain_id=None):
        self.MAX_DEPTH = max_depth
        
        # [Security Fix #1] 域分离配置
        # 如果没有提供 Domain ID，则生成一个随机的 UUID
        # 在生产环境中，这应该是一个固定的 Application ID
        self.DOMAIN = str(domain_id) if domain_id else str(uuid.uuid4())
        
        print(f"🔧 [System] Init CryptoContext | Domain: {self.DOMAIN} | Mode: {setup_mode}")
        
        # [Security Fix #2] 强制 Strong RSA 生成
        # 移除不安全的 secrets.randbits 分支
        print("🔐 [Security] Generating Strong RSA Modulus (Slow but Safe)...")
        key = rsa.generate_private_key(public_exponent=65537, key_size=bit_length)
        pub_nums = key.public_key().public_numbers()
        self.M = pub_nums.n
        self.G = 4 
        del key # 立即销毁私钥
            
        self.M_str = str(self.M)
        self.G_str = str(self.G)
        
        # 初始化 Rust 实例时传入 Domain
        try:
            self._prime_helper = RustAccumulator(self.M_str, self.G_str, self.MAX_DEPTH, self.DOMAIN)
        except Exception as e:
            print(f"🔥 [CRITICAL] Failed to init Rust core: {e}")
            raise

    def fast_pow(self, base, exp):
        return int(RustAccumulator.safe_pow_mod(str(base), str(exp), self.M_str))

class PrimeRegistry:
    def __init__(self, context):
        self.ctx = context
        self.cache = {} 
    
    def register_agent(self, agent_id):
        if agent_id in self.cache:
            return self.cache[agent_id]
        
        # Hash-to-Prime 现在包含了 Domain Prefix
        try:
            p_str = self.ctx._prime_helper.hash_to_prime(str(agent_id))
            p = int(p_str)
            self.cache[agent_id] = p
            return p
        except ValueError as e:
             # 处理 FFI 返回的安全错误
             print(f"❌ Prime generation failed for {agent_id}: {e}")
             raise

    def get_prime(self, agent_id):
        return self.register_agent(agent_id)

class HolographicAccumulator:
    def __init__(self, context):
        self.ctx = context
        # 传递 Domain 到每个累加器实例
        self._backend = RustAccumulator(context.M_str, context.G_str, context.MAX_DEPTH, context.DOMAIN)
        
        self.current_T = int(self._backend.get_state(), 16)
        self.depth = self._backend.get_depth()
        self.history = []

    def update_state(self, agent_id):
        try:
            t_next_str = self._backend.update_state(str(agent_id))
            self.current_T = int(t_next_str)
            self.depth = self._backend.get_depth()
            
            self.history.append({
                'depth': self.depth, 
                'agent': agent_id, 
                'T': self.current_T,
                'ops': self._backend.get_op_count()
            })
            return self.current_T
        except Exception as e:
            print(f"⚠️ State Update Failed: {e}")
            raise

    def get_op_count(self):
        return self._backend.get_op_count()

class SnapshotAccumulator(HolographicAccumulator):
    def __init__(self, context):
        super().__init__(context)
        self.snapshot_store = []
        self.segment_id = 0
        
    def update_state_with_check(self, agent_id, agent_prime=None):
        try:
            new_t_str, is_folded, snapshot_data = self._backend.update_with_snapshot(
                str(agent_id), 
                self.segment_id
            )
            
            self.current_T = int(new_t_str)
            self.depth = self._backend.get_depth()
            
            if is_folded:
                block = json.loads(snapshot_data)
                block["timestamp"] = __import__("time").time()
                self.snapshot_store.append(block)
                print(f"💾 [Snapshot] Atomically Folded Block #{self.segment_id}")
                self.segment_id += 1
            
            self.history.append({
                'depth': self.depth,
                'agent': agent_id,
                'T': self.current_T,
                'folded': is_folded,
                'ops': self._backend.get_op_count()
            })
            return self.current_T
        except Exception as e:
             print(f"⚠️ Snapshot Update Failed: {e}")
             raise
