# HOTFIX-3: managed 语义闭环修复

> 状态: 已实现
> 关联: HOTFIX-1（后端路径+managed消失）、HOTFIX-2（前端状态同步）
> 目标文件: `validation.py` + `database_ops.py` + `datasource.ts`

---

## 问题分析

managed 属性的设计意图是"数据源页面中解决冲突的选择标记"——多个 game/mod 共享同一 appid/mixed_id 时，用户通过 radio 选定一个 `managed=true`，其他为 `false`。但当前三个环节未闭合：

| # | 问题 | 根因 |
|---|------|------|
| 1 | 保存后计算映射仍报 `appid not unique` | `validate_database` 检查全部 game，不识别 managed；管道传入全量数据库 |
| 2 | 不冲突的 game/mod 显示为未选中（managed=false） | `_scan_from_libraries` 硬编码 `managed: False`，无"单例即默认 managed"逻辑 |
| 3 | 保存时错误列表不断增加 | `_populateFromDatabase` 用 `[...errors, ...db.errors]` 追加，每次 save 都重复追加 |

---

## 一、修复1：validate_database 只检查 managed 条目

### 文件: `src/modmanager/validation.py`

修改 `validate_database` 函数的唯一性检查逻辑（第 181-203 行）：

**新逻辑**：
1. 先检查是否有任何 `game` 的 `managed` 为 `true`
2. 如果没有 → 全部视为 managed（向后兼容无 managed 字段的旧数据库）
3. 如果有 → 只对 `managed: true` 的 game 检查 appid 唯一性

```python
# 判断是否使用 managed 过滤
has_any_managed = any(
    isinstance(g.get("managed"), bool) and g.get("managed") is True
    for g in games if isinstance(g, dict)
)

# Track seen appids for uniqueness
seen_appids: set[str] = set()

for idx, game_obj in enumerate(games):
    if not isinstance(game_obj, dict):
        errors.append(...)
        continue

    appid = game_obj.get("appid")
    # ... existing type/empty checks ...

    # 如果有 managed 字段且当前条目为 false，跳过唯一性检查
    if has_any_managed and not game_obj.get("managed"):
        continue

    if appid in seen_appids:
        errors.append(f"E_DATABASE_INVALID: game[{idx}]['appid'] {appid!r} is not unique")
        continue
    seen_appids.add(appid)

    # ... existing path checks ...
```

---

## 二、修复2：不冲突的 game/mod 默认 managed=true

### 文件: `src/modmanager/database_ops.py`

在 `_scan_from_libraries` 中，所有 game 构建完成后，对无重复的 appid 设置 `managed: true`。

**位置**：在 `_scan_from_libraries` 中，第 182-185 行（games_out 排序后、`_build_mod_from_games` 调用前），新增：

```python
# 对无重复的 appid 自动设置 managed=true
appid_counts: dict[str, int] = {}
for g in games_out:
    appid = str(g.get("appid", ""))
    appid_counts[appid] = appid_counts.get(appid, 0) + 1
for g in games_out:
    appid = str(g.get("appid", ""))
    if appid_counts.get(appid, 1) == 1:
        g["managed"] = True
```

同时对 `add_manual_game` 中新创建的 game 也设置 `managed: true`（手动添加的单条必然是唯一的）：

在 `add_manual_game` 第 421 行 `"managed": False,` 改为 `"managed": True,`。

**注意**：`liveupdate_database` 中已有 `old_games` 参数保留了旧的 managed 值。当 game 是首次出现且无重复时自动设为 true；当用户之前手动设置过 managed 时保留用户的值。这部分逻辑需要兼容：只在 `old_games` 中没有记录（全新 game）且无重复时才自动设为 true。

调整后的逻辑：
```python
for g in games_out:
    appid = str(g.get("appid", ""))
    if appid_counts.get(appid, 1) == 1:
        # 如果 old_games 中有此 appid，保留旧 managed 值；否则默认 true
        if old_games and appid in old_games:
            g["managed"] = old_games[appid].get("managed", True)
        else:
            g["managed"] = True
```

实际上，`_scan_from_libraries` 已经在分支中使用了 `old_games` 来读取 managed（HOTFIX-1 的修复）。当 `old_games` 为 None（首次扫描）时 managed 从 `old_games` 读取会 fallback 到 `False`。我们只需把 fallback 改为"检查是否重复，无重复则 true"。

但在当前代码中，managed 的读取和赋值都在 game 插入 `game_map` 时完成（第 167/178 行），此时还不知道完整的 `appid_counts`。所以自动 managed=true 的逻辑应该放在后期处理阶段（games_out 构建后）。

最终方案：在 games_out 构建后（第 185 行之后），添加后处理：

```python
# Auto-managed: 无重复的 appid 默认 managed=true（首次扫描时）
# 如果 old_games 中有用户之前保存的值则保留
appid_counts: dict[str, int] = {}
for g in games_out:
    appid = str(g.get("appid", ""))
    appid_counts[appid] = appid_counts.get(appid, 0) + 1
for g in games_out:
    appid = str(g.get("appid", ""))
    if appid_counts.get(appid, 1) == 1 and not g.get("managed"):
        # 无重复且当前 managed 不是 true → 自动设为 true
        g["managed"] = True
```

**这个逻辑放在 old_games 读取之后是正确的**：
- 如果 old_games 中用户显式设过 managed=false（虽然不常见），会被 `old_games` 覆盖（已在第 167 行的 `old_games.get(appid, {}).get("managed", False)` 中处理）
- 如果是首次扫描全新 game，`old_games` 返回默认 False，然后后处理会检测到无重复并设为 True
- 如果是 old_games 中已设为 True 的，`g["managed"]` 已经为 True，`not g.get("managed")` 为 False，不会重复赋值

---

## 三、修复3：_populateFromDatabase 错误不累积

### 文件: `frontend/src/stores/datasource.ts`

`_populateFromDatabase` 中的错误合并（第 308-309 行）：

```typescript
// 当前 (有问题):
warnings.value = [...warnings.value, ...((db.warnings as string[]) || [])]
errors.value = [...errors.value, ...((db.errors as string[]) || [])]

// 修复: 替换而非追加
warnings.value = (db.warnings as string[]) || []
errors.value = (db.errors as string[]) || []
```

或者区分场景：在 `updateDatabase` 中先清空再调用。

最简单的修复：**直接改为替换**，因为 `_populateFromDatabase` 本意就是从 db 中重建本地状态，不需要保留旧错误。

```typescript
warnings.value = (db.warnings as string[]) || []
errors.value = (db.errors as string[]) || []
```

---

## 四、改动范围总结

| 文件 | 改动 | 行数 |
|------|------|------|
| `src/modmanager/validation.py` | `validate_database`: 只对 managed=true 的游戏检查唯一性 | ~10 行 |
| `src/modmanager/database_ops.py` | `_scan_from_libraries`: 后处理，无重复 appid 自动 managed=true | ~8 行 |
| `src/modmanager/database_ops.py` | `add_manual_game`: managed 默认 true | 1 行 |
| `frontend/src/stores/datasource.ts` | `_populateFromDatabase`: 错误替换而非追加 | 2 行 |

## 五、验证要点

1. 存在重复 appid 游戏 → 用户选一个 managed=true → 保存 → 计算映射 → 不再报 `not unique`
2. 无重复 appid 的游戏 → 扫描后自动显示 managed=true（radio 默认选中）
3. 不存在 managed 字段的旧数据库 → validate_database 行为不变（全部检查）
4. 保存时错误列表不再翻倍增长
