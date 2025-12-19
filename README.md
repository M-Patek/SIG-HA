# HA-DTS 协议白皮书：面向群体智能的可验证拓扑隐写框架
**Holographic Accumulator for Distributed Topology Steganography**

---

## 1. 愿景与定义 (Vision & Definition)

在零信任的去中心化 Agent 网络（Swarm Intelligence）中，单纯的行为日志不足以构建信任。我们需要一种机制，能够将**“谁做了什么” (Identity)** 与 **“在什么上下文中做的” (Topology)** 同时编码进一个不可篡改的数学指纹中。

**HA-DTS** 是一种基于数论的混合架构协议，它通过**非交换全息累加器**，实现了对大规模分布式图结构的高效、安全、保序追踪。

---

## 2. 核心抽象层级 (Core Abstraction: VTP)

我们将协议解耦为通用的 **可验证拓扑协议 (Verifiable Topology Protocol, VTP)**，由三个核心算子组成形式化三元组 $(\Phi, \Omega, \Sigma)$。

### 2.1 语义映射算子 (Identity Mapper: $\Phi$)

负责将离散的 Agent 身份无碰撞地映射到代数域。

- **定义**：
$$\Phi: \text{AgentID} \to \mathcal{P} \subset \mathbb{Z}^+$$
- **数学约束**：
    - **强单射性 (Strong Injectivity)**：确保身份唯一性。
    - **素性/正交性 (Primality/Orthogonality)**：$\forall a \neq b, \gcd(\Phi(a), \Phi(b)) = 1$。
- **当前实现**：基于 Miller-Rabin 素性测试的 Hash-to-Prime 算法，将 AgentID 映射为 2048-bit 安全大素数。

### 2.2 演化算子 (Evolution Operator: $\Omega$)

负责定义状态在时空维度上的单向流转。

- **定义**：$S_{t+1} = \Omega(S_t, P, \Gamma)$
- **核心公式**：
$$T_{\text{next}} \equiv (T_{\text{prev}}^{P_{\text{agent}}} \cdot G^{H(\text{depth})}) \pmod M$$
- **数学约束**：
    - **非交换性 (Non-commutativity)**：$\Omega(A, B) \neq \Omega(B, A)$。确保路径顺序被永久编码。
    - **单向性 (One-wayness)**：基于大数分解与离散对数难题，不可逆推。
    - **子群闭包性 (Subgroup Closure)**：状态始终在 $QR_M$ (模 $M$ 的二次剩余群) 或大阶子群中演化，防止熵减。

### 2.3 折叠算子 (Folding Operator: $\Sigma$)

负责处理并行分支的无损合并。

- **定义**：$S_{\text{merged}} = \Sigma(S_{\text{branchA}}, S_{\text{branchB}})$
- **数学约束**：
    - **阿贝尔群性质 (Abelian Property)**：满足交换律与结合律，即 $\Sigma(A, B) = \Sigma(B, A)$。
- **当前实现**：基于模乘运算，允许大规模并行计算结果在任意拓扑节点汇聚。

---

## 3. 理论完备性与安全证明 (Theoretical Foundation)

### 3.1 采样公理 (Sampling Axiom)

> **Axiom 1**: Assume $T_0$ is sampled uniformly from a subgroup of large order in $\mathbb{Z}_M^*$.

为规避低阶子群攻击，系统初始状态 $T_0$ 必须满足：
$$T_0 \xleftarrow{R} \mathbb{G} \subset \mathbb{Z}_M^*, \text{ s.t. } |\mathbb{G}| \text{ is a large prime factor of } \lambda(M)$$
此公理确保演化轨迹覆盖足够大的状态空间，使得暴力破解在计算上不可行。

### 3.2 概率界证明 (Probability Bound)

在 $M$ 为 2048-bit 合数的前提下，任意两条不同路径发生指纹碰撞的概率上界为：
$$P_{\text{coll}} \le \frac{\text{poly}(n)}{\phi(M)} + \epsilon_{\text{hash}} \approx O(2^{-2048})$$
该概率远小于密码学碰撞阈值，具备绝对的计算安全性。

### 3.3 安全规约 (Security Reduction)

**定理**：HA-DTS 的路径伪造难度等价于 **Strong RSA 问题**。

**证明要点**：
构造模拟器 $\mathcal{B}$，若攻击者 $\mathcal{A}$ 能在多项式时间内伪造合法指纹 $T^*$，则 $\mathcal{B}$ 可利用 $\mathcal{A}$ 的输出通过扩展欧几里得算法提取 $e$ 次方根，从而破解 Strong RSA 假设。

---

## 4. 工程实现架构 (Engineering Architecture)

采用 **Rust + Python** 的混合架构以平衡极致性能与易用性：
- **Rust Core (rug/GMP)**：处理 2048-bit 模幂运算，单次状态跳变延迟 $< 0.25$ ms。
- **Python Interface (PyO3)**：提供 `SnapshotAccumulator` 抽象，负责 Agent 编排与拓扑管理。

## 5. 技术对比 (Comparison)

