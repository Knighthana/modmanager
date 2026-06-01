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
├── prep           ← 文件资源预处理器（真成员）
├── backup         ← 备份原语（真成员）
├── apply          ← 操作原语（真成员）
├── restore        ← 还原原语（真成员）
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

## 五、与当前矛盾的裁决

user 在审查报告中提出了三个裁定性问题，待 arch 在下一轮中讨论：

### 裁定 1：`.kmmignore` 归属

> `.kmmignore` 现在由 planner 自己解析和决定修改任务清单。在任务清单中直接删去相关内容，不暴露 ignore 体系给具体的操作原语。

**隐含裁决**：
- **work_memo 方向正确**（要求从 orchestrator `_dispatch_fileops` 移到 Planner）
- **repo_memo/DESIGN_BACKUP_OPS.md:186** 仍然写"调用点在 `_dispatch_fileops`"——**文档错了**
- 需要更新：从 backup/restore 原语和 orchestrator 中删除 ignore 相关逻辑，统一收归 Planner

### 裁定 2：`osplatform` 管理

> bootstrap 现在不管 osplatform，所有的默认值是单独的 osplatform 在管理。

**隐含裁决**：
- **代码实现正确**（`osplatform.defaultvalue.workspace_dir_get()`）
- **repo_memo 文档错了**——`DESIGN_BOOTSTRAP.md:76` 和 `DESIGN_USERCONFIG_OPS.md:59` 引用不存在的 `userconfig_ops._detect_platform_defaults()`
- **work_memo P21-GAP 方向正确**（指出函数名不对，指向 `osplatform.defaultvalue`）

### 裁定 3：`_list_orphans` 及相关 orphan 链路

> restore 整个操作（planner + restore）由 mapping 确定 scope，然后直接从 backupinfo 中判断文件在不在、正常不正常、跟外面的一样不一样，然后照着 mapping 的名单搬就行了。
> 汇报 backup_dir"还有哪些文件没有搬"是噪音——restore 原语不应该回答一个它没被问到的问题。

**裁决**：orphan 检测作为 restore 内嵌步骤 → **全部删除**。`detect_dirty_state()` 中对 `_collect_backup_original_paths` 的使用是备份完整性检查 → **保留**。

#### 清理范围

| 位置 | 内容 | 动作 |
|------|------|------|
| `backup_ops.py:661-663` | `_list_orphans()` 调用 + `W_EXTERNAL_FILE_ORPHAN` 警告生成 | **删** |
| `backup_ops.py:671` | 返回值中 `"orphans": orphans` | **改为** `"orphans": []` |
| `backup_ops.py:676-720±` | `delete_orphan_files()` 整函数 | **删** |
| `backup_ops.py:771` | `__all__` 中 `"delete_orphan_files"` | **删** |
| `backup_ops.py:550,567,619` | 其他返回路径中的 `"orphans"` 字段 | 保留为空 `[]`（返回结构兼容） |
| `backup_ops.py:186-206` | `_collect_backup_original_paths()` | **保留**（被 `detect_dirty_state` 使用） |
| `restore_ops.py:46` | `orphans: list[str] = []` 字段 | **删** |
| `restore_ops.py:152` | `"orphans": orphans` | **删** |
| `modmgr_web/adapters.py:94` | `"orphans": result.get("orphans", [])` | 保留（向后兼容，上游删后自然取到 `[]`） |
| `cli.py:8` | `delete_orphan_files` import | **删** |
| `cli.py:111-113` | `--delete-orphans` 参数定义 | **删** |
| `cli.py:414-417` | orphan 删除调用逻辑 | **删** |
| `DESIGN_RESTORE_OPS.md:71` | "存在本次 restore 未命中的外部文件或孤儿文件" | **删** |
| `TERMS_ERROR_CODES.md:30` | `W_EXTERNAL_FILE_ORPHAN` 条目 | **删** |
| `repo_test/` 中相关测试 | orphan 断言 | **删/更新** |

> 注：`backup_ops.py:550,567,619` 的 `"orphans": []` 是早期返回路径（gate 失败等），保留空列表不为具体 orphan 内容，仅保持返回结构稳定。`adapters.py` 同理——上游不再产生 orphan 内容后，`result.get("orphans", [])` 自然取到空列表。

