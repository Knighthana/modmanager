# 2026-06-01 — 架构漂移审查：user 最新架构裁定

> 来源：user 在审查文档矛盾过程中的实时裁定。

---

## 前置问题

在对具体矛盾（`.kmmignore`、`_detect_platform_defaults`、`_list_orphans` 等）深入修改之前，先更新架构总图，以此裁定「谁错了」。

---

## 一、总体架构

```
REQUEST(WEB/CLI)
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                   orchestrator                        │
│                    （唯一入口）                         │
│                                                       │
│  成员：                                               │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐   │
│  │ bootstrap │  │aggregator │  │ compute          │   │
│  │resolve+   │  │kmmrules → │  │ database+uc+     │   │
│  │verify     │  │ruleset    │  │ ruleset → forest │   │
│  │(前置准备)  │  │           │  │ +mapping         │   │
│  └──────────┘  └───────────┘  └──────────────────┘   │
│                                                     │
│  ┌──────────────────┐  ┌────────────────────────┐   │
│  │ updatecompute    │  │ fileops                 │   │
│  │ branchdecision+  │  │ 消费无旁支mapping       │   │
│  │ forest+mapping → │  │ → 产出供 backup/apply/ │   │
│  │ 新forest+mapping │  │   restore 消费的对象    │   │
│  └──────────────────┘  │ → call三个原语          │   │
│                         └────────────────────────┘   │
│                                                     │
│  ┌──────────────┐                                   │
│  │ database_ops │  ← 一等成员                        │
│  │ database的   │    discovery/generate/verify/CRUD  │
│  │ 发现/生成/   │                                    │
│  │ 校验/CRUD    │                                    │
│  └──────────────┘                                    │
│                                                     │
│  独立成员：                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ resolver │  │ verifier │  │ osplatform       │   │
│  │ 资源解析  │  │ schema   │  │ 平台检测+平台    │   │
│  │          │  │ 核验     │  │ 功能             │   │
│  └──────────┘  └──────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────┘
```

### 调度规则

根据 request 的不同，orchestrator 可以直接从以下任一起点开始流程：

- `aggregate`
- `compute` / `updatecompute`
- `fileops`

**流程顺序**：

1. orchestrator 先调用 **bootstrap** 进行 `resolve` + `verify` 两个操作，获得干净的消费品
2. orchestrator 决定将干净的消费品喂给自己的成员
3. 获取结果并返回

**bootstrap 的职责边界**：

- 只负责 `resolve` + `verify` 等 orchestrator **交办**的任务
- **调度的权限和职责仍然在 orchestrator 上**
- bootstrap 不负责平台默认值管理

**osplatform 的职责**：

- 独立组件，专门进行平台检测和提供平台相关功能
- **所有默认值由 osplatform 管理，bootstrap 不管 osplatform**

### compute 与 updatecompute 的语义

- **compute**：初步算出森林和映射
- **updatecompute**：对森林和映射用 `branchdecision` 进行"只保留想要的枝"的操作
  - 操作后的结果**可能**还存在分支，**可能**不存在分支
  - `updatecompute` 可以多次反复进行

---

## 二、fileops 子结构

```
fileops
├── planner        ← 总调度器，只负责逻辑处理，屏蔽无关信息
│                    · 管理 .kmmignore 文件完整生命周期（过滤 + 物理拷贝）
│                    · 管理所有 gate / preflight 逻辑
│                    · 下发任务清单给原语（scope 由 planner 决定）
├── prep           ← 文件资源预处理器（真成员）
├── backup         ← 备份原语（真成员）
│                    · 职责：依照任务清单检查 backupinfo 是否已有，
│                      将尚未备份的文件从外面拷贝进入 backup_dir 并更新 backupinfo
│                    · 不感知 .kmmignore / gate 逻辑
├── apply          ← 操作原语（真成员）
├── restore        ← 还原原语（真成员）
│                    · 职责：按照任务清单比对 backupinfo 中的存在性与 hash，
│                      将 hash 不相同的文件从 backup_dir 覆盖到外面
│                    · scope 由 planner 决定
└── run            ← 伪成员，由 (prep + backup + apply) 组成
```

### 原语约束（L1 硬约束）

- 原语之间**互不知晓**其他原语的存在
- 原语之间**无法参考**其他原语
- 原语只做**最简单的事情**
- planner 负责逻辑处理和**无关信息的屏蔽**

---

## 三、解耦原则

### 总体原则

架构设计允许**齐头并进**，**动作解耦**，动作之间不允许出现任何耦合。

**所有耦合迁移到资源描述符 `workresourcedescriptor` 上。**

