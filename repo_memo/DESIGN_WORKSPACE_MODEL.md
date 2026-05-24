# DESIGN_WORKSPACE_MODEL — 工作区模型

> Status: stable (初版冻结)
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义工作区的核心模型——先行容器、生命周期、目录结构、前后端契约、页面流拓扑。本模型替代旧的"快照是计算后产物"设计与 localStorage 分散存储模型。

创建：2026-05-16
实现状态：已落地并持续生效
来源裁定：`work_memo/2026-05-16_workspace_model_decisions.md`

---

## 0. 前置决策汇总

| Q# | 决策 | 备注 |
|-----|------|------|
| Q1 | 工作区是**先行容器**，用户在动手前创建，随后所有操作在此容器内进行 | 替代旧"快照是计算后产物"模型 |
| Q2 | 工作区创建时强制绑定一个 database，绑定后不可变更 | 换 database 需新建工作区 |
| Q3 | `workspace_id` 由后端生成，前端不假设资源是文件系统中的文件 | 前端永远不知道内部文件名/路径 |
| Q4 | 工作区 ID 在 URL 路径中：`POST /api/workspace/{workspaceId}/...` | REST 惯例，URL 自文档化 |
| Q5 | orchestrator 新增下属 `workspacemanager`（纯小写），负责工作区 CRUD 与文件读写 | 路由层不直接调 workspacemanager，全部通过 orchestrator |
| Q6 | 工作区存放于 `~/.cache/kmm/workspace/{workspace_id}/`，路径可由 user_config 配置 | Windows 换算 `%LOCALAPPDATA%/kmm/workspace/` |
| Q7 | 前端浏览器存储：`sessionStorage`（主读源） + `localStorage`（新 Tab 初始化回退），按 workspace_id 分键 | 淘汰旧的 `modmanager:workspace` 全部字段 |

---

## 1. 核心模型

### 1.1 工作区是先行容器

**旧模型**：快照是计算完成后被动生成的缓存产物。用户操作了一圈，系统在背后悄悄产生一个快照。

**新模型**：工作区是用户**主动创建**的任务容器。用户在心里想——
> "我要搞一件事：用这套规则，看这个数据库，做这些决策，得到那个森林。"

这个"一件事"就是一个工作区。创建先于填充，容器先于内容。

类比：Git branch / Jupyter Notebook / Photoshop 项目文件。

### 1.2 工作区生命周期

```
创建（选 database）
    │
    ├── 聚合规则 → 规则集存入工作区
    ├── 收集决策 → 决策存入工作区
    ├── 执行计算 → mapping + SVG 存入工作区
    ├── 查看森林 → 以 workspace_id 索引结果
    ├── 删除工作区 → 清空目录
    └── （随时可新建另一个工作区，尝试不同参数）
```

- 创建：用户在 WorkspaceListPage 点"新建"，选择 database，后端生成 `workspace_id` 并建目录
- 填充：用户在工作区内操作（聚合规则、选决策、计算），每一步结果写入该工作区目录
- 查看：用户进入 ForestsPage，以 `workspace_id` 索引 SVG 和 mapping
- 删除：用户在工作区列表页删除，后端清空对应目录
- 切换：用户回到 WorkspaceListPage，选择另一个工作区进入

### 1.3 与 database 的关系

- 一个工作区绑定**一个** database，创建时选定，不可变更
- 若用户想用另一个 database，应新建工作区
- database 与工作区解耦：database 是全局可复用的扫描数据，工作区是某次任务的特定上下文

### 1.4 前端不假设资源形式

前端持有后端返回的 `workspace_id`（一个字符串），通过端点 + `workspace_id` 索引一切资源。前端**禁止**拼接或猜测工作区内部路径。约束目标：哪天后端换成 Redis / S3 / SQLite，前端一行代码不改。

---

## 2. 架构拓扑

### 2.1 orchestrator 与下属

