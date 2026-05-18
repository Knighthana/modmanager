# DESIGN_COMPUTE_PREP_PAGE — 计算准备页设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义「计算准备」页面的布局、交互行为、managed_entries 构造逻辑、compute 触发流程与结果查看导航
> 创建：2026-05-13
> 更新：2026-05-14 — 决策/结果迁移至前端 localStorage
> 更新：2026-05-14 — 【§十二补充裁定】删除 `aggregated_rule_path`，`aggregated_rule_set` 改为必填 dict；补充 hash 校验逻辑
> 依赖：DESIGN_GUI.md（页面流）、DESIGN_GUI_WORKSPACE.md（workspace 结构）、DESIGN_GUI_DATASOURCE_TAB.md（数据源展示）

---

## 一、定位

计算准备是 pipeline 计算前的最后一步。用户在此：

1. 查看被选定规则影响的 game / mod 清单
2. （可选）对重复条目做预选——取消不需要的路径，减少 engine 产生的分支
3. 触发计算

---

## 二、布局

```
┌ 计算准备 ───────────────────────────────────────────────────────────────────┐
│                                                                              │
│  [▶ 开始计算]  [查看结果]      覆盖 2 个库，5 个游戏 (2 个有多个入口)          │
│                                                                              │
│ ▶ 库                                                                         │
│ ┌──────┬────┬──────────────────────────────────────┬──────┬──────┬────────┐  │
│ │ 选中  │ 序 │ 路径                                   │ 游戏  │ MOD  │ 可见   │  │
│ ├──────┼────┼──────────────────────────────────────┼──────┼──────┼────────┤  │
│ │  ☑   │ 1  │ /mnt/d/SteamLibrary/steamapps          │  2   │  3   │  👁    │  │
│ │  ◐   │ 2  │ /mnt/e/SteamLibrary/steamapps          │  1   │  1   │  👁    │  │
│ └──────┴────┴──────────────────────────────────────┴──────┴──────┴────────┘  │
│                                                                              │
│ ▶ 游戏                                                                        │
│ ┌──────┬────┬────────┬──────────┬──────────────────────────────────────────┐ │
│ │ 选中  │ 序 │ appid   │ 名称      │ 路径 (white-space:nowrap; overflow-x:auto)│ │
│ ├──────┼────┼────────┼──────────┼──────────────────────────────────────────┤ │
│ │  ☑   │ 1  │ 270150 │ RWR      │ /mnt/d/.../common/RWR           ←重复   │ │
│ │  ☐   │ 2  │ 270150 │ RWR      │ /mnt/e/.../common/RWR                    │ │
│ │  ☑   │ 3  │ 107410 │ Arma3    │ /mnt/d/.../common/Arma3                 │ │
│ └──────┴────┴────────┴──────────┴──────────────────────────────────────────┘ │
│                                                                              │
│ ▶ MOD                                                                         │
│ ┌──────┬────┬──────────────────┬──────────┬───────────────────────────────┐  │
│ │ 选中  │ 序 │ mixed_id          │ 名称      │ 路径                           │  │
│ ├──────┼────┼──────────────────┼──────────┼───────────────────────────────┤  │
│ │  ☑   │ 1  │ 270150:260609... │ Castle   │ /mnt/d/.../2606099273         │  │
│ └──────┴────┴──────────────────┴──────────┴───────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 顶部操作区

| 元素 | 初始状态 | 行为 |
|------|---------|------|
| [▶ 开始计算] | 始终可点击 | 构建 managed_entries → `POST /api/workspace/{id}/pipeline/compute` |
| [查看结果] | 灰色（disabled） | workspace.perDatabase[name].results.timestamp 非空时亮起可点击 → 跳转 `/forest` |
| 提示文字 | 动态计算 | "覆盖 N 个游戏 (X 个有多个入口) / 覆盖 N 个 MOD (Y 个有多个入口)" |

**按钮状态**：[查看结果] 不依赖 [▶ 开始计算] 的触发——它只看 `workspace.perDatabase[name].results.timestamp` 是否为 null。这样两个按钮之间无耦合。

### 2.2 表格列

| 列 | 内容 | 说明 |
|----|------|------|
| 选中 | checkbox | 默认全选 |
| 序 | 数字 | 表格行号 |
| appid / mixed_id | 字符串 | 标识符 |
| 名称 | 字符串 | 游戏名（来自 database）或 MOD 名（来自 rule） |
| 路径 | `div { white-space: nowrap; overflow-x: auto; scrollbar-width: none }` | 水平可滚动，无滚动条 |

### 2.3 数据来源

计算准备页加载时：

```
→ 从 workspace.aggregatedRuleSet 读取聚合规则 dict
  → POST /api/rules/affected-entries { aggregated_rule_set }
  → 后端对比 database + aggregated_rule_set
  → 返回：
      {
        libraries: [{ index, path, game_count, mod_count }],
        games: [{ appid, name, basepath, libraryIndex, has_duplicate }],
        mods: [{ mixed_id, nickname, path, libraryIndex, gameIndex, has_duplicate }]
      }
  → 前端按 libraryIndex 分组渲染三张表