### 资源描述符（WorkResourceDescriptor）

**前端约束**：

- 前端保持对资源细节的**无知**
- 前端中任何涉及资源细节知识的实现都需要被清退
- 前端只需要知道 `workresourcedescriptor` 这个符号

**Web 实现**：

- 资源描述符是 `workspaceId`
- 但后端**不能假设**所有资源描述符都是 `workspaceId`
- 后端需要判断资源描述符的含义

**Resolver 实现**：

- resolver 目前可以只实现 `workspaceId` 和 `pathtofile`
- 使用 resolver 应当能够解析出不同结果
- 测试标准：如果未来用 `redisindex` 进行资源描述，当前实现能否做到无缝衔接？

**resolve 流程**：

```
{"workspacedescriptor":"${workspaceId}"}  →  files needed
```

**verify 流程**：

```
no null, verify(schema, resource)
```

---

## 四、前端存储规范

| 操作 | 行为 |
|------|------|
| **写入** | `sessionStorage` + `localStorage` 直接**写穿**（同时写入） |
| **读取** | 先读 `sessionStorage` |
| **sessionStorage 为空** | 从 `localStorage` 读值 → 载入 `sessionStorage` → 再从 `sessionStorage` 读值 |
| **两者均为空** | 触发专门的**默认状况处理流程**（所有落进默认处理流程的情况仍需要添加详细定义） |

---

## 五、裁定全集（共 15 项）

> §五—§八（合并前）中分散的裁定在此统一归并，按执行状态分组。

### ▸ 已执行（无需本轮动作）

| 裁定 | 主题 | 概要 | 执行确认 |
|:---:|------|------|:---:|
| 2 | `osplatform` 管理默认值 | 代码正确（`osplatform.defaultvalue`），文档错误 | ✅ commit `d2ae234` |
| 3 | orphan 链路全删 | `_list_orphans` + `delete_orphan_files` + CLI `--delete-orphans` + 文档清理 | ✅ commits `d2ae234`/`4837948` |
| 4 | BUG-2 进度透传 | 所有 `do_work` 透传 `on_progress` | ✅ commit `d2ae234` |
| 6 | CODE-3~7 清扫 | 删死代码 / 修注释 / `modmanager` → `modmgr` | ✅ commit `d2ae234` |
| 10 | CLI 保留全能力 | `dispatch()` 三种 resolver 不删减 | ✅ 无需代码变更 |
| 11 | workspace META 格式确认 | `database_name` 格式正确 | ✅ 无需代码变更 |
| 12 | prep 暂不拆分 | 继续承载目录创建 + 建树 | ✅ 本轮不动作 |

### ▸ 已解决（确认无动作，审计链收口）

| 问题 | 状态 | 关联裁定 |
|------|:---:|:---:|
| P22-GAP（required 键数） | ✅ 代码和文档均为 6 键 | — |
| BUG-1（`_list_orphans` 未实现） | ✅ 不实现函数，删除调用链 | 裁定 3 |

### ▸ 待执行（按推进顺序）

| 裁定 | 主题 | 概要 |
|:---:|------|------|
| 7 | `database_ops` 提升 | `generate_database` 从 bootstrap 移入 `database_ops`；bootstrap 仅 resolve+verify |
| 5 | validator / normalizer 归位 | `validate_kmm_rule_files` → bootstrap → verifier；`normalize_rule_actions` → aggregator 入口 |
| 1 | `.kmmignore` 过滤归属 | ignore 过滤逻辑由 Planner 内部管理（已在 `planner_fileops.py:91-112` 完成过滤迁移，剩余 orchestrator 中的物理拷贝 — 见裁定 13） |
| 13 | `.kmmignore` 物理拷贝归属 | `_copy_kmmignore_to_backup` / `_copy_kmmignore_from_backup` 从 `orchestrator/__init__.py` 迁入 Planner |
| 14 | `check_backup_gate` 迁出原语 | `check_backup_gate` 从 `backup_ops.py` 移入 Planner / `preflight.py`；backup 原语不再持有 gate 逻辑 |
| 8 | Web 路由层 `resolver_type` 强制 | Web 端 `resolver_type` 必须为 `"workspace"` |
| 9 | 删除 `pipeline.py` + 前端迁移 | 后端删 `pipeline.py` 整文件 + 补充 `/{workspace_id}/pipeline/visualize`；前端 3 处端点迁移到 workspace-aware |
| 15 | API 响应删除 `backup_dir` | `PipelineResult.backup_dir` 废弃；`adapters.py` 移除透传；前端改从 workspace 层面获取备份信息 |