```
orchestrator（唯一调度入口，星形中心）
    │
    ├── workspacemanager  ★ 新增：工作区 CRUD、规则/决策/结果读写
    ├── bootstrap         # 环境初始化（user_config 加载、first_use）
    ├── aggregator        # 规则聚合
    ├── engine            # 计算引擎
    └── backup_ops        # 备份操作
```

**核心原则（延续）**：
- orchestrator 是唯一调度入口
- 路由层**不替** orchestrator 做环境准备——路由层只提取参数，调用 orchestrator，返回结果
- 路由层**不直接调** workspacemanager、aggregator、engine——全部通过 orchestrator

### 2.2 workspacemanager 的接口

```python
# src/modmanager_web/core/workspacemanager.py

class WorkspaceManager:
    """工作区生命周期管理。由 orchestrator 调用，路由层不直接使用。"""

    def create(self, name: str, database_name: str) -> str:
        """创建工作区目录和 meta.json，返回 workspace_id。"""

    def delete(self, workspace_id: str) -> None:
        """删除工作区目录及全部内容。"""

    def list_all(self) -> list[dict]:
        """列出所有工作区元信息（id, name, database_name, created_at, ...）。"""

    def read_meta(self, workspace_id: str) -> dict:
        """读取工作区 meta.json。"""

    def write_aggregated_rule(self, workspace_id: str, rule_set: dict) -> None:
        """将聚合规则集写入工作区。"""

    def read_aggregated_rule(self, workspace_id: str) -> dict:
        """从工作区读取聚合规则集。"""

    def write_decisions(self, workspace_id: str, decisions: dict) -> None:
        """将用户决策写入工作区。"""

    def read_decisions(self, workspace_id: str) -> dict:
        """从工作区读取用户决策。"""

    def write_mapping(self, workspace_id: str, mapping: dict) -> None:
        """将计算结果 mapping 写入工作区。"""

    def read_mapping(self, workspace_id: str) -> dict:
        """从工作区读取计算结果 mapping。"""

    def write_svg(self, workspace_id: str, svg_content: str) -> None:
        """将森林 SVG 写入工作区。"""

    def read_svg(self, workspace_id: str) -> str:
        """从工作区读取森林 SVG 内容。"""

    def write_fingerprints(self, workspace_id: str, fingerprints: dict) -> None:
        """写入数据指纹（规则文件 + database 的 sha256）。"""

    def read_fingerprints(self, workspace_id: str) -> dict:
        """读取数据指纹。"""

    def exists(self, workspace_id: str) -> bool:
        """检查工作区是否存在。"""
```

### 2.3 orchestrator 调用 workspacemanager

```
orchestrator.compute(workspace_id, ...)
    │
    ├── ws = workspacemanager
    ├── rule_set = ws.read_aggregated_rule(workspace_id)
    ├── decisions = ws.read_decisions(workspace_id)
    ├── database_path = resolve_database(ws.read_meta(workspace_id).database_name)
    ├── result = engine.compute(rule_set, database_path, decisions)
    ├── ws.write_mapping(workspace_id, result.mapping)
    ├── ws.write_svg(workspace_id, result.svg)
    └── ws.write_fingerprints(workspace_id, compute_fingerprints(...))
```

路由层只做：

```python
@app.post("/api/workspace/{workspace_id}/pipeline/compute")
async def compute(workspace_id: str):
    return orchestrator.compute(workspace_id=workspace_id, ...)
```

---

## 3. 目录结构

### 3.1 默认路径

| 平台 | 路径 |
|------|------|
| Linux | `~/.cache/kmm/workspace/{workspace_id}/` |
| Windows | `%LOCALAPPDATA%/kmm/workspace/{workspace_id}/` |

### 3.2 user_config 可配置

`user_config.json` 新增字段：

| 字段 | 类型 | 必需 | 说明 |
|------|------|:--:|------|
| `workspace_dir` | `string \| null` | 否 | 工作区根目录。`null` 或未设置时使用默认路径 |