```

> 此端点轻量——只查询"哪些条目被引用"，不执行完整 compute。

### 2.4 库表 tri-state checkbox

库表位于游戏表之前，提供批量选中/取消操作。

| 状态 | 含义 | 点击后 |
|:---:|------|------|
| ☑ 全选 | 此库所有 game + mod = ☑ | → 全部取消（child → ☐） |
| ◐ 半选 | 部分 game/mod = ☑ | → 全部取消（child → ☐） |
| ☐ 清空 | 无 game/mod = ☑ | → 全部选中（child → ☑） |

**Element Plus 实现**：
```vue
<el-checkbox 
  v-model="lib.checked" 
  :indeterminate="isIndeterminate(lib.index)"
  @change="toggleLibrary(lib.index)"
/>
```

`indeterminate = true` 时显示 ◐ 横线标记。

**双向联动**：
- 库 checkbox 变化 → 遍历该库的 game[] + mod[] → 同步设置全部 child
- 任意 game/mod checkbox 变化 → 重新计算父库状态，更新 `checked` / `indeterminate`
- 纯前端 Pinia computed——不调后端

**分组依据**：`POST /api/rules/affected-entries` 返回的每条 game/mod 带 `libraryIndex` 字段。前端据此 group。

### 2.5 可见/隐藏按钮

每库行的 `👁` 按钮：toggle 展开/折叠该库的 game + mod 行。纯 UI 折叠效果——不改变 checkbox 状态，不影响 managed_entries。

---

## 三、checkbox 交互

### 3.1 默认状态

所有行 **默认全部选中**（不干预 = 全留给 engine）。

### 3.2 重复条目视觉提示

- 同一 appid / mixed_id 有多行时 → 对应行柔和高亮（如浅黄色背景或淡边框色）
- 高亮应柔和（非刺眼），仅在需要分辨时可见
- 所有重复冲突解决后（每组只保留一项），高亮自动消除
- 顶部提示文字实时更新："覆盖 N 个游戏 (X 个有多个入口)"

### 3.3 用户操作

- 用户可以**取消** checkbox → 对应的条目不参与 compute
- 取消操作**仅改变前端本地状态**（Pinia ref），不调后端
- 同一 appid/mixed_id 的条目组：用户可以任意留任意去（包括全留、只留一个、全部取消）
- 全部取消的含义：对该 appid/mixed_id，无偏好 → engine 自行处理所有条目

---

## 四、managed_entries 构造

### 4.1 触发时机

点击 [▶ 开始计算] 时，从 Pinia ref 中收集 checkbox 状态。

### 4.2 构造规则

```python
managed_entries = {}

for game in games:
    if game.checked == False:  # 用户取消了
        if game.appid not in managed_entries["game"]:
            managed_entries["game"][game.appid] = []
        # 不添加此路径 → 相当于"排除此路径"

# 等价逻辑：收集所有"被保留的路径"（即 checked=True 的路径）
for appid in all_appids:
    kept = [g.path for g in games if g.appid == appid and g.checked]
    if len(kept) < total_for_appid:  # 用户取消了一部分
        managed_entries["game"][appid] = kept

