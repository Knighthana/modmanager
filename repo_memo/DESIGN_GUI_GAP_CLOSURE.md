# DESIGN_P4_GUI_GAP_CLOSURE — GUI 缺口补齐

> 状态：FINAL ✅（2026-05-07 实现完成）  
> 来源：`work_memo/2026-05-06.md` 中记录的 3 个 GUI 缺口  
> 依赖：P0-P3 全部已完成（322 Python + 18 前端 tests）  
> 接口风格：RESTful 低耦合，KISS 原则  
> 阶段目标：排查干净后端业务模块逻辑问题 + 排查干净前端应有什么、如何显示

---

## 1. 目标

补齐 Phase 3 前端 GUI 中剩余的 3 个功能缺口，并在实现过程中对触及的业务逻辑进行逻辑完备性审查。

| 缺口 | 当前状态 | 目标 |
|------|---------|------|
| G1: ConflictsPage "重新计算"传空参数 | `database: {}, kmm_rule_paths: []` | 持久化上次 pipeline 参数，复用 |
| G2: RulesPage 完全占位 | `onScan()` 返回空，`showContent()` 硬编码字符串 | 后端 scan/read API + 前端对接 |
| G3: BackupPage 完全占位 | `onScan()` / `restore()` 均为空实现 | 后端 list/inspect API + pipeline restore 端点 + 前端对接 |

---

## 2. 非目标

- 不修改 pipeline 核心逻辑（compute / backup / apply / run）的运算过程
- 不新增前端页面或路由
- 不修改数据模型（database / user_config / kmm_rule schema）
- 不引入认证或权限机制
- 不做客户端/服务端分离架构
- 不做路径安全校验（`..` 黑名单等）——安全由操作语义保证（只读 vs 写入），不在前端或路由层做字符串级拦截

---

## 3. 架构定界

### 3.1 角色模型

当前 WebUI 是**服务端的控制面板**，不存在"客户端"。所有路径操作均为服务端本地文件系统操作：

```
  Browser (前端 Vue SPA)
      │  fetch / SSE
      ▼
  FastAPI (localhost)
      │  import
      ▼
  modmanager 核心模块 (bootstrap / engine / backup_ops / ...)
      │
      ▼
  本地文件系统 (kmm_rule / backup_dir / database.json ...)
```

### 3.2 REST 资源语义

| 资源组 | URL 前缀 | 语义 | 与现有端点关系 |
|--------|---------|------|---------------|
| rules | `/api/rules/` | 规则**文件**的扫描与读取（只读） | **新资源**，独立于 pipeline |
| backups | `/api/backups/` | 备份**产物**的列出与查看（只读） | **新资源**，独立于 `/api/pipeline/backup`（备份操作动词） |
| pipeline | `/api/pipeline/` | 文件系统**变更操作**（compute/backup/apply/restore/run/visualize） | 已有；本次新增 `restore` |

说明：
- `/api/rules/` 负责 kmm_rule 文件本身的浏览和内容读取，不是"规则引擎"。
- `/api/backups/` 负责已产出备份目录的浏览与详情查看（产物管理），不是"备份执行"。
- `/api/pipeline/` 继续负责计算/备份/应用/**恢复**/可视化的**执行**操作。
- `restore`（从备份目录将文件复制回原位）是 `apply`（将映射写入磁盘）的**反向操作**，语义完全不同，不耦合。

### 3.3 操作安全性（非路径字符串过滤）

安全性通过**操作语义**保证，而非路径字符串黑名单：

