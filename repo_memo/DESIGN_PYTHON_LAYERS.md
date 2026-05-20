# Python 代码分层与 Rust 迁移规则

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 Python 代码的分层结构，明确 Rust 迁移时的翻译规则和约束，确保未来跨语言重实现时的行为等价性

创建：2026-05-14

---

## 0. 分层总览

Python 代码按功能职责分为 4 层，自下而上分别为：

```
┌─────────────────────────────────────────┐
│ 第 3 层：Entry Points（入口）             │  参考实现
│ cli.py / modmanager_web/routes/          │  ↓
├─────────────────────────────────────────┤
│ 第 2 层：Orchestration（编排）            │  精确翻译
│ orchestrator/  / bootstrap.py            │  ↓
├─────────────────────────────────────────┤
│ 第 1 层：Core Business Logic（业务核心）  │  精确翻译
│ engine.py / rule_aggregator.py / ...     │  ↓
├─────────────────────────────────────────┤
│ 第 0 层：Protocol Parsers（协议解析）    │  精确翻译
│ acf_parser.py / vdf_parser.py / ...      │  ↓
└─────────────────────────────────────────┘
```

---

## 1. 第 0 层：Protocol Parsers（协议解析）

### 职责
解析和生成特定二进制或文本协议格式的文件。

### 包含的模块
- `acf_parser.py` — ACF（Attribute Cert File）格式解析
- `vdf_parser.py` — VDF（Valve Data Format）格式解析
- `iojson.py` — JSON 文件 I/O 工具

### 特性
- 无业务逻辑，纯格式转换
- 输入：文件路径或字节流 → 输出：结构化 dict/list
- 与后续层完全解耦

### Rust 迁移规则
**翻译目标**：行为精确对应
- 解析逻辑：字符逐个匹配，状态机行为完全一致
- 错误处理：异常类型可重新包装，但触发条件不变
- 输出结构：dict key 名称完全相同（禁止重命名）

**例外**：无

---

## 2. 第 1 层：Core Business Logic（业务核心）

### 职责
实现项目的核心业务逻辑，与具体的"怎么跑"无关，仅定义"做什么"和"怎么算"。

### 包含的模块
- `engine.py` — 映射计算引擎
  - 输入：database（game/mod 数组）、aggregated_rule_set、branch_decisions、managed_entries
  - 输出：trees、final_mapping、warnings、errors
  - 核心算法：拓扑排序、冲突检测、文件级哈希匹配
  
- `rule_aggregator.py` — 规则聚合和合并
  - 输入：多个 *.kmmrule.json 文件路径 + action_orders
  - 输出：aggregated_rule_set（单一大对象）
  - 核心逻辑：字段规范化、权限验证、多源合并
  
- `steam_scanner.py` — Steam 库发现和扫描
  - 输入：libraryfolders.vdf 路径或 Steam 库根路径
  - 输出：steamlib[]、game[]、mod[] 结构
  - 核心逻辑：递归遍历、ACF 解析、路径规范化
  
- `database_ops.py` — 数据库扫描和缓存
  - 输入：user_config、discovery mode（auto/manual）、paths
  - 输出：database dict（可选持久化为 JSON）
  
- `path_resolver.py` — 路径扩展和规范化
  - 输入：用户输入的路径字符串
  - 输出：规范化路径（platform-aware）
  
- `backup_ops.py` — 差异备份和恢复
- `backup_ops.py` — 差异备份和恢复
  - 输入：`final_mapping`、`database`、`user_config`
  - 说明：`backup_ops` 不依赖调用方传入单一 `backup_dir`。实现通过 `backup_dir_builder.build_backup_dirs(final_mapping, database, user_config)` 推导出每个 content/app 的 `backup_dir` 映射（形如 `{ backup_dir: [file_paths] }`），并对每个目录独立执行差异备份、写入 `backupinfo.json` 以及扫描/校验流程。
  - 输出：backup metadata（包括 `backupinfo.json`、tree/hash 信息、复制统计等）

### 特性
- 包含所有项目的核心决策逻辑
- 对 Python/CLI/Web 无依赖，纯函数式或状态机
- 必须有相应的单元测试覆盖行为

### Rust 迁移规则
**翻译目标**：行为精确对应，不允许"优化"导致结果差异
- 算法：逻辑完全相同，可用更快的数据结构但结果不变
- 函数签名：入参出参的名称和顺序不变
- 异常类型：可以改为 Rust 的 Result<T, E>，但触发条件和错误码不变
- 字段定义：struct/dataclass 的字段名、类型、顺序保持一致

**验证方法**：给定相同的输入，Rust 版本的输出与 Python 版本完全一致（包括浮点精度、排序、格式）

---

## 3. 第 2 层：Orchestration（`orchestrator/` 包）

**文件**：`src/modmanager/orchestrator/`（包，非单文件）

**入口**：`dispatch(request: TaskRequest) -> PipelineResult`
所有请求（Web API / CLI）通过此单一入口进入。根据 `request.intent` 路由到对应管线。

**子模块**：

