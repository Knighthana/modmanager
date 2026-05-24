# DESIGN_DATABASE_OPS — 数据库管理模块

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定 `database_ops` 模块的公开 API——数据库发现、CRUD、完整性校验
> 创建: 2026-05-23

---

## 一、模块定位

`src/modmgr/database_ops.py` 管理 Steam 数据库的生命周期——从扫描生成到手动维护到完整性校验。

数据库的**首次生成**和**读取**入口在 `bootstrap.generate_database()` 和 `POST /api/database/generate`，本模块提供底层能力。

## 二、公开 API

### 2.1 发现与生成

#### `discover_with_fallback(working_pathstyle, *, manual_override_steamlibs, greedy_parsing, manual_only) -> dict`

**职责**：组合自动扫描和手动指定两种路径，生成一份完整的 database dict。

**行为**：
1. 若不是 `manual_only` → 调用 `SteamScanner.discover_steam_libraries()` 自动扫描
2. 合并手动指定的 `manual_override_steamlibs`（manual 优先）
3. 扫描所有库 → 发现游戏（ACF）和 mod（workshop/content）
4. 写入 `OS` 对象（`workingpathstyle` / `steamlibpathstyle`）
5. 返回 `{OS, steamlib, game, mod}`

### 2.2 Steam 库 CRUD

| 函数 | 职责 |
|------|------|
| `list_steamlibs(database)` | 列出所有 Steam 库 |
| `add_manual_steamlib(database, *, path)` | 新增手动库（名称→路径规范化，去重） |
| `remove_manual_steamlib(database, *, path)` | 移除库及其关联的 game/mod |
| `update_manual_steamlib(database, *, old_path, new_path)` | 重命名库，更新关联条目的路径前缀 |

### 2.3 游戏 CRUD

| 函数 | 职责 |
|------|------|
| `list_games(database, *, steamlib_path)` | 按库列出游戏 |
| `add_manual_game(database, *, steamlib_path, appid, basepath, modpath)` | 新增手动游戏 |
| `remove_manual_game(database, *, appid)` | 移除游戏及关联 mod |
| `update_manual_game(database, *, appid, updates)` | 更新游戏属性 |

### 2.4 完整性

#### `verify_database_integrity(database) -> list[str]`

校验 database 内部一致性：steamlib → game → mod 路径前缀匹配、引用完整性。返回错误列表。

### 2.5 增量刷新

#### `liveupdate_database(database, *, steamlib_paths, greedy_parsing)` -> dict

对已有 database 执行增量刷新——仅扫描指定库，合并新旧数据。

## 三、内部结构

database dict 的标准形状：

```json
{
  "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
  "steamlib": [{"path": "...", "contains_libraryfolders_vdf": true, "game": [...]}],
  "game": [{"appid": "270150", "name": "...", "basepath": "...", "modpath": "..."}],
  "mod": [{"mixed_id": "270150:123", "path": "...", "appid": "270150"}]
}
```

`_ensure_database_shape()` 在每次操作前保证四个顶层键存在。

## 四、路径规范化

所有入口路径经 `_ensure_steamapps()` 处理——若不以 `/steamapps` 结尾则自动追加。CRUD 操作中的路径比较使用 `normalize_posix()` 归一化后的字符串相等。

## 五、不变式

- `steamlib[].path` 始终以 `/steamapps` 结尾
- `game[].basepath` 以某个 `steamlib.path` 为前缀
- `game[].modpath` 以 `steamapps/workshop/content/{appid}/` 结尾
- `mod[].path` 以 `game[].modpath/{modid}` 为前缀

## 六、测试断言

- `discover_with_fallback(manual_only=True)` 不执行自动扫描
- `add_manual_steamlib` 重复路径不创建新条目
- `remove_manual_steamlib` 连带清除关联的 game/mod
- `verify_database_integrity` 对合法 database 返回空列表
- `verify_database_integrity` 检测到断链返回错误
- `_ensure_database_shape` 为缺失键写入默认值
