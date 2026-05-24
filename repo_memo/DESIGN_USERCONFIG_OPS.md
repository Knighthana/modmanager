# DESIGN_USERCONFIG_OPS — user_config 管理模块

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定 `userconfig_ops` 模块的职责边界、公开 API、内容默认值、平台检测逻辑
> 创建: 2026-05-23

---

## 一、模块定位

`src/modmgr/userconfig_ops.py` 是 user_config 生命周期的**唯一管理者**。bootstrap 不创建、不补全、不写入 user_config——全部委托给本模块。

## 二、公开 API

### 2.1 `userconfig_init(path: str) -> dict`

**职责**：确保 `path` 位置存在一份完整合法的 `user_config.json`。

**行为**：

| 场景 | 动作 |
|------|------|
| 文件不存在 | 创建——写入 DEFAULTS + 平台默认值（`_detect_platform_defaults()`） |
| 文件存在但缺必填键 | 加载 → 逐键检查 REQUIRED_KEYS → 缺失的从 DEFAULTS 补（不覆盖已有值） → 写回 |
| 文件存在、必填齐全 | 加载返回，不动 |
| JSON 解析失败 | `ValueError` |
| `schema_namespace` 不匹配 | `ValueError` |

### 2.2 `userconfig_save(config_index: str, data: dict) -> None`

**职责**：将调用方提供的 `data` 写入 `config_index`。

**写入前**：
1. 校验 `data` 是否符合 `user_config.schema.json`（若 `jsonschema` 可用）
2. 若 `baksuffix` 发生变更，自动同步 `bakignore`（追加新值）

**校验失败**：`ValueError`，不写入。

## 三、默认值

### 3.1 结构默认值

```python
DEFAULTS = {
    "schema_namespace": "KMM_UserConfig",
    "schema_version": "knighthana@0.1.0",
    "baksuffix": "kmmbackup",
    "kmmignore": [],
    "bakignore": ["kmmbackup"],
    "rule_sources": {},
    "path_alias": [],
    "workspace_dir": None,       # 由 _detect_platform_defaults() 填入
    "databases": {"default": {"path": ""}},  # 同上
}
REQUIRED_KEYS = list(DEFAULTS.keys())
```

### 3.2 平台默认值（`_detect_platform_defaults()`）

创建或补全时，`workspace_dir` 和 `databases.default.path` 按当前运行平台填入：

| 平台 | `workspace_dir` | `databases.default.path` |
|------|----------------|--------------------------|
| Linux | `~/.cache/kmm/workspace/` | `~/.local/share/kmm/database.json` |
| Windows | `%LOCALAPPDATA%/kmm/workspace/` | `%LOCALAPPDATA%/kmm/database/database.json` |
| macOS | `~/Library/Caches/kmm/workspace/` | `~/Library/Application Support/kmm/database.json` |

> 这是本模块**内部逻辑**，不对外暴露。调用方无需知道平台默认值。

## 四、不变式

- `REQUIRED_KEYS` 与 `user_config.schema.json` 的 `required` 数组**完全一致**
- `DEFAULTS["bakignore"]` 初始值与 `DEFAULTS["baksuffix"]` 一致
- `userconfig_init` 永远只**补空**，不覆盖已有值
- `userconfig_save` 在 `baksuffix` 变更时自动同步 `bakignore`

## 五、被依赖关系

| 调用方 | 调哪个 | 场景 |
|--------|--------|------|
| `bootstrap.discover_user_config()` | `init` | 文件不存在或缺字段 |
| `routes/config.py::save_config()` | `save` | 前端设置面板保存 |
| 其他模块 | **禁止直接调用** | 全部通过 bootstrap 或 config 路由 |

## 六、测试断言

- 新创建的文件包含全部 9 个 REQUIRED_KEYS
- `workspace_dir` 和 `databases.default.path` 在创建时按当前平台填入
- 已有文件缺 `kmmignore` → init 补为 `[]`，其他键不动
- `baksuffix` 已有人工设置值 → init 不动
- `schema_namespace` 不对 → `ValueError`
- JSON 损坏 → `ValueError`
- `userconfig_save` 修改 `baksuffix` 后 `bakignore` 自动追加新值
- `userconfig_save` schema 校验失败 → `ValueError`，文件不变