| 模块 | 文件 | 职责 |
|------|------|------|
| 核心 | `__init__.py` | `dispatch()` 入口 + `PipelineResult` dataclass |
| Entry | `entry.py` | `TaskRequest` + `Intent` enum — 请求归一化 |
| Resolver | `resolver.py` | `CleanContext` + 三种 Resolver（workspace / file_paths / raw_dict）— 资源收集 |
| Planner | `planner_fileops.py` | `FileOpsPlan` + `plan_fileops()` — 推导 + preflight 决策 |
| Preflight | `preflight.py` | `run_apply_preflight()` / `run_restore_preflight()` — 门禁检查 |
| Compute 管线 | `compute_pipeline.py` | `compute()` / `compute_ws()` — 映射生产 |
| 共享 | `_common.py` | `PipelineResult` dataclass, 共享 helper |

**职责**：作为星形拓扑核心，统一调度所有流程。不直接执行文件操作或映射计算——这些由独立的 `*_ops.py` 原语模块执行。

---

## 4. 第 3 层：Entry Points（入口）

### 职责
把第 2 层的 Orchestrator 暴露给用户——通过 CLI 命令或 HTTP API。

### 包含的模块
- `cli.py` — 命令行接口
  - 工具：argparse / click
  - 职责：参数解析、进度显示、结果格式化
  
- `modmanager_web/routes/` — REST API 路由
  - 框架：FastAPI
  - 职责：HTTP 请求解析、Pydantic 校验、SSE 流推送、响应格式化

### 特性
- 最接近用户，最容易变更
- 对 Python 框架有强依赖
- 包含 UI 逻辑（进度条、错误提示、JSON 序列化）

### Rust 迁移规则
**翻译目标**：参考实现，最终由宿主环境重实现，不要求精确对应
- 不需要逐行翻译：CLI 可以用 clap，Web 可以用 actix-web，完全不同的生态
- 业务逻辑：完全使用第 0-2 层的 Rust 版本
- 目标结果：用户看到同样的输出格式、同样的错误消息、同样的流程体验

**建议做法**：
1. 完成 Rust 版本的第 0-2 层
2. 参考 Python 的 cli.py/routes 设计 Rust 的 CLI 或 Web 入口
3. 调用 Rust 的第 0-2 层完成任务
4. 禁止把第 3 层的逻辑"下推"到第 1-2 层

---

## 5. 迁移检查清单

当 Rust 版本完成后，验证以下内容：

### 第 0 层
- [ ] 每个 parser 给定相同输入，输出完全一致（JSON 序列化方式、key 顺序）
- [ ] 错误信息相同或可对应

### 第 1 层
- [ ] 给定相同的 database/aggregated_rule_set/decisions，engine.compute() 结果完全一致
- [ ] rule_aggregator 的输出结构字段名、顺序相同
- [ ] 路径规范化逻辑结果相同（尤其是 Windows 路径）
- [ ] 所有测试用例通过（428 个 Python 测试，需在 Rust 版本重新运行）

### 第 2 层
- [ ] `dispatch()` 的调用顺序不变（Resolver → Planner → Primitive）
- [ ] 相同的输入配置，得到相同的输出
- [ ] 异常触发条件、错误码完全一致

### 第 3 层
- [ ] 用户通过新的 CLI/Web 看到相同的结果格式
- [ ] 进度显示的 step 名称和顺序相同
- [ ] 错误消息翻译准确

---

## 6. 禁止事项

**以下做法在迁移过程中严格禁止**：

1. **"优化" 第 1 层逻辑**
   - 例：发现 Python 版本某处有冗余判断，Rust 版本删除 → ❌ 禁止
   - 例：改进哈希算法从 SHA256 换成 Blake3 → ❌ 禁止
   - **理由**：业务逻辑是当前项目的定义，改它会改变行为

2. **把第 3 层的操作下推到第 1-2 层**
   - 例：Python Web API 的某个 route 实现了特殊的缓存，移植时改成第 2 层的 Orchestrator → ❌ 禁止
   - **理由**：第 3 层改动不影响 Rust，第 1-2 层改动会

3. **跳过错误检查**
   - 例：Python 中有个校验，Rust 版本因为"用了类型系统就不需要了" → ❌ 禁止
   - **理由**：运行时保证必须保持

4. **改变数据结构**
   - 例：Python dict 的 key 改名（database 的 "mixed_id" → "mixedId"） → ❌ 禁止
   - **理由**：外部的 JSON Schema 和前端都依赖这个结构

---

## 7. 里程碑与时间表

| 阶段 | 交付 | 条件 |
|------|------|------|
| **P0: Python 定型** | 第 0-2 层完整，428 tests 通过 | ✅ 已完成（May 13） |
| **P1: Rust 0-2 层原型** | 对应 Python 版本的 Rust 实现 | 依赖迁移启动 |
| **P2: 测试覆盖** | Rust 版本的同等测试用例通过 | 依赖 P1 完成 |
| **P3: CLI/Web 包装** | Rust 版本的入口实现 | 依赖 P2 通过 |
| **P4: 验证等价性** | 对比 Python/Rust 输出一致 | 依赖 P3 可运行 |

---

## 8. 文档链接

- 设计文档：`repo_memo/DESIGN_ORCHESTRATOR.md`
- 分层架构：`repo_memo/DESIGN_EXECUTION_PLAN.md`
- 测试框架：`tests/` 目录