### 3.3 目录内容（MVP）

```
{workspace_dir}/{workspace_id}/
├── meta.json              # 元信息
├── aggregated_rule.json   # 聚合后的规则集（后端权威副本）
├── decisions.json         # managed_entries + branch_decisions
├── mapping.json           # compute 产出的最终映射
├── forest.svg             # 森林可视化图
└── fingerprints.json      # 规则文件 + database 的 sha256 指纹
```

### 3.4 各文件结构

#### meta.json

```json
{
  "schema_namespace": "KMM_WorkspaceMeta",
  "schema_version": "knighthana@0.1.0",
  "workspace_id": "abc123def456",
  "name": "我的第一次实验",
  "database_name": "default",
  "created_at": "2026-05-16T10:30:00Z",
  "updated_at": "2026-05-16T10:35:00Z",
  "app_version": "1.0.0"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_namespace` | `string` | Schema 命名空间标识，固定为 `"KMM_WorkspaceMeta"` |
| `schema_version` | `string` | Schema 版本号，如 `"knighthana@0.1.0"` |
| `workspace_id` | `string` | 后端生成的唯一标识 |
| `name` | `string` | 用户指定的工作区名称 |
| `database_name` | `string` | 绑定的 database 名称（创建时选定，不可变） |
| `created_at` | `string` | ISO 8601 时间戳 |
| `updated_at` | `string` | 最后修改时间（每次写入任一文件时更新） |
| `app_version` | `string` | 创建工作区时的应用版本 |

#### aggregated_rule.json

聚合规则模块（`aggregator`）的标准输出格式。详见 `DESIGN_RULE_AGGREGATOR.md`。

#### decisions.json

```json
{
  "schema_namespace": "KMM_WorkspaceDecisions",
  "schema_version": "knighthana@0.1.0",
  "managed_entries": {
    "game": { "appid": ["/path/to/game"] },
    "mod": { "mixed_id": ["/path/to/mod"] }
  },
  "branch_decisions": {
    "root_path": "chosen_source_path"
  }
}
```

格式与 `TERMS_FIELD_FREEZE.md` 冻结定义一致。

#### mapping.json

计算引擎输出的最终映射数组。详见 `DESIGN_FOREST_MODEL.md`。

#### fingerprints.json

```json
{
  "schema_namespace": "KMM_WorkspaceFingerprints",
  "schema_version": "knighthana@0.1.0",
  "kmmrule": "sha256:abc...xyz",
  "database": "sha256:def...uvw",
  "computed_at": "2026-05-16T10:35:00Z"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_namespace` | `string` | Schema 命名空间标识，固定为 `"KMM_WorkspaceFingerprints"` |
| `schema_version` | `string` | Schema 版本号，如 `"knighthana@0.1.0"` |
| `kmmrule` | `string` | 参与聚合的规则文件内容的 sha256 |
| `database` | `string` | 绑定的 database 文件内容的 sha256 |
| `computed_at` | `string` | 计算时间 |

用于判断缓存是否失效：打开工作区时比对当前磁盘文件的 sha256 与 fingerprints 中记录，不一致则提示"底层数据已变化，建议重新计算"。

### 3.5 扩展预留

- 目录可随时新增文件（如 `export.zip`、`diff.json`），不破坏现有结构
- `meta.json` 的 JSON 对象可随时新增字段
- 文件格式版本号（如 `snapshot_version`）暂不需要——MVP 规模下直接改结构即可

---

## 4. URL 结构

### 4.1 总体规则

工作区在 URL 路径中体现为 `{workspace_id}` 路径段。所有与工作区相关的端点前缀为 `/api/workspace/{workspace_id}/`。

### 4.2 端点表