| 端点 | 操作类型 | 安全性 |
|------|---------|--------|
| `POST /api/rules/scan` | 只读 | 列出目录下的 `.json` 文件 |
| `POST /api/rules/read` | 只读 | 返回文件内容 |
| `POST /api/backups/list` | 只读 | 列出 `kmmbackup_*` 目录 |
| `POST /api/backups/inspect` | 只读 | 读取 backupinfo.json |
| `POST /api/pipeline/compute` | 只读 | 纯计算，不写磁盘 |
| `POST /api/pipeline/backup` | 写入（仅备份区） | 将文件复制到 backup_dir |
| `POST /api/pipeline/apply` | 写入（目标区） | 将映射写入磁盘原始位置 |
| `POST /api/pipeline/restore` | 写入（目标区） | 从备份目录恢复文件到原始位置 |
| `POST /api/pipeline/visualize` | 只读 | 纯渲染 |

不做路径 `..` 过滤等伪安全措施。此面板由用户在自己机器上运行，安全边界在操作系统层而非应用层。

### 3.4 耦合性审查（KISS 原则）

**现有端点**：

| 端点 | 审查结论 | 说明 |
|------|---------|------|
| `POST /api/pipeline/compute` | ✅ 保持 | 单做聚合+计算，职责清晰 |
| `POST /api/pipeline/backup` | ✅ 保持 | 单做差异备份执行，职责清晰 |
| `POST /api/pipeline/apply` | ✅ 保持 | 单做映射应用到磁盘，职责清晰 |
| `POST /api/pipeline/run` | ✅ 保持 | 编排器（组合调用），无重复逻辑 |
| `POST /api/pipeline/visualize` | ✅ 保持 | 纯渲染后处理 |
| `POST /api/database/generate` | ✅ 保持（后端） | 单做 Steam 库发现 |
| `POST /api/config/discover` | ✅ 保持 | 单做配置发现 |
| `POST /api/config/save` | ✅ 保持 | 单做配置保存 |

**前端 Store 违规**：

| 位置 | 问题 | 处置 |
|------|------|------|
| `ForestStore.discoverDatabase()` | 名义上"发现数据库"，实际串联了 config discover + save 副作用 | 拆分：`discoverDatabase()` 只做 DB 发现；新增独立 `loadConfig()` action |
| `ConflictsPage.onRecalculate()` | 传空 `database: {}`，依赖隐式全局状态 | 从 `lastSuccessfulParams` 读取 |

---

## 4. 方案设计

### 4.1 G1: ConflictsPage 参数持久化

**根因**：`ConflictsPage.vue` 第 71 行 `onRecalculate()` 硬编码传空。

**方案**：在 `ForestStore` 中新增 `lastSuccessfulParams` 状态，在 `runPipeline()` / `computeOnly()` 成功执行后自动存储。`onRecalculate()` 从 store 读取。

**涉及文件**：
- `frontend/src/stores/forest.ts` — 新增 `lastSuccessfulParams` 字段，在 action 中写入
- `frontend/src/pages/ConflictsPage.vue` — `onRecalculate()` 改为从 store 读取
- `frontend/src/types/` — 可能扩展 `PipelineParams` 类型

**验收**：
- ForestPage 执行"计算映射"后 → 切换到 ConflictsPage → 点击"重新计算" → pipeline 携带正确的 database / rules / user_config
- 无参数时"重新计算"按钮 disabled + tooltip 说明"请先在 Forest 页面执行计算"

### 4.2 G2: RulesPage — 后端 API

**新增资源**：`/api/rules/`

| 方法 | 路径 | 描述 | 请求 body | 响应 |
|------|------|------|----------|------|
| POST | `/api/rules/scan` | 扫描目录，返回 kmm_rule 文件列表 | `{ dir: string }` | `ApiResponse { data: { files: [{ name, path, size }] } }` |
| POST | `/api/rules/read` | 读取指定文件内容 | `{ path: string }` | `ApiResponse { data: { content: string, name, path, size } }` |

**设计约束**：
- 扫描仅列出 `.json` 文件（不递归）
- `read` 接口直接返回文件原始文本（不做 JSON 解析 / 校验，保持 KISS）
- 路径不存在时返回 `ok: false` + error 信息

**后端实现**：
- 新增 `src/modmanager_web/routes/rules.py` — Rules 路由模块
- 新增 `src/modmanager_web/schemas.py` — `RulesScanRequest` / `RulesReadRequest` Pydantic 模型
- 在 `src/modmanager_web/app.py` 注册路由

