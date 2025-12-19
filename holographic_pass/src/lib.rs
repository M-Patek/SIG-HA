use pyo3::prelude::*;
use rug::{Integer, ops::Pow};
use sha2::{Sha256, Digest};

/// 定义 Python 模块
#[pymodule]
fn holographic_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<RustAccumulator>()?;
    Ok(())
}

/// [Core] 核心累加器的 Rust 实现
/// 对应 Python 中的 HolographicAccumulator
#[pyclass]
struct RustAccumulator {
    modulus: Integer, // 全局模数 M
    current_t: Integer, // 当前代数指纹 T
    depth: u64,       // 当前深度
    generator: Integer, // 生成元 G
}

#[pymethods]
impl RustAccumulator {
    /// 初始化：接收大整数模数 M 的字符串形式（避免精度丢失）
    #[new]
    fn new(modulus_str: String, generator: u64) -> Self {
        let m = Integer::from_str_radix(&modulus_str, 10).unwrap();
        RustAccumulator {
            modulus: m,
            current_t: Integer::from(2), // 初始状态 T=2
            depth: 0,
            generator: Integer::from(generator),
        }
    }

    /// 获取当前状态 (Hex 字符串)
    fn get_state(&self) -> String {
        self.current_t.to_string_radix(16)
    }

    fn get_depth(&self) -> u64 {
        self.depth
    }

    /// [Algorithm] 确定性 Hash-to-Prime 算法
    /// 实现指南中的 Source 179-198
    fn hash_to_prime(&self, agent_id: String) -> String {
        let mut nonce = 0u64;
        let input_bytes = agent_id.as_bytes();

        loop {
            // 1. 生成候选数: SHA256(AgentID + Nonce)
            let mut hasher = Sha256::new();
            hasher.update(input_bytes);
            hasher.update(&nonce.to_le_bytes());
            let result = hasher.finalize();

            // 2. 转换为 Integer
            let hex_str = hex::encode(result);
            let mut candidate = Integer::from_str_radix(&hex_str, 16).unwrap();

            // 3. 强制设置高位和低位，保证是大奇数
            candidate.set_bit(255, true); 
            candidate.set_bit(0, true);

            // 4. Miller-Rabin 素性测试 (25轮)
            if candidate.is_probably_prime(25) != rug::integer::IsPrime::No {
                return candidate.to_string_radix(10);
            }

            nonce += 1;
        }
    }

    /// [Core Op] 更新状态
    fn update_state(&mut self, agent_id: String) -> String {
        // 1. 计算 P_agent
        let p_str = self.hash_to_prime(agent_id.clone());
        let p_agent = Integer::from_str_radix(&p_str, 10).unwrap();

        // 2. 路径项: Path = T ^ P mod M
        let path_term = self.current_t.clone().pow_mod(&p_agent, &self.modulus).unwrap();

        // 3. 深度项: Depth = G ^ Hash(depth) mod M
        let depth_hash_bytes = Sha256::digest(self.depth.to_string().as_bytes());
        let depth_hash_int = Integer::from_str_radix(&hex::encode(depth_hash_bytes), 16).unwrap();
        let depth_term = self.generator.clone().pow_mod(&depth_hash_int, &self.modulus).unwrap();

        // 4. 合并: T_next = (Path * Depth) mod M
        let next_t = (path_term * depth_term) % &self.modulus;

        // 更新内部状态
        self.current_t = next_t;
        self.depth += 1;

        self.current_t.to_string_radix(10)
    }

    /// [Fix] 强制设置内部状态 (用于 Snapshot 回滚或重置)
    /// 修复了 Python 层折叠状态后 Rust 层状态不同步的 Bug
    fn set_state(&mut self, t_str: String, depth: u64) {
        self.current_t = Integer::from_str_radix(&t_str, 10).unwrap();
        self.depth = depth;
    }

    /// [Optimization] 通用模幂运算 Helper
    /// 允许 Python 侧利用 rug 的高性能进行任意计算 (如 ParallelScope 合并)
    /// result = (base ^ exp) % modulus
    #[staticmethod]
    fn pow_mod_unsafe(base_str: String, exp_str: String, modulus_str: String) -> String {
        let base = Integer::from_str_radix(&base_str, 10).unwrap();
        let exp = Integer::from_str_radix(&exp_str, 10).unwrap();
        let m = Integer::from_str_radix(&modulus_str, 10).unwrap();
        
        let result = base.pow_mod(&exp, &m).unwrap();
        result.to_string_radix(10)
    }
}
