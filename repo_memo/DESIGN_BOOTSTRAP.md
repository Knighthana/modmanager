# DESIGN_BOOTSTRAP — 环境初始化与默认路径规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 bootstrap 模块的初始化流程、三平台默认路径、Steam 发现顺序、首次使用行为

创建：2026-05-21

---

## 一、user_config.json 的发现与创建

### 1.1 搜索位置（单级，不回退）

| 平台 | 路径 |
|------|------|
| Linux | `~/.config/kmm/user_config.json` |
| Windows | `%APPDATA%/kmm/user_config.json` |
| macOS | `~/Library/Preferences/kmm/user_config.json` |

如果文件存在且内容为合法 JSON dict → 加载返回，`first_use=false`。

如果文件不存在或内容无效 → 在该位置创建默认 `user_config.json`，`first_use=true`。

### 1.2 首次创建的默认值

首次创建 `user_config.json` 时，以下字段会被自动填入：

| 字段 | 默认值 |
|------|--------|
| `schema_namespace` | `"KMM_UserConfig"` |
| `schema_version` | `"knighthana@0.1.0"` |
| `databases` | `{"default": {"path": "<平台默认 database 路径>"}}` |
| `source_path` | user_config.json 自身的绝对路径 |
| `first_use` | `true` |

### 1.3 默认路径汇总

| 用途 | Linux | Windows | macOS |
|------|-------|---------|-------|
| `user_config` | `~/.config/kmm/` | `%APPDATA%/kmm/` | `~/Library/Preferences/kmm/` |
| `database`（首次默认） | `~/.local/share/kmm/database.json` | `%LOCALAPPDATA%/kmm/database/database.json` | `~/Library/Application Support/kmm/database.json` |
| `workspace`（未设置 `workspace_dir` 时） | `~/.cache/kmm/workspace/` | `%LOCALAPPDATA%/kmm/workspace/` | `~/Library/Caches/kmm/workspace/` |

> 所有路径均可通过 `user_config` 中的对应字段覆盖。上表仅定义**未显式配置时的默认值**。

---

## 二、Steam 库自动发现

### 2.1 Linux

按以下顺序搜索，命中第一个存在的目录即停止：

1. `~/.steam/steam/steamapps/`（默认安装）
2. `~/.local/share/Steam/steamapps/`（Flatpak / 部分发行版）
3. `/mnt/*/SteamLibrary/steamapps/`（外部库，扫描 `/mnt/` 下第一层目录）
4. 用户通过 `user_config` 手动指定的路径

### 2.2 Windows

1. `%PROGRAMFILES(X86)%/Steam/steamapps/`（默认安装）
2. 从注册表 `HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Valve\Steam\InstallPath` 读取 Steam 安装目录 → `steamapps/`
3. 用户通过 `user_config` 手动指定的路径

### 2.3 macOS

1. `~/Library/Application Support/Steam/steamapps/`（默认安装）
2. 用户通过 `user_config` 手动指定的路径

---

## 三、`workspace_dir` 配置

`user_config.workspace_dir` 允许用户自定义工作区根目录。未设置时按 §1.3 中的默认路径。

常见用途：Windows 用户将 workspace 迁移到非系统盘。

---

## 四、`databases` 配置

`user_config.databases` 是一个 `{name: {path}}` 映射。首次创建时自动填入 `{"default": {"path": "<平台默认>"}}`。

用户可通过前端或手动编辑添加更多 database 条目。每个工作区创建时绑定一个 database name，后续该工作区通过此 name 解析对应的 database 文件路径。

---

## 五、关于 `source_path`

`source_path` 是 bootstrap 返回结构中的**正式参数**，记录 `user_config.json` 实际加载/创建的绝对路径。该参数由 orchestrator 消费（用于日志、路径解析等场景），前端仅做只读展示。

用户可将 `user_config.json` 存储在任何位置（通过显式传入 `user_config_path` 参数），bootstrap 均会返回对应的 `source_path`。

---

## 六、与 storage 文档的关系

本文档是存储路径的**运行时权威**。`DESIGN_STORAGE.md` 描述存储分类与生命周期。两者互补——本文档定义「默认位置在哪」，`DESIGN_STORAGE.md` 定义「各类数据属于哪种存储」。

---

## 七、未来扩展

- 允许通过 `user_config` 显式指定 database 和 workspace 路径（已支持 `workspace_dir` 和 `databases[name].path`）
- macOS Steam 自动发现当前为推测路径（`~/Library/Application Support/Steam/`），需实际验证