---

## 六、矛盾裁定汇总与剩余待办

### 已裁决（文档 / 代码方向已明确）

| 矛盾 | 谁错了 | 动作 |
|------|--------|------|
| `.kmmignore` 调用点 | `repo_memo/DESIGN_BACKUP_OPS.md:186` 错了 | 文档改为 Planner；代码从 `__init__.py` 迁往 Planner |
| `_detect_platform_defaults()` | `repo_memo` 两个文档错了 | 文档改为引用 `osplatform.defaultvalue` |
| orphan 链路 | 设计噪音 | 按 §五 清理范围删除 orphan 相关代码和文档 |

### 裁定 4：BUG-2 — restore SSE 进度透传

> 透传必须一路传回前端。按照"让前端时刻掌握运行状况，避免用户以为程序卡死无响应"的标准进行进度回调的汇报透传工作。

**执行点**：所有涉及原语调用的层（web route → orchestrator dispatch → fileops → 原语），`on_progress` 必须逐层透传，不允许吞没。

**具体修复**：

| 位置 | 动作 |
|------|------|
| `modmgr_web/routes/pipeline.py:107-111` | `do_work` 中 `on_progress` 传给 `restore_from_backup` |
| 全量审计 | 搜 `def do_work(*, on_progress)` 所有调用点，确认 `on_progress` 都被透传 |
| `DESIGN_ORCHESTRATOR.md §二` | 已规定"每个阶段必须至少发送一次进度事件"——代码必须遵守 |

### 裁定 5：P11-GAP — validator / normalizer 调用点

> validator 必然是 verifier 的职责——只要是对照 schema 马上能出结论的 verify，那就是 bootstrap 调用 verifier 这个成员来做。
> path_normalizer 实际上是对 path_string 进行 verify 和 clean，面向的是用户输入，因此在 aggregator 入口做。

**分工**：

| 模块 | 调用方 | 调用时机 | 职责 |
|------|--------|---------|------|
| `rule_validator.validate_kmm_rule_files()` | **bootstrap → verifier** | kmm_rule 文件加载后、送入 aggregator 前 | schema 校验 + C1-C10 语义检查（即时 yes/no） |
| `path_normalizer.normalize_rule_actions()` | **aggregator 入口** | `aggregate()` 函数内部，加载每个 kmm_rule 文件后 | 路径归一化（`"path"` 拒绝、尾 `/` 补全、`".."` 拒绝） |

**具体修复**：

| 位置 | 动作 |
|------|------|
| `bootstrap.py` 或 verifier 模块 | 新增：加载 kmm_rule 文件后调用 `validate_kmm_rule_files()`，不合格的拒绝进入后续流程 |
| `rule_aggregator.py` `aggregate()` | 入口处（`§6.3` 流程 Step 1-2 之间）调用 `normalize_rule_actions()` 对每个文件做路径归一化 |
| `DESIGN_RULE_AGGREGATOR.md` | 更新聚合流程，加入 `normalize_rule_actions` 步骤 |
| `DESIGN_BOOTSTRAP.md` | 补充 verifier 职责：包含 kmm_rule 的 schema 验证 |

### 裁定 6：CODE-3~7 — 低优先清扫

> 做好清理工作。

**清单**：

| # | 位置 | 动作 |
|---|------|------|
| CODE-3 | `acf_parser.py` | 删 `find_appmanifest_acf_files`、`find_appworkshop_acf_files`（零调用方） |
| CODE-4 | `routes/config.py:40` | 删 `isinstance(rs, list)` 死分支，保留 `isinstance(rs, dict)` 及其迁移逻辑 |
| CODE-5 | `preflight.py` | 删 `run_apply_preflight` / `run_restore_preflight` 中未使用的 `context` 参数 |
| CODE-6 | `bootstrap.py:146-147` | 注释 `source_path` / `first_use` → `config_index` |
| CODE-7 | `__init__.py` / `app.py` | `modmanager` → `modmgr` |

### 裁定 7：P12-GAP — database 生成归属

> 按"单独成员"方案走。将 `database_ops` 提升为 orchestrator 一等成员。

**方案**：

