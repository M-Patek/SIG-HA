from holographic_pass.core import CryptoContext, PrimeRegistry, SnapshotAccumulator
from holographic_pass.models import AgentState
from holographic_pass.scopes import SwarmScope, update_global_with_swarm
from holographic_pass.security import StateSealer, TraceInspector, TopologyGuard
from holographic_pass.benchmark import HolographicBenchmark

def main():
    print("🐱 === Holographic Pass System Demo === 🐱\n")
    
    # 1. 初始化基础设施
    ctx = CryptoContext(bit_length=2048, max_depth=5)
    reg = PrimeRegistry()
    acc = SnapshotAccumulator(ctx)
    inspector = TraceInspector(ctx, reg)
    
    # 2. 创建一个初始任务
    state = AgentState(task_id="TASK-001", payload="Find the best fish")
    print(f"📝 任务开始: {state.payload}")
    
    # 3. 模拟标准流程: Agent_A -> Agent_B
    # Agent A 处理
    p_a = reg.register_agent("Agent_A")
    state.meta.trace_t = acc.update_state_with_check("Agent_A", p_a)
    state.meta.path_log.append("Agent_A")
    
    # Agent B 处理
    p_b = reg.register_agent("Agent_B")
    state.meta.trace_t = acc.update_state_with_check("Agent_B", p_b)
    state.meta.path_log.append("Agent_B")
    
    print(f"⛓️  主链状态: {state.summary()}")
    
    # 4. 模拟 Swarm 集群处理 (Agent_C 是一群猫)
    print("\n🏰 进入 Swarm 'Research_Team'...")
    swarm = SwarmScope("Research_Team", ctx, reg)
    swarm.track_sub_task("Sub_Cat_1")
    swarm.track_sub_task("Sub_Cat_2")
    
    # 结算 Swarm
    result = swarm.seal_and_export()
    
    # 将 Swarm 结果合并回主链
    # 注意：这里需要手动更新 state 中的 trace_t
    new_global_t = update_global_with_swarm(acc, result)
    state.meta.trace_t = new_global_t
    state.meta.depth = acc.depth
    state.meta.path_log.append("Research_Team")
    
    print(f"✅ Swarm 合并完成: {state.summary()}")
    
    # 5. 安全锁定 (Sealing)
    print("\n🔐 正在进行状态锚定...")
    envelope = StateSealer.seal(state, extra_metrics={"cost": "5 dried fish"})
    is_valid = StateSealer.verify(envelope)
    print(f"   验证结果: {is_valid}")
    
    # 6. 运行压力测试
    print("\n🚀 运行基准测试...")
    bm = HolographicBenchmark(ctx, reg)
    bm.run(iterations=50)

    print("\n😺 所有演示结束，系统运行完美！")

if __name__ == "__main__":
    main()
