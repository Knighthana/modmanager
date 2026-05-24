# DESIGN_STORAGE — 存储与默认位置规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 冻结项目所有持久化存储的分类、默认位置、搜索策略与生命周期。作为跨模块存储行为的唯一权威来源。
> 更新：2026-05-16 — 新增工作区存储分类与 `workspace_dir` 字段；前端决策/结果迁移到后端工作区目录


---

## 1. 存储分类

项目中的持久化存储分为六类：

| 分类 | 特征 | 示例 |
|------|------|------|
| **用户配置** | 控制工具行为的首选项，用户可编辑 | `user_config.json` |
| **磁盘扫描数据** | 工具扫描磁盘产生的客观数据 | `database.json` |
| **工作区** | 用户创建的任务容器，内含规则/决策/结果/SVG | `~/.cache/kmm/workspace/{id}/` |
| **运行产出** | 流水线运行的中间文件 | 无（聚合结果已迁移至工作区） |
| **备份产物** | 文件替换前的安全副本，不可自动丢弃 | `*.kmmbackup` 目录 |
| **前端浏览器存储** | 纯 UI 偏好 + Tab 级导航状态 | `localStorage:uiState` / `sessionStorage:currentWorkspaceId` |

---

## 2. 平台默认路径

### 2.1 基础路径常量

| 概念 | Linux | Windows |
|------|-------|---------|
| **用户配置目录** | `~/.config/kmm/` | `%APPDATA%/kmm/` |
| **工作区默认目录** | `~/.cache/kmm/workspace/` | `%LOCALAPPDATA%/kmm/workspace/` |
| **数据库默认目录** | `~/.local/share/kmm/` | `%LOCALAPPDATA%/kmm/database/` |
| **备份目录** | Steam 库下（详见 `DESIGN_BACKUP_DIR.md` / `DESIGN_BACKUP_OPS.md`） | Steam 库下 |

### 2.2 路径优先级总则

当同一文件存在"用户明确指定"和"默认位置"两条路径时，**前者绝对优先**。
默认位置仅在没有显式参数时生效。

---

## 3. user_config.json — 用户配置

### 3.1 生效规则（单级、唯一）

**user_config 只有一份生效。** 不再执行多级搜索与合并。

生效来源二选一：

| 来源 | 触发条件 | 行为 |
|------|----------|------|
| **显式传入** | Orchestrator / CLI / Web API 接收到 `user_config_path` 参数 | 直接使用该路径 |
| **默认搜索** | 未传入 `user_config_path` | 搜索平台默认位置 |

### 3.2 默认搜索路径（仅一个位置）

| 平台 | 路径 |
|------|------|
| Linux | `~/.config/kmm/user_config.json` |
| Windows | `%appdata%/kmm/user_config.json` |

仅搜索此一处，不做多级回退。

### 3.3 自动生成（first-use 机制）

```
搜索 user_config.json
  ├── 文件存在 → 加载并返回，first_use = false
  └── 文件不存在
        ├── 尝试在目标位置创建空默认 user_config.json
        │     ├── 写入成功 → 返回空配置，first_use = true
        │     └── 写入失败 → 报错：
        │           "E_NO_WRITE_PERMISSION: 无法创建 user_config.json，
        │            请指定具有写入权限的目录，或通过参数显式传入 config 路径"
        └──
```

**first_use 标记**：当自动创建了空配置文件时，bootstrap 在返回值中设置 `first_use: true`。
前端据此展示引导流程，提醒用户填写运行必需信息（如 Steam 库路径、规则文件位置等）。

### 3.4 显式传入路径不存在的处理

若用户显式传入的 `user_config.json` 不存在：
1. 尝试在**该指定路径**创建默认空文件
2. 成功 → 同 first_use 流程
3. 失败 → 同权限错误

### 3.5 字段定义

`user_config.json` 的 JSON Schema 见 `repo_spec/user_config.schema.json`。

当前字段：

| 字段 | 类型 | 必需 | 说明 |
|------|------|:--:|------|
| `schema_namespace` | `string` | **是** | Schema 命名空间标识，固定为 `"KMM_UserConfig"` |
| `schema_version` | `string` | **是** | Schema 版本号，如 `"knighthana@0.1.0"` |
| `baksuffix` | `string` | **是** | 备份目录名后缀 |
| `bakignore` | `string[]` | **是** | 备份时忽略的目录后缀（系统自动维护，与 `baksuffix` 联动） |
| `rule_sources` | `{name: {paths: [...]}}` | **是** | 规则文件来源映射——与 `databases` 格式一致。前端只传 name，后端按名解析路径 |
| `path_alias` | `object[]` | 否 | 路径别名列表（当前无消费者，保留供未来扩展） |
| `workspace_dir` | `string \| null` | **是** | 工作区根目录。bootstrap 首次创建时按平台填入默认值并固化 |
| `databases` | `{name: {path}}` | **是** | database 名称→路径映射 |

