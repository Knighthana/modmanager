# DESIGN_SESSION_2026-05-09 — 维护期 Bug 修复（阶段 A）

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 本轮工作会话任务分解：TODO-8 分支决策持久化、TODO-9 onDbPathBlur 校验、TODO-6 下游路径门禁强制执行、TODO-11 aggregator 层路径 ~ 展开
> 创建：2026-05-09

---

## 1. 背景

从 `work_memo/states.md` 选取 4 个 bug 作为本轮优先修复项。已全部完成文档覆盖：

| TODO | 描述 | 设计文档 |
|------|------|----------|
| TODO-6 | 下游路径门禁未强制执行 | `DESIGN_PATH_RESOLVER.md` §4 |
| TODO-11 | Rules / user_config 路径无 ~ 展开（aggregator 层） | `DESIGN_REST_API.md` §5.2 + `DESIGN_PATH_RESOLVER.md` |
| TODO-8 | ConflictsPage branch decisions 刷新丢失 | `DESIGN_GUI.md` §二.3（2026-05-09 新增） |
| TODO-9 | onDbPathBlur 静默失败 | `DESIGN_GUI.md` §三.1（2026-05-09 新增） |

---

## 2. 任务分解

### 阶段 A1：TODO-11 — Rules / user_config 路径 ~ 展开（aggregator 层）

**问题**：Pipeline 路由在接收 `kmm_rule_paths` 和 `user_config_path` 时，未调用 `path_resolver` 展开 `~` / `$HOME`，导致包含 `~` 的路径直接传递给 aggregator 后解析失败。

**设计约束**（`DESIGN_REST_API.md` §5.2）：
- `routes/pipeline.py` 的 `/compute` 和 `/run` 端点应对 `req.kmm_rule_paths[]` 每项调用 `resolve_file_path`
- `req.user_config_path` 应调用 `resolve_file_path`

| # | 任务 | 模块 | 类型 |
|---|------|------|------|
| A1-01 | pipeline 路由 `compute` 端点：`kmm_rule_paths` 每项过 `resolve_file_path` | `routes/pipeline.py` | 后端 |
| A1-02 | pipeline 路由 `run` 端点：同上 | `routes/pipeline.py` | 后端 |
| A1-03 | `user_config_path` 过 `resolve_file_path` | `routes/pipeline.py` | 后端 |
| A1-04 | 后端测试补充（含 `~` 路径用例） | `tests/test_web_api.py` | 测试 |
| A1-05 | Python 全量回归 | `pytest tests/` | 验证 |

### 阶段 A2：TODO-6 — 下游路径门禁强制执行

**问题**：`DESIGN_PATH_RESOLVER.md` §4 要求下游模块对路径做合规性断言（目录以 `/` 结尾、文件不以 `/` 结尾），但 `engine.py` 和 `backup_ops.py` 中尚未强制执行。

**设计约束**：
- 目录路径必须以 `/` 结尾 — 违规即 `raise ValueError`
- 文件路径不得以 `/` 结尾 — 违规即 `raise ValueError`
- 任何模块禁止再做路径「猜测」或「补全」

| # | 任务 | 模块 | 类型 |
|---|------|------|------|
| A2-01 | `engine.py` 入口添加路径合规性断言 | `src/modmanager/engine.py` | 后端 |
| A2-02 | `backup_ops.py` 入口添加路径合规性断言 | `src/modmanager/backup_ops.py` | 后端 |
| A2-03 | 移除下游模块中残留的路径补全/猜测逻辑 | `engine.py` / `backup_ops.py` | 后端 |
| A2-04 | 后端测试补充（违规路径断言触发） | `tests/test_engine.py` / `tests/test_backup_ops.py` | 测试 |
| A2-05 | Python 全量回归 | `pytest tests/` | 验证 |

### 阶段 A3：TODO-8 — ConflictsPage branch decisions 刷新丢失

**问题**：用户做出的分支决策仅保存在 ConflictsPage 本地状态，刷新或切换页面后丢失。

**设计约束**（`DESIGN_GUI.md` §二.3）：
- `ForestStore` 新增 `branchDecisions` 状态
- `setDecision()` 写入 store
- ConflictsPage 从 store 读取
- `reset()` 不清除 `branchDecisions`

| # | 任务 | 模块 | 类型 |
|---|------|------|------|
| A3-01 | `ForestStore` 新增 `branchDecisions: Record<string, string>` 状态 | `stores/forest.ts` | 前端 |
| A3-02 | 新增 `setDecision(rootPath, sourcePath)` action | `stores/forest.ts` | 前端 |
| A3-03 | `reset()` 保留 `branchDecisions`（与 `lastSuccessfulParams` 同级） | `stores/forest.ts` | 前端 |
| A3-04 | `ConflictsPage.vue` 改为从 store 读取/写入 `branchDecisions` | `pages/ConflictsPage.vue` | 前端 |
| A3-05 | 前端 Vitest 更新（store + ConflictsPage 持久化） | `frontend/src/__tests__/` | 测试 |
| A3-06 | 前端构建验证 | `npm run build` | 验证 |

### 阶段 A4：TODO-9 — onDbPathBlur 静默失败

**问题**：用户在 Database 路径输入框输入后失焦，路径校验失败时无任何可见反馈。

**设计约束**（`DESIGN_GUI.md` §三.1）：
- blur 时调用 `POST /api/database/load` 校验
- 成功 → 更新 store，切换锁定状态
- 失败 → 显示错误气泡，保留用户输入
- 空输入不触发校验
- 异步执行不阻塞 UI

