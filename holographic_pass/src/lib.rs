use pyo3::prelude::*;
use rug::{Integer, ops::Pow, integer::Order};
use sha2::{Sha256, Digest};
use rand::{Rng, thread_rng};
use std::{thread, time::Duration};

const MAX_STRING_LEN: usize = 4096; 

#[pymodule]
fn holographic_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<RustAccumulator>()?;
    Ok(())
}

#[pyclass]
struct RustAccumulator {
    modulus: Integer,
    current_t: Integer,
    depth: u64,
    max_depth: u64,
    generator: Integer,
    op_count: u64,
    max_op_limit: u64,
    domain_context: String, 
}

#[pymethods]
impl RustAccumulator {
    #[new]
    fn new(modulus_str: String, generator_str: String, max_depth: u64, domain: String) -> PyResult<Self> {
        Self::_validate_input(&modulus_str)?;
        Self::_validate_input(&generator_str)?;
        Self::_validate_input(&domain)?;
        
        // [Security Fix #5] FFI Panic Protection
        let m = Integer::from_str_radix(&modulus_str, 10)
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid modulus format"))?;
            
        let g = Integer::from_str_radix(&generator_str, 10)
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid generator format"))?;
        
        Ok(RustAccumulator {
            modulus: m,
            current_t: Integer::from(2),
            depth: 0,
            max_depth: max_depth,
            generator: g,
            op_count: 0,
            max_op_limit: 1_000_000,
            domain_context: domain,
        })
    }

    fn get_state(&self) -> String {
        self.current_t.to_string_radix(16)
    }

    fn get_depth(&self) -> u64 {
        self.depth
    }
    
    fn get_op_count(&self) -> u64 {
        self.op_count
    }

    fn hash_to_prime(&mut self, agent_id: String) -> PyResult<String> {
        Self::_validate_input(&agent_id)?;
        self._inject_computation_jitter(); // [Fix #3] CPU-Heavy Jitter
        
        let mut nonce = 0u64;
        let prefix = format!("{}:", self.domain_context);
        let prefix_bytes = prefix.as_bytes();
        let id_bytes = agent_id.as_bytes();

        loop {
            let mut candidate_bytes: Vec<u8> = Vec::new();
            for i in 0..4 {
                let mut hasher = Sha256::new();
                hasher.update(prefix_bytes);
                hasher.update(id_bytes);
                hasher.update(&nonce.to_le_bytes());
                hasher.update(&(i as u32).to_le_bytes());
                candidate_bytes.extend_from_slice(&hasher.finalize());
            }

            let mut candidate = Integer::from_digits(&candidate_bytes, Order::Msf);
            candidate.set_bit(1023, true); 
            candidate.set_bit(0, true);

            if candidate.is_probably_prime(64) != rug::integer::IsPrime::No {
                return Ok(candidate.to_string_radix(10));
            }

            nonce += 1;
            if nonce > 100_000 { // 降低 Loop 阈值防止 DoS
                 return Err(pyo3::exceptions::PyRuntimeError::new_err("Failed to find prime (nonce limit)"));
            }
        }
    }

    fn update_state(&mut self, agent_id: String) -> PyResult<String> {
        Self::_validate_input(&agent_id)?;
        self._check_op_limit()?;
        
        let (next_t, _) = self._compute_transition(agent_id)?;
        self.current_t = next_t.clone();
        self.depth += 1;
        Ok(next_t.to_string_radix(10))
    }

    /// [Security Fix #4] 区块链式快照更新
    /// 引入 prev_snapshot_hash 防止回滚攻击
    fn update_with_snapshot(&mut self, agent_id: String, segment_id: u64, prev_snapshot_hash: String) -> PyResult<(String, bool, String)> {
        Self::_validate_input(&agent_id)?;
        Self::_validate_input(&prev_snapshot_hash)?;
        self._check_op_limit()?;
        
        let (next_t, next_depth) = self._compute_transition(agent_id)?;

        if next_depth >= self.max_depth {
            let t_str = next_t.to_string_radix(10);
            
            // Hash Chain: Hash(Current_T || Prev_Hash)
            let mut hasher = Sha256::new();
            hasher.update(t_str.as_bytes());
            hasher.update(prev_snapshot_hash.as_bytes()); // Link to previous block
            let snapshot_hash = hex::encode(hasher.finalize());
            
            // New Seed derivation
            let new_seed = Integer::from_str_radix(&snapshot_hash, 16)
                .map_err(|_| pyo3::exceptions::PyValueError::new_err("Snapshot hash parse failed"))? 
                % &self.modulus;
            
            self.current_t = new_seed.clone();
            self.depth = 0;
            
            let snapshot_info = format!(
                r#"{{"segment_id": {}, "final_t": "{}", "snapshot_hash": "{}", "prev_hash": "{}"}}"#,
                segment_id, t_str, snapshot_hash, prev_snapshot_hash
            );
            
            Ok((self.current_t.to_string_radix(10), true, snapshot_info))
        } else {
            self.current_t = next_t.clone();
            self.depth = next_depth;
            Ok((self.current_t.to_string_radix(10), false, "".to_string()))
        }
    }

