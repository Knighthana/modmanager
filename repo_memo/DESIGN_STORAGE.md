# DESIGN_STORAGE — 存储与默认位置规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 冻结项目所有持久化存储的分类、默认位置、搜索策略与生命周期。作为跨模块存储行为的唯一权威来源。
> 创建：2026-05-09
> 更新：2026-05-09 — 新增 §8.5 偏好保存时机（TODO-21）、§8.5.1 前端 Database 副本生命周期、§8.6 用户偏好生命周期（TODO-23）
> Supersedes: 替代 `DESIGN_RULE_AGGREGATOR.md` §2.2 中过时的三级搜索链描述

---

## 1. 存储分类

项目中的持久化存储分为四类：

| 分类 | 特征 | 示例 |
|------|------|------|
| **用户配置** | 控制工具行为的首选项，用户可编辑 | `user_config.json` |
| **运行产出** | 工具运行生成的数据文件 | `database.json`（含扫描缓存职责）、`aggregated_rule_set.json` |
| **备份产物** | 文件替换前的安全副本，不可自动丢弃 | `kmmbackup_*` 目录 |
| **前端状态** | UI 层持久化的用户输入与视图状态 | localStorage 键值 |

---

## 2. 平台默认路径

### 2.1 基础路径常量

| 概念 | Linux | Windows |
|------|-------|---------|
| **用户配置目录** | `~/.config/kmm/` | `%appdata%/kmm/` |
| **运行产出默认目录** | `~/.local/share/kmm/` | 进程本体文件所在目录 |
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

## 4. database.json — 运行产出

### 4.1 输出路径

优先级：
1. `user_config.database_output_path`（若为非空字符串）
2. 平台默认位置（见 §2.1）

| 平台 | 默认位置 |
|------|----------|
| Linux | `~/.local/share/kmm/database.json` |
| Windows | `<exe_dir>/database.json` |

### 4.2 history 字段

`database.json` 中预留 `history` 字段。当前为空数组 `[]`，不写入任何历史记录。
未来用于审计追溯，本次不实现。

---

## 5. aggregated_rule_set.json — 运行产出

### 5.1 输出路径

优先级：
1. `user_config.aggregated_ruleset_output_path`（若为非空字符串）
2. 平台默认位置（见 §2.1）

| 平台 | 默认位置 |
|------|----------|
| Linux | `~/.local/share/kmm/aggregated_rule_set.json` |
| Windows | `<exe_dir>/aggregated_rule_set.json` |

---

## 6. 扫描缓存（已废弃）

扫描缓存的概念已废弃。`database.json` 中通过 `managed` 字段区分去重状态：
- 扫描结束后，所有 game 和 mod 条目写入 database，此时可能存在同名 appid / mixed_id 的多条记录，各条目的 `managed` 初始为 `false`
- 用户在数据源页面通过 radio 选择保留的条目，将其 `managed` 设为 `true`
- 同 appid / mixed_id 最多一个 `managed: true`
- 流水线下游仅消费 `managed: true` 的条目

因此不需要独立的缓存文件。database 同时承担"扫描结果存储"和"去重后的干净数据"两个角色。

---

## 7. 备份目录

备份目录的位置、命名与生命周期已在 `DESIGN_BACKUP.md` 中完整规定，本文档不重复。
备份目录不受 `user_config` 中的输出路径配置影响——备份始终写入 Steam 库下。

---

## 8. 前端持久化

### 8.1 抽象接口

`frontend/src/utils/persistence.ts` 定义了 `PersistenceAdapter` 接口：

```typescript
interface PersistenceAdapter {
  get<T>(key: string): T | null
  set<T>(key: string, value: T): void
  remove(key: string): void
  keys(): string[]
}
```

**定位**：用于前端临时或长期存储 UI 状态与用户输入数据。不直接写入后端文件系统。
所有键使用 `modmanager:` 前缀以避免与其他应用冲突。

### 8.2 Web 端实现：LocalStorageAdapter

当前唯一实现。底层为浏览器 `localStorage`。
- 存储受浏览器同源策略保护
- 容量通常 ≥ 5MB
- 数据在浏览器清除缓存时丢失（可接受——数据源始终在后端文件中）