| # | 任务 | 模块 | 类型 |
|---|------|------|------|
| A4-01 | `ForestPage.vue` 添加 `onDbPathBlur` 处理函数 | `pages/ForestPage.vue` | 前端 |
| A4-02 | 异步调用 `/api/database/load` + 成功/失败分支处理 | `pages/ForestPage.vue` | 前端 |
| A4-03 | 失败时调用 `notify.ts` 显示错误气泡 | `pages/ForestPage.vue` | 前端 |
| A4-04 | 前端 Vitest 更新（blur 成功/失败/空输入） | `frontend/src/__tests__/` | 测试 |
| A4-05 | 前端构建验证 | `npm run build` | 验证 |

---

## 3. 执行顺序

```
A1（后端 pipeline 路径展开）   ──→  可并行
A2（后端路径门禁断言）         ──→  可并行
                                        │
                                        ▼
A3（前端 branchDecisions 持久化）──→ 建议先于 A4（避免 store 冲突）
                                        │
                                        ▼
A4（前端 onDbPathBlur 校验）     ──→  依赖 A3 的 store 结构
```

**推荐顺序**：A1 → A2 → A3 → A4
- A1/A2 后端独立，可调换顺序
- A3 必须在 A4 之前（A4 可能引用 A3 的 store 结构）
- 前端构建验证放在最后统一执行

---

## 4. 验收标准

| 验收项 | 条件 |
|-------|------|
| TODO-11 | `POST /api/pipeline/compute` 传入含 `~` 的 `kmm_rule_paths` / `user_config_path`，后端正确展开并执行 |
| TODO-6 | 传入不含 `/` 结尾的目录路径，`engine` / `backup_ops` 抛出明确 `ValueError` |
| TODO-8 | ConflictsPage 做出决策 → 刷新页面 → 决策仍存在；切换到其他页面再回来 → 决策仍存在 |
| TODO-9 | Database 路径输入框填入无效路径 → 失焦 → 显示红色错误气泡；填入有效路径 → 失焦 → 自动锁定并更新 |
| 回归 | `pytest tests/` 全部通过；`npm run build` 成功；前端 Vitest 全部通过 |

---

## 6. 第二阶段：DataSource 去重 + E_DUP 错误码（TODO-16, TODO-17, TODO-18）

### TODO-16: DataSource 页面去重（managed + radio）

**设计文档**：`DESIGN_GUI_DATASOURCE_TAB.md` §3.3（2026-05-09 修订版）

**原则**：进来不管，出去必须合法。

| # | 任务 | 模块 |
|---|------|------|
| 16-01 | `ModRow` 类型新增 `managed: boolean` | `types/index.ts` |
| 16-02 | `_populateFromDatabase` 读取 `managed` 初始化 radio 状态 | `datasource.ts` |
| 16-03 | 计算重复组：`duplicateAppids`（按 appid）+ `duplicateMixedIds`（按 mixed_id） | `datasource.ts` |
| 16-04 | Game 表 radio：每组重复条目各一个 radio，绑定本地 managed 状态。Game/Mod 表各自独立 | `DataSourcePage.vue` |
| 16-05 | Mod 表 radio：同上，按 mixed_id 分组 | `DataSourcePage.vue` |
| 16-06 | "确认并进入规则概览"按钮 → 收集 managed → `POST /api/database/save` → 后端校验写入 | 前后端 |
| 16-07 | 后端校验失败返回错误列表，前端逐条平铺展示 | 前后端 |
| 16-08 | 修正 warnings 传递：累积而非覆盖 | `datasource.ts` |
| 16-09 | 前端测试更新 | `DataSourcePage.test.ts` / `datasource.test.ts` |

### TODO-17: 表头"可见性" ✅ 已完成（commit a00c5e1）

### TODO-18: W_DUPLICATE → E_DUPLICATE

**设计文档**：`DESIGN_ENGINE_INVARIANTS.md`（2026-05-09 新增错误码清单）

| # | 任务 | 模块 |
|---|------|------|
| 18-01 | `W_DUPLICATE_APPID` → `E_DUPLICATE_APPID` | `database_ops.py` |
| 18-02 | 新增 `E_DUPLICATE_MIXED_ID` 检测（遍历 mod 列表检测同 mixed_id 重复） | `database_ops.py` |
| 18-03 | 重复消息列入 errors 列表（非 warnings） | `database_ops.py` |
| 18-04 | `errorCodes.ts`：移入 `ERROR_DESCRIPTIONS`，新增 `E_DUPLICATE_MIXED_ID` | 前端 |
| 18-05 | `zh-CN.ts`：key 名同步更新 | 前端 |
| 18-06 | `DataSourcePage.vue`：`W_DUPLICATE` → `E_DUPLICATE` | 前端 |
| 18-07 | 错误/警告逐条平铺（不计数） | 前端 |
| 18-08 | 测试更新（Python 2 文件 + TS 2 文件） | 测试 |
| 18-09 | 全量回归 | 验证 |

---

## 5. 涉及文件汇总

### 后端
- `src/modmanager_web/routes/pipeline.py` — A1
- `src/modmanager/engine.py` — A2
- `src/modmanager/backup_ops.py` — A2
- `tests/test_web_api.py` — A1
- `tests/test_engine.py` / `tests/test_backup_ops.py` — A2

### 前端
- `frontend/src/stores/forest.ts` — A3
- `frontend/src/pages/ConflictsPage.vue` — A3
- `frontend/src/pages/ForestPage.vue` — A4
- `frontend/src/__tests__/` — A3, A4
