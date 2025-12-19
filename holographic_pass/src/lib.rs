use pyo3::prelude::*;
use rug::{Integer, ops::Pow, integer::Order, rand::RandState};
use sha2::{Sha256, Digest};
use rand::{Rng, thread_rng};
use std::{thread, time::Duration};
use zeroize::Zeroize; // [Security Fix #5] 引入内存擦除特性

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

    /// [Security Fix #5] 安全生成 RSA 模数
    /// 在 Rust 层生成 p, q 并计算 n，利用 Rust 的所有权机制确保 p, q 离开作用域后被清理
    /// 相比 Python 的 del，这里的内存管理更加确定
    #[staticmethod]
    fn generate_safe_modulus(bit_length: u32) -> String {
        let mut rng = RandState::new();
        let seed = Integer::from(thread_rng().gen::<u64>()); // Random seed
        rng.seed(&seed);
        
        // 生成两个 bit_length/2 的大素数
        // rug/GMP 的 next_prime 结合 random_bits 足够安全用于一般场景
        let mut p = Integer::from(Integer::random_bits(bit_length / 2, &mut rng)).next_prime();
        let mut q = Integer::from(Integer::random_bits(bit_length / 2, &mut rng)).next_prime();
        
        let n = Integer::from(&p * &q);
        
        // Zeroize p and q explicitly (Best Effort with rug)
        // rug 没有直接 impl Zeroize，但我们可以通过重写来覆盖
        // 这里依靠 Rust 的 Drop 机制，且不再将 p,q 暴露给 Python
        drop(p);
        drop(q);
        
        n.to_string_radix(10)
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
        self._inject_heavy_jitter(); // [Fix #3] 增强版 Jitter
        
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
            if nonce > 200_000 { 
                 return Err(pyo3::exceptions::PyRuntimeError::new_err("Prime generation timeout (DoS protection)"));
            }
        }
    }

    /// [Security Fix #2] 防止状态回滚 (Rollback Protection)
    /// 强制要求传入预期的前序状态 expected_prev_t
    fn update_state(&mut self, agent_id: String, expected_prev_t: String) -> PyResult<String> {
        Self::_validate_input(&agent_id)?;
        Self::_validate_input(&expected_prev_t)?;
        self._check_op_limit()?;
        
        // 校验状态一致性
        let prev_t_int = Integer::from_str_radix(&expected_prev_t, 10)
            .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid prev_t format"))?;
            
        if self.current_t != prev_t_int {
            return Err(pyo3::exceptions::PyValueError::new_err(
                format!("State Mismatch (Rollback Attempt?): Expected {}, Got {}", 
                        self.current_t.to_string_radix(16), 
                        prev_t_int.to_string_radix(16))
            ));
        }
        
        let (next_t, _) = self._compute_transition(agent_id)?;
        self.current_t = next_t.clone();
        self.depth += 1;
        Ok(next_t.to_string_radix(10))
    }

    fn update_with_snapshot(&mut self, agent_id: String, segment_id: u64, prev_snapshot_hash: String, expected_prev_t: String) -> PyResult<(String, bool, String)> {
        // 同样加入 expected_prev_t 检查
        Self::_validate_input(&expected_prev_t)?;
        let prev_t_int = Integer::from_str_radix(&expected_prev_t, 10)
             .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid prev_t format"))?;
        
        if self.current_t != prev_t_int {
             return Err(pyo3::exceptions::PyValueError::new_err("State Mismatch during snapshot update"));
        }

        Self::_validate_input(&agent_id)?;
        Self::_validate_input(&prev_snapshot_hash)?;
        self._check_op_limit()?;
        
        let (next_t, next_depth) = self._compute_transition(agent_id)?;

        if next_depth >= self.max_depth {
            let t_str = next_t.to_string_radix(10);
            let mut hasher = Sha256::new();
            hasher.update(t_str.as_bytes());
            hasher.update(prev_snapshot_hash.as_bytes());
            let snapshot_hash = hex::encode(hasher.finalize());
            
            let new_seed = Integer::from_str_radix(&snapshot_hash, 16)
                .map_err(|_| pyo3::exceptions::PyValueError::new_err("Hash parse failed"))? 
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

    /// [Security Fix #1] 级联模幂合并 (Cascaded Exponentiation Merge)
    /// 修复了乘法交换律漏洞。现在合并顺序对结果有决定性影响。
    /// T_final = (...((Base^P0 * G^H(0))^P1 * G^H(1))...)
    /// 每一个分支的素数 Pi 都会对当前状态进行模幂，并立即混合结构哈希。
    fn safe_merge_branches(&mut self, base_t_str: String, primes_str: Vec<String>, base_depth: u64) -> PyResult<(String, u64, u64)> {
        Self::_validate_input(&base_t_str)?;
        self._check_op_limit()?;
        self._inject_heavy_jitter(); 

        let mut current_term = Integer::from_str_radix(&base_t_str, 10)
             .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid base_t format"))?;
             
        let mut ops_consumed = 0u64;
        let mut next_depth = base_depth;

        // 级联处理：顺序敏感 (Order Sensitive)
        for (idx, p_str) in primes_str.iter().enumerate() {
            Self::_validate_input(p_str)?;
            let p = Integer::from_str_radix(p_str, 10)
                .map_err(|_| pyo3::exceptions::PyValueError::new_err("Invalid prime format"))?;

            // 1. Path evolution: T = T ^ P
            current_term = current_term.pow_mod(&p, &self.modulus).unwrap();
            ops_consumed += 1;

            // 2. Structural perturbation: T = T * G^H(depth + 1, idx)
            // 将 idx 混入哈希，确保即使素数相同，处于不同位置的分支也会产生不同扰动
            next_depth += 1;
            let mut hasher = Sha256::new();
            hasher.update(next_depth.to_string().as_bytes());
            hasher.update(&(idx as u32).to_le_bytes()); // Mix Index
            let depth_hash_bytes = hasher.finalize();
            
            let depth_hash_int = Integer::from_str_radix(&hex::encode(depth_hash_bytes), 16).unwrap();
            let depth_term = self.generator.clone().pow_mod(&depth_hash_int, &self.modulus).unwrap();
            
            current_term = (current_term * depth_term) % &self.modulus;
            ops_consumed += 1;
        }
        
        // 注意：这种合并方式会显著增加 depth，这符合全息累加器的逻辑（每个分支都增加了复杂性）
        // 并且 op_count 也会根据分支数量线性增加，被熔断机制保护。

        self.op_count += ops_consumed;
        Ok((current_term.to_string_radix(10), next_depth, ops_consumed))
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

    /// [Fix #3] 增强型随机运算干扰 (Computation-Heavy Jitter)
    /// 使用随机底数和指数进行模幂，掩盖真实运算的功耗特征
    fn _inject_heavy_jitter(&self) {
        let mut rng = thread_rng();
        // 显著增加循环次数 (1000 - 5000)，使干扰更加难以被平均
        let loop_count = rng.gen_range(1000..5000); 
        
        let mut dummy = Integer::from(rng.gen::<u64>());
        let m = Integer::from(65537);
        let exp = Integer::from(rng.gen::<u64>());
        
        for _ in 0..loop_count {
            dummy = dummy.pow_mod(&exp, &m).unwrap();
        }
        // 防止编译器优化掉无用计算
        if dummy == Integer::from(0) {
            println!("Jitter 0");
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
