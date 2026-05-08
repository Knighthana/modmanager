# Tasklist Archive — 已完成 Phase 归档

> 来源：repo_memo/TASKLIST.md（2026-05-08 拆分）
> 说明：已完成 Phase 的历史任务表，归档保存。当前 TODO 请参考 work_memo/states.md。

---

## M1 Core + Patches ✅
- 核心映射引擎（6 条规则 + 环检测 + 分枝）✅
- `def_destin`/`def_action` 继承移交聚合器 ✅
- sub 鉴权移交聚合器，移除 `validate_forest_roots` ✅
- 同 mod 内 actionlist 自动裁决（later wins）✅
- delete 叶折叠 ✅
- `provenance_ref` / `action_order` / `sidecar_ref` 在 changerequest 中传导 ✅

## 备份/替换/恢复（Phases 7–13）✅
- 差异备份、替换执行、从备份恢复 ✅
- 脏数据检测、冲突检查、orphan 治理 ✅

## 聚合器 ✅
- 完整聚合器实现（6 步流水线）✅
- 权限鉴权（game + sub）✅
- 多规则合并策略 ✅

## Forest 可视化 ✅
- ASCII / DOT / DOT→SVG / HTML standalone ✅

## Steam 发现与数据库 ✅
- 多库发现、CRUD、liveupdate/regen ✅

---

## Phase 1: Bootstrap & Orchestrator ✅

| 模块 | 文件 | 职责 |
|------|------|------|
| Bootstrap | `src/modmanager/bootstrap.py` ✅ | user_config 三级搜索+合并、Steam 数据库生成 |
| Orchestrator | `src/modmanager/orchestrator.py` ✅ | 流水线调度 |
| CLI 适配 | `src/modmanager/cli.py` ✅ | 编排逻辑迁移 |
| 测试 | `tests/test_bootstrap.py` ✅ (11 tests) | `tests/test_orchestrator.py` ✅ (7 tests) |

---

## Phase 2: Web API 层 ✅

| 模块 | 文件 | 职责 |
|------|------|------|
| Schemas | `src/modmanager_web/schemas.py` ✅ | Pydantic 模型 |
| Adapters | `src/modmanager_web/adapters.py` ✅ | PipelineResult → ApiResponse |
| SSE Bridge | `src/modmanager_web/sse.py` ✅ | 进度回调桥接 |
| Routes | `src/modmanager_web/routes/{config,database,pipeline}.py` ✅ | REST 端点 |
| App | `src/modmanager_web/app.py` ✅ | FastAPI 应用工厂 |
| 测试 | `tests/test_web_api.py` ✅ (15 tests) | |

---

## Phase 3: 前端 GUI ✅

| 模块 | 位置 | 职责 |
|------|------|------|
| Vue SPA | `frontend/` | Vue 3 + Vite + TypeScript + Element Plus + Pinia |
| M3 前置 | `forest_visual.py`（修改） | SVG 节点嵌入交互属性 |
| 静态挂载 | `app.py`（修改） | FastAPI StaticFiles + SPA fallback |

### 四个页面
| 页面 | 路由 | 职责 |
|------|------|------|
| ForestPage | `/forest` | 参数表单 + Forest SVG 展示 + SSE 进度 |
| ConflictsPage | `/conflicts` | 冲突列表 + 候选选择 + 重新计算 |
| RulesPage | `/rules` | kmm_rule 文件浏览 |
| BackupPage | `/backup` | 备份列表 + 恢复操作 |

---

## Phase P0: 森林模型重构 ✅

| # | 任务 | 模块 | 状态 |
|---|------|------|------|
| P0-01~P0-06 | ForestTree + 5 个新函数 | `engine.py` | done |
| P0-07~P0-10 | 新函数单元测试 | `test_engine.py` | done |
| P0-11~P0-13 | compute_mapping 重写 | `engine.py` | done |
| P0-14~P0-16 | 集成测试适配 | `tests/*` | done |
| P0-17~P0-19 | 下游模块适配 | orchestrator/Web API | done |
| P0-20~P0-25 | forest_visual 重写 | `forest_visual.py` | done |
| P0-26~P0-30 | 前端适配 | frontend/ | done |
| P0-31~P0-33 | 全量回归 | all | done |

---

## Phase P1: Backup 实现 ✅

| # | 任务 | 模块 | 状态 |
|---|------|------|------|
| P1-01~P1-02 | workshop timeupdated | `acf_parser.py` | done |
| P1-03~P1-07 | backup_dir_builder 核心 | `backup_dir_builder.py` | done |
| P1-08~P1-09 | 循环防护 | `backup_ops.py` | done |
| P1-10~P1-14 | 集成适配 | orchestrator/CLI/Web/前端 | done |
| P1-15~P1-16 | 回归 | all | done |

---

## Phase P4: GUI 缺口补齐 ✅

### G1: ConflictsPage 参数持久化
| # | 任务 | 状态 |
|---|------|------|
| G1-01~G1-05 | lastSuccessfulParams + 重新计算按钮 | done |

### G2: RulesPage 后端 API + 前端接入
| # | 任务 | 状态 |
|---|------|------|
| G2-01~G2-07 | scan/read API + RoutesPage 对接 | done |

### G3: BackupPage 后端 API + 前端接入
| # | 任务 | 状态 |
|---|------|------|
| G3-01~G3-09 | list/inspect/restore API + BackupPage 对接 | done |

### ForestStore 解耦修复
| # | 任务 | 状态 |
|---|------|------|
| B1-01~B1-04 | discoverDatabase 拆分 + loadConfig | done |

---

## Phase P5: 手动模式 + Fixture 集成 ✅

### M1: ForestPage 手动模式
| # | 任务 | 状态 |
|---|------|------|
| M1-01~M1-05 | discoveryMode + manualSteamPath + radio 切换 | done |

### M2: Fixture 生成器增强
| # | 任务 | 状态 |
|---|------|------|
| M2-01 | generate_fixture --with-db | done |

---

## Phase P6: 数据源独立选项卡 ✅

### 后端修复
| # | 任务 | 模块 | 状态 |
|---|------|------|------|
| B1 | manual_only 参数 | `database_ops.py` | done |
| B2 | 重复 appid 检测 | `database_ops.py` | done |
| B3 | manual_only 传递 | `bootstrap.py` | done |

### 前端重构
| # | 任务 | 状态 |
|---|------|------|
| F1~F8 | DataSourcePage + store + persistence + 路由 | done |

### 测试
| # | 任务 | 状态 |
|---|------|------|
| T1~T3 | 后端+前端测试扩展 | done |

---

## Phase P7: 通用路径解析模块 ✅

| # | 任务 | 模块 | 状态 |
|---|------|------|------|
| R1~R2 | resolve_directory_path / resolve_file_path | `path_resolver.py` | done |
| R3 | 单元测试 (18 tests) | `tests/test_path_resolver.py` | done |
| R4~R5 | DataSource 手动路径 + database/load 端点 | bootstrap + routes | done |

---

## Future（已完成部分）

### P2: 引擎细节修复 ✅
| # | 任务 | 状态 |
|---|------|------|
| T1 | same actionlist: delete→create 不警告 | done |
| E1 | 术语统一（结点/节点） | done |

### P3: GUI 增强 ✅
| # | 任务 | 状态 |
|---|------|------|
| GUI1 | Forest 全部/仅分岔切换 | done |
| GUI2 | M4 交互（hover高亮 + 点击选枝） | done |
