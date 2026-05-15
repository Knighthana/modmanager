# 2026-05-16 工作区模型定义、设计与实现

> TODO-71 完成。工作区从"计算后缓存产物"重构为"用户主动创建的先行容器"。

---

## 〇、前置裁定

讨论文档：`work_memo/2026-05-16_workspace_model_decisions.md`

本次讨论从 `DESIGN_SVG_CACHE_AND_FOREST_LIST.md` 出发，经过三轮深入讨论，推翻旧"快照是计算后产物"模型，确立了新工作区模型的核心裁定：

| 裁定 | 内容 |
|------|------|
| 工作区 | 先行容器——用户在动手前创建，所有后续操作在此容器内进行 |
| 绑定 | 创建时强制选 database，绑定后不可变更 |
| ID | 后端生成（SHA256 trunc 24），前端不假设资源是文件 |
| URL | `/api/workspace/{workspaceId}/...` — REST 惯例，全量重构 |
| 架构 | orchestrator 新增下属 `workspacemanager`（纯小写） |
| 存储 | `~/.cache/kmm/workspace/{id}/` 目录 + user_config 可配置 `workspace_dir` |
| 前端存储 | sessionStorage（主读，Tab 隔离）+ localStorage（留档，新 Tab 回退）|

---

## 一、Phase 1 — 文档体系重构（W1–W7）

### 新建
- `repo_memo/DESIGN_WORKSPACE_MODEL.md` — 10 大节：核心模型、架构拓扑、目录结构、URL 结构（36 个端点）、页面流拓扑（含 §5.6 导航状态管理）、浏览器存储三层方案、WorkspaceListPage 规范

### 废弃 / 归档
- `repo_memo/DESIGN_SVG_CACHE_AND_FOREST_LIST.md` → **superseded**
- `repo_memo/DESIGN_GUI_WORKSPACE.md` → 重写为 superseded 存根，记录旧 localStorage 迁移表

### 更新
| 文档 | 核心改动 |
|------|---------|
| `DESIGN_STORAGE.md` | 存储分类 5→6；新增 `workspace_dir` 字段；用户决策/结果从 localStorage 迁移到工作区目录 |
| `DESIGN_REST_API.md` | 端点表从 18→36 个（含 16 个新工作区端点）；schema 精简；包结构更新 |
| `DESIGN_ORCHESTRATOR.md` | 拓扑图新增 workspacemanager 节点；compute/run 签名改为 `workspace_id` |
| `DESIGN_GUI.md` | ForestPage/ConflictsPage/DatabaseSelector 替换旧 localStorage 引用 |
| `DESIGN_FRONTEND_LAYER_INDEPENDENCE.md` | useDataSourceStore/useComputeStore 从"刷新后丢弃"改为工作区持久化 |
| `PATTERNS_ENGINEERING.md` | 第 11/12 条更新：业务数据后端权威 + 工作区持久化 |
| `TERMS_FIELD_FREEZE.md` | 新增 5 个冻结字段（`workspace_id`, `workspace_dir`, `currentWorkspaceId`, `decisions.*`）；废弃 6 个旧字段 |
| `DESIGN_DATA_CLEANUP.md` | 状态恢复表/验收条件全部替换为工作区模型 |

---

## 二、Phase 2 — 后端实现（W8–W15）

### 新增模块
| 文件 | 行数 | 说明 |
|------|:--:|------|
| `src/modmanager/core/workspacemanager.py` | 198 | WorkspaceManager 类：create/delete/list + 6 对读写方法 |
| `src/modmanager_web/routes/workspace.py` | 230 | 12 个端点（CRUD 4 + decisions 2 + forest 2 + rules 2 + pipeline 2） |

### 改造模块
| 文件 | 改动 |
|------|------|
| `orchestrator.py` | 新增 `compute_ws(workspace_id)` + `run_ws(workspace_id)` |
| `schemas.py` | 新增 `CreateWorkspaceRequest`、`SaveDecisionsRequest` |
| `app.py` | 注册 workspace 路由 |

### 验证
- 396 个已有后端测试全部通过
- 工作区 API 端到端测试通过（create → list → meta → decisions save/load → delete）

---

## 三、Phase 3 — 前端实现（W16–W22）

### 新增页面
| 文件 | 说明 |
|------|------|
| `WorkspaceListPage.vue` | 工作区列表页：列表/创建/删除/进入，按 updated_at 降序 |

### 路由重构
```
旧：/datasource → /rules-overview → /compute-prep → /forest  (线性流水线)
新：/ (工作区列表) ← 中枢
      ├── /workspace/:id/rules
      ├── /workspace/:id/compute
      └── /workspace/:id/forest
```
旧路由全部重定向到 `/`。

### 页面改造
| 页面 | 改动 |
|------|------|
| ForestPage | 接收 `workspace_id`；SVG 从 `GET /api/workspace/{id}/forest/svg` 获取 |
| ComputePrepPage | 工作区上下文；新增"计算并查看"按钮（跳过列表直达森林） |
| RulesOverviewPage | 聚合走 `POST /api/workspace/{id}/rules/aggregate` |
| DataSourcePage | 降为纯 database 管理；存储从 `loadWorkspace` 迁移到 `loadUiState('datasource')` |

### 存储层重建
- `persistence.ts` 重写：sessionStorage 主读 + localStorage 留档
- `LayoutShell.vue`：工作区感知导航栏（无工作区时禁用相关菜单项）
- `main.ts`：启动时调用 `migrateOldWorkspace()` 清除旧 `modmanager:workspace` key

---

## 四、Phase 4 — 清理与验证（W23–W25）

### W23 — 旧 workspace.py 残留
经代码搜索确认：`src/` 下无任何旧 `workspace.py` 文件残留。旧 workspace REST 端点已在方案 B 阶段删除。

### W24 — 测试适配
14 个前端测试从旧 localStorage workspace 模型适配到新工作区模型：
- ComputePrepPage: 4 tests
- ForestPage: 1 test
- OperationsPage: 4 tests
- RulesOverviewPage: 3 tests
- SettingsPage: 1 test
- DataSourcePage: 1 test

### W25 — 全链路验证
- 后端：396 passed, 1 subtests passed
- 前端：16 test files, 137 tests passed
- 共计 533 tests 全部通过，零失败

---

## 五、统计数据

| 指标 | 数值 |
|------|:--:|
| 新建文件 | 6 |
| 修改文件 | 20 |
| 归档文件 | 1 |
| 新增代码行 | ~1280 |
| 删除代码行 | ~330 |
| 工作区端点 | 12 |
| 后端测试 | 396 |
| 前端测试 | 137 |

---

## 六、本次相关的 TODO

| TODO | 状态 |
|------|:--:|
| TODO-71 — trees 到底存哪 | ✅ 完成 |
| TODO-70 — 森林图展示打磨 | 独立任务，不随本次完成 |
| TODO-10/51-53/66-69 | 不动 |
| audit_todo_future 三项 | 不动 |

TODO-71 是本次会话的核心交付。本次完成了从设计方案讨论到前后端全栈实现的完整闭环。