#### 工作区管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/workspace/create` | 创建工作区。body: `{ name, database_name }` → `{ workspace_id, meta }` |
| `POST` | `/api/workspace/{workspace_id}/delete` | 删除工作区。→ `204 No Content` |
| `GET` | `/api/workspace/list` | 列出所有工作区。→ `[{ workspace_id, name, database_name, created_at, ... }]`（按 `updated_at` 降序） |
| `GET` | `/api/workspace/{workspace_id}/meta` | 获取单个工作区元信息。→ `meta.json` 内容 |

#### 规则（工作区上下文内）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/workspace/{workspace_id}/rules/aggregate` | 聚合规则并存入工作区。body: `{ rule_paths }` → `{ ok, rule_set }` |
| `GET` | `/api/workspace/{workspace_id}/rules/aggregated` | 读取工作区中已聚合的规则集。→ `rule_set dict` |

#### 流水线（工作区上下文内）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/workspace/{workspace_id}/pipeline/compute` | 执行计算；从工作区读取 `aggregated_rule` 与 `decisions`，调用引擎计算，结果（`mapping`、`svg`、`fingerprints`）写回工作区；通过 SSE 返回，最终事件包含经 `adapt_pipeline_result` 序列化的 `PipelineResult`。 |
| `POST` | `/api/workspace/{workspace_id}/pipeline/run` | 在工作区上下文执行全流水线（compute → backup → apply）；通过 SSE 返回 `PipelineResult`（由 `adapt_pipeline_result` 序列化）。 |
| `POST` | `/api/workspace/{workspace_id}/pipeline/backup` | 在工作区上下文执行差异备份；通过 SSE 返回 `PipelineResult`（含 `backup_result`、`backed_up` 等字段，序列化由 `adapt_pipeline_result` 完成）。 |
| `POST` | `/api/workspace/{workspace_id}/pipeline/apply` | 在工作区上下文提交 apply（通过 `dispatch()` 以 `Intent.APPLY` 进入 Resolver → Planner → 原语管线）；通过 SSE 返回 `PipelineResult`（含 `apply_result`、`applied`、`apply_warnings` 等）。 |

#### 决策（工作区上下文内）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/workspace/{workspace_id}/decisions/save` | 保存用户决策到工作区。body: `{ managed_entries, branch_decisions }` |
| `GET` | `/api/workspace/{workspace_id}/decisions/load` | 从工作区读取用户决策。→ `decisions.json` 内容 |

#### 森林可视（工作区上下文内）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/workspace/{workspace_id}/forest/svg` | 读取森林 SVG。Content-Type: `image/svg+xml` |
| `GET` | `/api/workspace/{workspace_id}/forest/mapping` | 读取最终映射结果。→ `mapping.json` 内容 |

#### 不受工作区影响的端点（全局）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/database/generate` | 扫描生成 database（全局操作） |
| `POST` | `/api/database/read` | 读取 database |
| `POST` | `/api/database/save` | 保存 database |
| `POST` | `/api/config/save` | 保存 user_config |
| `POST` | `/api/config/discover` | 发现 user_config |
| `POST` | `/api/rules/scan` | 扫描规则文件（全局操作） |
| `POST` | `/api/rules/read` | 读取规则文件内容 |
| `POST` | `/api/rules/affected-entries` | 查询受影响条目 |
| `POST` | `/api/backups/list` | 列出备份 |
| `POST` | `/api/backups/inspect` | 查看备份详情 |

约束说明（强制清退）：

- 不再提供 generic `/api/pipeline/backup` 与 `/api/pipeline/apply` 执行端点。
- backup/apply 执行仅允许走 workspace 流水线路由。

### 4.3 已删除的端点

以下端点随旧 workspace 模型一并移除：

- ~~`POST /api/workspace/save-inputs`~~
- ~~`POST /api/workspace/save-decisions`~~
- ~~`POST /api/workspace/save-results`~~
- ~~`GET /api/workspace/status`~~

（以上端点已在方案 B 裁定中删除。`DESIGN_REST_API.md` 应同步移除这些条目。）

### 4.4 URL 风格说明