- `database_ops` 从工具模块提升为 orchestrator 一等成员，职责：database 的发现、生成、完整性校验、CRUD
- `bootstrap.generate_database()` → 拆分：
  - 编排逻辑（解析 user_config 中的 database 路径 → 决定调什么）→ 上移到 orchestrator
  - 扫描 + 写盘逻辑 → 移入 `database_ops.generate_database()`
- bootstrap 不再持有 `generate_database` 函数

**具体修复**：

| 位置 | 动作 |
|------|------|
| `bootstrap.py:336-338` | 删除 `write_json_file(db_path, database)`——写盘由 `database_ops` 负责 |
| `database_ops.py` | 新增 `generate_database()` 函数，聚合 `discover_with_fallback()` + 写盘 |
| orchestrator | 在需要 database 时直接调 `database_ops.generate_database()`，不再经过 bootstrap |
| `DESIGN_BOOTSTRAP.md` | 移除对 `generate_database` 的描述 |
| `DESIGN_DATABASE_OPS.md` | 补充：提升为 orchestrator 成员，承担 generate 职责 |

---

### 已裁决（全部）

| 矛盾 | 裁定 | 动作 |
|------|------|------|
| `.kmmignore` 调用点 | Planner 内部 | 代码迁入 Planner；`DESIGN_BACKUP_OPS.md:186` 修正 |
| `_detect_platform_defaults()` | 代码对，文档错 | `repo_memo` 改为引用 `osplatform.defaultvalue` |
| orphan 链路 | 噪音，删除 | 按裁定 3 清理清单删除 |
| BUG-2 | SSE 进度透传 | 全链路 `on_progress` 透传，搜所有 `do_work` |
| P11-GAP | validator → verifier，normalizer → aggregator | 各自入口补调用 |
| P12-GAP | `database_ops` 升为一等成员 | 扫描+写盘从 bootstrap 移入 `database_ops` |
| CODE-3~7 | 清扫 | 删死代码、修注释、改名 |
| P22-GAP | 已解决 | 6 键确认 |

---

### 已解决（确认无动作）

| 问题 | 状态 |
|------|------|
| P22-GAP（required 键数） | ✅ 代码和文档均为 6 键 |
| BUG-1（`_list_orphans`） | ✅ 不实现函数，删除调用链（见裁定 3） |

---

## 七、基于新架构的文档修正清单

以下 `repo_memo/` 文档需要根据 §一~~四 的架构裁定修正：

| 文档 | 修正点 |
|------|--------|
| `DESIGN_BACKUP_OPS.md:186` | "调用点在 `_dispatch_fileops`" → 改为 Planner 层 |
| `DESIGN_BACKUP_OPS.md §十三` | `.kmmignore` 保留逻辑描述改为 Planner 内部 |
| `DESIGN_BOOTSTRAP.md:76` | `userconfig_ops._detect_platform_defaults()` → `osplatform.defaultvalue` |
| `DESIGN_BOOTSTRAP.md` | 移除 `generate_database` 描述（已移入 `database_ops`） |
| `DESIGN_USERCONFIG_OPS.md:59` | `_detect_platform_defaults()` → `osplatform.defaultvalue` |
| `DESIGN_RESTORE_OPS.md:71` | 删除 orphan 相关描述 |
| `DESIGN_RULE_AGGREGATOR.md` | 聚合流程加入 `normalize_rule_actions` 步骤（aggregator 入口） |
| `DESIGN_RULE_VALIDATION.md` | validator 调用方标为 bootstrap → verifier |
| `DESIGN_DATABASE_OPS.md` | 提升为 orchestrator 一等成员，承担 `generate_database()` 职责 |
| `TERMS_ERROR_CODES.md:30` | 删除 `W_EXTERNAL_FILE_ORPHAN` 条目 |

---

## 八、新方案合理性讨论 — 衍生裁定

> 2026-06-01，基于 §一~四 总图展开的架构讨论。

### 裁定 8：Web 端点的 resolver_type 限制

> Web 请求一律走 workspaceId 资源流程。`resolver_type="raw_dict"` 只允许 CLI 使用。

**决定**：Web 层构造 `TaskRequest` 时 `resolver_type` 必须为 `"workspace"`。`"raw_dict"` 和 `"file_paths"` 保留给 CLI。将此约束写入 `DESIGN_ORCHESTRATOR.md` 或 `DESIGN_ORCHESTRATOR_CONTRACT.md` 作为 L1 硬约束。

