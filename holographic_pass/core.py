import json
import secrets
import uuid
import time
from holographic_core import RustAccumulator

class CryptoContext:
    def __init__(self, bit_length=2048, max_depth=10, setup_mode="production", domain_id=None):
        self.MAX_DEPTH = max_depth
        self.DOMAIN = str(domain_id) if domain_id else str(uuid.uuid4())
        
        print(f"🔧 [System] Init CryptoContext | Domain: {self.DOMAIN} | Mode: {setup_mode}")
        
        # [Security Fix #5] 使用 Rust 侧生成的安全 RSA 模数
        # 避免在 Python 内存中处理私钥
        print("🔐 [Security] Delegating Safe Modulus Generation to Rust Core...")
        try:
            # bit_length 必须传递给 Rust
            self.M_str = RustAccumulator.generate_safe_modulus(bit_length)
            self.M = int(self.M_str)
            self.G = 4
            self.G_str = str(self.G)
        except Exception as e:
            print(f"🔥 [CRITICAL] Modulus generation failed: {e}")
            raise
        
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
        # [Security Fix #4] 请求限流 (Rate Limiting)
        self.request_log = {}
        self.RATE_LIMIT_WINDOW = 1.0 # 1秒
        self.MAX_REQUESTS_PER_WINDOW = 100 
    
    def register_agent(self, agent_id):
        # DoS Protection: Rate Limiting
        now = time.time()
        # 简单清理过期记录
        self.request_log = {k: v for k, v in self.request_log.items() if now - v < self.RATE_LIMIT_WINDOW}
        
        # 全局限流 (简单实现，实际应针对 IP 或 Session)
        if len(self.request_log) > self.MAX_REQUESTS_PER_WINDOW:
             raise RuntimeError("Rate Limit Exceeded: Too many prime generation requests")
        
        self.request_log[agent_id] = now

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
            # [Security Fix #2] 传递 expected_prev_t 防止回滚
            t_next_str = self._backend.update_state(
                str(agent_id), 
                str(self.current_T)
            )
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
        self.last_snapshot_hash = "0" * 64 
        
    def update_state_with_check(self, agent_id, agent_prime=None):
        try:
            # [Security Fix #2] 同样传递 expected_prev_t
            new_t_str, is_folded, snapshot_data = self._backend.update_with_snapshot(
                str(agent_id), 
                self.segment_id,
                self.last_snapshot_hash,
                str(self.current_T) 
            )
            
            self.current_T = int(new_t_str)
            self.depth = self._backend.get_depth()
            
            if is_folded:
                block = json.loads(snapshot_data)
                block["timestamp"] = __import__("time").time()
                
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
