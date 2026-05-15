# 2026-05-16 工作区模型裁定记录

> Status: 当前迭代的权威裁定
> 来源: 用户与 arch 关于 DESIGN_SVG_CACHE_AND_FOREST_LIST.md 的讨论

---

## 〇、旧文档处理

- `repo_memo/DESIGN_SVG_CACHE_AND_FOREST_LIST.md` — **归档**。核心前提（快照是计算后产物）被推翻；白名单归属错误；端点命名错误
- 新建 `repo_memo/DESIGN_WORKSPACE_MODEL.md` — 本裁定落地文档

---

## 一、核心裁定：工作区是先行容器，非计算后产物

**旧模型**：快照是计算完成后生成的缓存产物（被动）。

**新模型**：工作区是用户**先创建**的任务容器（主动）。用户在动手之前创建，随后所有操作在此容器内进行。

类比：Git branch / Jupyter Notebook / Photoshop 项目文件——先有容器，再填充内容。

这解决了：
- aggregated rule 无处存放 → 自然属于工作区
- "存哪"三方拉扯 → 一个工作区一个目录，干净利落
- 用户换 database/规则 想试试 → 新建工作区，语义清晰
- 森林列表页定位模糊 → 提升为流程中枢

---

## 二、命名

### 术语
- **工作区** = workspace
- 标识符：`workspace_id`（后端生成）
- 旧 `workspace.json` 概念已彻底废除。新定义是唯一权威——遇见任何 `workspace` 不符合本裁定，错的是旧文档/旧代码

### 代码命名风格
- Python 引擎层（orchestrator 及下属）：**纯小写**，如 `workspacemanager`
- Web API 路由层端点路径：**驼峰**，如 `POST /api/workspace/{workspaceId}/pipeline/compute`
- 前后端名称迥异，避免混淆

---

## 三、工作区生命周期

1. 用户进入工作区列表页 → 点击"新建"
2. **创建时必须选择 database**（绑定后不可变更，换 database 需新建工作区）
3. 后端生成 `workspace_id`，返回前端
4. 用户在工作区内：聚合规则 → 选择决策 → 计算 → 查看森林
5. 工作区可删除，可切换

---

## 四、URL 结构（全量重构）

采用方案 B：工作区 ID 在 URL 路径中。

```
POST   /api/workspace/create                    # 创建工作区
POST   /api/workspace/{workspaceId}/delete       # 删除工作区
GET    /api/workspace/list                       # 列表所有工作区

# 工作区内的操作
POST   /api/workspace/{workspaceId}/rules/aggregate
POST   /api/workspace/{workspaceId}/pipeline/compute
POST   /api/workspace/{workspaceId}/pipeline/run
GET    /api/workspace/{workspaceId}/forest/svg
POST   /api/workspace/{workspaceId}/decisions/save
GET    /api/workspace/{workspaceId}/decisions/load
# ...
```

### 为什么不用 body 传 workspace_id
- URL 不自文档化：看日志/调试时不知道操作的是哪个工作区
- 反 REST 惯例：资源标识应在 URL 中
- 缓存层不可用：反向代理只看 URL
- 中间件/路由分组困难：FastAPI `APIRouter(prefix="/api/workspace/{workspace_id}")` 可以直接做工作区级中间件

---

## 五、架构拓扑

```
orchestrator（唯一调度入口，星形中心）
    │
    ├── workspacemanager  ★ 新增：工作区 CRUD、规则/决策/结果读写
    ├── bootstrap         # 环境初始化（user_config 加载、first_use）
    ├── aggregator        # 规则聚合
    ├── engine            # 计算引擎
    └── backup_ops        # 备份操作
```

### 核心原则（延续方案 B 裁定）
- **orchestrator 是唯一调度入口**
- **路由层不替 orchestrator 做环境准备**：路由层只提取 workspace_id，调用 orchestrator，返回结果
- **路由层不直接调 workspacemanager、aggregator、engine**——全部通过 orchestrator

### 新增下级：workspacemanager
- 职责：工作区目录 CRUD、元信息读写、规则/决策/结果文件读写
- 聚合完成后，orchestrator 调 workspacemanager 存入工作区
- 计算时，orchestrator 从 workspacemanager 取出所需数据，交给 engine
- 计算完毕后，orchestrator 调 workspacemanager 写入 mapping + svg

### 前端不假设资源是文件
- 前端**禁止**拼接或猜测任何工作区内部路径
- 所有资源一律通过端点 + workspace_id 索引
- 约束目标：哪天后端换成 Redis/S3/SQLite，前端一行不改

---

## 六、工作区目录结构（MVP）

```
~/.cache/kmm/workspace/{workspace_id}/
├── meta.json              # 元信息：name, database_name, created_at, app_version
├── aggregated_rule.json   # 聚合后的规则集（后端权威副本）
├── decisions.json         # managed_entries + branch_decisions
├── mapping.json           # compute 产出
├── forest.svg             # 森林可视化图
└── fingerprints.json      # 规则文件 + database 的 sha256（缓存失效校验用）
```

- 目录可扩展（JSON 对象天然可加字段，新文件可直接放入）
- Windows 默认路径：`%appdata%\.cache\kmm\workspace\`
- 路径可由 `user_config` 配置（新增字段 `workspace_dir`），未配置或恢复默认时用上述默认值

---

## 七、localStorage 精简

### 淘汰
```
modmanager:workspace           # 旧 workspace 概念，全部字段作废
  包括：lastDatabase, perDatabase, aggregatedRuleSet, aggregatedRuleHash