`databases` 子字段：

| 字段 | 类型 | 必需 | 说明 |
|------|------|:--:|------|
| `databases[name].path` | `string` | 是 | database 文件路径 |

示例：
```json
"databases": {
  "wsl_scan": { "path": "/mnt/d/database_wsl.json" }
}
```

### 3.6 与 Orchestrator / Bootstrap 的接口

Orchestrator 向 bootstrap 传递 config 来源：

```python
# type A: 显式指定
{"type": "local", "path": "/explicit/path/to/user_config.json"}

# type B: 使用默认搜索
{"type": "default", "path": None}
```

bootstrap 据此执行 §3.2-§3.4 的搜索/创建逻辑。

返回结构新增 `first_use` 字段：

```python
{
    "config": { ... },      # 内存中的 user_config 字典（可能为空）
    "source_path": "...",   # 实际加载/创建的绝对路径
    "first_use": True,      # 是否自动创建了空配置文件
}
```

---

## 4. database.json — 磁盘扫描数据

### 4.1 定位

`database.json` 是 `POST /api/database/generate` 扫描磁盘后产生的**纯客观数据**。它描述"磁盘上有什么"，不包含任何用户决策或计算产物。

**database.json 中禁止包含**：
- ❌ `managed` 字段（用户对重复条目的取舍 → 前端 localStorage decisions）
- ❌ `warnings` 字段（扫描过程中的警告 → 在 API 响应中返回，不写入文件）
- ❌ `errors` 字段（扫描过程中的错误 → 同上）

### 4.2 输出路径

database.json 的路径来源于 `user_config.databases[name].path`。`name` 由前端请求参数 `database_name?` 指定，不传则用默认（`databases` 对象的第一个 key）。

| 平台 | 默认位置 |
|------|----------|
| Linux | `~/.local/share/kmm/database.json` |
| Windows | `%LOCALAPPDATA%/kmm/database/database.json` |

默认位置仅在 `databases` 对象为空且未传入 `database_name?` 时生效。

### 4.3 history 字段

`database.json` 中预留 `history` 字段。当前为空数组 `[]`，不写入任何历史记录。
未来用于审计追溯，本次不实现。

### 4.4 重复条目处理

database 扫描可能发现同一个 appid 出现在多个 Steam 库中（重复 game），或同一 mixed_id 对应多个路径（重复 mod）。这些重复条目**全部写入 database.json**，不作过滤。

用户对重复条目的取舍（managed_entries）通过工作区 decisions API（`/workspace/{id}/decisions/save`）持久化在工作区目录中，compute 时从工作区读取。详见 `DESIGN_WORKSPACE_MODEL.md`。

---

## 5. 工作区存储 — 后端目录

### 5.1 定位

工作区是用户创建的任务容器，包含该任务的规则聚合结果、用户决策、计算产物（mapping + SVG）和指纹。所有数据以后端工作区目录为权威。

**完整设计见 `DESIGN_WORKSPACE_MODEL.md`**。本文档仅记录其与存储体系的交叉点。

### 5.2 目录结构

```
{workspace_dir}/{workspace_id}/
├── meta.json              # 元信息：name, database_name, created_at, app_version
├── aggregated_rule.json   # 聚合后的规则集（后端权威副本）
├── decisions.json         # managed_entries + branch_decisions
├── mapping.json           # compute 产出
├── forest.svg             # 森林可视化图
└── fingerprints.json      # 规则文件 + database 的 sha256 指纹
```

### 5.3 与 user_config 的关系

工作区根目录由 `user_config.workspace_dir` 配置。未设置时使用平台默认路径。

### 5.4 与 database.json 的职责边界

| 内容 | database.json | 工作区目录 | compute 参数 |
|------|:---:|:---:|:---:|
| steamlib[] | ✅ | — | — |
| game[]（纯数据，无 managed） | ✅ | — | — |
| mod[]（纯数据，无 managed） | ✅ | — | — |
| 聚合规则集 | — | ✅ aggregated_rule.json | ✅（从工作区读取） |
| branch 决策 | — | ✅ decisions.json | ✅（从工作区读取） |
| managed 预选 | — | ✅ decisions.json | ✅（从工作区读取） |
| mapping 结果 | — | ✅ mapping.json | — |
| SVG | — | ✅ forest.svg | — |
| warnings / errors | API 响应返回 | — | — |

---

## 6. aggregated_rule_set.json — 已迁移

聚合结果现写入工作区目录（`{workspace_dir}/{workspace_id}/aggregated_rule.json`）。
详见 `DESIGN_WORKSPACE_MODEL.md`。

---

## 7. 备份目录

备份目录的位置、命名、结构与执行生命周期已在 `DESIGN_BACKUP_DIR.md` 与 `DESIGN_BACKUP_OPS.md` 中规定，本文档不重复。
备份目录不受 `user_config` 中的输出路径配置影响——备份始终写入 Steam 库下。

---