- Python 引擎层（orchestrator 及下属）：**纯小写**，如 `workspacemanager`
- Web API 路由层端点路径：**驼峰**，如 `POST /api/workspace/{workspaceId}/pipeline/compute`
- 前后端名称迥异，避免混淆

---

## 5. 页面流拓扑

### 5.1 中枢式结构

```
旧（线性流水线）：
  数据来源 → 规则概览 → 计算准备 → 森林可视

新（中枢式）：
  工作区列表（中枢，应用默认首页）
      ├── 新建工作区 → 规则概览 → 计算准备 → 森林可视
      ├── 打开已有工作区 → （进入上述流程的任一阶段）
      └── 删除工作区
```

### 5.2 各页面职责

| 页面 | 新职责 | 路由 |
|------|--------|------|
| **WorkspaceListPage** | 工作区中枢：列表/创建/删除/进入 | `/`（默认首页） |
| **DataSourcePage** | 全局 database 管理（增删改查），与工作区解耦 | `/datasource` |
| **RulesOverviewPage** | 工作区上下文内：聚合规则，结果存入工作区 | `/workspace/{id}/rules` |
| **ComputePrepPage** | 工作区上下文内：收集用户决策，触发计算 | `/workspace/{id}/compute` |
| **ForestPage** | **纯查看器**：以 workspace_id 索引 SVG + mapping | `/workspace/{id}/forest` |
| AdvancedPage | 调试/高级（不变） | `/advanced` |
| SettingsPage | 设置（不变） | `/settings` |

### 5.3 页面进入方式

```
WorkspaceListPage（首页）
  ├── 点击 DataSource（导航栏） → DataSourcePage（全局 database 管理）
  ├── 点击 Settings（导航栏） → SettingsPage
  ├── 点击工作区卡片"进入" → 进入该工作区
  │     └── 根据工作区状态，跳转到：
  │           ├── 尚未聚合规则 → /workspace/{id}/rules
  │           ├── 尚未计算 → /workspace/{id}/compute
  │           └── 已有结果 → /workspace/{id}/forest
  └── 点击"新建工作区" → 弹出对话框 → 输入名称 + 选 database → 创建 → /workspace/{id}/rules
```

### 5.4 计算准备页按钮

| 按钮 | 行为 |
|------|------|
| **计算** | `compute` → 完成后跳转到 WorkspaceListPage（用户可在列表中看到最新结果） |
| **计算并查看** | `compute` → 完成后**直接跳转**到 `/workspace/{id}/forest`，跳过列表 |

### 5.5 森林可视页收窄

ForestPage 不再负责计算触发或参数管理，只做一件事：**把树的展示做好**。这是 TODO-70 的范畴，不在本次实现范围。

### 5.6 前端导航状态："当前工作区"

#### 问题

工作区相关页面的 URL 自带 `workspace_id`（如 `/workspace/abc123/rules`），前端可直接从 `route.params` 获取。但全局页面（DataSourcePage、SettingsPage 等）的 URL 不含工作区信息。用户从列表进入工作区，再跳到全局页面，再点导航栏"计算准备"时，前端需要知道用户"在哪个工作区里"。

#### 方案：Pinia 内存状态 + 多道防护

前端 Pinia store 维护一个 `currentWorkspaceId: string | null`：

```
用户进入 /workspace/abc123/*  → store.currentWorkspaceId = "abc123"
用户跳到 /datasource           → store 仍持有 "abc123"（不丢）
用户点"规则概览"              → 从 store 读 → 构造 /workspace/abc123/rules
用户从未进入任何工作区        → store.currentWorkspaceId = null
                                  → 点工作区相关导航 → 跳转 WorkspaceListPage + 提示
```

#### 防护一：URL → store 强制同步

路由守卫或页面 `onMounted` 中，每次进入 `/workspace/:id/*` 路由时强制同步：

