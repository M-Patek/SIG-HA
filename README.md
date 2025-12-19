# SIG-HA: Hierarchical Holographic Accumulators

**SIG-HA** 是一个基于密码学累加器（Cryptographic Accumulators）构建的高性能、可验证的分布式系统状态追踪框架。它通过代数性质（如素数指数运算）将复杂的 Agent 交互路径和拓扑结构“折叠”进一个定长的代数指纹中，实现全息（Holographic）级的状态审计与安全验证。

## 🌟 核心特性

* **全息状态追踪 (Holographic Tracing)**：利用公式 $T_{next} = (T_{prev}^{P_{agent}} \cdot G^{H(depth)}) \pmod M$ 将路径与深度信息融合。
* **分层作用域 (Hierarchical Scopes)**：
    * **SwarmScope**：支持子任务集群的本地审计与结果导出，用于分级索引管理。
    * **ParallelScope**：利用乘法交换律实现并行处理分支的无损合并。
* **自动快照折叠 (State Folding)**：当处理深度达到阈值时，自动将状态归档并重置种子，确保长路径下的计算效率。
* **多维安全保障**：
    * **StateSealer**：通过哈希锚定业务数据 (Payload) 与代数指纹，防止数据篡改。
    * **TraceInspector**：提供全息侦探功能，根据已知路径重算指纹并验证其合法性。
    * **TopologyGuard**：基于预定义拓扑结构的合法转移校验，确保 Agent 访问合规。

## 📂 模块指南

| 模块 | 描述 |
| :--- | :--- |
| `core.py` | 核心引擎。包含加密上下文 `CryptoContext`、素数注册表 `PrimeRegistry` 及核心累加器实现。 |
| `scopes.py` | 结构化逻辑。处理 Swarm 集群任务和并行路径的合并算子。 |
| `security.py` | 安全防御层。提供状态锁定、路径验证和拓扑准入校验。 |
| `models.py` | 数据模型。定义了全息元数据 `HolographicMeta` 和全局状态容器 `AgentState`。 |
| `benchmark.py` | 性能评估。模拟高并发场景下的碰撞检测与时延测试。 |

## 🚀 快速开始

您可以运行 `demo_runner.py` 来观察系统的完整运行流程，包括 Agent 交互、Swarm 任务处理、结果合并以及状态锁定：

```bash
python demo_runner.py
```

### 核心用法示例

```python
from holographic_pass.core import CryptoContext, PrimeRegistry, SnapshotAccumulator
from holographic_pass.security import TraceInspector

# 1. 初始化基础设施
ctx = CryptoContext(bit_length=2048)
reg = PrimeRegistry()
acc = SnapshotAccumulator(ctx)

# 2. 模拟 Agent 处理并更新指纹
p_a = reg.register_agent("Agent_A")
trace_t = acc.update_state_with_check("Agent_A", p_a)

# 3. 验证路径合法性
inspector = TraceInspector(ctx, reg)
is_valid, msg = inspector.verify_path(trace_t, ["Agent_A"])
print(f"验证结果: {is_valid}")
```

## 📊 性能表现

系统内置了 `HolographicBenchmark` 工具，用于测试不同比特长度下的处理时延。通过代数合并算法，即使在复杂的并行分支场景下，也能保持极低的验证成本。
