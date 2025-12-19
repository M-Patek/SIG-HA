use pyo3::prelude::*;
use rug::{Integer, ops::Pow, integer::Order};
use sha2::{Sha256, Digest};
use rand::{Rng, thread_rng};
use std::{thread, time::Duration};

const MAX_STRING_LEN: usize = 4096; // [Security Fix #5] 限制输入字符串最大 4KB

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
}

#[pymethods]
impl RustAccumulator {
    #[new]
    fn new(modulus_str: String, generator_str: String, max_depth: u64) -> PyResult<Self> {
        // [Security Fix #5] 构造函数输入校验
        Self::_validate_input(&modulus_str)?;
        Self::_validate_input(&generator_str)?;
        
        let m = Integer::from_str_radix(&modulus_str, 10).unwrap();
        let g = Integer::from_str_radix(&generator_str, 10).unwrap();
        
        Ok(RustAccumulator {
            modulus: m,
            current_t: Integer::from(2),
            depth: 0,
            max_depth: max_depth,
            generator: g,
            op_count: 0,
            max_op_limit: 1_000_000,
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

    /// [Security Fix #2] Hash-to-Prime with Jitter
    fn hash_to_prime(&mut self, agent_id: String) -> PyResult<String> {
        Self::_validate_input(&agent_id)?; // FFI 检查
        self._inject_jitter(); 
        
        let mut nonce = 0u64;
        let input_bytes = agent_id.as_bytes();

        loop {
            let mut candidate_bytes: Vec<u8> = Vec::new();
            for i in 0..4 {
                let mut hasher = Sha256::new();
                hasher.update(input_bytes);
                hasher.update(&nonce.to_le_bytes());
                hasher.update(&(i as u32).to_le_bytes());
                candidate_bytes.extend_from_slice(&hasher.finalize());
            }

            let mut candidate = Integer::from_digits(&candidate_bytes, Order::Msf);
            
            // [Security Fix #3] 弱素数防御
            // 严格控制位长，消除“合数拆解”歧义
            candidate.set_bit(1023, true); 
            candidate.set_bit(0, true);

            // 使用 64 轮 Miller-Rabin 测试 (Error prob < 2^-128)
            // 配合 Jitter，这足以抵御针对性的合数注入攻击
            if candidate.is_probably_prime(64) != rug::integer::IsPrime::No {
                return Ok(candidate.to_string_radix(10));
            }

            nonce += 1;
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

    fn update_with_snapshot(&mut self, agent_id: String, segment_id: u64) -> PyResult<(String, bool, String)> {
        Self::_validate_input(&agent_id)?;
        self._check_op_limit()?;
        
        let (next_t, next_depth) = self._compute_transition(agent_id)?;

        if next_depth >= self.max_depth {
            let t_str = next_t.to_string_radix(10);
            let mut hasher = Sha256::new();
            hasher.update(t_str.as_bytes());
            let snapshot_hash = hex::encode(hasher.finalize());
            
            let new_seed = Integer::from_str_radix(&snapshot_hash, 16).unwrap() % &self.modulus;
            
            self.current_t = new_seed.clone();
            self.depth = 0;
            
            let snapshot_info = format!(
                r#"{{"segment_id": {}, "final_t": "{}", "snapshot_hash": "{}"}}"#,
                segment_id, t_str, snapshot_hash
            );
            
            Ok((self.current_t.to_string_radix(10), true, snapshot_info))
        } else {
            self.current_t = next_t.clone();
            self.depth = next_depth;
            Ok((self.current_t.to_string_radix(10), false, "".to_string()))
        }
    }

    /// [Security Fix #1] 返回消耗的 OpCount，以便 Python 端累计
    /// Returns: (t_final_str, next_depth, ops_consumed)
    fn safe_merge_branches(&mut self, base_t_str: String, primes_str: Vec<String>, base_depth: u64) -> PyResult<(String, u64, u64)> {
        Self::_validate_input(&base_t_str)?;
        // 这里的 primes_str 已经在 Python 侧经过 get_prime 验证，风险较低，但仍需小心
        for p in &primes_str {
             Self::_validate_input(p)?;
        }

        self._check_op_limit()?;
        self._inject_jitter(); 

        let base_t = Integer::from_str_radix(&base_t_str, 10).unwrap();
        let mut ops_consumed = 0u64;
        
        let mut p_total = Integer::from(1);
        for p_str in primes_str {
            let p = Integer::from_str_radix(&p_str, 10).unwrap();
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

        let base = Integer::from_str_radix(&base_str, 10).unwrap();
        let exp = Integer::from_str_radix(&exp_str, 10).unwrap();
        let m = Integer::from_str_radix(&modulus_str, 10).unwrap();
        let result = base.pow_mod(&exp, &m).unwrap();
        Ok(result.to_string_radix(10))
    }

    // --- Helpers ---

    fn _compute_transition(&mut self, agent_id: String) -> PyResult<(Integer, u64)> {
        let p_str = self.hash_to_prime(agent_id)?; // Propagate Jitter & Validation
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

    fn _inject_jitter(&self) {
        let mut rng = thread_rng();
        let delay_micros = rng.gen_range(50..500); // [Fix #2] Timing Side-Channel Mitigation
        thread::sleep(Duration::from_micros(delay_micros));
    }
    
    fn _check_op_limit(&self) -> PyResult<()> {
        if self.op_count > self.max_op_limit {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "DoS Protection: Operation count exceeded limit (Complexity Attack Detected)."
            ));
        }
        Ok(())
    }

    /// [Security Fix #5] 内存溢出防御
    fn _validate_input(input: &str) -> PyResult<()> {
        if input.len() > MAX_STRING_LEN {
            return Err(pyo3::exceptions::PyValueError::new_err(
                format!("Input length {} exceeds maximum safety limit {}", input.len(), MAX_STRING_LEN)
            ));
        }
        Ok(())
    }
}