### 裁定 1 详细：`.kmmignore` 归属

> `.kmmignore` 现在由 planner 自己解析和决定修改任务清单。在任务清单中直接删去相关内容，不暴露 ignore 体系给具体的操作原语。

**决定**：`.kmmignore` 过滤逻辑 + 物理拷贝均由 Planner 内部管理，原语不感知。

### 裁定 5 详细：validator / normalizer 调用点

> validator 必然是 verifier 的职责 — 只要是对照 schema 马上能出结论的 verify，那就是 bootstrap 调用 verifier 这个成员来做。
> path_normalizer 实际上是对 path_string 进行 verify 和 clean，面向的是用户输入，因此在 aggregator 入口做。

| 模块 | 调用方 | 调用时机 | 职责 |
|------|--------|---------|------|
| `rule_validator.validate_kmm_rule_files()` | **bootstrap → verifier** | kmm_rule 文件加载后、送入 aggregator 前 | schema 校验 + C1-C10 语义检查 |
| `path_normalizer.normalize_rule_actions()` | **aggregator 入口** | `aggregate()` 内部，每个 kmm_rule 文件加载后 | 路径归一化 |

**具体修复**：

| 位置 | 动作 |
|------|------|
| `bootstrap.py` 或 verifier 模块 | 新增：加载 kmm_rule 文件后调用 `validate_kmm_rule_files()`，不合格的拒绝进入后续流程 |
| `rule_aggregator.py` `aggregate()` | 入口处调用 `normalize_rule_actions()` 对每个文件做路径归一化 |
| `DESIGN_RULE_AGGREGATOR.md` | 更新聚合流程，加入 `normalize_rule_actions` 步骤 |
| `DESIGN_BOOTSTRAP.md` | 补充 verifier 职责：包含 kmm_rule 的 schema 验证 |

### 裁定 7 详细：database 生成归属

> 将 `database_ops` 提升为 orchestrator 一等成员。

- `bootstrap.generate_database()` → 拆分：编排逻辑上移 orchestrator，扫描+写盘移入 `database_ops.generate_database()`
- bootstrap 不再持有 `generate_database` 函数
- `database_ops.py` 新增 `generate_database()` 聚合 `discover_with_fallback()` + 写盘

**具体修复**：

| 位置 | 动作 |
|------|------|
| `bootstrap.py:336-338` | 删除 `write_json_file(db_path, database)`——写盘由 `database_ops` 负责 |
| `database_ops.py` | 新增 `generate_database()` 函数，聚合 `discover_with_fallback()` + 写盘 |
| orchestrator | 在需要 database 时直接调 `database_ops.generate_database()`，不再经过 bootstrap |
| `DESIGN_BOOTSTRAP.md` | 移除对 `generate_database` 的描述 |
| `DESIGN_DATABASE_OPS.md` | 补充：提升为 orchestrator 一等成员，承担 generate 职责 |

### 裁定 8 详细：Web resolver_type 限制

> Web 请求一律走 workspaceId 资源流程。`resolver_type="raw_dict"` 只允许 CLI 使用。

Web 层构造 `TaskRequest` 时 `resolver_type` 必须为 `"workspace"`。约束写入 `DESIGN_ORCHESTRATOR_CONTRACT.md` 作为 L1 硬约束。

### 裁定 9 详细：`pipeline.py` 删除 + 前端路由迁移

**后端**：删除 `src/modmgr_web/routes/pipeline.py` 整文件。

| 旧端点 | 替代 |
|--------|------|
| `POST /compute` | `POST /{workspace_id}/pipeline/compute`（已有） |
| `POST /visualize` | `POST /{workspace_id}/pipeline/visualize`（需补充） |
| `POST /restore` | `POST /{workspace_id}/pipeline/restore`（已有） |
| `POST /run` | `POST /{workspace_id}/pipeline/run`（已有） |

**前端**：3 处端点迁移。

| 文件 | 旧调用 | 新调用 |
|------|--------|--------|
| `frontend/src/stores/forest.ts:139` | `/pipeline/compute` | `/{workspaceId}/pipeline/compute` |
| `frontend/src/stores/forest.ts:96` | `/pipeline/run` | `/{workspaceId}/pipeline/run` |
| `frontend/src/components/BackupPage.vue:242` | `/pipeline/restore` (发 `backup_dir`) | `/{workspaceId}/pipeline/restore` (发 `workspaceId`) |

**约束**：前端不再发送 `backup_dir` 文件路径。

### 裁定 13 详细：`.kmmignore` 物理拷贝

