# Bootstrap + Orchestrator — 决策记录

状态：全部已决策 ✅
更新：2026-04-30

---

## 决策汇总

| Q# | 决策 |
|-----|------|
| Q1 | **自动检测**：从 `__file__` 向上查找 `pyproject.toml`，未找到则 fallback 到 site-packages 路径 |
| Q2 | 启动时按层级拼接三个 user_config 文件 |
| Q3 | 多接口：`mode="auto"` 自动发现，`mode="manual"` 传入路径；只缓存成功的 |
| Q4 | 以文件颗粒度外部传入 kmm_rule，支持批量 |
| Q5 | 不需要分步等待，采用分模块细粒度 + `run()` 聚合入口 |
| Q6 | **方案 A**：orchestrator 为唯一调度入口，CLI 变为薄壳 |
| Q7 | 回调 `(step, finished: int, total: int, message)`；log + stderr/stdout 并行 |
| Q8 | 会话持久化当前仅存 `action_order` |

## 详细设计

见 `direct/DESIGN_BOOTSTRAP_ORCHESTRATOR.md`