```typescript
store.currentWorkspaceId = route.params.workspace_id
sessionStorage.setItem('modmanager:currentWorkspaceId', route.params.workspace_id)
```

URL 是导航权威，store 只是缓存。这样即使 store 持有旧值，进入工作区页面后立即被 URL 修正。

#### 防护二：进入前验证工作区存在

进入任何 `/workspace/:id/*` 页面时，先调 `GET /api/workspace/{id}/meta`。若 404：

1. 弹提示"该工作区已被删除"
2. 清空 `store.currentWorkspaceId`
3. 跳转到 WorkspaceListPage

这覆盖了"用户在另一个 Tab 或列表页删除了当前工作区"的场景。

#### 防护三：无工作区时导航栏提示

`store.currentWorkspaceId === null` 时，侧栏中工作区相关项（"规则概览""计算准备""森林可视""冲突裁决"）灰显。文本仅保留 emoji + 名称（如 `📋 规则概览`），无过长说明文字。点击灰显项弹出 `el-popover` 气泡提示"请先在 📂 工作区 页面创建或选择一个工作区"。

用户创建/进入工作区后，菜单项恢复正常路由链接。

#### 多 Tab 隔离：`sessionStorage`

`modmanager:currentWorkspaceId` 存储在 `sessionStorage` 而非 `localStorage`。Pinia store 中的 `currentWorkspaceId` 是其运行时镜像——页面初始化时从 sessionStorage 读入，进入工作区页面时两者同时更新。

`sessionStorage` 特性：**每个 Tab 独立存储，同 Tab 内跨刷新持久，关 Tab 即清**。

| 场景 | `localStorage` | `sessionStorage` |
|------|---------------|-----------------|
| Tab A 打开工作区 abc，Tab B 打开工作区 xyz | Tab B 写入覆盖 Tab A | 各自独立，互不干扰 |
| Tab A 刷新 | 读到 Tab B 写的错误值 ❌ | 读到自己的 abc ✅ |
| 浏览器关闭重开 | 残留上次垃圾值 | 清空，干干净净从列表开始 ✅ |
| 复制 Tab（Duplicate Tab） | 共享值，可能冲突 | Chrome 复制时快照，之后各自独立 ✅ |

复制 Tab 场景对用户价值高：用户在原 Tab 打开工作区 abc，复制 Tab，在新 Tab 切换到 xyz。两个 Tab 各自记住自己的 `currentWorkspaceId`，刷新不丢，互不干扰——可同时对比两棵树。

`uiState`（`libraryVisibility`、`gameVisibility` 等）保留在 `localStorage`——侧边栏折叠、表格可见性这类偏好，用户在一个 Tab 改了，另一个 Tab 同步是预期行为。

---

## 6. 前端浏览器存储

### 6.1 原则

- **sessionStorage 是主读源**（Tab 隔离，刷新不丢）。每个 Tab 内改动后立即生效，互不干扰
- **localStorage 是留档**（新 Tab 初始化回退源）。仅在新 Tab 打开、sessionStorage 为空时被读一次，之后不再回退
- 后端是业务数据的唯一权威（规则、决策、映射、SVG）。前端不做业务数据持久缓存

### 6.2 旧结构淘汰

以下全部删除，职责迁移到后端工作区目录或移除：

```json
modmanager:workspace        ← 整个 key 删除
  包含：lastDatabase, perDatabase, aggregatedRuleMeta,
        selectedRulePaths, aggregatedRuleHash

modmanager:lastDatabase     ← 删除（工作区绑定 database，创建时选定）
modmanager:decisions:*      ← 删除（存入工作区 decisions.json）
modmanager:results:*        ← 删除（存入工作区 mapping.json）
```

### 6.3 新结构

#### sessionStorage（每 Tab 独立，主读源）

```
modmanager:sidebarCollapsed              # 侧边栏折叠状态
modmanager:activeTab                     # 当前标签页
modmanager:currentWorkspaceId            # 当前活跃工作区 ID
modmanager:uiState:datasource            # DataSourcePage 全局可见性 + 表单
modmanager:uiState:{workspace_id}        # ComputePrepPage 工作区级可见性
```

