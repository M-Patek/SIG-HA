import json
import secrets
import uuid
from cryptography.hazmat.primitives.asymmetric import rsa
from holographic_core import RustAccumulator

class CryptoContext:
    def __init__(self, bit_length=2048, max_depth=10, setup_mode="production", domain_id=None):
        self.MAX_DEPTH = max_depth
        self.DOMAIN = str(domain_id) if domain_id else str(uuid.uuid4())
        
        print(f"🔧 [System] Init CryptoContext | Domain: {self.DOMAIN} | Mode: {setup_mode}")
        
        # [Security Fix #1] Trapdoor Risk Mitigation
        # 在生产模式下，应通过 MPC (Secure Multiparty Computation) 导入无陷门模数
        # 这里模拟 Strong RSA 生成，并显式警告私钥销毁的重要性
        print("🔐 [Security] Generating Strong RSA Modulus...")
        key = rsa.generate_private_key(public_exponent=65537, key_size=bit_length)
        pub_nums = key.public_key().public_numbers()
        self.M = pub_nums.n
        
        # [Fix] G=4 in Strong RSA Group
        # 4 = 2^2，是二次剩余。如果 p,q 是 Safe Primes，QR 子群阶数极大
        # 这里我们假定 key generation 产生了足够好的素数
        self.G = 4 
        
        # 💥 DESTROY PRIVATE KEY OBJECT IMMEDIATELY 💥
        del key 
            
        self.M_str = str(self.M)
        self.G_str = str(self.G)
        
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
        
        try:
            p_str = self.ctx._prime_helper.hash_to_prime(str(agent_id))
            p = int(p_str)
            self.cache[agent_id] = p
            return p
        except ValueError as e:
             print(f"❌ Prime generation failed for {agent_id}: {e}")
             raise

    def get_prime(self, agent_id):
        return self.register_agent(agent_id)

class HolographicAccumulator:
    def __init__(self, context):
        self.ctx = context
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
        # [Fix #4] Chain Genesis Hash
        self.last_snapshot_hash = "0" * 64 
        
    def update_state_with_check(self, agent_id, agent_prime=None):
        try:
            # [Fix #4] 传入 last_snapshot_hash 形成链式结构
            new_t_str, is_folded, snapshot_data = self._backend.update_with_snapshot(
                str(agent_id), 
                self.segment_id,
                self.last_snapshot_hash
            )
            
            self.current_T = int(new_t_str)
            self.depth = self._backend.get_depth()
            
            if is_folded:
                block = json.loads(snapshot_data)
                block["timestamp"] = __import__("time").time()
                
                # 验证链完整性
                if block.get("prev_hash") != self.last_snapshot_hash:
                     raise RuntimeError("Snapshot Chain Integrity Violation!")
                     
                self.snapshot_store.append(block)
                self.last_snapshot_hash = block["snapshot_hash"]
                
                print(f"💾 [Snapshot] Block #{self.segment_id} Linked & Sealed.")
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
