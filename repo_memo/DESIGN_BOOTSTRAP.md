# DESIGN_BOOTSTRAP — 环境初始化与默认路径规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 bootstrap 模块的初始化流程、三平台默认路径、Steam 发现顺序、首次使用行为

创建：2026-05-21
更新：2026-05-23 — §二 重写为 P1/P2 优先级模型；新增 steam.exe 推导、注册表、WSL 桥接、pathstyle 写入

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

## 二、Steam 库发现

### 2.0 总体原则：用户意图优先于自动推导

| 优先级 | 方式 | 说明 |
|--------|------|------|
| **P1** | 用户显式指定路径 | 用户通过 UI 或 `user_config` 提供的路径，可信度最高。只要提供，**必须**使用。 |
| **P2** | 自动推导 | 仅在用户未提供 P1 路径时生效。含注册表、硬编码默认路径、WSL 桥接扫描。 |

### 2.1 用户显式指定（P1，全平台通用）

**Windows**：用户通过文件选择器定位 `steam.exe`。系统据此推导：

```
steam.exe 所在目录 = SteamRoot
  → 检查 SteamRoot/steamapps/libraryfolders.vdf（新版 Steam）
  → 否则检查 SteamRoot/config/libraryfolders.vdf（旧版 Steam）
  → 解析 VDF 展开所有库
  → SteamRoot/steamapps/ 本身作为默认库
  → 均失败 → 报错"无法从此 steam.exe 推断 Steam 库位置"
```

> 不要求用户直接输入 VDF 路径——普通用户不知道 VDF 是什么。"选 steam.exe"是 Windows 用户都能理解的交互。

**Linux / macOS**：用户直接输入 `steamapps/` 目录路径（现有方式）。

所有平台均支持用户通过 `user_config` 持久化手动指定的路径，后续扫描自动读取。

### 2.2 自动推导（P2）

仅在用户未提供 P1 路径时生效。各平台自动搜索顺序：

#### Windows

1. 注册表 `HKEY_LOCAL_MACHINE\SOFTWARE\Valve\Steam\InstallPath` → 推导 SteamRoot → vdf 展开（读注册表不需要 UAC 提权）
2. `%PROGRAMFILES(X86)%/Steam/steamapps/`（默认安装）
3. `%PROGRAMFILES%/Steam/steamapps/`（备选）

#### Linux

1. `~/.steam/steam/steamapps/`（默认安装）
2. `~/.local/share/Steam/steamapps/`（Flatpak / 部分发行版）
3. WSL 桥接：将 `/mnt/<drive>/` 转换为 Windows 起始路径后执行一次 Windows 自动推导（覆盖 `/mnt/c/Program Files (x86)/Steam/` 等场景）
4. `/mnt/*/SteamLibrary/steamapps/`（外部库，扫描 `/mnt/` 下第一层目录）

#### macOS

1. `~/Library/Application Support/Steam/steamapps/`（默认安装）

### 2.3 扫描完成后：pathstyle 写入 user_config

扫描完成后，系统须将检测到的路径风格（`steamlib_pathstyle`）写入 `user_config`，作为后续路径归一化的默认值：

| 字段 | 含义 | 可能值 |
|------|------|--------|
| `steamlib_pathstyle` | Steam 库的主路径风格（由首个成功解析的 VDF 判定） | `"windows"` / `"linux"` |

此字段供 orchestrator 的 `_detect_pathstyle()` 消费——当用户未在操作参数中显式指定 pathstyle 时，回退到此配置值。

> WSL 场景：若在 Linux 下通过 WSL 桥接扫描到 Windows 库，`steamlib_pathstyle` 可能为 `"windows"`——此时 orchestrator 需要同时支持 WSL 路径映射（`/mnt/c/...` ↔ `C:\...`）。

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
- macOS Steam 自动发现需实际验证（路径 `~/Library/Application Support/Steam/` 为推测值）
- 注册表读取需在 Windows 环境下实测，确认 64/32 位注册表视图行为
- `steam.exe` 推导 → VDF 展开链路需处理新版/旧版 Steam 目录结构差异

---

## 八、测试断言

测试组可以据本文档编写正例断言：

### 平台识别

- Linux 下 `user_config` 默认路径为 `~/.config/kmm/user_config.json`
- Windows 下 `user_config` 默认路径为 `%APPDATA%/kmm/user_config.json`
- macOS 下 `user_config` 默认路径为 `~/Library/Preferences/kmm/user_config.json`
- 各平台下 `database`、`workspace` 默认路径符合 §1.3 表

### 显式传入路径

- 通过参数显式传入 `user_config.json` 路径时，bootstrap 直接使用该路径，不搜索默认目录
- 显式路径加载成功后 `source_path` 返回该路径，`first_use=false`
- 显式路径不存在时，bootstrap 在**该指定位置**创建默认文件，`first_use=true`

### 默认目录首次创建

- 默认目录下不存在 `user_config.json` 时，bootstrap 自动创建
- 创建的文件须包含 §1.2 规定的全部默认字段
- `databases` 默认值为 `{"default": {"path": "<平台默认 database 路径>"}}`——该路径指向 §1.3 表中对应平台的 database 默认位置
- `first_use=true` 仅当文件由 bootstrap 首次创建时为真

### Databases 解析

- 若 `user_config.databases` 中填入了非默认路径的 database，bootstrap 返回的 `databases` 字典应**完整保留用户填写的路径**，不回落默认
- 若 `user_config.databases` 中填入了多个 database（如 `"default"`、`"secondary"`），bootstrap 应全部保留

### 规则文件来源（rule_sources）

- `user_config.rule_sources` 中填写的路径应被完整保留并返回
- 以 `/` 结尾的目录路径表示「自动扫描该目录下的 `*.kmmrule.json` 文件」
- 以 `.kmmrule.json` 结尾的文件路径表示「直接加载该文件」
- 后端保存时自动归一化：检测到目录路径缺 `/` 则补齐

### 工作区根目录

- `user_config.workspace_dir` 为空或未设置时，按 §1.3 表中对应平台默认值解析

### Steam 库发现（§二）

- 用户提供了 P1 路径时，自动推导（P2）**不得**执行——跳过注册表、硬编码路径、WSL 桥接
- Windows 下 `steam.exe` 推导：从 `steam.exe` 所在目录成功定位到 `libraryfolders.vdf`（新版/旧版）时，VDF 展开结果须包含 `SteamRoot/steamapps/`
- Linux WSL 桥接：`/mnt/c/Program Files (x86)/Steam/` 存在时，应能解析其下 `steamapps/libraryfolders.vdf`
- 扫描完成后 `user_config.steamlib_pathstyle` 被写入，值为 `"windows"` 或 `"linux"`
