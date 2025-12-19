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
