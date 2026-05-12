# DESIGN_STORAGE — 存储与默认位置规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 冻结项目所有持久化存储的分类、默认位置、搜索策略与生命周期。作为跨模块存储行为的唯一权威来源。
> 创建：2026-05-09
> 更新：2026-05-13 — 【重大改版】新增 §5 workspace.json 作为用户决策与计算结果的独立存储载体；database.json 移除 managed / warnings / errors 字段；§8 前端持久化缩减为仅 UI 状态
> Supersedes: 替代 `DESIGN_RULE_AGGREGATOR.md` §2.2 中过时的三级搜索链描述

---

## 1. 存储分类

项目中的持久化存储分为五类：

| 分类 | 特征 | 示例 |
|------|------|------|
| **用户配置** | 控制工具行为的首选项，用户可编辑 | `user_config.json` |
| **磁盘扫描数据** | 工具扫描磁盘产生的客观数据 | `database.json` |
| **用户决策与结果** | 用户的主观选择 + 上次计算结果 | `workspace.json` |
| **运行产出** | 流水线运行的中间文件 | `aggregated_rule_set.json` |
| **备份产物** | 文件替换前的安全副本，不可自动丢弃 | `kmmbackup_*` 目录 |

---

## 2. 平台默认路径

### 2.1 基础路径常量

| 概念 | Linux | Windows |
|------|-------|---------|
| **用户配置目录** | `~/.config/kmm/` | `%appdata%/kmm/` |
| **运行产出默认目录** | `~/.local/share/kmm/` | 进程本体文件所在目录 |
| **用户决策与结果** | `~/.local/share/kmm/` | `%localappdata%/kmm/` |
| **扫描缓存目录** | `/tmp/kmm/` | 进程本体文件所在目录 |
| **备份目录** | Steam 库下（详见 `DESIGN_BACKUP.md`） | Steam 库下 |

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
| `bakprefix` | `string` | 否 | 备份目录名前缀，默认 `"kmmbackup_"` |
| `bakignore` | `string[]` | 否 | 备份扫描忽略模式列表 |
| `database_output_path` | `string \| null` | 否 | `database.json` 输出路径。`null` 时使用默认位置 |
| `aggregated_ruleset_output_path` | `string \| null` | 否 | `aggregated_rule_set.json` 输出路径。`null` 时使用默认位置 |
| `rule_sources` | `string[]` | 否 | 规则文件来源列表。目录以 `/` 结尾（后端自动扫描 `*.kmmrule.json`），或以 `.kmmrule.json` 结尾的文件直接加载。后端保存时自动归一化：检测到目录路径缺 `/` 则补齐 |
| `path_alias` | `object[]` | 否 | 路径别名列表（当前无消费者，保留供未来扩展） |

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
- ❌ `managed` 字段（用户对重复条目的取舍 → 属于 workspace.decisions）
- ❌ `warnings` 字段（扫描过程中的警告 → 在 API 响应中返回，不写入文件）
- ❌ `errors` 字段（扫描过程中的错误 → 同上）

### 4.2 输出路径

优先级：
1. `user_config.database_output_path`（若为非空字符串）
2. 平台默认位置（见 §2.1）

| 平台 | 默认位置 |
|------|----------|
| Linux | `~/.local/share/kmm/database.json` |
| Windows | `<exe_dir>/database.json` |

### 4.3 history 字段

`database.json` 中预留 `history` 字段。当前为空数组 `[]`，不写入任何历史记录。
未来用于审计追溯，本次不实现。

### 4.4 重复条目处理

database 扫描可能发现同一个 appid 出现在多个 Steam 库中（重复 game），或同一 mixed_id 对应多个路径（重复 mod）。这些重复条目**全部写入 database.json**，不作过滤。

用户对重复条目的取舍（managed_entries）存储在 `workspace.json` 中。Pipeline 计算时由 orchestrator 读取 database + workspace.managed_entries，过滤后传入 engine。详见 `DESIGN_WORKSPACE_STATE.md`。

---

## 5. workspace.json — 用户决策与计算结果

### 5.1 定位

`workspace.json` 是当前工作会话中用户主观决策和上次计算结果的持久化文件。

**完整设计见 `DESIGN_WORKSPACE_STATE.md`**。本文档仅记录其与存储体系的交叉点。

### 5.2 文件位置

