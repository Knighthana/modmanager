# database_ops_promotion — database_ops 提升为一等成员

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 裁定 7 的测试断言 — 验证 `generate_database` 从 bootstrap 迁移到 `database_ops`
> 依据: `DESIGN_DATABASE_OPS.md`、`DESIGN_BOOTSTRAP.md`、`work_memo/2026-06-01_TASK_arch_drift_review.md` 裁定 7

---

## 一、适用范围

| 源文档 | 迁移内容 | 测试期望 |
|--------|---------|---------|
| `DESIGN_BOOTSTRAP.md` | bootstrap 不再持有 `generate_database` | bootstrap 模块中该符号不可 import |
| `DESIGN_DATABASE_OPS.md` | `database_ops` 升为 orchestrator 一等成员，承担 `generate_database()` | `database_ops.generate_database()` 存在且功能完整 |

---

## 二、黑箱测试断言

### 2.1 bootstrap 边界

| # | 断言 | 级别 |
|---|------|:---:|
| T-DB-01 | `from modmgr.bootstrap import generate_database` → `ImportError` | MUST |
| T-DB-02 | `bootstrap.__all__` 不含 `"generate_database"` | MUST |
| T-DB-03 | `bootstrap.discover_user_config()` 仍可正常调用（不受迁移影响） | MUST |

### 2.2 database_ops 新职责

| # | 断言 | 级别 |
|---|------|:---:|
| T-DB-04 | `from modmgr.database_ops import generate_database` → 成功 | MUST |
| T-DB-05 | `database_ops.__all__` 含 `"generate_database"` | MUST |
| T-DB-06 | `generate_database(mode="auto", config_index=..., working_pathstyle="linux")` 返回 dict 且含 `OS`, `steamlib`, `game`, `mod` 四键 | MUST |
| T-DB-07 | `generate_database()` 产出写入 `user_config.databases[name].path` 指定位置（通过 mode/greedy_parsing 参数控制） | MUST |
| T-DB-08 | `generate_database()` 支持 `on_progress` 回调透传 | MUST |

### 2.3 Web 路由适配

| # | 断言 | 级别 |
|---|------|:---:|
| T-DB-09 | `POST /api/database/generate` 调用链不经过 `bootstrap.generate_database` | MUST |
| T-DB-10 | `POST /api/database/generate` 调用链通过 `database_ops.generate_database` 完成 | MUST |

### 2.4 文档一致性

| # | 断言 | 级别 |
|---|------|:---:|
| T-DB-11 | `DESIGN_BOOTSTRAP.md` 全文不出现 `generate_database` | MUST |
| T-DB-12 | `DESIGN_DATABASE_OPS.md` 中明确 `generate_database()` 为本模块公开 API | MUST |

---

## 三、repo_memo 负面描述迁移记录

以下描述已从 `DESIGN_BOOTSTRAP.md` 移除（已无需该函数，bootstrap 职责边界不含 database 生成）：

| 原位置 | 内容 | 迁移后 |
|--------|------|--------|
| `DESIGN_BOOTSTRAP.md §一` | 原含 bootstrap 调用链（含 database 生成步骤） | 已修正为仅 resolve+verify 流程 |
| 隐式引用 | bootstrap 作为 database 生成入口 | 入口改为 `DESIGN_DATABASE_OPS.md` 描述的 `database_ops.generate_database()` |

---

## 四、验收标准

- [ ] 全部 T-DB-01 ~ T-DB-12 通过
- [ ] 现有测试（`test_bootstrap.py`、`test_database_ops.py`、`test_web_api.py`）不受影响（可能需要适配测试导入路径）
- [ ] `POST /api/database/generate` 功能不变（SSE 流正常，输出格式不变）