## 8. 前端浏览器存储

### 8.1 原则

> **后端工作区目录是业务数据的唯一权威。** 前端仅存储纯 UI 偏好和 Tab 级导航状态。
> 用户决策（decisions）和计算结果（mapping）存后端工作区目录，compute 时由 orchestrator 从工作区读取。
> 前端不持久缓存业务数据。

### 8.2 抽象接口

`frontend/src/utils/persistence.ts` 定义了 `PersistenceAdapter` 接口：

```typescript
interface PersistenceAdapter {
  save(key: string, value: unknown): void
  load<T>(key: string): T | null
  clear(key: string): void
}
```

### 8.3 允许存储的内容

#### sessionStorage（每 Tab 独立，主读源）

| key | 内容 | 说明 |
|-----|------|------|
| `modmanager:sidebarCollapsed` | `boolean` | 侧边栏折叠状态 |
| `modmanager:activeTab` | `string` | 当前标签页 |
| `modmanager:currentWorkspaceId` | `string` | 当前活跃工作区 ID |
| `modmanager:uiState:datasource` | `object` | DataSourcePage 全局可见性 + 表单 |
| `modmanager:uiState:{workspace_id}` | `object` | ComputePrepPage 工作区级可见性 |

#### localStorage（全局留档，仅新 Tab 初始化回退）

| key | 内容 | 说明 |
|-----|------|------|
| `modmanager:sidebarCollapsed` | `boolean` | 侧边栏折叠留档 |
| `modmanager:uiState:datasource` | `object` | DataSourcePage 留档 |
| `modmanager:uiState:{workspace_id}` | `object` | ComputePrepPage 留档 |

**读写规则**：sessionStorage 优先；空则读 localStorage → 写入 sessionStorage。改动时同时写两处。完整规则见 `DESIGN_WORKSPACE_MODEL.md` §6。

### 8.4 禁止存储的内容

- ❌ 数据库扫描结果（libraries, games, mods）
- ❌ 用户决策（managed_entries, branch_decisions）
- ❌ pipeline 计算结果（trees, final_mapping, mapping_result）
- ❌ 聚合规则集（aggregated_rule_set）
- ❌ 警告/错误列表（warnings, errors）
- ❌ user_config 内容
- ❌ database 内容

### 8.5 错误处理

```typescript
// save/load 失败时 notify 警告而非静默忽略
try { pers.save(key, value) } catch {
  notify.warning("偏好保存失败，下次启动可能丢失设置")
}
```

### 8.6 Tauri2 预留：TauriStoreAdapter

接口已预留，实现时替换为 Tauri `Store` API（`@tauri-apps/plugin-store`）。
切换时仅需替换 adapter 实例，上层调用方（store 模块）无感知。

### 8.7 数据恢复流程

用户刷新页面后，状态恢复分为三路：

| 数据类型 | 恢复来源 |
|---------|---------|
| 业务数据（database, 工作区列表, mapping, SVG） | 后端 API 获取 |
| 用户决策与聚合规则（decisions, aggregated_rule） | 后端工作区目录（通过 workspace 端点） |
| UI 状态（sidebar, activeTab, 可见性, 表单输入） | `sessionStorage`（优先）→ `localStorage`（回退） |

详见 `DESIGN_WORKSPACE_MODEL.md` §6。

---

## 9. 关于 `/tmp/` 的政策

| 使用场景 | 路径 | 政策 |
|----------|------|------|
| Linux 扫描缓存 | `/tmp/kmm/kmm_lib_scan_cache.json` | **有意设计**，可丢弃重建 |
| 测试代码 | `tempfile.TemporaryDirectory()` | 自动清理，不受规范约束 |
| 工具脚本（diagnose / fixture） | 各自指定 | 测试/诊断用途，不纳入运行时规范 |

**禁止**在生产代码中将 `/tmp/` 用于需要持久化的数据（database.json、user_config 等）。

---

## 10. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | user_config 搜索策略 | 单级、唯一。移除旧三级搜索合并 |
| D2 | user_config 缺失时行为 | 自动生成空文件 + first_use 标记（而非抛异常） |
| D3 | database / aggregated 默认路径 | Linux: `~/.local/share/kmm/`；Win: exe 所在目录 |
| D4 | 扫描缓存独立于 database | managed 决策由工作区目录的 decisions.json 管理 |
| D6 | 前端持久化 | 仅存储 UI 偏好（localStorage）+ Tab 级导航状态（sessionStorage），业务数据存后端工作区 |
| D8 | managed 字段归属 | decisions/mapping 存后端工作区目录，compute 时 orchestrator 从 workspacemanager 读取 |
| D9 | warnings / errors 归属 | 扫描/计算产物，在 API 响应中返回，不写入 database.json |
| D10 | 前端 developer 副本 | 删除——前端不再持有 database 或 user_config 的本地缓存副本 |
| D11 | user_config 搜索策略 | 单级、唯一 |
