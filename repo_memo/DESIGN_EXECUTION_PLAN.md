# DESIGN_EXECUTION_PLAN — 全面重构执行计划

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 记录 2026-05-13 起的重构执行方案，聚焦数据模型收敛、工作区权威落地、前端状态清退、mock-first 页面重写与存量适配。
> 原则：每步必绿（每完成一个 Phase 子步骤立即跑全量测试，不累积）。

---

## 一、数据模型终态

### 数据模型终态

|  | database.json | 前端浏览器存储 | user_config.json | compute 参数 |
|--|:---:|:---:|:---:|:---:|
| **磁盘描述** | steamlib[], game[], mod[]（纯扫描数据） | — | — | — |
| **用户决策** | — | 工作区目录 `decisions.json` (managed_entries + branch_decisions) | baksuffix, bakignore, output_paths | ✅ |
| **计算结果** | — | 工作区目录 `mapping.json`（完整 trees + final_mapping） | — | — |
| **路径元数据** | OS.workingPathstyle | — | — | — |

### managed_entries 格式（方案 B：路径列表）

```json
{
  "game": { "270150": ["/mnt/d/.../RWR"] },
  "mod": { "270150:2606099273": ["/mnt/d/.../mod"] }
}
```
值列表表达"仅保留这些路径"。不在其中的 appid/mixed_id → 全部保留。

### 关键 API 数据流

```
POST /api/database/generate        → 返回: { database(无managed), warnings, errors }
POST /api/database/read            → 返回指定 database 内容
POST /api/workspace/{id}/pipeline/compute → 参数从工作区读取；orchestrator 自行加载 database
POST /api/config/discover          → 返回 user_config
```

---

## 二、分阶段执行

### Phase 0 — 设计定稿

**产出 3 新 + 3 改文档，验收：六文档一致无矛盾。**

| # | 文档 | 类型 | 内容 |
|---|------|------|------|
| 0.1 | `repo_logs/DOC_ARCHIVE_2026-05-19_DESIGN_GUI_WORKSPACE.md` | 归档（原 DESIGN_WORKSPACE_STATE.md 重写） | 迁移记录 |
| 0.2 | `repo_logs/DOC_ARCHIVE_2026-05-19_DESIGN_DATA_CLEANUP.md` | 归档 | 清退记录 |
| 0.3 | `DESIGN_MOCK_INFRA.md` | 新 | MSW 架构、mock/real 切换机制、`npm run dev:mock` 命令、mock 数据约定 |
| 0.4 | `DESIGN_STORAGE.md` | 改 | database.json 不包含 managed/warnings/errors；workspace 章节收敛为后端工作区权威 |
| 0.5 | `DESIGN_GUI_DATASOURCE_TAB.md` | 改 | §3.3 managed 逻辑重写：从存 database 改为存 workspace |
| 0.6 | `DESIGN_ENGINE_INVARIANTS.md` | 改 | 移除 managed 相关约束；补充 orchestrator workspace 过滤职责 |

**受影响的已有文档归档规则**：见 `DOCUMENT_METADATA.md` 与 `DOCUMENT_GOVERNANCE.md`，旧版先迁入 `repo_logs/` 并保留日期前缀。

---

### Phase 1 — 后端底层改造（串行，仅 Python，不动前端）

**验收：全部 Python 测试通过。不可回退边界：database.json 不再含 managed/warnings/errors；managed_entries 由前端通过请求参数传入；orchestrator 通过 workspacemanager 读取工作区数据。**

| 步骤 | 任务 | 涉及文件 | 测试 |
|------|------|---------|------|
| 1.1 | `database_ops.py` 移除 managed/warnings/errors 写入 | database_ops.py | `test_database_ops.py` 更新 |
| 1.2 | `engine.py` 移除 `validate_database` 中的 managed 过滤逻辑 | engine.py | `test_engine.py` 更新 |
| 1.3 | `orchestrator.py` 新增 `_apply_managed_filter`（接收 managed_entries 参数） | orchestrator.py | `test_orchestrator.py` 更新 |
| 1.4 | `schemas.py` `ComputeRequest` / `RunRequest` 新增 `managed_entries`、`branch_decisions`、`database_name` 可选字段 | schemas.py | — |
| 1.5 | `routes/pipeline.py` compute/run 端点：orchestrator 内部通过 bootstrap 获取 database；managed_entries 从请求参数接收 | routes/pipeline.py | `test_web_api.py` 更新 |
| 1.6 | `routes/database.py` generate 端点：不再写入 managed/warnings/errors；新增 read 端点 | routes/database.py | `test_web_api.py` 更新 |
| 1.7 | `routes/rules.py` 新增 `POST /api/rules/affected-entries` 端点 | routes/rules.py | `test_web_api.py` 更新 |
| 1.8 | 全量 Python 测试回归 + 文档更新 | — | `pytest` 全量 |

---

### Phase 2 — 前端清退 + 接入 workspace API

**验收：前端构建成功 + Vitest 全部通过。不可回退边界：localStorage 中不存在业务数据 key。**

