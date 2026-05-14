# Phase 4 — 前端数据自动恢复 + manual 模式缓存修正

> Status: plan
> Authority: arch
> Created: 2026-05-14
> Source: `work_memo/states.md` TODO-56, TODO-57

---

## Task 4.1: `bootstrap.py` — manual 模式跳过缓存

### 问题
`generate_database()` 中缓存检查位于 mode 分支之前。manual 模式需要重新扫描指定路径，不应返回旧缓存。

### 当前代码（`bootstrap.py` 约 185-198 行）
```python
config = discover_user_config()
db_path = config.get("databases", {}).get(database_name, {}).get("path")

# 缓存检查 —— 在所有 mode 分支之前
cache_file = Path(db_path)
if cache_file.exists() and cache_file.stat().st_size > 0:
    cached = load_json_file(db_path)
    if isinstance(cached, dict) and isinstance(cached.get("steamlib"), list):
        return cached  # ← manual 模式也会走这里
```

### 修正
将缓存检查移到 auto 模式分支内，或在缓存检查前判断 mode：

```python
# manual 模式跳过缓存
if mode != "manual":
    cache_file = Path(db_path)
    if cache_file.exists() and cache_file.stat().st_size > 0:
        try:
            cached = load_json_file(db_path)
            if isinstance(cached, dict) and isinstance(cached.get("steamlib"), list):
                return cached
        except Exception:
            pass
```

### 涉及文件
`src/modmanager/bootstrap.py`

---

## Task 4.2: `DataSourcePage.vue` — onMounted 自动加载 database

### 问题
页面刷新后，database 数据丢失。用户必须手动点"扫描"或"读取"。

### 修正
在 `onMounted` 中：
1. 从 localStorage 读 `lastDatabase`
2. 若存在 → 自动调 `POST /api/database/read { database_name: lastDatabase }` 
3. 将返回的 database dict 填入 datasourceStore（`updateDatabase(db)`）
4. 下拉自动选中 `lastDatabase`

### 伪代码
```ts
onMounted(async () => {
  const lastDb = pers.load<string>('lastDatabase')
  if (lastDb) {
    selectedDatabase.value = lastDb
    try {
      const resp = await apiPost('/database/read', { database_name: lastDb })
      if (resp.ok && resp.data) {
        store.updateDatabase(resp.data as Record<string, unknown>)
      }
    } catch { /* 静默失败——用户可以手动扫描 */ }
  }
})
```

---

## Task 4.3: `AdvancedPage.vue` — Database tab 自动加载

### 修正
Database tab 激活时（或页面 onMounted），自动调 `/api/database/read` 加载当前 database 内容展示。

### 涉及文件
`frontend/src/pages/AdvancedPage.vue`

---

## Task 4.4: `ForestPage.vue` — onMounted 恢复上次结果

### 修正
在 `onMounted` 中：
1. 从 localStorage 读 `lastDatabase`
2. 若存在 → 读 `results:{lastDatabase}` 
3. 若存在 → 展示"上次计算结果：X 棵树，Y 个映射"（或恢复可视化）

---

## 执行顺序

1. Task 4.1 — bootstrap.py manual 模式缓存修正
2. Task 4.2 — DataSourcePage 自动加载
3. Task 4.3 — AdvancedPage 自动加载
4. Task 4.4 — ForestPage 恢复结果

---

## 验收

```bash
python -m pytest tests/ -x -q   # Python 测试全绿
cd frontend && npm run build     # 前端构建成功
```
