# 文件操作页面工作区适配方案

> Last-Updated: 2026-05-18

## 目标

对 `OperationsPage` 进行改造，使其符合现有"工作区"逻辑——即与 `ComputePrepPage`、`ConflictsPage` 等工作区页面保持一致的行为模式。

## 背景

当前 `OperationsPage` 仍使用**全局管线端点**（`/pipeline/backup`、`/pipeline/apply`、`/pipeline/restore`），需显式传递 `mapping_result`、`final_mapping`、`database_name`、`backup_dir` 等参数。页面顶部还有 `DatabaseSelector` 组件让用户手动选库。

其他工作区页面的统一模式：
1. 从路由提取 `workspaceId`
2. 调用工作区专用 API（`/workspace/{id}/...`）
3. 数据库从工作区绑定自动获取
4. 计算结果持久化在工作区目录中
5. `onMounted` 时设置 `appStore.setCurrentWorkspaceId(workspaceId)`

## 改造内容

### 一、后端

#### 1.1 `src/modmanager/core/workspacemanager.py`

新增方法，用于在 `meta.json` 中读写 `backup_dir` 字段：

```python
def write_backup_dir(self, workspace_id: str, backup_dir: str) -> None:
    """Write backup_dir into meta.json and update updated_at."""
    ws_dir = self._dir(workspace_id)
    meta_path = ws_dir / self._META
    meta = load_json_file(meta_path)
    meta["backup_dir"] = backup_dir
    meta["updated_at"] = _utcnow()
    write_json_file(meta_path, meta)

def read_backup_dir(self, workspace_id: str) -> str | None:
    """Read backup_dir from meta.json, return None if absent."""
    meta = self.read_meta(workspace_id)
    return meta.get("backup_dir")
```

`meta.json` 新增可选字段 `"backup_dir": "..."` — 仅在 backup 操作后写入，restore 操作读取。

#### 1.2 `src/modmanager/orchestrator.py`

新增两个工作区感知函数，对标已有的 `compute_ws()` 和 `run_ws()`。文件头部新增 `backup_ws`、`apply_ws` 到 `__all__`。

**`backup_ws(workspace_id, *, on_progress=None) -> PipelineResult`**：

流程：
1. 通过 `_get_workspace_manager()` + `discover_user_config()` 获取 wm 和 user_config
2. 校验工作区存在、有 mapping
3. 读取 `meta["database_name"]`，调用 `_resolve_database()` 加载数据库
4. 读取 `wm.read_mapping()` 获取 mapping_result
5. 从 `mapping_result["final_mapping"]` 提取路径列表，调用 `build_backup_dir()` 自动推导 backup_dir
6. 调用已有的 `backup(mapping_result, backup_dir, on_progress=on_progress)`
7. 成功后将 `backup_dir` 写入工作区：`wm.write_backup_dir(workspace_id, backup_dir)`
8. 返回 `PipelineResult`

错误处理：
- 工作区不存在 → `PipelineResult(ok=False, errors=["workspace not found"])`
- 无 mapping → `PipelineResult(ok=False, errors=["no mapping in workspace — compute first"])`
- 数据库解析失败 → `PipelineResult(ok=False, errors=[str(exc)])`

**`apply_ws(workspace_id, *, dry_run=False, on_progress=None) -> PipelineResult`**：

流程：
1. 通过 `_get_workspace_manager()` + `discover_user_config()` 获取 wm 和 user_config
2. 校验工作区存在、有 mapping
3. 读取 `wm.read_backup_dir()` 获取 backup_dir
4. 若 backup_dir 为 None → 从 mapping + database 自动推导（与 backup_ws 逻辑一致）
5. 调用已有的 `apply(final_mapping, backup_dir, dry_run=dry_run, on_progress=on_progress)`
6. 返回 `PipelineResult`

错误处理：
- 工作区不存在 → 错误
- 无 mapping → 错误
- backup_dir 为 None 且无法推导 → 错误

#### 1.3 `src/modmanager_web/schemas.py`

新增请求模型：