| 步骤 | 任务 | 涉及文件 |
|------|------|---------|
| 2.1 | `persistence.ts` 削减：注释声明"仅 UI 状态"（discoveryMode、manualPath、sidebar 折叠、tab 可见性偏好）；save/load 失败时 notify 警告而非静默 | persistence.ts |
| 2.2 | `stores/datasource.ts` 移除 saveToCache/loadFromCache/clearCache；移除 datasource-db 持久化；扫描结果仅暂存 Pinia 内存 | datasource.ts |
| 2.3 | `stores/forest.ts` 移除 watch + savePersistentState/loadPersistentState | forest.ts |
| 2.4 | 各 store/page 改为调用 workspace 端点读写 decisions/mapping；浏览器端仅保留 UI 状态持久化 | datasource.ts, forest.ts, DataSourcePage.vue 等 |
| 2.5 | branch_decisions 保存：ConflictPage 通过工作区 decisions 端点保存（非每次切 radio） | ConflictsPage.vue |
| 2.6 | 更新全部前端测试 | `frontend/src/__tests__/` |

---

### Phase 3 — MSW mock + 四页面重写

**原则：SettingsPage / OperationsPage / RulesOverviewPage / 计算准备 从 mock 起步。ForestPage / DataSourcePage / ConflictsPage 保持真实 API。**

| 步骤 | 任务 | 涉及文件 |
|------|------|---------|
| 3.1 | 搭建 `frontend/src/mocks/` + MSW handler 文件 + `npm run dev:mock` + 页面水印 [MOCK MODE] | mocks/, package.json, vite.config.ts |
| 3.2 | SettingsPage mock-first 重写：user_config（主职责）+ Database JSON 编辑（独立模块，大编辑区） | SettingsPage.vue |
| 3.3 | OperationsPage mock-first 实现：映射摘要统计 + 操作按钮（备份/应用/恢复/dry-run） | OperationsPage.vue |
| 3.4 | RulesOverviewPage mock-first 实现：规则选择 + 详情展开 + [保存规则选择] | RulesOverviewPage.vue |
| 3.5 | 计算准备 mock-first 实现：受影响条目表格 + checkbox 预选 + [▶ 开始计算] + [查看结果] | ComputePrepPage.vue |
| 3.6 | 四页面从 mock 切换到真实 API | 各页面改 import |

---

### Phase 4 — 存量适配 + 迁移收尾

| 步骤 | 对应 TODO | 任务 |
|------|----------|------|
| 4.1 | TODO-22 | 三项迁移：ForestPage 字段迁出到 Settings / RulesOverview / Operations / 计算准备 |
| 4.2 | TODO-20 | 选项卡解耦：审查 + 禁止跨选项卡直接调用 |
| 4.3 | TODO-23 | user config 路径迁入设置页 + 启动导航 |
| 4.4 | TODO-24 | backup dir 语义澄清 |
| 4.5 | TODO-26 | 手动路径 → 手动路径列表 |
| 4.6 | TODO-29 | Settings Database JSON 保存按钮修复（若 Phase 3 未覆盖） |
| 4.7 | TODO-31 | Forest 小地图点击定位修复（几何中心）+ 窗口大小调整 |

---

### 🔒 挂起任务（不在此次重构范围内）

| TODO | 内容 |
|------|------|
| TODO-10 | 空输入校验 |
| TODO-19 | 重复 radio 视觉提示 |

---

## 三、工程质量纪律

1. **每步必绿**：Phase 1 每完成一个子步骤立即 `pytest` 全量；Phase 2 每步 `npm run test`
2. **不可回退边界**：Phase 1/2 完成后，database.json 不再含 managed；localStorage 不再含业务数据。任何试图恢复旧行为的代码视为违规
3. **文档先行**：Phase 1.1 开工前，Phase 0 设计文档必须全部就位
4. **归档不删**：见上方归档规则；旧版移入 `repo_logs/`，主目录只保留当前口径
5. **workspace 状态**：decisions/mapping 存后端工作区目录 `~/.cache/kmm/workspace/{id}/`（详见 `DESIGN_WORKSPACE_MODEL.md`）

---

## 四、关键设计决策记录（本讨论产出）

| # | 决策 | 结论 |
|---|------|------|
| D1 | managed 归属 | 后端工作区目录 `decisions.json` 为权威；请求体中的 `managed_entries` 作为单次计算输入 |
| D6 | compute 端点 database 参数 | 不接收完整 database dict。orchestrator 内部通过 bootstrap 获取。接收 `database_name?` 选择目标 database |
| D7 | workspace 模式（2026-05-16 更新） | 后端工作区目录（decisions/mapping/SVG）— 详见 `DESIGN_WORKSPACE_MODEL.md` |
| D12 | decisions 范围 | managed_entries + branch_decisions 存工作区 `decisions.json`，compute 时由工作区加载并可被请求覆盖 |
| D13 | results 存储粒度 | 完整结果存工作区 `mapping.json`；前端可派生摘要用于展示 |
