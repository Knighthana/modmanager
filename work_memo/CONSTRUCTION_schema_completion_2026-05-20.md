# 施工计划：Schema 补全与字段统一

> 创建：2026-05-20 by arch
> 状态：completed
> 目标：补全 repo_spec/ 全部缺失 schema，将 schema_namespace + schema_version 落地到所有持久化 JSON 产出

## 原则

- **就地修改**，不「删旧建新」——所有既有结构仅追加字段
- `repo_memo/` 设计文档为权威
- 持久化数据组 schema 强制 `schema_namespace` + `schema_version`
- 瞬态通信组 schema 不嵌入 namespace/version 数据字段
- 文档级 `version` 统一为 `"knighthana@0.1.0"`

## 阶段 A：schema 层

### A1. 新增 9 个 schema

| 文件 | 组别 | schema_namespace |
|------|:---:|---|
| `api_response.schema.json` | 瞬态 | — |
| `workspace_meta.schema.json` | 持久化 | `KMM_WorkspaceMeta` |
| `workspace_decisions.schema.json` | 持久化 | `KMM_WorkspaceDecisions` |
| `workspace_fingerprints.schema.json` | 持久化 | `KMM_WorkspaceFingerprints` |
| `apply_result.schema.json` | 瞬态 | — |
| `backup_result.schema.json` | 瞬态 | — |
| `restore_result.schema.json` | 瞬态 | — |
| `preflight_manifest.schema.json` | 瞬态 | — |
| `affected_entries.schema.json` | 瞬态 | — |

### A2. 修改既有 10 个 schema

| 文件 | 改动 |
|------|------|
| `database.schema.json` | required 增加 `schema_namespace`、`schema_version`；加对应 properties；加文档 version |
| `user_config.schema.json` | required 改为 `["schema_namespace", "schema_version"]`；加 `workspace_dir`；加文档 version |
| `backupinfo.schema.json` | required 增加 `schema_namespace`；加对应 property；加文档 version |
| `sse_event.schema.json` | 方案 B：object 包装 + version，oneOf 移入 $defs |
| `aggregated_rule_set.schema.json` | 加文档 version |
| `kmm_rule.schema.json` | 加文档 version |
| `dry_run_output.schema.json` | 加文档 version |
| `mapping_output.schema.json` | 加文档 version |
| `branch_decisions.schema.json` | 加文档 version |
| `resource_whitelist.json` | 加文档 version |

## 阶段 B：实现层——6 处 Python 代码追加字段

| 文件 | 产出 | 追加 |
|------|------|------|
| `database_ops.py` L191-199 | `database.json` | `schema_namespace: "KMM_Database"`, `schema_version: "knighthana@0.1.0"` |
| `bootstrap.py` L127-135 | `user_config.json` | `schema_namespace: "KMM_UserConfig"`, `schema_version: "knighthana@0.1.0"` |
| `backup_ops.py` L254, L264 | `backupinfo.json` | `schema_namespace: "KMM_BackupInfo"`；`schema_version` 改为 `"knighthana@0.1.0"` |
| `workspacemanager.py` L69-76 | `meta.json` | `schema_namespace: "KMM_WorkspaceMeta"`, `schema_version: "knighthana@0.1.0"` |
| `routes/workspace.py` L106-110 | `decisions.json` | `schema_namespace: "KMM_WorkspaceDecisions"`, `schema_version: "knighthana@0.1.0"` |
| `orchestrator.py` L833-838 | `fingerprints.json` | `schema_namespace: "KMM_WorkspaceFingerprints"`, `schema_version: "knighthana@0.1.0"` |

## 阶段 C：文档清理——4 个设计文档检查

| 文档 | 检查要点 |
|------|---------|
| `DESIGN_STORAGE.md` §3.5 | user_config 字段表是否需要增加 namespace/version 的说明 |
| `DESIGN_BACKUP_DIR.md` | backupinfo 结构描述是否遗漏 `schema_namespace` |
| `DESIGN_WORKSPACE_MODEL.md` §3.4 | meta/decisions/fingerprints 示例是否缺少 namespace/version |
| `DESIGN_REST_API.md` | ApiResponse 描述是否与新 schema 一致 |

## 实现顺序

1. 阶段 A — 新增 9 schema + 修改 10 既有 schema
2. 阶段 B — 修改 6 处 Python 代码
3. 阶段 C — 检查并修正 4 个设计文档
4. arch 终验
