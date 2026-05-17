# 森林页 UI 改进 — 2026-05-17

## 一、森林可视重写

来源：用户提供的 `description/thegraphiccontainerexample.html` 示例代码。

### 容器弹性链条（零硬编码）
- `ForestPage.vue`：`.forest-page` 设 `display:flex; flex-direction:column; height:100%; overflow:hidden`
- `ForestViewer.vue`：CSS flex 链从 `el-card` → `el-card__body` → `.forest-wrapper` → `.forest-container` 全部打通

### svg-pan-zoom 原生集成
- `panEnabled: false`，自定义鼠标拖拽：3px 阈值区分 click/drag，text/tspan/a 元素保护（不劫持选中/链接点击）
- `beforePan` 约束视野不超出图片边界
- `minZoom = fitZoom`（contain 即下限），`maxZoom = 80`
- `ResizeObserver` → resize + fit + center + 小地图刷新
- `setTimeout(60ms)` 规避容器尺寸竞态

### SVG 预处理
- DOMParser 解析 SVG 字符串 → 补全 viewBox → 剥离硬编码 width/height → set 100%
- DOMParser 不可用时回退 innerHTML
- SVG 直接 append 到 `forest-container`（无包装 div）

### 小地图
- 尺寸以容器高度为基准：`maxH = Math.min(250, containerH * 0.4)`，宽度按 SVG 比例反推
- 极端竖长图防御：宽度 < 50px 时保底 50px；高度超容器回缩
- 蓝色滑块实时反映视口位置
- 点击/拖拽小地图跳转主视口

### 树节点交互
- hover 高亮（关联 refs / referenced-by 同时高亮，其他变暗）
- click 选枝 / 候选源设置决策
- selected 节点蓝色 drop-shadow

---

## 二、pack 二维排列接口（后端）

文件：`src/modmanager/forest_visual.py`

新增参数 `pack_enabled: bool = False`（默认关闭，保持原始竖排）：

```python
def visualize_payload(payload, output_format, show_m1_details=False,
                      aspect_ratio=16/9, pack_enabled=False)
def _render_dot(model, show_m1_details=False, aspect_ratio=16/9, pack_enabled=False)
```

`pack_enabled=True` 时：
- 自动计算二维网格列数（`columns = round((tree_count * aspect_ratio) ** 0.5)`）
- 生成 `pack=true; packmode="array_cN"` 属性
- source 节点按边独立 ID（保证树间断开，pack 能拆分）
- 跳过引用边（防止 pack 组件合并）

`pack_enabled=False`（默认）时：
- 原始共享 source 节点（按路径去重）
- 渲染引用边
- 无 pack 属性

调用方式：`visualize_payload(payload, "svg")` 竖排，`visualize_payload(payload, "svg", pack_enabled=True)` 二维网格。

---

## 三、UI 一致性

### 页面标题与导航统一
修复 6 个页面：根元素统一 `xxx-page gui-page` class + `margin:0 auto; padding:16px 24px` CSS，标题 emoji 与导航文本一致。

| 页面 | 标题 |
|------|------|
| 冲突裁决 | ⚔️ 冲突裁决 |
| 文件操作 | 💾 文件操作 |
| 规则制定 | ✏️ 规则制定 |
| 设置面板 | ⚙️ 设置面板 |
| 进阶用户 | 👨‍💻 进阶用户 |
| 工作区 | 📂 工作区（inline style → class） |

### 图标调整
- 进阶用户：🔧 → 👨‍💻
- App 标题：🔧 → 🧩
- App 标题布局：emoji 独立左列 28px + 文字右列 14px 自然换行

---

## 四、OperationsPage 恢复

- 新增路由 `/workspace/:id/operations`
- LayoutShell 侧栏添加 💾 文件操作（位于冲突裁决后、数据来源前）

---

## 五、其他修复

- ComputePrepPage 测试：修正 `apiGet`/`apiPost` mock 方法名不匹配
- App.vue 注释：修正"workspace 已移除"为"旧 workspace status check 已移除"