#### localStorage（全局留档，仅新 Tab 初始化回退）

```
modmanager:sidebarCollapsed
modmanager:uiState:datasource
modmanager:uiState:{workspace_id}
```

注意：`activeTab` 和 `currentWorkspaceId` 不在 localStorage 中——新 Tab 默认进 WorkspaceListPage，不需要跨 Tab 共享这些值。

### 6.4 读写规则

```
写：用户改动
  → sessionStorage.setItem(key, value)     # 本 Tab 立即生效
  → localStorage.setItem(key, value)       # 为下次新 Tab 留档

读：页面初始化
  val = sessionStorage.getItem(key)
  if val != null:
      使用 val                                # 本 Tab 内已有值，直接用
  else:
      val = localStorage.getItem(key)         # 新 Tab，从留档回退
      if val != null:
          sessionStorage.setItem(key, val)    # 写入 session，后续不再回退
          使用 val
      else:
          使用默认值                          # 首次使用，无历史留档
```

**删除工作区**时，前端顺带清理 `localStorage['modmanager:uiState:{id}']` 和 `sessionStorage['modmanager:uiState:{id}']`。

### 6.5 为什么这样设计

| 问题 | 解法 |
|------|------|
| Tab 隔离 | sessionStorage 每 Tab 独立——Tab A 和 Tab B 各维护各的可见性 |
| 跨会话持久 | localStorage 留档——下次新 Tab 回退到上次任一 Tab 最后写入的值 |
| "上次改动丢失" | 每次改动立即写 localStorage（同步写盘，不依赖 beforeunload） |
| 无后端污染 | 全是前端自己的存储——CLI 不会见到任何前端专属文件 |
| 两个 Tab 互相覆盖 | 与 sidebarCollapsed 同款冲突模式，概率极低，接受 |

### 6.6 各页面可见性归属

| 页面 | 性质 | 存储 key |
|------|------|------|
| **DataSourcePage** | 全局（database 管理，不绑定工作区） | `modmanager:uiState:datasource` |
| **ComputePrepPage** | 工作区上下文 | `modmanager:uiState:{workspace_id}` |

DataSourcePage 的表单状态（`discoveryMode`、`manualPaths`、`greedyParsing`）也存入 `modmanager:uiState:datasource`。

### 6.7 workspace store

前端 Pinia store 中维护 `currentWorkspaceId`（当前活跃工作区，内存态）。页面初始化时从 `sessionStorage['modmanager:currentWorkspaceId']` 读入；进入 `/workspace/:id/*` 页面时两者同步更新。详见 §5.6。

工作区内的所有业务数据（规则、决策、结果）以后端工作区目录为权威——前端不做持久缓存。

---

## 7. WorkspaceListPage

### 7.1 职责

1. 调用 `GET /api/workspace/list` 获取所有工作区
2. 展示工作区卡片列表，按 `updated_at` 降序（最新在最上面），标记 `最新` 标签
3. 提供交互：
   - **新建**：弹出对话框，输入名称 + 选择 database → `POST /api/workspace/create`。创建成功后**不自动跳转**——停留在列表页，在新卡片上弹出一次性 popover 提示"创建成功！请点击进入按钮开始安排工作"，用户自行决定何时进入
   - **进入**：跳转到对应工作区（默认进入规则概览页）
   - **删除**：弹出确认对话框 → `POST /api/workspace/{id}/delete` → 刷新列表
   - **刷新**：重新 GET 列表
4. 创建对话框中的 database 下拉选项来自 `user_config.databases` 的 keys

### 7.2 UI 规范

**按钮**（语义色区分操作危险性）：

