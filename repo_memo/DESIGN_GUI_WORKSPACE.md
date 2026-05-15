# DESIGN_GUI_WORKSPACE — 前端工作区状态（已迁移）

> Status: superseded
> Authority: authoritative（新权威为 DESIGN_WORKSPACE_MODEL.md）
> Read-Tier: task-scoped
> Purpose: 本文档描述的旧 localStorage 工作区模型已被 `DESIGN_WORKSPACE_MODEL.md` 替代。本文档保留为迁移记录，不作为当前实现依据。
> 创建：2026-05-14（原 DESIGN_WORKSPACE_STATE.md 归档重写）
> 更新：2026-05-16 — 新工作区模型替代旧 localStorage 模型

---

## 迁移摘要

旧模型将用户决策（decisions）和计算结果摘要（results）存储在前端 `localStorage` 的 `modmanager:workspace` key 中，按 database name 分 `perDatabase` 索引。

新模型将决策和计算结果存入**后端工作区目录** `~/.cache/kmm/workspace/{workspace_id}/`，工作区是用户主动创建的先行容器——用户在动手前创建工作区，所有后续操作在此容器内进行。

### 旧 localStorage key 的迁移

| 旧 key | 迁移到 |
|--------|--------|
| `modmanager:workspace` | **删除**。全部字段拆分迁移 |
| `modmanager:workspace.lastDatabase` | **删除**。工作区绑定 database，创建时选定 |
| `modmanager:workspace.perDatabase[name].decisions` | `{workspace_dir}/{id}/decisions.json` |
| `modmanager:workspace.perDatabase[name].lastComputeSummary` | `{workspace_dir}/{id}/mapping.json` |
| `modmanager:workspace.selectedRulePaths` | **删除**。规则聚合结果存入工作区 `aggregated_rule.json` |
| `modmanager:workspace.aggregatedRuleMeta` | **删除**。指纹校验由后端工作区 `fingerprints.json` 管理 |
| `modmanager:workspace.uiState` | `modmanager:uiState`（localStorage，保留） |

### 新浏览器存储

| key | 介质 | 内容 |
|-----|------|------|
| `modmanager:uiState` | localStorage | UI 偏好（libraryVisibility, gameVisibility, activeTab, sidebarCollapsed） |
| `modmanager:currentWorkspaceId` | sessionStorage | 当前活跃工作区 ID（Tab 隔离，刷新不丢） |

---

## 当前权威

- 工作区模型：`DESIGN_WORKSPACE_MODEL.md`
- 存储规范：`DESIGN_STORAGE.md`
- REST API：`DESIGN_REST_API.md`
- UI 偏好持久化：`DESIGN_STORAGE.md` §8
