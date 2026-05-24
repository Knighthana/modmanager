# DESIGN_BOOTSTRAP — 环境初始化与默认路径规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 bootstrap 模块的初始化流程、三平台默认路径、Steam 发现顺序、首次使用行为

创建：2026-05-21
更新：2026-05-25 — §1.1 config_index 必填，删除平台默认路径猜测；§1.3 默认路径汇总移至 `userconfig_ops._detect_platform_defaults()`；§五 config_index 必填

---

## 一、启动流程

### 1.1 调用链

```
CLI / Web ──(config_index)──▶ orchestrator ──(config_index)──▶ bootstrap
                                                                 │
                                                    ┌────────────┘
                                                    ▼
                                          schema verify
                                         ╱              ╲
                                   通过                  失败
                                     │               ╱        ╲
                                     │         不完整          非法
                                     │           │              │
                                     │    userconfig_init   报错退出
                                     │    (仅调用init)     orchestrator
                                     │           │        透传给调用方
                                     │    再次 schema verify
                                     │           │
                                     └───────────┘
                                          │
                                   加载为有效 userconfig
                                          │
                                   返回给 orchestrator
```

### 1.2 规则

`config_index` 是 `discover_user_config()` 的**必填参数**——调用方必须传入 `user_config.json` 的完整路径。bootstrap 不执行任何平台默认路径猜测。

bootstrap 在确定路径后执行 schema verify（依据 `user_config.schema.json`）：

| 结果 | 行为 |
|------|------|
| **通过**——所有 required 字段齐备，值合法，schema_version 匹配 | 加载返回 |
| **不完整**——required 字段缺失 | 调 `userconfig_ops.userconfig_init(config_index)` 补全默认值 → **再次 schema verify** → 通过则返回，仍失败则报错 |
| **非法**——schema_namespace 错误、JSON 损坏、schema_version 不匹配、值不在允许域中 | 报错退出，不创建、不补全 |

> 默认值是 `userconfig_ops` 的私有知识。bootstrap 不知道、也不应该知道默认值是什么。它只负责"这里缺了 → 调 init → 再验"。

### 1.4 生效后的约定

一旦 bootstrap 成功加载 userconfig，后续所有任务（compute、backup、apply、restore）需要的配置值全部从这份 userconfig 读取。**不重复发现、不重新加载。**

### 1.3 首次创建 / 补全的默认值

`userconfig_init()` 在以下字段不存在或为空时自动填入默认值：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `schema_namespace` | `"KMM_UserConfig"` | 固定 |
| `schema_version` | `"knighthana@0.1.0"` | bootstrap 硬编码；与 bootstrap 自身的 `EXPECTED_SCHEMA_VERSION` 常量一致 |
| `baksuffix` | `"kmmbackup"` | 备份目录后缀 |
| `bakignore` | `["kmmbackup"]` | 备份时忽略的目录后缀；初始值与 baksuffix 默认值一致，保证首次创建的配置同步；与 `baksuffix` 联动——每添加一个新 baksuffix 值，bakignore 自动追加同名条目 |
| `rule_sources` | `{}` | `{name: {paths: [...]}}` 对象——与 `databases` 格式一致 |
| `path_alias` | `[]` | 路径别名列表，当前无消费者，保留供未来扩展；不在 required 中——缺失不触发补全 |
| `workspace_dir` | `<平台默认>` | bootstrap 按平台填入默认值后**固化**——运行时以此为准，不再做平台回退 |
| `databases` | `{"default": {"path": "<平台默认 database 路径>"}}` | |

### 1.3 默认路径

平台默认路径（`workspace_dir` 和 `database`）现在由
`userconfig_ops._detect_platform_defaults()` 内部维护。
`discover_user_config()` / bootstrap 不再包含任何平台路径猜测逻辑。

> `workspace_dir` 由 `userconfig_init` 首次创建 `user_config` 时按平台填入默认值。
> 之后运行时以 `user_config.workspace_dir` 的值为准，**不再执行平台回退**。

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

### 2.3 扫描完成后：pathstyle 写入 database