| 按钮 | 类型 | 大小 | 文字 |
|------|------|:--:|------|
| 新建工作区 | `type="primary"`（蓝） | default | `➕ 新建工作区` |
| 进入 | `type="success"`（绿） | small | `▶ 进入` |
| 删除 | `type="danger"`（红） | small | `🗑 删除` |

**删除确认对话框**：`confirmButtonType='danger'`（红），按钮文字 `🗑 确认删除` / `✖ 取消`。

**卡片**：

```
┌──────────────────────────────────────────────┐
│  📂 工作区                        [➕ 新建]   │
├──────────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐     │
│  │ 📋 我的第一次实验                     │     │
│  │ 🗄 database: default                 │     │
│  │ 🕐 2026-05-16 10:30   🆕 最新       │     │
│  │              [▶ 进入] [🗑 删除]      │     │
│  └─────────────────────────────────────┘     │
└──────────────────────────────────────────────┘
```

**创建成功提示**：新卡片上显示 `el-popover`（`placement="top"`），内容为"创建成功！请点击进入按钮开始安排工作"。用户点击进入后自动清除。此提示仅出现在刚创建的工作区卡片上，切换页面后不残留。

### 7.3 扩展预留

卡片上预留按钮位置供未来功能：
- 查看涉及的 games / mods
- 重命名工作区
- 导出 / 导入
- 基于此工作区克隆新工作区

---

## 8. 不在本文档范围

| 事项 | 说明 |
|------|------|
| 资源白名单机制 | 独立的模型，仅用于外部资源请求（kmmrule preview/README）；当前以 `repo_spec/resource_whitelist.json` 作为规范来源，后续可迁移为独立设计文档 |
| TODO-70（森林图展示打磨） | 森林可视页的纯展示优化——小地图比例、滚动条、放缩数值。独立任务，与工作区模型无关 |
| `force_compute` 参数 | compute 端点的缓存跳过标志，MVP 后可加 |
| 外部资源端点（preview/README） | TODO-66/67 范畴 |
| `useAppStore` 唯一写者 | ✅ 已完成。组件通过 Pinia `useAppStore` 读写浏览器存储，不直接 import persistence.ts。Tauri 迁移时仅改 persistence 底层 |
| API 调用规则 | ✅ 已完成。`API_ENDPOINTS` 常量不含 `API_BASE`，路径为相对路径；`apiPost`/`apiGet`/`streamSse` 内部拼接 `API_BASE + path`。详见 `DESIGN_FRONTEND_LAYER_INDEPENDENCE.md` §1 |

---

## 9. 权威文档引用

本文档引用以下权威文档。若冲突，以本文档（新模型）为准——旧文档需按本文档更新：

| 文档 | 关系 | 需要更新 |
|------|------|:--:|
| `DESIGN_STORAGE.md` | workspace 目录路径定义归属 | ✅ 新增 `workspace_dir` 字段与目录类型 |
| `DESIGN_ORCHESTRATOR.md` | workspacemanager 下属拓扑 | ✅ 新增 workspacemanager 节点与接口 |
| `DESIGN_REST_API.md` | URL 全量重构 | ✅ 端点表改写，URL 加 workspace_id 前缀 |
| `repo_logs/DOC_ARCHIVE_2026-05-19_DESIGN_GUI_WORKSPACE.md` | 旧 localStorage 模型被替代 | ✅ 已归档，由本文档替代 |
| `TERMS_FIELD_FREEZE.md` | 新增冻结字段 | ✅ 新增 workspace 相关字段 |
| `DESIGN_FOREST_MODEL.md` | 不变 | 否 |
| `DESIGN_ENGINE_INVARIANTS.md` | 不变 | 否 |
| `DESIGN_RULE_AGGREGATOR.md` | 不变 | 否 |

---

## 10. 实现优先级

1. 文档（本文档 + 关联文档更新）
2. 后端 `workspacemanager` 模块 → 端点改造 → orchestrator 集成
3. 前端路由重排 → WorkspaceListPage → 各页面改造 → localStorage 清理
4. 全链路验证