**前端对接**：
- `frontend/src/pages/RulesPage.vue` — `onScan()` 调用 `POST /api/rules/scan`，`showContent()` 调用 `POST /api/rules/read`
- 文件列表支持点击展开内容（复用已有的 `el-dialog`）

### 4.3 G3: BackupPage — 后端 API

**新增资源**：`/api/backups/`（只读产物浏览）

| 方法 | 路径 | 描述 | 请求 body | 响应 |
|------|------|------|----------|------|
| POST | `/api/backups/list` | 列出备份目录 | `{ dir: string }` | `ApiResponse { data: { backups: [{ name, path, file_count, created_at }] } }` |
| POST | `/api/backups/inspect` | 查看备份详情 | `{ path: string }` | `ApiResponse { data: { path, file_count, files: [{ relpath, size, hash }], dirty, conflicts } }` |

**恢复操作**：新增 `POST /api/pipeline/restore`

| 方法 | 路径 | 描述 | 请求 body | 响应 |
|------|------|------|----------|------|
| POST | `/api/pipeline/restore` | 从备份目录恢复文件到原始位置 | `{ backup_dir: string, target_files?: string[] }` | SSE 流，最终 `ApiResponse { data: { ok, restored, skipped, errors, orphans } }` |

**关键语义区别**：
- `POST /api/pipeline/apply` = 将 `final_mapping` 作用到磁盘（**正向**：apply 映射结果）
- `POST /api/pipeline/restore` = 从备份目录将文件复制回原始位置（**逆向**：undo 映射结果）
- 二者语义互逆，不耦合，不复用

**设计约束**：
- `list` 扫描目录下所有以 `kmmbackup_` 为前缀的子目录，统计基本信息
- `inspect` 读取备份目录下的 `backupinfo.json`，复用 `load_backup_info()` + `detect_dirty_state()` + `inspect_conflict()`
- `restore` 直接调用 `backup_ops.restore_from_backup()`，不通过 orchestrator（restore 语义简单，无需编排）

**后端实现**：
- 新增 `src/modmanager_web/routes/backups.py` — Backups 路由模块
- 扩展 `src/modmanager_web/routes/pipeline.py` — 新增 `/restore` 端点
- 扩展 `src/modmanager_web/schemas.py` — 新增相关 Pydantic 模型
- 在 `src/modmanager_web/app.py` 注册路由

**前端对接**：
- `frontend/src/pages/BackupPage.vue` — `onScan()` 调用 `POST /api/backups/list`，表格显示备份目录列表
- 详情面板：点击某行展开 `inspect` 结果（文件列表 + dirty/conflict 状态）
- "恢复"按钮：调用 `POST /api/pipeline/restore`（确认后执行，支持 select 指定文件或全部恢复）

---

## 5. 任务分解

### Phase G1: ConflictsPage 参数持久化（5 tasks）

| # | 任务 | 模块 | 类型 |
|---|------|------|------|
| G1-01 | ForestStore 新增 `lastSuccessfulParams` 状态 | `stores/forest.ts` | 前端 |
| G1-02 | `runPipeline()` / `computeOnly()` 成功后写入 `lastSuccessfulParams` | `stores/forest.ts` | 前端 |
| G1-03 | ConflictsPage `onRecalculate()` 改为读取 `lastSuccessfulParams` 构建参数 | `pages/ConflictsPage.vue` | 前端 |
| G1-04 | 无参数时"重新计算"按钮 disabled + tooltip | `pages/ConflictsPage.vue` | 前端 |
| G1-05 | 前端 Vitest 更新（ConflictsPage + store） | `frontend/src/__tests__/` | 测试 |

### Phase G2: RulesPage 后端 API + 前端接入（7 tasks）

