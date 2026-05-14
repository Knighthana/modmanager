# HOTFIX-4: E_DUPLICATE 残留 + SVG 画布自适应高度

> 状态: 设计完成，待实现
> 关联: HOTFIX-1/2/3（managed 语义闭环）、TODO-15 Step 1（SVG 宽度自适应）
> 目标文件: `routes/database.py` + `ForestViewer.vue`

---

## 问题1：已选 radio 后仍提示 E_DUPLICATE_APPID / E_DUPLICATE_MIXED_ID

### 根因

`E_DUPLICATE_APPID` 和 `E_DUPLICATE_MIXED_ID` 是扫描阶段产生的通知，存于 `database["errors"]` 中。用户通过 radio 选择 managed=true 消除了冲突并保存后，这些错误没有被清理，随数据库文件持久化。后续 `_populateFromDatabase` 读取时将它们展示为红色错误。

### 修复

在 `POST /api/database/save` 中，保存前清除已由 managed 解决的重复通知。

**文件**: `src/modmanager_web/routes/database.py`
**位置**: 第 118 行 `write_json_file` 之前

```python
# ── 清除已由 managed 解决的重复 appid/mixed_id 通知 ──
if "errors" in db:
    db["errors"] = [
        e for e in db["errors"]
        if not str(e).startswith("E_DUPLICATE_APPID") and not str(e).startswith("E_DUPLICATE_MIXED_ID")
    ]
if "warnings" in db:
    db["warnings"] = [
        w for w in db["warnings"]
        if not str(w).startswith("E_DUPLICATE_APPID") and not str(w).startswith("E_DUPLICATE_MIXED_ID")
    ]

# ── Write to file ── (原有代码)
write_json_file(req.output_path, db)
```

### 语义说明

- `/database/save` 在执行前已通过校验确保了 managed 约束（每 appid/mixed_id 最多一个 true）
- 校验通过 = 冲突已解决 → 重复通知已无意义 → 清除
- 如果校验失败（仍有未解决的冲突），不会走到清除逻辑

---

## 问题2：SVG 画布纵向空白

### 当前行为

`.forest-container` 固定 `min-height: 500px`，无论 SVG 缩放后实际高度多少，容器始终保留 500px 高度，产生大量纵向空白。

### 目标行为

- 画布宽度由页面决定 ✓（TODO-15 Step 1 已完成）
- SVG 缩放比例由画布宽度决定 ✓
- **画布高度 = 等比例缩放后的 SVG 高度**（无纵向空白）

### 修复方案

**文件**: `frontend/src/components/ForestViewer.vue`

#### 1. 新增 `containerMinHeight` 计算属性

在 `svgStyle` computed 之后添加：

```typescript
const containerMinHeight = computed(() => {
  // 无 SVG 内容时使用默认高度
  if (!store.svgContent) return 500
  // 获取 SVG 的自然高度（transform 不影响 layout，getBoundingClientRect 返回自然尺寸）
  const svgEl = containerRef.value?.querySelector('svg')
  if (!svgEl) return 500
  const naturalH = svgEl.getBoundingClientRect().height
  if (naturalH <= 0) return 500
  // 视觉高度 = 自然高度 × scale + 纵向偏移（如果有）
  const visualH = naturalH * scale.value
  return Math.max(visualH, 100)  // 最小 100px 防止容器塌陷
})
```

#### 2. 模板绑定

将 `forest-container` div 绑定 `:style`:

```html
<div
  v-if="store.svgContent"
  ref="containerRef"
  class="forest-container"
  :style="{ minHeight: containerMinHeight + 'px' }"
  ...
>
```

#### 3. CSS 调整

`.forest-container` 的 `min-height: 500px` 改为更小的 fallback：

```css
.forest-container {
  width: 100%;
  min-height: 100px;  /* fallback，当 SVG 未加载或计算失败时使用 */
  /* ... 其他不变 */
}
```

### 效果

- SVG 适配宽度后，容器高度自动缩放到刚好容纳 SVG
- 用户滚轮缩放时，容器高度跟随变化（因为 `containerMinHeight` 是 computed，依赖 `scale`）
- 用户拖拽平移时，内容可能超出容器（被 `overflow: hidden` 裁剪），这是预期行为

---

## 三、改动范围

| 文件 | 改动 | 行数 |
|------|------|------|
| `src/modmanager_web/routes/database.py` | `/save` 写入前清除 E_DUPLICATE_* | ~8 行 |
| `frontend/src/components/ForestViewer.vue` | 新增 `containerMinHeight` computed + 模板绑定 + CSS | ~12 行 |

## 四、验证要点

1. 扫描后有重复 → 选择 radio → 保存 → 错误列表中的 E_DUPLICATE_* 消失
2. SVG 加载后容器高度紧贴 SVG 内容，无纵向空白
3. 滚轮缩放后容器高度自动跟随
4. 不同大小的森林图均正确适应