### 8.3 Tauri2 预留：TauriStoreAdapter

接口已预留，实现时替换为 Tauri `Store` API（`@tauri-apps/plugin-store`）。
切换时仅需替换 adapter 实例，上层调用方（store 模块）无感知。

### 8.4 持久化的数据

| 键 | 写入者 | 内容 |
|------|------|------|
| `modmanager:datasource` | `stores/datasource.ts` | 数据源页面状态：discoveryMode、manualPath、cachePath、libraries、games、mods、warnings、列可见性 |
| `modmanager:forest-store` | `stores/forest.ts` | Forest 页面状态：pipelineForm、storedDatabase、userConfig、databaseSummary、dbManualOverride |

约束：
- `modmanager:forest-store` 使用深度 watch，字段变更自动持久化
- `reset()` 不清除持久化的输入字段（pipelineForm、storedDatabase 等保留）
- 分支决策 `branchDecisions` 通过 store 状态管理，不在 localStorage 中单独存储

### 8.5 偏好保存时机（TODO-21）

用户在前端对各选项卡的操作偏好，应在以下时机触发持久化：

| 操作 | 触发时机 | 说明 |
|------|----------|------|
| 数据源"扫描 Steam 库" | **按钮按下后** | 保存 discoveryMode、manualPath、cachePath 等扫描参数 |
| 数据源可见性切换 | 即时（现有行为保持） | 库/游戏/MOD 的 visibility 开关 |
| 数据源 managed 选择 | 仅"确认并进入规则概览"时 | 不在每次 radio 点击时持久化 |
| 设置页修改 | 用户点击"保存"按钮后 | 调用 `POST /api/config/save` |
| 数据库扫描结果 | 后端更新时同步刷新 | 扫描完成/保存 managed 后，前端从 API 响应中获取最新 database 并覆盖本地副本 |

**原则**：数据量小、用户频繁调整的（如可见性）即时保存；涉及数据一致性校验的（如 managed）批量提交时保存。

### 8.5.1 前端 Database 副本生命周期

前端 Pinia store 中持有的 database 副本（`games`、`mods`、`libraries`）遵循以下规则：

| 事件 | 行为 |
|------|------|
| 页面刷新 / 重新打开 | **保留**。通过 localStorage 持久化，不清除 |
| "扫描 Steam 库"完成 | 后端返回新 database → 覆盖前端副本 → 写入 localStorage |
| "保存当前选择" / "确认并进入"完成 | 后端写入 managed 字段并返回更新后的 database → 覆盖前端副本 → 写入 localStorage |
| 其他选项卡读取 database | 从 localStorage 读取，**不**发起后端文件 I/O |

**目的**：前端与后端数据保持同步的同时，减少无谓的文件读取操作。database 的权威副本始终在后端磁盘文件中，前端 localStorage 为只读缓存。

### 8.6 用户偏好生命周期

| 阶段 | 行为 |
|------|------|
| **加载** | 应用启动时，从 localStorage 恢复 `modmanager:datasource` 和 `modmanager:forest-store`。不存在时使用默认值 |
| **更新** | 按 §8.5 的时机自动或手动触发 `persistence.set()` |
| **清除** | 用户可通过浏览器"清除站点数据"清除。工具本身不提供"重置所有偏好"按钮（现阶段） |
| **迁移** | 键名前缀 `modmanager:` 预留版本号空间。未来若数据结构变动，采用 `modmanager:v2:` 前缀 + 旧键自动迁移策略 |
| **start page 偏好（TODO-23）** | 在 `modmanager:forest-store` 或独立键中存储 `startPage` 字段。user_config 未配置时导航到 `/settings`；已配置时导航到 `startPage` 指定的默认页 |

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
| D4 | 扫描缓存独立于 database | 不与 database.json 合并，缓存去重前全量结果 |
| D5 | 扫描缓存放 `/tmp/`（Linux） | 可丢弃，重启自然清理，有意为之 |
| D6 | 前端持久化 | localStorage + 抽象接口，为 Tauri2 预留 |
| D7 | database history 字段 | 预留空数组，本次不实现 |