| # | 任务 | 模块 | 类型 |
|---|------|------|------|
| G2-01 | 新增 `RulesScanRequest` / `RulesReadRequest` Schema | `schemas.py` | 后端 |
| G2-02 | 实现 `POST /api/rules/scan` 路由（`os.listdir` + 过滤 `*.json`） | `routes/rules.py`（新文件） | 后端 |
| G2-03 | 实现 `POST /api/rules/read` 路由（`open` + `read` + 错误处理） | `routes/rules.py` | 后端 |
| G2-04 | app.py 注册 rules 路由（`include_router`） | `app.py` | 后端 |
| G2-05 | routes/rules.py 单元测试（正常路径 + 路径不存在 + 非目录） | `tests/test_web_api.py` | 测试 |
| G2-06 | RulesPage.vue 销毁占位代码，对接 scan/read API | `pages/RulesPage.vue` | 前端 |
| G2-07 | 前端 Vitest 更新（RulesPage） | `frontend/src/__tests__/` | 测试 |

### Phase G3: BackupPage 后端 API + 前端接入（9 tasks）

| # | 任务 | 模块 | 类型 |
|---|------|------|------|
| G3-01 | 新增 `BackupListRequest` / `BackupInspectRequest` / `RestoreRequest` Schema | `schemas.py` | 后端 |
| G3-02 | 实现 `POST /api/backups/list` 路由（扫描 `kmmbackup_*` 目录） | `routes/backups.py`（新文件） | 后端 |
| G3-03 | 实现 `POST /api/backups/inspect` 路由（读取 backupinfo + dirty + conflict） | `routes/backups.py` | 后端 |
| G3-04 | 实现 `POST /api/pipeline/restore` 端点（封装 `restore_from_backup` + SSE） | `routes/pipeline.py` | 后端 |
| G3-05 | app.py 注册 backups 路由 | `app.py` | 后端 |
| G3-06 | routes/backups.py + pipeline restore 端点单元测试 | `tests/test_web_api.py` | 测试 |
| G3-07 | BackupPage.vue 销毁占位代码，对接 list/inspect API | `pages/BackupPage.vue` | 前端 |
| G3-08 | 恢复按钮对接 `POST /api/pipeline/restore`（确认对话框 + SSE 进度） | `pages/BackupPage.vue` | 前端 |
| G3-09 | 前端 Vitest 更新（BackupPage） | `frontend/src/__tests__/` | 测试 |

### 附 B1: ForestStore 解耦修复（4 tasks）

| # | 任务 | 模块 | 类型 |
|---|------|------|------|
| B1-01 | 拆分 `discoverDatabase()` → 只做 DB 发现，移除 config discover+save 副作用 | `stores/forest.ts` | 前端 |
| B1-02 | 新增独立的 `loadConfig()` action（discover + save config） | `stores/forest.ts` | 前端 |
| B1-03 | ForestPage 按序调用 discover + loadConfig | `pages/ForestPage.vue` | 前端 |
| B1-04 | 前端 Vitest 更新（ForestStore + ForestPage） | `frontend/src/__tests__/` | 测试 |

---

## 6. 验收标准

| 验收项 | 条件 |
|-------|------|
| Python 全量回归 | 322+ 新增测试全部通过 |
| 前端 Vitest | 18+ 新增测试全部通过 |
| 前端构建 | `npm run build` 成功 |
| G1 E2E | ForestPage 计算 → ConflictsPage "重新计算" → 参数正确；无参数时按钮 disabled |
| G2 E2E | RulesPage 输入有效目录 → 扫描显示 `.json` 文件列表 → 点击查看内容 |
| G3 E2E | BackupPage 输入目录 → 扫描显示备份列表 → 查看详情（dirty/conflict 状态） → 恢复（确认后执行） |

---

## 7. 执行顺序