| 特性指标 | Merkle Tree | CRDT (无冲突复制) | **HA-DTS (本协议)** |
| :--- | :--- | :--- | :--- |
| **顺序敏感性** | 强 (位置依赖) | 弱 (最终一致性) | **强 (代数非交换)** |
| **存储开销** | $O(\log n)$ | $O(n)$ | **$O(1)$ (常数级)** |
| **分支合并** | 困难 | 极强 | **原生支持 (代数折叠)** |

---

## 6. 结语 (Conclusion)

HA-DTS 将混乱的 Swarm 行为抽象为优雅的代数方程。它不仅是一个算法，更是数字生命体在复杂网络中存在的**数学证明**。

# SIG-HA: 混合架构全息累加器追踪框架 (Rust Accelerated)

**SIG-HA (Hierarchical Holographic Accumulators)** 是一个专为大规模 Agent 协作网络设计的可验证状态追踪框架。在最新版本中，系统通过 **PyO3** 深度集成了 **Rust (rug/GMP)** 内核，将算力密集的代数运算下沉至原生层，解决了原有架构在处理大数模幂时的性能瓶颈。

---

## 🌟 核心特性

* **全息状态追踪 (Holographic Tracing)**：利用公式 $T_{next} = (T_{prev}^{P_{agent}} \cdot G^{H(depth)}) \pmod M$ 将路径与深度信息融合。
* **Rust 原生加速**：核心算子基于 `rug` (GMP 绑定) 实现，2048-bit 模幂运算性能较纯 Python 库提升约 30 倍。
* **确定性映射 (Hash-to-Prime)**：内置 Miller-Rabin 素性测试，确保 Agent 身份到素数域的映射既安全又具备数学唯一性。
* **自动快照折叠 (State Folding)**：当路径深度达到阈值时，系统会自动归档状态并重置种子，防止长链下的计算效率下降。

---

## 📂 模块化架构

| 模块 | 核心功能 | 实现逻辑 |
| :--- | :--- | :--- |
| **`lib.rs`** | Rust 算力内核 | 实现 `RustAccumulator` 类，包含高性能模幂及 `hash_to_prime` 算法。 |
| **`core.py`** | 核心控制平面 | 定义 `CryptoContext` 与 `SnapshotAccumulator`，作为 Rust 引擎的 Python 包装器。 |
| **`scopes.py`** | 拓扑聚合算子 | 提供 `SwarmScope` (集群任务) 与 `ParallelScope` (并行分支合并) 的加速实现。 |
| **`security.py`** | 安全防御层 | 包含 `StateSealer` (数据锁定) 和 `TraceInspector` (全息路径验证)。 |
| **`models.py`** | 全局数据模型 | 定义全息元数据 `HolographicMeta` 与状态容器 `AgentState`。 |

---

## 🛠️ 安装与构建

系统需要 Rust 工具链及 Python 开发环境。

```bash
# 进入核心目录
cd holographic_pass

# 使用 maturin 构建并安装 Rust 扩展
maturin develop --release
```

---

## 🚀 快速开始

### 1. 初始化基础环境
```python
from holographic_pass.core import CryptoContext, SnapshotAccumulator

# 初始化 2048-bit 上下文，设置最大深度阈值
ctx = CryptoContext(bit_length=2048, max_depth=10)
acc = SnapshotAccumulator(ctx)
```

### 2. 更新 Agent 状态
```python
# Rust 引擎会自动处理 AgentID 到素数的映射及后续模幂运算
acc.update_state_with_check("Credit_Approval_Agent")
print(f"当前全息指纹 (T): {acc.current_T}")
print(f"当前执行深度: {acc.depth}")
```

### 3. 并行路径合并 (Parallel Merging)
```python
from holographic_pass.scopes import ParallelScope

# 初始化合并算子
scope = ParallelScope(ctx, reg, base_t=acc.current_T, current_depth=acc.depth)
scope.add_branch_result("Worker_A")
scope.add_branch_result("Worker_B")

# ⚡ 利用乘法交换律进行无损合并
t_merged, new_depth = scope.merge()
```

---

## 📊 性能表现

根据内置 `benchmark.py` 的测试：
* **Rust Core (rug)**：单跳累加器更新延迟约为 **0.25ms**。
* **Python Logic**：在处理同等规模的大数运算时，延迟通常在 **7.0ms** 以上。
* **系统吞吐量**：在单核 CPU 上支持每秒约 **4,000** 次的运算操作。

---

## ⚠️ 开发注意事项

1.  **状态同步 (Sync)**：在进行快照折叠或手动修改 Python 侧状态后，务必调用 `_backend.set_state()` 确保底层 Rust 寄存器同步，否则会导致计算结果不一致。
2.  **数据交互**：为保证跨语言调用的精度，所有 2048-bit 级别的大整数在 FFI 边界均以 **字符串 (String)** 形式传递。
3.  **依赖项**：Linux 环境下需预装 `libgmp-dev` 以支持 `rug` 库的编译。

---

**SIG-HA** 旨在将 Agent 行为的“黑箱”转化为透明的代数方程，为零信任 AI 协作提供数学底座。
