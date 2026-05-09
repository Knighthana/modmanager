# HOTFIX-4 v2: E_DUPLICATE 残留 + SVG 画布自适应高度（第二轮）

> 状态: 设计完成，待实现
> 取代: `HOTFIX4-duplicate-cleanup-and-svg-height.md`（第一版修复不彻底）
> 目标文件: `routes/database.py` + `DataSourcePage.vue` + `ForestViewer.vue`

---

## 问题1：E_DUPLICATE 残留 — 双重根因

### 根因 A（后端）：无条件删除 + 不返回清洗后的数据

第一版修复无条件过滤所有 E_DUPLICATE，且只在后端文件中删除，前端从未收到清洗后的数据库。

### 根因 B（前端）：save 成功后使用本地未清洗的 db

`doSave()` 中 `store.updateDatabase(db)` 使用的 `db` 是从 `lastResult` 克隆的本地副本，**仍含有 E_DUPLICATE 错误**。后端虽然清洗了文件，但前端从未拉取清洗后的版本。

### 修复 A（后端）：条件删除 + 返回清洗后的 db

**文件**: `src/modmanager_web/routes/database.py`

在 `POST /database/save` 中，校验通过后，加入判断逻辑：只有当**所有重复 appid 组**都已被 managed 解决（每组恰好一个 managed=true），才删除对应类型的 E_DUPLICATE 错误。

```python
    # ── 条件清除 E_DUPLICATE ──
    from collections import Counter

    # 检查 game 重复是否已全部解决
    appid_counts = Counter(str(g.get("appid", "")) for g in games_raw)
    duplicate_appids = {a for a, c in appid_counts.items() if c > 1}
    appid_managed = Counter()
    for g in games_raw:
        if g.get("managed"):
            a = str(g.get("appid", ""))
            if a in duplicate_appids:
                appid_managed[a] += 1
    all_games_resolved = all(appid_managed.get(a, 0) == 1 for a in duplicate_appids)

    # 检查 mod 重复是否已全部解决
    mods_raw: list[dict[str, Any]] = db.get("mod", []) or []
    mid_counts = Counter(str(m.get("mixed_id", "")) for m in mods_raw)
    duplicate_mids = {m for m, c in mid_counts.items() if c > 1}
    mid_managed = Counter()
    for m in mods_raw:
        if m.get("managed"):
            mid = str(m.get("mixed_id", ""))
            if mid in duplicate_mids:
                mid_managed[mid] += 1
    all_mods_resolved = all(mid_managed.get(m, 0) == 1 for m in duplicate_mids)

    # 仅当解决后才清除
    if all_games_resolved:
        db["errors"] = [e for e in db.get("errors", []) if not str(e).startswith("E_DUPLICATE_APPID")]
        db["warnings"] = [w for w in db.get("warnings", []) if not str(w).startswith("E_DUPLICATE_APPID")]
    if all_mods_resolved:
        db["errors"] = [e for e in db.get("errors", []) if not str(e).startswith("E_DUPLICATE_MIXED_ID")]
        db["warnings"] = [w for w in db.get("warnings", []) if not str(w).startswith("E_DUPLICATE_MIXED_ID")]

    # ── Write to file ──
    write_json_file(req.output_path, db)
```

且在成功响应中**返回清洗后的 database**，以便前端同步：

```python
    return {
        "ok": True,
        "data": {"path": req.output_path, "database": db},
        "errors": [],
        "warnings": [],
    }
```

### 修复 B（前端）：使用后端返回的清洗后 db

**文件**: `frontend/src/pages/DataSourcePage.vue`

`doSave()` 成功分支中，改用 `resp.data.database`（后端返回的清洗后版本）：

```typescript
if (resp.ok) {
  const savedDb = (resp.data as { path: string; database: Record<string, unknown> })?.database || db
  forestStore.storedDatabase = savedDb
  store.updateDatabase(savedDb)
  // ... 其余不变
}
```

---

## 问题2：SVG 高度 — computed DOM 访问不可靠

### 根因

`containerMinHeight` 是 computed，内部访问 `containerRef.value?.querySelector('svg')`。Vue computed 在渲染阶段求值，此时 template ref 可能尚未填充；且 SVG 由 `v-html` 异步插入，`querySelector` 可能在 DOM 就绪前返回 null（fallback 到 500px）。

### 修复：改为命令式 ref + 在关键点显式更新

**文件**: `frontend/src/components/ForestViewer.vue`

#### A. 删除 computed，改为 ref + 更新函数

替换第 165-173 行的 `containerMinHeight` computed：

```typescript
const containerHeight = ref(500)

function updateContainerHeight() {
  const svgEl = containerRef.value?.querySelector('svg')
  if (!svgEl) return
  const naturalH = svgEl.getBoundingClientRect().height
  if (naturalH <= 0) return
  containerHeight.value = Math.max(naturalH * scale.value, 100)
}
```

#### B. 在 fitToContainer() 末尾调用

在 `fitToContainer()` 函数中，`return true` 之前加入：
```typescript
  updateContainerHeight()
```

#### C. 在 onWheel 中调用

在 `onWheel` 函数中，`userAdjustedScale.value = true` 之后加入：
```typescript
  updateContainerHeight()
```

#### D. 模板绑定改为 ref

第 14 行 `:style="{ minHeight: containerMinHeight + 'px' }"` → `:style="{ minHeight: containerHeight + 'px' }"`

---

## 三、改动范围

| 文件 | 改动 | 
|------|------|
| `src/modmanager_web/routes/database.py` | 条件删除 E_DUPLICATE + 响应返回 cleaned db |
| `frontend/src/pages/DataSourcePage.vue` | doSave 使用 resp.data.database |
| `frontend/src/components/ForestViewer.vue` | computed → ref + 显式 updateContainerHeight 调用 |
