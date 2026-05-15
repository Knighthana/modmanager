# TODO — uiState 并入 workspace

> Source: `work_memo/2026-05-14_audit_todo_future.md` item 2
> Doc: 审计 §1.1 `DESIGN_GUI_WORKSPACE.md`

## 目标
将分散的 UI 状态持久化 key 聚合进 `workspace.uiState`。

## workspace 结构（新增）
```json
{
  "uiState": {
    "sidebarCollapsed": false,
    "datasource": {
      "discoveryMode": "all",
      "manualPaths": [],
      "greedyParsing": false,
      "libraryVisibility": {},
      "gameVisibility": {}
    },
    "computePrep": {
      "libraryVisibility": {}
    }
  }
}
```

## 涉及文件

| 文件 | 改动 |
|------|------|
| `pages/DataSourcePage.vue` | `pers.save('datasource-xxx')` → `workspace.uiState.datasource.xxx` |
| `pages/ComputePrepPage.vue` | `libraryVisibility` 存/取 workspace.uiState.computePrep |
| `utils/persistence.ts` | 注释更新 |
| `DESIGN_GUI_WORKSPACE.md` | 补充 uiState 结构 |

## 不在此范围
- `useWorkspaceStore` 唯一写者（audit_todo_future item 1）
- Transport Abstraction（audit_todo_future item 3）
- `activeTab` / `sidebarCollapsed`（当前无实现）