# mod 同理
```

### 4.3 输出格式

```json
{
  "game": {
    "270150": ["/mnt/d/.../RWR"]       // 用户保留了这一个
  },
  "mod": {
    "270150:2606099273": ["/mnt/d/.../mod"]
  }
}
```

- 值为**列表**——表达"仅保留这些路径"
- **不在** managed_entries 中的 appid/mixed_id → 全部保留（用户未干预）
- 某 appid 的值若为**空列表** `[]` → 全部排除

---

## 五、compute 触发

### 5.1 请求

```json
POST /api/workspace/{id}/pipeline/compute
{
  "database_name": "HOSTB_SSD",
  "aggregated_rule_set": { ... },
  "managed_entries": { ... },
  "branch_decisions": { ... }
}
```

`database_name` 由前端 database 下拉组件提供。`aggregated_rule_set` 从 workspace.aggregatedRuleSet 读取（必填 dict）。`managed_entries` 和 `branch_decisions` 从 `workspace.perDatabase[name].decisions` 读取。
database 由 orchestrator 内部通过 bootstrap 获取，调用方不传入完整 database dict。

> **不再接受 `aggregated_rule_path` 参数**。compute 只接受 dict，文件是备份产物不是 compute 输入。

### 5.2 响应处理

```
compute SSE 流结束 → onResult:
   成功 →
     1. 前端从响应提取摘要 → 写 localStorage.modmanager:results:{database_name}
     2. [查看结果] 按钮亮起（localStorage.results:{name}.timestamp 非 null）
     3. 页面显示 "✅ 计算完成：42 棵树，15 个映射"
   失败 →
     1. 错误信息在页面展示
     2. [查看结果] 保持灰色
```

### 5.3 不自动跳转

compute 成功后**不自动跳转** Forest。用户需主动点击 [查看结果]。避免打断用户可能的后续操作。

---

## 六、数据流

### 6.1 hash 校验（加载时）

```
计算准备页 mount
  → 从 user_config.rule_sources 读取当前 rule 文件路径列表
  → 计算路径+内容的 SHA-256 hash（sorted(paths) + sorted(contents)）
  → 从 localStorage 读取 workspace.aggregatedRuleHash
  → 比对：
      ├── 一致 → 复用 workspace.aggregatedRuleSet（规则未变更）
      └── 不一致 → 清空 workspace.aggregatedRuleSet
                   → 提示"规则已变更，请重新聚合"
```

### 6.2 加载流程

```
计算准备页 mount（hash 校验通过后）
  → 从 workspace.aggregatedRuleSet 读取聚合规则 dict
  → POST /api/rules/affected-entries { aggregated_rule_set } → 返回被引用条目列表（含重复标记）
  → 渲染表格
  → 从 workspace.perDatabase[name].decisions 恢复历史决策

用户取消 checkbox → Pinia ref 更新 → 顶部提示文字实时更新

用户点 [▶ 开始计算]
  → 从 workspace.perDatabase[name].decisions 读 decisions
  → 从 workspace.aggregatedRuleSet 读聚合规则 dict
  → 收集 checkbox 状态 → 构建 managed_entries
  → POST /api/workspace/{id}/pipeline/compute { database_name, aggregated_rule_set, managed_entries, branch_decisions }
  → orchestrator 内部获取 database
  → 成功 → 前端写 workspace.perDatabase[name].results 到 localStorage → [查看结果] 亮起

用户点 [查看结果]
  → router.push('/forest')
```

---

## 七、空状态与边界情况

| 场景 | 行为 |
|------|------|
| 无规则选择 | 显示"请先在规则概览选择规则" + [前往规则概览] 链接 |
| 所选规则不涉及任何 game/mod | 显示"当前规则集未覆盖任何游戏或 MOD" |
| 有规则但无重复 | 顶部显示"覆盖 N 个游戏 (0 个有多个入口)"，表格无高亮行 |
| workspace.perDatabase[name].results.timestamp 为空 | [查看结果] 灰色 disabled |
| compute 中途关闭页面 | workspace.perDatabase[name].results 不更新（只有成功后写入） |
| aggregatedRuleHash 不匹配 | 清空 aggregatedRuleSet，提示"规则已变更，请重新聚合" |

---

## 八、实现文件

| 文件 | 职责 |
|------|------|
| `frontend/src/pages/ComputePrepPage.vue` | 页面组件（含 hash 校验逻辑） |
| `src/modmanager_web/routes/rules.py`（改） | 新增 `POST /api/rules/affected-entries` |
| `src/modmanager_web/schemas.py`（改） | `ComputeRequest` 新增 `managed_entries`、`aggregated_rule_set` 字段；删除 `aggregated_rule_path` |

---

## 九、决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | managed_entries 存储 | 前端 localStorage（`modmanager:decisions:{name}.managed_entries`），compute 时作为参数传入 |
| D2 | 默认 checkbox 状态 | 全选（不干预 = 全部留给 engine） |
| D3 | 重复条目视觉提示 | 柔和高亮，非刺眼 |
| D4 | compute 后行为 | 不自动跳转——用户主动点 [查看结果] |
| D5 | [查看结果] 按钮状态 | 依 localStorage.results:{name}.timestamp 是否非 null 决定 |
| D6 | 数据来源 | 新增 `POST /api/rules/affected-entries` 轻量查询端点 |
