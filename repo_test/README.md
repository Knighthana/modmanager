# 测试基础设施

> Status: evolving
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 规定测试文件组织、pytest 配置、前后端测试约定
> Last-Updated: 2026-05-19

---

## 一、测试文件布局

```
tests/                    # Python 后端测试（pytest）
  test_*.py               # 命名强制 test_ 前缀，由 pytest 收集
frontend/src/__tests__/   # TypeScript 前端测试（Vitest）
  **/*.test.ts            # 命名强制 .test.ts 后缀
tools/                    # 工具脚本
```

## 二、pytest 配置

`pyproject.toml` 中必须配置 `testpaths` 以限制收集范围：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

否则 pytest 从项目根递归扫描，可能误收集 `tools/` 下命名的脚本。

## 三、当前测试覆盖

### Python 后端 — 19 个文件

| 文件 | 覆盖范围 |
|------|---------|
| `test_backup_dir_builder.py` | 备份目录推导、suffix 生成、自定义 ID |
| `test_backup_ops.py` | 差异备份、应用映射、恢复、循环防护、脏状态 |
| `test_bootstrap.py` | user_config 发现、数据库生成 |
| `test_cli_database_ops.py` | CLI 数据库操作 |
| `test_contract.py` | 接口契约 |
| `test_database_ops.py` | 数据库读写 |
| `test_engine.py` | 映射计算引擎 |
| `test_forest_visual.py` | Forest SVG 可视化 |
| `test_integration_fixtures.py` | Fixture 集成 |
| `test_iojson.py` | JSON 文件读写 |
| `test_orchestrator.py` | 流水线调度（引擎函数） |
| `test_orchestrator_engine.py` | 引擎函数 dry_run、bakignore、build_backup_dirs |
| `test_path_resolver.py` | 路径解析 |
| `test_paths.py` | 路径工具 |
| `test_pathstyle.py` | 路径风格 |
| `test_rule_aggregator.py` | 规则聚合 |
| `test_steam_scanner.py` | Steam 库扫描 |
| `test_validation.py` | 输入校验 |
| `test_web_api.py` | Web API 端点 |

### TypeScript 前端 — 14 个文件

| 文件 | 覆盖范围 |
|------|---------|
| `api/sse.test.ts` | SSE 传输层 |
| `components/ForestViewer.test.ts` | Forest 查看器组件 |
| `pages/AdvancedPage.test.ts` | 进阶用户页面 |
| `pages/BackupPage.test.ts` | 备份管理页面 |
| `pages/ComputePrepPage.test.ts` | 计算准备页面 |
| `pages/ConflictsPage.test.ts` | 冲突裁决页面 |
| `pages/DataSourcePage.test.ts` | 数据来源页面 |
| `pages/ForestPage.test.ts` | Forest 页面 |
| `pages/RulesOverviewPage.test.ts` | 规则概览页面 |
| `pages/RulesPage.test.ts` | 规则管理页面 |
| `pages/SettingsPage.test.ts` | 设置页面 |
| `stores/datasource.test.ts` | 数据源 store |
| `stores/forest.test.ts` | Forest store |
| `App.test.ts` | 应用入口 |

## 四、测试约定

1. Python 测试文件命名 `test_*.py`，放 `tests/` 下
2. 前端测试文件命名 `*.test.ts`，放 `frontend/src/__tests__/` 下
3. `pyproject.toml` 必须配 `testpaths = ["tests"]`
4. 新增引擎函数必须同步添加测试
5. backupinfo 正例结构、backup_dir 结构与 restore 主路径正例，优先以 [backupinfo_expectations.md](backupinfo_expectations.md) 为准