> `.kmmignore` 文件相关任务应全部由 planner 下发。backup/restore 保持无知状态 — backup 照任务清单备份，restore 照任务清单恢复，scope 由 planner 决定。

**决定**：`_copy_kmmignore_to_backup()` / `_copy_kmmignore_from_backup()` 从 `orchestrator/__init__.py` 迁入 Planner。

### 裁定 14 详细：gate 迁出原语

> `check_*_gate` 出现在 backup 原语中是严重问题。preflight 逻辑应仅保留在 planner 及其附属部件内部。

**决定**：`check_backup_gate` 从 `backup_ops.py` 移入 `planner_fileops.py` 或 `preflight.py`。`preflight.py` 中原有 `from ..backup_ops import check_backup_gate` 改为从 Planner 内部获取。

### 裁定 15 详细：移除 `backup_dir` API 字段

> `backup_dir` 不应出现在 API 响应中。前端知道 `workspaceId` 足够。

**决定**：
- `PipelineResult.backup_dir` → 删除或改为 `workspace_id`
- `adapters.py:66-67` `data["backup_dir"] = pr.backup_dir` → 删除
- 前端 `total_backup_dirs` 等改从 `GET /{workspace_id}/backups` 获取

---

## 六、文档影响面（完整汇总，30 项）

| # | 文档/代码 | 修正点 | 来源 |
|:--|------|------|:--|
| 1 | `DESIGN_BACKUP_OPS.md:186` | "调用点在 `_dispatch_fileops`" → Planner 层 | 裁定 1 |
| 2 | `DESIGN_BACKUP_OPS.md §十三` | `.kmmignore` 保留逻辑改为 Planner 内部 | 裁定 1 |
| 3 | `DESIGN_BACKUP_OPS.md` | 移除 `check_backup_gate` 及所有 gate 逻辑描述 | 裁定 14 |
| 4 | `DESIGN_BOOTSTRAP.md:76` | `userconfig_ops._detect_platform_defaults()` → `osplatform.defaultvalue` | 裁定 2 |
| 5 | `DESIGN_BOOTSTRAP.md` | 移除 `generate_database`；补充 verifier 职责含 kmm_rule 验证 | 裁定 5+7 |
| 6 | `DESIGN_USERCONFIG_OPS.md:59` | `_detect_platform_defaults()` → `osplatform.defaultvalue` | 裁定 2 |
| 7 | `DESIGN_RESTORE_OPS.md:71` | 删除 orphan 相关描述 | 裁定 3 |
| 8 | `DESIGN_RULE_AGGREGATOR.md` | 聚合流程加入 `normalize_rule_actions` 步骤 | 裁定 5 |
| 9 | `DESIGN_RULE_VALIDATION.md` | validator 调用方标为 bootstrap → verifier | 裁定 5 |
| 10 | `DESIGN_DATABASE_OPS.md` | 提升为 orchestrator 一等成员，承担 `generate_database()` | 裁定 7 |
| 11 | `TERMS_ERROR_CODES.md:30` | 删除 `W_EXTERNAL_FILE_ORPHAN` 条目 | 裁定 3 |
| 12 | `DESIGN_ORCHESTRATOR.md` | 架构图加入 `database_ops`；明确 bootstrap 只做 resolve+verify；补充 prep 成员 | 裁定 7+总图 |
| 13 | `DESIGN_ORCHESTRATOR_CONTRACT.md` | Web 层 `resolver_type` 必须为 `"workspace"`（L1 硬约束） | 裁定 8 |
| 14 | `DESIGN_REST_API.md` | 删除非 workspace pipeline 端点 + `backup_dir` 响应字段；补充 workspace 级别备份列表端点 | 裁定 9+15 |
| 15 | `DESIGN_COMM_PROTOCOL.md` | 删除非 workspace pipeline 端点协议 + `backup_dir` 响应字段 | 裁定 9+15 |
| 16 | `DESIGN_GUI_EXECUTION_PROTOCOL.md` | 前端请求一律带 `workspaceId` | 裁定 8 |
| 17 | `DESIGN_WORKSPACE_MODEL.md` | workspace 作为消费品来源/产品去向 | 裁定 9 |
| 18 | `DESIGN_GUI_BACKUP_RESTORE.md` | 移除 `backup_dir` 路径参数，改用 `workspaceId`（如存在此文档） | 裁定 9 |
| 19 | `DESIGN_PREFLIGHT_APPLY.md` | `context` 参数已从 preflight 函数签名中删除 | 裁定 6 |
| 20 | `DESIGN_ENGINE_INVARIANTS.md` | orphan 相关内容清理（如有） | 裁定 3 |
| 21 | `DESIGN_PLANNER.md`（或新建） | Planner 全权管理 `.kmmignore` 文件生命周期（过滤+物理拷贝）；接管 gate 逻辑 | 裁定 13+14 |
| 22 | `READING_PACKAGES.md` | 任务包可能需要重组 | 裁定 7 |
| 23 | `src/modmgr/orchestrator/__init__.py` | 删除 `_copy_kmmignore_to_backup` / `_copy_kmmignore_from_backup`（迁入 Planner） | 裁定 13 |
| 24 | `src/modmgr/backup_ops.py` | 删除 `check_backup_gate` 及相关 gate 函数（迁入 Planner） | 裁定 14 |
| 25 | `src/modmgr/orchestrator/_common.py` | `PipelineResult.backup_dir` 字段废弃或改为 `workspace_id` | 裁定 15 |
| 26 | `src/modmgr_web/adapters.py` | 移除 `pr.backup_dir` 透传到 API 响应的代码 | 裁定 15 |
| 27 | `frontend/src/stores/forest.ts` | 非 workspace 端点 → `/{workspaceId}/pipeline/{compute,run}` | 裁定 9 |
| 28 | `frontend/src/components/BackupPage.vue` | `backup_dir` 路径 → `workspaceId` | 裁定 9 |
| 29 | `src/modmgr/bootstrap.py` | 删除 `generate_database` 函数（扫描+写盘移入 `database_ops`） | 裁定 7 |
| 30 | `src/modmgr/database_ops.py` | 新增 `generate_database()` 函数 | 裁定 7 |