```

### 保留 / 新增
```
modmanager:uiState             # 纯 UI 偏好
  ├── libraryVisibility        # 库表可见性
  ├── gameVisibility           # 游戏表可见性
  ├── activeTab                # 当前标签页
  └── sidebarCollapsed         # 侧边栏折叠

modmanager:lastWorkspaceId     # 新增：恢复上次打开的工作区
```

---

## 八、页面流拓扑

```
旧（线性流水线）：
  数据来源 → 规则概览 → 计算准备 → 森林可视

新（中枢式）：
  工作区列表（中枢，应用默认首页）
      ├── 新建工作区 → 规则聚合 → 计算准备 → 森林可视
      ├── 打开已有工作区 → 继续 / 查看 / 重算
      └── 删除工作区
```

### 各页面职责

| 页面 | 旧职责 | 新职责 |
|------|--------|--------|
| 数据来源 | 流水线第一站 | 全局 database 管理（增删改查），与工作区解耦 |
| 规则概览 | 流水线第二站 | 工作区上下文内的规则聚合，结果存入工作区 |
| 计算准备 | 流水线第三站 | 工作区上下文内：用户决策收集，触发计算 |
| 森林可视 | 流水线终点 | **纯查看器**，以 workspace_id 索引 SVG + mapping |
| **工作区列表** | （不存在） | 中枢页面：创建/列表/删除/进入工作区 |

### 计算准备页新增按钮

- "计算" — 计算后跳转到工作区列表（默认行为）
- **"计算并查看"** — 计算后跳过快照列表，直接进入森林可视页查看本次结果

### 工作区列表页特征
- 按创建/更新时间降序排列，最新在最上面
- 标记"最新"
- 预留按钮位置供未来扩展（如查看涉及的 games/mods 等）

---

## 九、TODO 归属

| TODO | 状态 |
|------|------|
| TODO-71（trees 存哪） | 本次实现。完成后自动标记完成 |
| TODO-70（森林图展示打磨） | **独立任务**，不与 TODO-71 挂钩，留待单独讨论 |
| TODO-66（preview 图片） | 外部资源，走白名单机制，不在本次范围 |
| TODO-67（README 查看） | 同上 |
| TODO-10/51/52/53/68/69 | 不动 |
| audit_todo_future 三项 | 不动（可延后） |

---

## 十、外部资源 vs 内部资源

| | 外部资源 | 内部资源 |
|------|---------|---------|
| 是什么 | 本地硬盘文件（kmmrule preview/README） | 本系统产物（SVG、mapping、快照） |
| 前端知道什么 | 文件路径或访问符号（展示用 + 索引用） | 只知道后端给的对象名字（展示用的路径字符串不算真路径） |
| 访问方式 | 资源端点 + 白名单机制 | 业务端点 |
| 白名单文件 | `repo_spec/resource_whitelist.json` | 不需要 |

本次不实现外部资源部分。

---

## 十一、实现范围（MVP）

### 必须做
- [ ] 工作区列表页（创建/删除/进入）
- [ ] 后端 workspace CRUD 端点 + workspacemanager 模块
- [ ] 工作区目录结构 + 元信息读写
- [ ] compute 端点改造为工作区感知（URL 含 workspace_id）
- [ ] 规则聚合结果存入工作区
- [ ] ForestPage 改为接收 workspace_id
- [ ] 淘汰旧 localStorage 字段（modmanager:workspace）
- [ ] 数据来源页降为纯 database 管理
- [ ] 计算准备页加"计算并查看"按钮
- [ ] 规则概览页移到工作区上下文
- [ ] 前端路由拓扑重排（中枢式）
- [ ] URL 全量重构（所有端点加 workspace_id 路径前缀）

### 可延后
- [ ] `lastWorkspaceId` 恢复
- [ ] `activeTab` / `sidebarCollapsed` 迁入 uiState
- [ ] `force_compute` 参数
- [ ] 工作区重命名
- [ ] 外部资源白名单（TODO-66/67）
- [ ] TODO-70 展示打磨
- [ ] audit_todo_future 三项

---

## 十二、文档计划

| 文档 | 操作 |
|------|------|
| `repo_memo/DESIGN_SVG_CACHE_AND_FOREST_LIST.md` | **归档** |
| `repo_memo/DESIGN_WORKSPACE_MODEL.md` | **新建**（本裁定落地文档） |
| `repo_memo/DESIGN_STORAGE.md` | 更新（workspace 路径定义、user_config.workspace_dir 字段） |
| `repo_memo/DESIGN_REST_API.md` | 更新（URL 结构全量重构） |
| `repo_memo/DESIGN_GUI_WORKSPACE.md` | 更新（页面流重排） |
| `repo_memo/DESIGN_ORCHESTRATOR.md` | 更新（新增 workspacemanager 下属） |
| `repo_memo/TERMS_FIELD_FREEZE.md` | 更新（新字段） |

### 文档撰写优先级
1. `DESIGN_WORKSPACE_MODEL.md`（新权威设计，最先写）
2. 其他已有文档按需更新

---

## 十三、执行顺序

1. 文档 — `DESIGN_WORKSPACE_MODEL.md` + 关联文档更新
2. 后端 — workspacemanager 模块 → 端点改造 → orchestrator 集成
3. 前端 — 路由重排 → 工作区列表页 → 各页面改造 → localStorage 清理
4. 验证 — 全链路测试

---

本裁定与 `audit_todo_future.md` 不冲突（审计要求的三项延后事项均不在本次 MVP 范围）。

若本裁定与 `repo_memo/` 下已有文档冲突，以本裁定为准；受影响的文档列出在第 12 节。
