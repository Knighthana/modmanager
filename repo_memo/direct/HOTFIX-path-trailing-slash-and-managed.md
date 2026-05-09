# 热修复: E_PATH_GATE_DIR 与 managed 属性双重 Bug

> 状态: 已实现
> 关联: 用户即时报告
> 目标文件: `src/modmanager/database_ops.py`

---

## 一、问题1：E_PATH_GATE_DIR — 目录路径不以 `/` 结尾

### 根因

`database_ops.py` 中 `basepath`、`modpath`、`mod.path` 三个目录路径在写入数据库时均未追加尾部 `/`，违反了 `path_resolver.py` 第 7 行规定的"目录路径必须以 `/` 结尾"的路径规范。当 `engine.py` compute 阶段执行门禁断言时报 `ValueError("E_PATH_GATE_DIR: ...")`。

### 受影响位置（均在同一文件 `database_ops.py`）

| 行号 | 函数 | 字段 | 问题 |
|------|------|------|------|
| 164 | `_scan_from_libraries` | `game.basepath` | `normalize_posix(...)` 无尾部 `/` |
| 165 | `_scan_from_libraries` | `game.modpath` | 同上 |
| 175-176 | `_scan_from_libraries` | 同上（duplicate 分支） | 同上 |
| 69 | `_build_mod_from_games` | `mod.path` | `f"{normalized_modpath}/{modid_str}"` 无尾部 `/` |
| 416 | `add_manual_game` | `game.basepath` | `normalize_posix(...)` 无尾部 `/` |
| 417 | `add_manual_game` | `game.modpath` | 同上 |
| 462 | `update_manual_game` | `basepath`/`modpath` | `normalize_posix(value)` 无尾部 `/` |

### 修复方案

**方案：在 `database_ops.py` 中各赋值点显式追加 `/`。**

不使用全局修改 `normalize_posix`（避免影响其他依赖该函数不追加 `/` 的调用方）。

#### 修改点

1. **`_scan_from_libraries` 第 164-165 行**：
   ```python
   "basepath": normalize_posix(game_info.basepath) + '/',
   "modpath": normalize_posix(game_info.modpath) + '/',
   ```

2. **`_scan_from_libraries` 第 175-176 行**（duplicate 分支，同样修改）：
   ```python
   "basepath": normalize_posix(game_info.basepath) + '/',
   "modpath": normalize_posix(game_info.modpath) + '/',
   ```

3. **`_build_mod_from_games` 第 69 行**：
   ```python
   "path": f"{normalized_modpath}/{modid_str}/",
   ```

4. **`add_manual_game` 第 416-417 行**：
   ```python
   "basepath": normalize_posix(basepath) + '/',
   "modpath": normalize_posix(modpath) + '/',
   ```

5. **`update_manual_game` 第 462 行**：
   ```python
   target[key] = normalize_posix(value) + '/'
   ```

---

## 二、问题2：managed 属性全部为 false

### 根因

数据库生成/重建流水线中 `managed` 被硬编码为 `False`，且无保留先前用户设定值的逻辑。

| 行号 | 函数 | 问题 |
|------|------|------|
| 70 | `_build_mod_from_games` | `"managed": False` 硬编码，不读取 `old_mod` |
| 167, 178 | `_scan_from_libraries` | `"managed": False` 硬编码 |
| 412-419 | `add_manual_game` | 完全缺少 `"managed"` 键 |
| 457 | `update_manual_game` | `allowed` 集合不包含 `"managed"` |
| 520-577 | `liveupdate_database` | 全量重建后 managed 全部丢失 |
| 580-610 | `regen_database` | 同上 |

### 修复方案

#### 2.1 `_build_mod_from_games` — 保留旧 managed 值

第 63-64 行已有 `prev = old_mod.get(mixed_id, {})` 和 `localdate = prev.get(...)`，在其后追加 managed 读取：

```python
prev = old_mod.get(mixed_id, {})
localdate = prev.get("localdate", game.get("localdate", 0))
managed = prev.get("managed", False)  # 新增
```

第 70 行改为：
```python
"managed": managed,
```

#### 2.2 `_scan_from_libraries` — 接受旧数据库以保留 managed

函数签名新增参数 `old_games: dict[str, dict[str, Any]] | None = None`。

第 167 行（首次出现分支）：
```python
"managed": old_games.get(appid, {}).get("managed", False) if old_games else False,
```

第 178 行（duplicate 分支同样修改）。

#### 2.3 `liveupdate_database` — 传递旧数据

在调用 `_scan_from_libraries` 前构建 `old_games` 索引并传入：

```python
old_games = {str(g.get("appid", "")): g for g in old_db.get("game", [])}
updated = _scan_from_libraries(
    scanner, libraries, 
    greedy_parsing=greedy_parsing,
    old_games=old_games,  # 新增
)
```

（注意：`old_games` 已在第 543 行定义，可复用）

#### 2.4 `regen_database` — 传递旧数据

同理：
```python
old_games = {str(g.get("appid", "")): g for g in database.get("game", [])}
rebuilt = _scan_from_libraries(
    scanner, libraries,
    greedy_parsing=greedy_parsing,
    old_games=old_games,  # 新增
)
```

#### 2.5 `add_manual_game` — 添加 managed 键

在第 412-419 行的 game 字典中插入：
```python
"managed": False,
```

#### 2.6 `update_manual_game` — 允许更新 managed

第 457 行 `allowed` 集合加入 `"managed"`：
```python
allowed = {"name", "localdate", "basepath", "modpath", "mods_found", "managed"}
```

同时需确保 `managed` 值类型正确（bool）：
```python
elif key == "managed" and isinstance(value, bool):
    target[key] = value
```

---

## 三、改动范围总结

| 文件 | 修改函数 | 修改行数（约） | 变更性质 |
|------|---------|---------------|---------|
| `database_ops.py` | `_scan_from_libraries` | ~5 行 | 路径追加 `/`、managed 保留 |
| `database_ops.py` | `_build_mod_from_games` | ~3 行 | 路径追加 `/`、managed 保留 |
| `database_ops.py` | `add_manual_game` | ~2 行 | 路径追加 `/`、添加 managed |
| `database_ops.py` | `update_manual_game` | ~2 行 | 路径追加 `/`、允许 managed |
| `database_ops.py` | `liveupdate_database` | ~2 行 | 传递 old_games |
| `database_ops.py` | `regen_database` | ~2 行 | 传递 old_games |

**仅修改一个文件**，不新增文件，不修改其他模块。

## 四、验证要点

1. 数据库生成后，`game[].basepath` 和 `game[].modpath` 以 `/` 结尾
2. `mod[].path` 以 `/` 结尾
3. 用户保存 `managed: true` 后执行 liveupdate，对应条目的 `managed` 保持 `true`
4. 新扫描到的 game/mod 默认 `managed: false`
5. `add_manual_game` 生成的条目包含 `"managed": false`
6. 通过 `update_manual_game` 可修改 `managed`
7. `regen_database` 后 managed 值保留与 liveupdate 一致
