# DESIGN_OSPLATFORM — 操作系统探测与默认值

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定 `osplatform` 模块的职责——OS 探测、默认值提供。其余模块禁止自行探测操作系统。
> 创建: 2026-05-23

---

## 一、模块定位

`src/modmgr/osplatform.py` 是系统中**唯一**拥有 OS 知识的模块。其余模块需要 OS 相关信息时，必须向 `osplatform` 请求，禁止自行调用 `sys.platform`、读 `/proc/version`、或硬编码平台默认值。

## 二、OS 探测

### 2.1 `platform() -> str`

返回 `"linux"`、`"windows"`、`"darwin"`、`"wsl"` 之一。

**检测逻辑**：

```
if sys.platform == "win32"  → "windows"
if sys.platform == "darwin" → "darwin"
if sys.platform == "linux":
    read /proc/version → if contains "microsoft" or "WSL" → "wsl"
    else → "linux"
```

> 读 `/proc/version` 是探测 WSL 的标准方式——WSL2 内核包含 `microsoft` 字符串。

## 三、默认值对象 `defaultvalue`

`osplatform.defaultvalue` 是一个内置了私有值表的对象。外部只能通过 `get` 方法获取值，每次调用时内部做一次平台检测以确定返回哪组值。

### 3.1 `defaultvalue.userconfig_index_get() -> dict`

返回 `user_config.json` 的默认索引对象：

| 平台 | 值 |
|------|----|
| Linux / WSL | `{"type": "path", "string": "~/.config/kmm/user_config.json"}` |
| Windows | `{"type": "path", "string": "%APPDATA%/kmm/user_config.json"}` |
| macOS | `{"type": "path", "string": "~/Library/Preferences/kmm/user_config.json"}` |

### 3.2 `defaultvalue.workspace_dir_get() -> str`

| 平台 | 值 |
|------|----|
| Linux / WSL | `~/.cache/kmm/workspace/` |
| Windows | `%LOCALAPPDATA%/kmm/workspace/` |
| macOS | `~/Library/Caches/kmm/workspace/` |

### 3.3 `defaultvalue.database_path_get() -> str`

| 平台 | 值 |
|------|----|
| Linux / WSL | `~/.local/share/kmm/database.json` |
| Windows | `%LOCALAPPDATA%/kmm/database/database.json` |
| macOS | `~/Library/Application Support/kmm/database.json` |

### 3.4 `defaultvalue.working_pathstyle_get() -> str`

| 平台 | 值 |
|------|----|
| Linux | `"linux"` |
| Windows | `"windows"` |
| macOS | `"linux"` |
| WSL | `"linux"` |

> WSL 返回 `"linux"`——工具本身运行在 Linux 上，输出路径使用 Linux 风格。WSL 的特殊处理（扫描 Windows Steam、VDF pathstyle 为 `"windows"`、加 `/mnt/x/` 前缀）由扫描器负责，不在默认值中体现。

## 四、调用方

| 调用方 | 请求的值 | 用途 |
|--------|---------|------|
| `userconfig_ops.userconfig_init()` | `workspace_dir_get()` + `database_path_get()` | 创建/补全 user_config 时的默认值 |
| Web 路由 `/api/os/defaults` | `userconfig_index_get()` | 当前端 sessionStorage/localStorage 均为空时提供默认 config_index |
| `paths.normalize_path()` | `platform()` | 大小写归一化判断 |
| `steam_scanner` / `database_ops` | `platform()` | WSL 判断 + 扫描策略差异 |
| `bootstrap` | **不再调用** | bootstrap 不再做任何 OS 探测 |

## 五、Web 端点

`GET /api/os/defaults` — 返回平台默认值，供前端首次加载使用。无状态，不依赖 user_config。

前端调用该端点后，必须将返回的 `userconfig_index` 写穿到 sessionStorage 与 localStorage；后续请求再通过 `X-UserConfig-Index` header 透传。

**请求**：无 body。

**响应**：
```json
{
  "ok": true,
  "data": {
    "platform": "linux",
    "userconfig_index": {"type": "path", "string": "~/.config/kmm/user_config.json"}
  },
  "errors": [],
  "warnings": []
}
```

## 六、不变式

- `sys.platform` 和 `/proc/version` 的读取**仅**存在于 `osplatform.py` 中
- 默认值的字符串形式（平台路径）是 `osplatform` 的私有知识，外部不可硬编码
- `defaultvalue` 每次 `get` 都做实时平台检测——不在模块加载时缓存（避免 import 时尚未完成环境初始化）
- WSL 检测仅在 `platform() == "linux"` 时触发

## 七、测试断言

- `platform()` 在 Windows 上返回 `"windows"`
- `platform()` 在 macOS 上返回 `"darwin"`
- `platform()` 在 Linux 上返回 `"linux"`（无 WSL 特征时）
- `platform()` 在 WSL 上返回 `"wsl"`（`/proc/version` 含 `microsoft`）
- `defaultvalue.userconfig_index_get()` 在不同平台返回正确路径
- 多次调用 `defaultvalue` 的 get 方法返回一致结果