```python
class WorkspaceApplyRequest(BaseModel):
    """Request body for POST /api/workspace/{id}/pipeline/apply."""
    dry_run: bool = False
```

backup 和 restore 端点无需额外参数（使用空 body 或无 body 模型）。

#### 1.4 `src/modmanager_web/routes/workspace.py`

新增三个 SSE 端点，所有端点返回 `StreamingResponse`（`text/event-stream`），与已有 `compute`/`run` 端点风格一致。

导入新增：`from modmanager.orchestrator import backup_ws, apply_ws`（追加到已有 import），`from modmanager.backup_ops import restore_from_backup`。
导入新增 schema：`from ..schemas import WorkspaceApplyRequest`。

**A. `POST /{workspace_id}/pipeline/backup`**

```python
@router.post("/{workspace_id}/pipeline/backup")
async def workspace_backup(workspace_id: str):
    def do_work(*, on_progress):
        return backup_ws(workspace_id=workspace_id, on_progress=on_progress)
    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

**B. `POST /{workspace_id}/pipeline/apply`**

```python
@router.post("/{workspace_id}/pipeline/apply")
async def workspace_apply(workspace_id: str, req: WorkspaceApplyRequest):
    def do_work(*, on_progress):
        return apply_ws(
            workspace_id=workspace_id,
            dry_run=req.dry_run,
            on_progress=on_progress,
        )
    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

**C. `POST /{workspace_id}/pipeline/restore`**

```python
@router.post("/{workspace_id}/pipeline/restore")
async def workspace_restore(workspace_id: str):
    wm = _get_workspace_manager()
    if not wm.exists(workspace_id):
        return adapt_error(f"workspace '{workspace_id}' not found")
    backup_dir = wm.read_backup_dir(workspace_id)
    if not backup_dir:
        return adapt_error("no backup_dir stored — run backup first")

    def do_work(*, on_progress):
        return restore_from_backup(backup_dir=backup_dir, target_files=None)
    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_restore_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

注意：需从 `..adapters` 额外导入 `adapt_restore_result`（已在 pipeline.py 中使用，需确认 workspace.py 中是否已有该 import）。

### 二、前端

#### 2.1 `frontend/src/pages/OperationsPage.vue` — 重写

**移除的 import / 变量 / 逻辑**：
- `import DatabaseSelector from '../components/DatabaseSelector.vue'`
- `import { generateBackupDir } from '../stores/forest'`
- `const databaseSelectorRef = ref<...>(null)`
- `const selectedDb = computed(...)`
- 所有 `databaseSelectorRef.value?.selectedDatabase` 引用
- 所有 `store.pipelineForm.backupDir` 引用
- 所有 `generateBackupDir()` 调用
- SSE 调用中所有显式参数（`mapping_result`、`final_mapping`、`backup_dir`、`database_name`）

**新增的 import / 变量 / 逻辑**：
- `import { useRouter, useRoute } from 'vue-router'`
- `import { useAppStore } from '../stores/app'`
- `import { apiGet } from '../api/transport'`
- `const router = useRouter()`
- `const route = useRoute()`
- `const appStore = useAppStore()`
- `const workspaceId = computed(() => route.params.workspaceId as string)`

**`onMounted`**：
```typescript
onMounted(async () => {
  if (workspaceId.value) {
    appStore.setCurrentWorkspaceId(workspaceId.value)
  }
  await loadMappingFromWorkspace()
})
```

**`loadMappingFromWorkspace()` 函数**：
1. 优先调用 `GET /workspace/${workspaceId}/forest/mapping`
2. 若成功且 data 包含 `trees` / `final_mapping` → 填充 `localResults`
3. 若失败或无数据 → 回退到 `forestStore` 内存态数据（`store.trees`、`store.finalMapping` 等）
4. 若两者皆空 → `hasResults` 为 false，显示空状态

**空状态改造**（模板 `v-if="!hasResults"` 块）：
将简单的 `<el-empty description="...">` 替换为带操作按钮的版本：
```html
<el-empty :description="STR.operationsPage.emptyState">
  <el-button type="primary" @click="router.push(`/workspace/${workspaceId}/compute`)">
    前往计算准备
  </el-button>
