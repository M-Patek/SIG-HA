import json
import secrets
from cryptography.hazmat.primitives.asymmetric import rsa
from holographic_core import RustAccumulator

class CryptoContext:
    def __init__(self, bit_length=2048, max_depth=10, setup_mode="production"):
        self.MAX_DEPTH = max_depth
        print(f"🔧 [System] Initializing CryptoContext ({bit_length}-bit)...")
        
        if setup_mode == "simulation":
            key = rsa.generate_private_key(public_exponent=65537, key_size=bit_length)
            pub_nums = key.public_key().public_numbers()
            self.M = pub_nums.n
            self.G = 4 
            del key
        else:
            self.M = secrets.randbits(bit_length)
            self.G = 4
            
        self.M_str = str(self.M)
        self.G_str = str(self.G)
        
        # 初始化辅助 Rust 实例
        try:
            self._prime_helper = RustAccumulator(self.M_str, self.G_str, self.MAX_DEPTH)
        except Exception as e:
            # [Security Fix #5] 捕捉可能的 Rust 初始化验证错误
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
        
        # Rust 侧包含 hash_to_prime 的 input validation
        p_str = self.ctx._prime_helper.hash_to_prime(str(agent_id))
        p = int(p_str)
        self.cache[agent_id] = p
        return p

    def get_prime(self, agent_id):
        return self.register_agent(agent_id)

class HolographicAccumulator:
    def __init__(self, context):
        self.ctx = context
        self._backend = RustAccumulator(context.M_str, context.G_str, context.MAX_DEPTH)
        
        self.current_T = int(self._backend.get_state(), 16)
        self.depth = self._backend.get_depth()
        self.history = []

    def update_state(self, agent_id):
        # 任何来自 Rust 的 Error (如 Input too long, Ops Limit) 都会转为 Python Exception
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
        
    def get_op_count(self):
        return self._backend.get_op_count()

class SnapshotAccumulator(HolographicAccumulator):
    def __init__(self, context):
        super().__init__(context)
        self.snapshot_store = []
        self.segment_id = 0
        
    def update_state_with_check(self, agent_id, agent_prime=None):
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