扫描完成后，系统须将检测到的路径风格写入 `database.json` 的 `OS` 对象（参见 `database.schema.json`）：

```json
"OS": {
    "workingpathstyle": "linux",
    "steamlibpathstyle": "windows"
}
```

| 字段 | 含义 | 可能值 |
|------|------|--------|
| `workingpathstyle` | 工具运行环境的路径风格 | `"linux"` / `"windows"` |
| `steamlibpathstyle` | Steam 库的主路径风格（由首个成功解析的 VDF 判定） | `"linux"` / `"windows"` |

> WSL 场景：若在 Linux 下通过 WSL 桥接扫描到 Windows 库，`steamlibpathstyle` 可能为 `"windows"`——此时 orchestrator 需要同时支持 WSL 路径映射（`/mnt/c/...` ↔ `C:\...`）。

---

## 三、`workspace_dir` 配置

`user_config.workspace_dir` 允许用户自定义工作区根目录。未设置时按 §1.3 中的默认路径。

常见用途：Windows 用户将 workspace 迁移到非系统盘。

---

## 四、`databases` 与 `rule_sources` 配置

### 4.1 `databases`

`user_config.databases` 是一个 `{name: {path}}` 映射。首次创建时自动填入 `{"default": {"path": "<平台默认>"}}`。

用户可通过前端或手动编辑添加更多 database 条目。每个工作区创建时绑定一个 database name，后续该工作区通过此 name 解析对应的 database 文件路径。

### 4.2 `rule_sources`

`user_config.rule_sources` 同样使用 `{name: {paths: [...]}}` 映射——与 `databases` 格式一致。前端仅知道和传递 `name`，后端按名解析路径列表。

### 4.3 `bakignore` 与 `baksuffix`

`bakignore` 是**系统自动维护**的字段，与 `baksuffix` 联动——用户每次添加一个新 `baksuffix` 值时，`bakignore` 自动追加同名条目。`bakignore` 仅在 backup 操作时生效，用于屏蔽旧的备份目录（避免"改了后缀后旧备份目录被误备份"）。

全操作忽略走 `.kmmignore` 文件规则（gitignore 语法），与 `bakignore` 的语义和管理周期完全不同。

---

## 五、关于 `config_index`

`config_index` 是 bootstrap 的**必填入参兼出参**——标识当前生效的 `user_config.json` 文件位置。

**入参**：**必填**。调用方在调用 `discover_user_config()` 时必须传入完整的文件路径。
bootstrap 从该位置读取/校验 user_config，**不执行任何平台默认路径猜测**。
若该位置无文件 → 调 `userconfig_init()` 创建。

**出参**：bootstrap 返回时携带 `config_index`，记录实际生效的文件路径。前端将此值透明保存，后续 `/config/save` 等操作原样传回。

**不入 `user_config` 内部**：`config_index` 不在 `user_config.json` 文件的 JSON 内容中持久化。它是 bootstrap 返回参数，仅为后续写入操作定位文件。

**与 `workspace_dir` 的区别**：`config_index` 是"这个文件在哪"（bootstrap 参数），`workspace_dir` 是"工作区放哪"（user_config 字段，固化后可修改）。

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

平台默认路径（`workspace_dir`、`database`）由 `userconfig_ops._detect_platform_defaults()` 维护，
`discover_user_config()` 不执行任何平台默认路径猜测。

### 显式传入路径

- 通过参数显式传入 `config_index` 时，bootstrap 直接使用该路径，不搜索默认目录
- 显式路径加载成功后 `config_index` 返回该路径
- 显式路径不存在时，bootstrap 调 `userconfig_init` 在**该指定位置**创建默认文件

### 默认目录首次创建

- 指定路径下不存在 `user_config.json` 时，`discover_user_config` 调 `userconfig_init` 在该路径创建
- 创建的文件须包含 §1.2 规定的全部默认字段
- `databases` 默认值为 `{"default": {"path": "<平台默认 database 路径>"}}`——该路径由 `_detect_platform_defaults()` 按平台填入

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
- 扫描完成后 `database.json` 的 `OS` 对象被写入，含 `workingpathstyle` 和 `steamlibpathstyle`