    fn safe_merge_branches(&mut self, base_t_str: String, primes_str: Vec<String>, base_depth: u64) -> PyResult<(String, u64, u64)> {
        Self::_validate_input(&base_t_str)?;
        for p in &primes_str { Self::_validate_input(p)?; }

        self._check_op_limit()?;
        self._inject_computation_jitter(); 

        let base_t = Integer::from_str_radix(&base_t_str, 10)
             .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid base_t format"))?;
             
        let mut ops_consumed = 0u64;
        
        let mut p_total = Integer::from(1);
        for p_str in primes_str {
            let p = Integer::from_str_radix(&p_str, 10)
                .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid prime format"))?;
            p_total *= p;
        }

        let term_path = base_t.pow_mod(&p_total, &self.modulus).unwrap(); 
        self.op_count += 1;
        ops_consumed += 1;

        let next_depth = base_depth + 1;
        let depth_hash_bytes = Sha256::digest(next_depth.to_string().as_bytes());
        let depth_hash_int = Integer::from_str_radix(&hex::encode(depth_hash_bytes), 16).unwrap();
        let term_depth = self.generator.clone().pow_mod(&depth_hash_int, &self.modulus).unwrap();
        self.op_count += 1;
        ops_consumed += 1;

        let t_final = (term_path * term_depth) % &self.modulus;

        Ok((t_final.to_string_radix(10), next_depth, ops_consumed))
    }

    #[staticmethod]
    fn safe_pow_mod(base_str: String, exp_str: String, modulus_str: String) -> PyResult<String> {
        Self::_validate_input(&base_str)?;
        Self::_validate_input(&exp_str)?;
        Self::_validate_input(&modulus_str)?;

        let base = Integer::from_str_radix(&base_str, 10)
             .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid base format"))?;
        let exp = Integer::from_str_radix(&exp_str, 10)
             .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid exp format"))?;
        let m = Integer::from_str_radix(&modulus_str, 10)
             .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid modulus format"))?;
             
        let result = base.pow_mod(&exp, &m).unwrap();
        Ok(result.to_string_radix(10))
    }

    // --- Helpers ---

    fn _compute_transition(&mut self, agent_id: String) -> PyResult<(Integer, u64)> {
        let p_str = self.hash_to_prime(agent_id)?; 
        let p_agent = Integer::from_str_radix(&p_str, 10).unwrap(); 

        let path_term = self.current_t.clone().pow_mod(&p_agent, &self.modulus).unwrap();
        self.op_count += 1;

        let depth_hash_bytes = Sha256::digest(self.depth.to_string().as_bytes());
        let depth_hash_int = Integer::from_str_radix(&hex::encode(depth_hash_bytes), 16).unwrap();
        
        let depth_term = self.generator.clone().pow_mod(&depth_hash_int, &self.modulus).unwrap();
        self.op_count += 1;

        let next_t = (path_term * depth_term) % &self.modulus;
        Ok((next_t, self.depth + 1))
    }

    /// [Fix #3] 真实算力干扰 (Computation-Heavy Jitter)
    /// 不再使用 sleep，而是进行真实的数学运算以模糊功耗特征
    fn _inject_computation_jitter(&self) {
        let mut rng = thread_rng();
        let loop_count = rng.gen_range(10..100); 
        let mut dummy = Integer::from(12345);
        let m = Integer::from(65537);
        // 执行无意义的模幂运算，消耗 CPU 周期
        for _ in 0..loop_count {
            dummy = dummy.pow_mod(&Integer::from(2), &m).unwrap();
        }
    }
    
    fn _check_op_limit(&self) -> PyResult<()> {
        if self.op_count > self.max_op_limit {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "DoS Protection: Operation count exceeded limit."
            ));
        }
        Ok(())
    }

    fn _validate_input(input: &str) -> PyResult<()> {
        if input.len() > MAX_STRING_LEN {
            return Err(pyo3::exceptions::PyValueError::new_err(
                format!("Input length {} exceeds maximum safety limit", input.len())
            ));
        }
        Ok(())
    }
}