1. **G2 + G3 后端**：新增 `routes/rules.py`、`routes/backups.py`，扩展 `schemas.py`，扩展 `pipeline.py` 新增 restore 端点，注册路由。后端新增不影响现有功能。
2. **B1 解耦**：ForestStore 拆分，ForestPage 适配。
3. **G1 + G2 + G3 前端**：ConflictsPage 参数持久化、RulesPage / BackupPage 对接真实 API。
4. **全量测试**：Python test_web_api 扩展 + 前端 Vitest 更新 + 构建验证。

---

## 8. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | 新增端点风格？ | 沿用现有 POST 风格（路径参数在 body 中），但遵循 REST 资源命名 |
| D2 | Rules read 是否解析 kmm_rule？ | 不解析，只返回原始 JSON 文本（KISS，前端负责高亮展示） |
| D3 | BackupPage 恢复操作是否新增端点？ | **是**，新增 `POST /api/pipeline/restore`（独立于 apply） |
| D4 | discoverDatabase 副作用是否本次修？ | 是，在 B1 中修复 |
| D5 | scan/list 接口是否递归？ | 不递归，仅扫描顶层目录 |
| D6 | 路径安全校验策略？ | **不做**。安全由操作语义保证（只读 vs 写入），不在路由层做字符串级过滤 |
| D7 | restore 通过 orchestrator 还是直接调 backup_ops？ | 直接调 `backup_ops.restore_from_backup()`，restore 语义简单无需编排 |
| D8 | restore 是否需要 SSE 流？ | 是，支持进度回调（逐个文件报告进度） |

---

## 9. Phase P5 追加：手动模式 + Fixture 集成

### 9.1 背景

Fixture 生成后，需要手动调用 `generate_database(mode='manual', paths=[...])` 生成 database.json。当前前端 ForestPage 只有"自动探测"（`mode='auto'`），无法指定手动路径。

`POST /api/database/generate` 的后端 schema 已支持 `mode: "manual"` + `paths: list[str]`，只差前端暴露。

### 9.2 ForestPage 手动模式

**UI 变更**：在数据源发现面板添加模式选择：

```
扫描模式:  (•) 🔍 自动发现 Steam 库    ( ) 📁 手动指定路径

┌─ 手动模式（展开时）──────────────────────────┐
│ Steam 库路径:                                │
│ ┌──────────────────────────────────────────┐ │
│ │ /tmp/fixture/steamapps                   │ │
│ └──────────────────────────────────────────┘ │
│ 💡 指向 steamapps/ 目录（含 appmanifest 和   │
│    workshop/content 的父目录）                │
└──────────────────────────────────────────────┘
```

**约束**：

| 条件 | 行为 |
|------|------|
| 自动模式（默认） | `mode: 'auto'`, `paths: null` — 现有行为不变 |
| 手动模式 + 路径为空 | 按钮 disabled + tooltip "请输入 Steam 库路径" |
| 手动模式 + 路径有效 | `mode: 'manual'`, `paths: [用户输入]` |
| Database JSON 手动填入 | 不变（已有功能，填入已生成的 database.json 直接使用，跳过扫描） |

**涉及文件**（仅前端）：

| 文件 | 改动 |
|------|------|
| `frontend/src/stores/forest.ts` | `pipelineForm` 加 `discoveryMode` + `manualSteamPath`；`discoverDatabase()` 按模式切换参数 |
| `frontend/src/pages/ForestPage.vue` | radio 切换 + 条件路径输入框 |
| `frontend/src/types/` | 扩展 `DiscoverParams` |
| `frontend/src/__tests__/` | mode 切换测试 |

**后端零改动**。

### 9.3 Fixture 生成器增强

`generate_fixture.py` 新增 `--with-db` 参数：

```bash
python tools/generate_fixture.py hot -o /tmp/fixture --with-db
# 生成 fixture + 自动调 generate_database(mode='manual') + 写 database.json
```

**涉及文件**：`tools/generate_fixture.py`

### 9.4 任务分解

见 `repo_logs/2026-05-08_TASKLIST_ARCHIVE.md` Phase P5（M1: 5 前端任务 + M2: 1 工具任务）