### 裁定 9：`pipeline.py` 删除

> `pipeline.py` 的 4 个端点全部绕过 workspace，`workspace.py` 已提供对应端点。

**决定**：删除 `src/modmgr_web/routes/pipeline.py` 整文件。

| 旧端点 | 替代 |
|--------|------|
| `POST /compute` | `POST /{workspace_id}/pipeline/compute`（已有） |
| `POST /visualize` | `POST /{workspace_id}/pipeline/visualize`（需补充） |
| `POST /restore` | `POST /{workspace_id}/pipeline/restore`（已有） |
| `POST /run` | `POST /{workspace_id}/pipeline/run`（已有） |

### 裁定 10：CLI 保留全能力

> 后端引擎能力是全的，限制只施加在 Web 入口层。

**决定**：`dispatch()` 三种 resolver 不做删减；约束由 Web 路由层执行。

### 裁定 11：workspace META 中的 database 形式

**确认**：`meta.json` 中为 `"database_name": "default"`（name ✅）。`WorkspaceResolver.resolve()` 第 58 行已用 name 解析路径。无需修改。

### 裁定 12：prep 暂时承载未分配职责

> 暂时把不该其他部分考虑的问题塞进 prep，以后再拆。

**决定**：prep 当前职责范围允许继续承载"目录创建 + 建树 + 其他预处理"，本轮不拆分。

---

## 九、文档影响面（完整汇总）

| 文档 | 修正点 | 来源 |
|------|--------|------|
| `DESIGN_BACKUP_OPS.md:186` | "调用点在 `_dispatch_fileops`" → Planner 层 | 裁定 1 |
| `DESIGN_BACKUP_OPS.md §十三` | `.kmmignore` 保留逻辑改为 Planner 内部 | 裁定 1 |
| `DESIGN_BOOTSTRAP.md:76` | `userconfig_ops._detect_platform_defaults()` → `osplatform.defaultvalue` | 裁定 2 |
| `DESIGN_BOOTSTRAP.md` | 移除 `generate_database` 描述；补充 verifier 职责含 kmm_rule 验证 | 裁定 5+7 |
| `DESIGN_USERCONFIG_OPS.md:59` | `_detect_platform_defaults()` → `osplatform.defaultvalue` | 裁定 2 |
| `DESIGN_RESTORE_OPS.md:71` | 删除 orphan 相关描述 | 裁定 3 |
| `DESIGN_RULE_AGGREGATOR.md` | 聚合流程加入 `normalize_rule_actions` 步骤 | 裁定 5 |
| `DESIGN_RULE_VALIDATION.md` | validator 调用方标为 bootstrap → verifier | 裁定 5 |
| `DESIGN_DATABASE_OPS.md` | 提升为 orchestrator 一等成员，承担 `generate_database()` | 裁定 7 |
| `TERMS_ERROR_CODES.md:30` | 删除 `W_EXTERNAL_FILE_ORPHAN` 条目 | 裁定 3 |
| `DESIGN_ORCHESTRATOR.md` | 架构图加入 `database_ops`；明确 bootstrap 只做 resolve+verify；补充 prep 成员 | 裁定 7+总图 |
| `DESIGN_ORCHESTRATOR_CONTRACT.md` | Web 层 `resolver_type` 必须为 `"workspace"`（L1 硬约束） | 裁定 8 |
| `DESIGN_REST_API.md` | 删除非 workspace 的 pipeline 端点描述 | 裁定 9 |
| `DESIGN_COMM_PROTOCOL.md` | 删除非 workspace 的 pipeline 端点协议 | 裁定 9 |
| `DESIGN_GUI_EXECUTION_PROTOCOL.md` | 前端请求一律带 `workspaceId` | 裁定 8 |
| `DESIGN_WORKSPACE_MODEL.md` | workspace 作为消费品来源/产品去向 | 裁定 9 |
| `DESIGN_PREFLIGHT_APPLY.md` | `context` 参数已从 preflight 函数签名中删除 | 裁定 6 |
| `DESIGN_ENGINE_INVARIANTS.md` | orphan 相关内容清理（如有） | 裁定 3 |
| `READING_PACKAGES.md` | 任务包可能需要重组 | 裁定 7 |