---

## 七、执行路线图

### 阶段 0：新增补充端点（裁定 9 前置）

| 步骤 | 内容 |
|------|------|
| 0.1 | 补充 `POST /{workspace_id}/pipeline/visualize` 端点（`workspace.py`） |

### 阶段 1：database_ops 提升（裁定 7）

| 步骤 | 内容 |
|------|------|
| 1.1 | `database_ops.py` 中新增 `generate_database()`（聚合 `discover_with_fallback()` + 写盘） |
| 1.2 | `bootstrap.py` 删除 `generate_database` 函数（写盘代码移出） |
| 1.3 | orchestrator / Web 路由改调 `database_ops.generate_database()` |
| 1.4 | 更新 `__all__` / import |

### 阶段 2：validator / normalizer 归位（裁定 5）

| 步骤 | 内容 |
|------|------|
| 2.1 | bootstrap → verifier：加载 kmm_rule 文件后调用 `validate_kmm_rule_files()` |
| 2.2 | aggregator 入口：`aggregate()` 内调用 `normalize_rule_actions()` |
| 2.3 | 更新调用方文档标签 |

### 阶段 3：Planner 扩权（裁定 1 + 13 + 14）

| 步骤 | 内容 |
|------|------|
| 3.1 | `_copy_kmmignore_to_backup` / `_copy_kmmignore_from_backup` 从 `orchestrator/__init__.py` 迁入 `planner_fileops.py` |
| 3.2 | `check_backup_gate` 从 `backup_ops.py` 迁入 `planner_fileops.py` / `preflight.py` |
| 3.3 | `preflight.py` 中原有 `from ..backup_ops import check_backup_gate` 改为 Planner 内部获取 |
| 3.4 | orchestrator `_dispatch_fileops` 中 `.kmmignore` 拷贝调用改为调 Planner |
| 3.5 | `backup_ops.py` 删除 `check_backup_gate` 及相关 gate 函数 |

### 阶段 4：Web 层净化（裁定 8 + 9 + 15）

| 步骤 | 内容 |
|------|------|
| 4.1 | 删除 `src/modmgr_web/routes/pipeline.py` 整文件 |
| 4.2 | `app.py` 删除 pipeline 路由注册 + import |
| 4.3 | Web 路由层全部 `TaskRequest` 强制 `resolver_type="workspace"` |
| 4.4 | `PipelineResult.backup_dir` 字段废弃 / 改为 `workspace_id` |
| 4.5 | `adapters.py` 移除 `pr.backup_dir` 透传 |
| 4.6 | 前端 3 处端点迁移 + `backup_dir` → `workspaceId` |

### 阶段 5：文档收尾（全部）

| 步骤 | 内容 |
|------|------|
| 5.1 | 按 §六 30 项清单更新 `repo_memo/` 所有文档 |
| 5.2 | 新建或更新 `DESIGN_PLANNER.md` |
| 5.3 | 全量回归测试