</el-empty>
```

**SSE 调用改为工作区端点**：

```typescript
// 备份
await streamSse(`/workspace/${workspaceId.value}/pipeline/backup`, {}, { ... })

// 应用
await streamSse(`/workspace/${workspaceId.value}/pipeline/apply`, { dry_run: dryRun.value }, { ... })

// 恢复
await streamSse(`/workspace/${workspaceId.value}/pipeline/restore`, {}, { ... })
```

**模板变更**：
- 删除 `<DatabaseSelector>` 区块（第 6-8 行）
- 空状态 `<el-empty>` 中增加 `<el-button>` 子元素

#### 2.2 `frontend/src/locales/zh-CN.ts`

`operationsPage.emptyState` 字符串从 `'尚未计算 → 前往计算准备'` 改为 `'尚未计算'`（因为按钮已提供跳转功能，文案只需描述当前状态）。

### 三、无需改动的部分

- `LayoutShell.vue` — 侧边栏菜单和路由已正确配置
- `router/index.ts` — 路由 `/workspace/:workspaceId/operations` 已存在
- `forestStore` — 全局管线方法保留不动
- `api/config.ts` — `API_ENDPOINTS` 不变
- 现有的 `adapt_restore_result` — 确认在 `adapters.py` 中存在

---

## 实施顺序

1. 后端 `workspacemanager.py` — 新增 `write_backup_dir` / `read_backup_dir`
2. 后端 `orchestrator.py` — 新增 `backup_ws` / `apply_ws`，更新 `__all__`
3. 后端 `schemas.py` — 新增 `WorkspaceApplyRequest`
4. 后端 `routes/workspace.py` — 新增三个端点，补充 import
5. 前端 `OperationsPage.vue` — 重写
6. 前端 `zh-CN.ts` — 更新 `emptyState` 字符串

---

## 第二轮修正（用户反馈）

用户反馈：选中工作区后页面仍提示"尚未计算"，质疑是否存在不必要的耦合。

### 诊断

数据加载链路（`onMounted` → `loadMappingFromWorkspace()` → `GET /workspace/{id}/forest/mapping` → `populateResults()`）逻辑本身正确。但发现两个具体问题：

1. **`hasResults` 只检查 `trees_count > 0`，忽略 `mapping_count`**。文件操作页面核心数据是 `final_mapping`（映射文件列表），而非 `trees`（决策树）。极端情况下有映射数据但无树时，页面会错误显示空状态。

2. **空状态不区分场景**。"正在加载"、"API 出错"、"确实未计算"三种情况共用同一个 `el-empty`，用户无法判断故障原因。

### 修正

1. `hasResults` 条件改为 `trees_count > 0 || mapping_count > 0`
2. 新增 `loadState`（`'loading' | 'loaded' | 'error'`）和 `loadError` 状态变量
3. 模板新增三个分支：
   - `loadState === 'loading'` → 显示加载中动画
   - `loadState === 'error'` → 显示错误信息 + 重试按钮
   - `!hasResults && loadState === 'loaded'` → 显示"尚未计算"+ 跳转按钮
4. `loadMappingFromWorkspace()` 中补充了 workspaceId 缺失时的错误处理

---

## 第三轮修正（用户反馈：dry_run、进度、摘要、backup_id）

### build_backup_dir 选择逻辑

**原则**：基于 **path prefix** 匹配。mapping 中每条目标路径，与 database 中各 game entry 的 `basepath` / `modpath` 做前缀匹配。命中哪个 game entry 就在其根目录下创建 backup dir。与数据库中存在多少条同名 appid 无关。

之前的"选择匹配数最多的 appid"逻辑是错误的——用 `(appid, region)` 做 Counter key 会合并同名 appid 的计数，且后续选择时只取第一条匹配 appid 的 entry，无法区分数据库中的多条同名 appid 记录。应改为按 entry index 独立匹配、path prefix 决定归属。

### dry_run 原则

- 所有文件操作（备份 / 应用 / 恢复）在 `dry_run=true` 时必须仅做预检查、不执行文件 I/O
- dry_run 返回结构化文件列表，每项含 `path`、`size`、`mtime`、`action`、`is_dir`
- 逐文件 `on_progress` 回调：备份/应用/恢复均支持 per-file 进度上报，前端进度条实时更新
- dry_run 结果在前端以持久文件列表表格展示（非短暂 toast），含路径、大小、修改时间、类型、操作列，用户可手动清除

### 文件操作页面补充

- **mappingStats 计算**：`新增`/`覆盖`/`删除` 三个统计值从 `final_mapping[].request.action` 实时统计（`create` → 新增，`replace` → 覆盖，`delete` → 删除），不再依赖数据库中可能为空的 `stats` 字段
- **摘要字段调整**：移除"树总数"，新增"操作警告"/"操作错误"（最近一次操作的警告/错误，持久化显示直到下次操作覆盖）
- **警告/错误显示规则**：badge 数量为 0 时不显示气泡、仅显示灰色文字；数量 >0 时显示气泡，点击弹出 `el-dialog` 表格逐条列出详情
- **映射警告/错误**与**操作警告/错误**各自独立，分别有对应的 dialog
- **摘要列宽**：使用 `table-layout: fixed` 强制四列均分，标签列固定 80px

### 关联文档过期标记

以下文档内容与实际代码不符：
- `repo_memo/DESIGN_GUI.md` §3.6：描述 `localStorage.results` 读取、全局 `/api/pipeline/*` 端点、页面包含 `DatabaseSelector`，均已过期
- `repo_memo/DESIGN_REST_API.md`：restore 端点标注为"后续实现"，`BackupRequest` schema 含旧的 `mapping_result: dict` 字段
- `repo_memo/DESIGN_ORCHESTRATOR.md`：`backup()` 函数签名缺少 `dry_run` 参数，`restore()` 函数完全未出现

### backup_id 来源规则

#### appid（游戏本体，modid==0，走 basepath）

从 `steamapps/appmanifest_{appid}.acf` 获取：

1. 读取 `AppState.StateFlags`
2. 若 `StateFlags` 不在允许列表（当前 `{4}`，`4` = StateFullyInstalled）中 → **不稳定，跳过此 app 的备份**，记录警告
3. 若在允许列表中 → 读取 `AppState.buildid`
4. `backup_id` = `format(int(buildid), 'x')` （小写 hex ascii）
5. 备份根目录：`{basepath}/kmmbackup_{appid}_{backup_id}/`

#### contentid（Workshop MOD，走 modpath）

从 `steamapps/workshop/appworkshop_{appid}.acf` 获取，**每个 contentid 独立计算**：

1. 读取 `AppWorkshop.WorkshopItemsInstalled.{contentid}.timeupdated` → T_local
2. 读取 `AppWorkshop.WorkshopItemDetails.{contentid}.latest_timeupdated` → T_remote
3. 若 T_local ≥ T_remote → 稳定，`backup_id` = `format(int(T_remote), 'x')`
4. 若 T_local < T_remote → **不稳定，跳过此 contentid 的备份**，记录警告
5. 备份根目录：`{modpath}/{contentid}/kmmbackup_{contentid}_{backup_id}/`

#### 备份前缀（bakprefix）

**从 user_config 读取**，不使用硬编码默认值。`user_config.bakprefix` 写什么就用什么（包括 `_` 的数量），严格照抄。

#### 多库同名 contentid

不同 Steam 库中相同 `{appid}:{contentid}` 各自独立处理：
- lib1 的 `270150:2606099273` → 备份在 lib1 的 `workshop/content/270150/2606099273/` 下，T_remote 来自 lib1 的 ACF
- lib2 的 `270150:2606099273` → 备份在 lib2 的 `workshop/content/270150/2606099273/` 下，T_remote 来自 lib2 的 ACF
- 两者 backup_id 可能不同（安装状态不同步）

#### 文件映射

mapping 路径 `/.../workshop/content/270150/2606099273/some/path/fileA` → 备份写入 `{备份根目录}/some/path/fileA`（相对于 contentid 根目录的路径）