| 平台 | 路径 |
|------|------|
| Linux | `~/.local/share/kmm/workspace.json` |
| Windows | `%localappdata%/kmm/workspace.json` |

### 5.3 单工作区策略

始终只有一份 `workspace.json`。新操作覆盖旧状态。不支持多 session 并存。

### 5.4 与 database.json 的职责边界

| 内容 | database.json | workspace.json | compute 参数 |
|------|:---:|:---:|:---:|
| steamlib[] | ✅ | — | — |
| game[]（纯数据，无 managed） | ✅ | — | — |
| mod[]（纯数据，无 managed） | ✅ | — | — |
| branch 决策 | — | ✅ decisions | ✅ |
| managed 预选 | — | — | ✅（可选参数，列表格式） |
| 扫描参数 | — | ✅ inputs | — |
| compute 结果摘要 | — | ✅ results | — |
| warnings / errors | —（API 响应） | ✅ results | — |

---

## 6. aggregated_rule_set.json — 运行产出

### 6.1 输出路径

优先级：
1. `user_config.aggregated_ruleset_output_path`（若为非空字符串）
2. 平台默认位置（见 §2.1）

| 平台 | 默认位置 |
|------|----------|
| Linux | `~/.local/share/kmm/aggregated_rule_set.json` |
| Windows | `<exe_dir>/aggregated_rule_set.json` |

---

## 7. 备份目录

备份目录的位置、命名与生命周期已在 `DESIGN_BACKUP.md` 中完整规定，本文档不重复。
备份目录不受 `user_config` 中的输出路径配置影响——备份始终写入 Steam 库下。

---

## 8. 前端持久化

### 8.1 原则

> 后端是唯一权威数据源。前端不做业务数据持久化。前端 Pinia store 仅暂存本次页面会话的内存状态。

### 8.2 抽象接口

`frontend/src/utils/persistence.ts` 定义了 `PersistenceAdapter` 接口：

```typescript
interface PersistenceAdapter {
  save(key: string, value: unknown): void
  load<T>(key: string): T | null
  clear(key: string): void
}
```

**定位**：仅用于前端 **UI 状态** 的持久化（无后端参与的纯视图偏好）。所有 key 使用 `modmanager:` 前缀。

### 8.3 允许存储的内容

| key（例） | 内容 | 写入者 |
|-----------|------|--------|
| `ui:tab` | 当前 tab 路由 | App.vue |
| `ui:sidebar-collapsed` | 侧边栏折叠状态 | LayoutShell |
| `datasource:form` | 表单输入（discoveryMode, manualPath, workingPathstyle, greedyParsing, databaseOutputPath） | DataSourceStore |
| `datasource:library-visibility` | 库可见性开关 | DataSourceStore |
| `datasource:game-visibility` | 游戏可见性开关 | DataSourceStore |

### 8.4 禁止存储的内容

- ❌ 数据库扫描结果（libraries, games, mods）
- ❌ pipeline 计算结果（trees, final_mapping, mapping_result）
- ❌ 警告/错误列表（warnings, errors）
- ❌ user_config 内容
- ❌ database 内容
- ❌ pipeline 参数（databasePath, rulesPaths, backupDir, userConfigPath —— 属于 workspace inputs）

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

用户刷新页面后，状态恢复分为两路：

| 数据类型 | 恢复来源 |
|---------|---------|
| 业务数据（database, pipeline 结果, decisions） | 后端 `GET /api/workspace/status` |
| UI 状态（tab, sidebar, 可见性, 表单输入） | `persistence.load()` |

详见 `DESIGN_DATA_CLEANUP.md`。

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
| D4 | 扫描缓存独立于 database | 【已废弃。managed 决策迁移至 workspace.json，database 不再承担去重职责】 |
| D5 | 扫描缓存放 `/tmp/`（Linux） | 可丢弃，重启自然清理，有意为之 |
| D6 | 前端持久化 | localStorage 仅保留 UI 状态；业务数据全部由后端 workspace 管理 |
| D7 | database history 字段 | 预留空数组，本次不实现 |
| D8 | managed 字段归属 | 从 database.json 移除，迁移至 workspace.json（2026-05-13） |
| D9 | warnings / errors 归属 | 扫描/计算产物，在 API 响应中返回，不写入 database.json |
| D10 | 前端 developer 副本 | 删除——前端不再持有 database 或 user_config 的本地缓存副本 |
