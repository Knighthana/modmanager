# Rust 迁移分层规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义当前项目的 Rust 迁移分层，明确每层的翻译精度要求和边界
>
> Last update: 2026-05-21 — 按算法归属重分层，`orchestrator/` 子模块下放到 Layer 1/2

创建：2026-05-14

---

## 0. 分层总览

按**算法归属**分层，不按文件位置分层。同一目录下的模块可能属于不同层。

```
┌─────────────────────────────────────────────────────────┐
│  Layer 3：Entry Points（入口）      参考实现              │
│  cli.py / modmanager_web/routes/ / sse.py / adapters.py │
├─────────────────────────────────────────────────────────┤
│  Layer 2：Dispatch & Phase（调度）  精确翻译              │
│  orchestrator/__init__.py  — dispatch() + 阶段串联       │
├─────────────────────────────────────────────────────────┤
│  Layer 1：Business Logic（业务算法）  精确翻译            │
│  engine / rule_aggregator / *_ops / path_resolver /     │
│  orchestrator/entry / resolver / planner / preflight /  │
│  compute_pipeline / _common                             │
├─────────────────────────────────────────────────────────┤
│  Layer 0：Protocol Parsers（协议解析）  精确翻译          │
│  acf_parser / vdf_parser / iojson                       │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Layer 0：Protocol Parsers（协议解析）

| 模块 | 职责 | Rust 翻译 |
|------|------|:---:|
| `acf_parser.py` | ACF（Valve KeyValue）格式解析 | 精确 |
| `vdf_parser.py` | VDF 格式解析 | 精确 |
| `iojson.py` | JSON 文件 I/O | 精确 |

**规则**：纯格式转换，无业务逻辑。输入字节流 → 输出 dict。错误触发条件不变。

---

## 2. Layer 1：Business Logic（业务算法）

包含所有「怎么算」的核心逻辑。Rust 翻译必须行为等价——相同输入 → 相同输出。

### 映射生产

| 模块 | 职责 | 关键函数 |
|------|------|---------|
| `engine.py` | 映射计算引擎 | `compute_mapping()` |
| `rule_aggregator.py` | 规则聚合 | `aggregate()` |
| `orchestrator/compute_pipeline.py` | compute 管线调度 | `compute()`, `compute_ws()` |

### 文件操作四层模型（业务部分）

| 模块 | 职责 | 关键函数 |
|------|------|---------|
| `orchestrator/entry.py` | 请求数据结构 | `TaskRequest`, `Intent` enum |
| `orchestrator/resolver.py` | 资源收集策略 | `WorkspaceResolver`, `FilePathResolver`, `RawDictResolver`, `CleanContext` |
| `orchestrator/planner_fileops.py` | 推导 + preflight 决策 | `plan_fileops()`, `FileOpsPlan`, `_collect_ignore_rules()` |
| `orchestrator/preflight.py` | 门禁检查 | `run_apply_preflight()`, `run_restore_preflight()` |
| `orchestrator/_common.py` | 共享数据结构 | `PipelineResult`, `ProgressCallback` |

### 文件操作原语

| 模块 | 职责 | 关键函数 |
|------|------|---------|
| `apply_ops.py` | apply 原语 | `apply_entries()` — file-to-file 替换 |
| `restore_ops.py` | restore 原语 | `restore_entries()` — hash 比对 + 恢复 |
| `backup_ops.py` | backup 原语 | `run_differential_backup()` — 差异备份 |

### 基础服务

| 模块 | 职责 |
|------|------|
| `database_ops.py` | 数据库扫描与缓存 |
| `steam_scanner.py` | Steam 库发现 |
| `path_resolver.py` | 路径规范化 |
| `backup_dir_builder.py` | backup_dir 推导 |

**Rust 翻译规则**：算法相同、签名相同、字段名类型顺序一致、错误码不变。禁止以「类型系统更强」为由删除运行时校验。

---

## 3. Layer 2：Dispatch & Phase（调度）

| 模块 | 职责 | Rust 翻译 |
|------|------|:---:|
| `orchestrator/__init__.py` | `dispatch()` 入口 + intent 路由 + phase 串联 | 精确 |

**唯一入口**：`dispatch(request: TaskRequest) -> PipelineResult`。

调度逻辑是业务规则的一部分：
- `COMPUTE_MAPPING` → compute 管线
- `BACKUP / APPLY / RESTORE / RUN` → Resolver → Planner → Preflight → Primitive
- Preflight 分支：apply/restore 必须过，run 豁免，backup 不需要
- Phase 序列：resolve → plan → (preflight) → execute
- 失败时短路径返回（preflight 失败不执行原语）

Rust 版本必须保持完全相同的路由逻辑和 phase 顺序。

---

## 4. Layer 3：Entry Points（入口）

| 模块 | 职责 | Rust 翻译 |
|------|------|:---:|
| `cli.py` | 命令行参数解析 + 显示 | 参考实现 |
| `modmanager_web/routes/*` | HTTP 路由 + 参数校验 | 参考实现 |
| `modmanager_web/sse.py` | SSE 流推送 | 参考实现 |
| `modmanager_web/adapters.py` | 结果格式适配 | 参考实现 |

**规则**：不要求精确翻译。Rust 可用完全不同的框架（clap / actix-web）。唯一要求：用户看到相同的输出格式、相同的错误消息、相同的流程体验。

Layer 3 代码中唯一需要精确翻译的是**构造 `TaskRequest` 的逻辑**——CLI 参数 → `TaskRequest` 的映射规则。但这是定义在 `orchestrator/entry.py`（Layer 1）中的，Layer 3 只是调用它。

---

## 5. 迁移检查清单

### Layer 0
- [ ] 每个 parser 给定相同输入，输出完全一致
- [ ] 错误信息相同或可对应

### Layer 1
- [ ] `engine.compute_mapping()` 结果完全一致（trees, final_mapping）
- [ ] `rule_aggregator.aggregate()` 输出结构字段名、顺序相同
- [ ] `plan_fileops()` 推导的 backup_dirs、preflight 决策相同
- [ ] `apply_entries()` / `restore_entries()` / `run_differential_backup()` 行为等价
- [ ] 路径规范化结果相同（含 Windows）
- [ ] 所有数据结构字段名、类型、顺序一致

### Layer 2
- [ ] `dispatch()` 的 intent 路由逻辑相同
- [ ] Phase 序列相同（resolve → plan → preflight? → execute）
- [ ] Preflight 分支决策相同
- [ ] 失败短路径返回行为相同

### Layer 3
- [ ] 用户通过新 CLI/Web 看到相同的结果格式
- [ ] 进度显示的 step 名称和顺序相同
- [ ] 错误消息翻译准确

---

## 6. 禁止事项

1. **禁止「优化」Layer 1 逻辑**：任何行为差异都是 bug
2. **禁止把 Layer 3 逻辑下推到 Layer 1-2**：路由适配不应混入业务算法
3. **禁止以类型系统为由删除运行时校验**：Python 的 `assert_file_path()` 等价物在 Rust 中也必须存在
4. **禁止改变数据结构**：字段名、类型、顺序不变。JSON Schema 和前端依赖这些结构

---

## 7. 里程碑

| 阶段 | 交付 | 状态 |
|------|------|:---:|
| **P0: Python 定型** | Layer 1-2 完成，测试通过 | ✅ |
| **P1: Rust Layer 0** | 协议解析层 | 待启动 |
| **P2: Rust Layer 1** | 业务算法层 | 待启动 |
| **P3: Rust Layer 2** | 调度层 | 待启动 |
| **P4: Rust Layer 3** | CLI/Web 入口 | 待启动 |
| **P5: 等价性验证** | 对比 Python/Rust 输出 | 待启动 |

---

## 8. 关联文档

- 调度架构：`DESIGN_ORCHESTRATOR.md`
- 执行计划（历史）：`DESIGN_EXECUTION_PLAN.md`
- 测试约定：`repo_test/README.md`
