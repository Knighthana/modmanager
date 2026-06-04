# 2026-06-03 — 架构重构遗留事项与疑虑

> 来源：`work_memo/2026-06-01_TASK_arch_drift_review.md`（已归档至 `repo_logs/2026-06-03_ARCH_REVIEW_COMPLETE.md`）
> 状态：open
> 新设计：`work_memo/2026-06-03_PLAN_DATAPORT.md`
> 关联 commit：`b416391`

---

## 〇、已解决

| # | 原问题 | 解决方案 |
|---|--------|---------|
| C1a | CleanContext 单一dataclass 还是多形态？ | **废弃 CleanContext**。Resolver 产 `SourceDescriptor`（纯解析，无 I/O）。DataPort.fetch() 按 intent 返回不同 clean dict 集合 |
| C1b | workspace 回写放在哪一层？ | **DataPort.push()**——唯一 I/O 通道 |
| C1c | 出口解耦是否纳入本轮？ | **DataPort 本身就是出口解耦**。不同后端换 DataPort 实现 |
| A4 | compute_ws 绕过 dispatch | **废除 compute_ws**。全链路走 dispatch → Resolver → DataPort.fetch → Engine → DataPort.push |
| A5/c8 | Web 路由运行时门禁 | **不做运行时门禁**。依赖 W1 测试 |
| S1 | database_name 格式校验 | DataPort 中统一校验（`..` 等路径穿越） |
| **P1** | .kmmignore 原语工单化 | **选方案 B（原地规则）**。kmmignore 始终原地生效，不搬动。Planner 执行时现场读取，过滤结果写入 `FileOpsPlan.ignore_rule_set`。不再需要物理拷贝、不需要原语改造、不需要 tree 扩展 |
| P1/code | 遗留代码清理 | 删除 `_copy_kmmignore_to_backup/from_backup` 两个函数（`planner_fileops.py:209-248`）；删除 `_dispatch_fileops` 中 kmmignore copy 调用（`__init__.py:150-155`） |

---

## 一、已裁决待执行（本轮可出任务卡）

| # | 摘要 | 细节 |
|---|------|------|
| K1 | kmmignore 遗留代码清理 | 删除 `_copy_kmmignore_to_backup/from_backup` + `_dispatch_fileops` 中调用 |
| A1 | preflight → planner 子模块 | `orchestrator/preflight.py` → `orchestrator/fileops/planner/preflight.py` |
| A2 | dispatch_fileops 拆分 | `_dispatch_fileops` 的 plan→gate→execute 全链迁入 `fileops/__init__.py:execute()`；orchestrator `__init__.py` 只保留 `dispatch()` 路由 + Resolver/DataPort 调用 |
| A3 | fileops/ 目录创建 | `orchestrator/fileops/{__init__,planner,preflight,prep}.py`（backup/restore/apply 未来再迁） |
| **DataPort** | 新增 I/O 适配层 | 见 `work_memo/2026-06-03_PLAN_DATAPORT.md`。Resolver 重写为纯解析（产 `SourceDescriptor`），CleanContext 废弃，`data_port.py` 实现 `fetch()`/`push()` |
| **compute** | compute_ws 废除 | compute 全链路走 `dispatch → Resolver.resolve → DataPort.fetch → Engine.compute → DataPort.push` |
| W1 | Web 路由合规测试 | 新增 repo_test SPEC + 测试代码：扫描所有 Web 路由，断言 `resolver_type == "workspace"` |
| F1 | BackupPage 守卫 | `workspaceId` 为 `undefined` 时重定向到首页 |
| F2 | forest.ts 错误提示 | `computeOnly()` / `runPipeline()` 错误路径改为用户可见 |
| T2 | 前端端点迁移测试 | BackupPage.vue ×1 + forest.ts ×2 的端点 URL 迁移增加自动化测试 |

---

## 二、讨论历史（本轮关键裁决记录）

| 轮次 | 议题 | 裁决 |
|:---:|------|------|
| 1 | preflight 归属 | preflight 是 planner 的子模块，物理目录体现 |
| 2 | compute_ws | 废除。全链路走 dispatch |
| 3 | Planner 与文件操作 | Planner 只决策不下场。kmmignore 加入原语工单 |
| 4 | Web 路由门禁 | 半审查 + 半测试。不加运行时断言 |
| 5 | dispatch_fileops | 方案B——`fileops/__init__.py:execute()` |
| 6 | I/O 边界 | DataPort：Resolver 纯解析，DataPort 唯一 I/O |
| 7 | CleanContext | 废弃，SourceDescriptor + fetch dict 取代 |
| **8** | **kmmignore 体验模型** | **方案 B — 原地规则。kmmignore 始终原地生效不搬动。两个状态不需版本追踪** |

---

## 三、P2（本轮可做）

| # | 摘要 |
|---|------|
| D1 | `DESIGN_PLANNER.md` 补全（输入/输出契约、错误码映射） |
| T1 | `path_normalizer` 独立测试 |
| T3 | e2e backup→restore（含 .kmmignore 完整链路） |
| U1 | `test_backup_tree.py::test_node_not_in_tree_produces_warning` 修复 |

---

## 四、P3（低优先）

| # | 摘要 |
|---|------|
| U2 | `tools/generate_fixture.py` 缺少 `config_index` 参数 |
| U3 | `test_rule_aggregator.py` LSP 类型噪音（None subscriptable ×27） |
| D2 | 旧 `repo_test/kmmignore_copy.md` 清理 |
| D3 | `READING_PACKAGES.md` 更新 |
| F3 | 存储键 `modmanager:` → `modmgr:` 旧数据失效 |
| S2 | `PipelineResult.backup_dir` CLI 消费者确认 |

---

## 五、汇总

| 状态 | 数量 | 内容 |
|:---:|:---:|------|
| ✅ 已解决 | 8 | C1a / C1b / C1c / A4 / A5(web) / S1 / P1 / K1 |
| 🟡 已裁决待执行 | 10 | K1 / A1 / A2 / A3 / DataPort / compute / W1 / F1 / F2 / T2 |
| 🟢 P2 | 4 | D1 / T1 / T3 / U1 |
| ⚪ P3 | 6 | U2 / U3 / D2 / D3 / F3 / S2 |
