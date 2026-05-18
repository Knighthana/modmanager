# 2026-05-18 文件操作页面工作区适配与引擎重构

## 概述

本场对 OperationsPage（文件操作页面）进行了全面改造以适配工作区模型，同时重构了 orchestrator 引擎函数架构、backup 目录命名规则、bakignore 忽略体系。

## 核心改动

### 1. 文件操作页面工作区适配
- 移除 `DatabaseSelector`，改为从路由提取 `workspaceId` 绑定工作区
- SSE 调用从全局 `/pipeline/*` 迁移到工作区端点 `/workspace/{id}/pipeline/*`
- 映射数据从工作区 API 加载（`GET /workspace/{id}/forest/mapping`）
- 新增加载态 / 错误态 / 空态三分支
- 摘要卡片重构：移除"树总数"，新增"操作警告/操作错误"，统计值从 `final_mapping[].request.action` 计算
- 警告/错误可点击查看详情，零值不弹气泡
- dry_run 覆盖三种操作，结果以持久文件列表表格展示

### 2. 引擎 / 工作区函数职责分离
- 引擎函数统一签名 `(final_mapping, database, user_config, flags, on_progress)`，内部调 `build_backup_dirs`
- `_ws` 函数退化为翻译工作区语境 → 委托引擎
- 新增 `restore()` 独立引擎原语（force 标志控制 HASH 比对）
- `apply()` gate check 改为 per-backup_dir FIFO，互不阻塞

### 3. backup 目录命名规则重订
- `bakprefix` → `baksuffix`，目录格式 `{id}.{hex}.{baksuffix}/`
- `backup_id` 来源：
  - app：`appmanifest_{appid}.acf` → `StateFlags ∈ {4}` → `buildid` → hex
  - contentid：`appworkshop_{appid}.acf` → T_local vs T_remote 比较 → T_remote → hex
- 每个 contentid 独立备份，path prefix 匹配决定归属

### 4. bakignore 三级忽略体系
- 硬编码底线 `.kmmbackup`（引擎内部始终生效）
- `user_config.bakignore` 目录名后缀列表
- `.kmmbakignore` 文件级 gitignore 模式（git 级联 + `gitignore-parser` 解析）
- backup 时 .kmmbakignore 拷入 backup_dir，apply 时反向拷出

### 5. dry_run 输出格式规范化
- backup：`{action:"copy", path, backup_path, size, mtime, is_dir}`
- apply：`{action, source, target, size, mtime, is_dir}`
- `backup_path` 格式 `{dir_basename}/{rel}`，含目录名前缀
- 前端表格：操作 / 类型 / 备份位置 / 源路径 / 大小 / 修改时间

### 6. 文档与测试
- `DESIGN_BACKUP.md` 全面重写
- `DESIGN_ORCHESTRATOR.md` 引擎/_ws 签名同步
- `DESIGN_GUI.md` §3.6 更新为工作区模式
- `user_config.schema.json` 字段更新
- 全项目 `bakprefix`/`kmmbackup_` → `baksuffix`/`.kmmbackup` 清理
- 403 个测试全部通过

## 施工文件

| 文件 | 说明 |
|------|------|
| `2026-05-18_PLAN_operations_workspace_adapt.md` | 文件操作页面改造方案 |
| `2026-05-18_PLAN_dry_run_output_spec.md` | dry_run 输出字段规范 |
| `2026-05-18_PLAN_engine_ws_separation.md` | 引擎/_ws 职责分离 |
| `2026-05-18_PLAN_bakignore_integration.md` | bakignore 接入引擎 |
| `2026-05-18_SNAPSHOT.md` | 全量已完成 / 悬空问题 / 架构决策 / 提交记录 |

## 背景文档

Steam 时间戳获取机制 → `repo_bkgd/MOD统一的TimeStamp如何拿到.md`

## 提交记录

```
26ba4ed docs: finalize SNAPSHOT
0f33cc1 docs: backup_path description — include dir basename prefix
8b9d5fe fix: backup_path includes dir basename prefix
c83e970 fix: backup_path relative to content_root
8d4e0bd fix: add missing 冲突裁决 grayed-out item
4aab9b0 test: fix all 403 tests
38b99b3 fix: gitignore-parser API + cascade logic
e6ac663 docs: sync DESIGN_ORCHESTRATOR + DESIGN_BACKUP §6
a97cfc6 feat: bakignore integration
22ba7d2 docs: bakignore integration plan
088bb0f docs: update SNAPSHOT
3bc0869 feat: engine/_ws separation
ae9461b refactor: bakprefix → baksuffix
7940c8c docs: session snapshot
a6e7e7b fix: per-backup_dir gate check in apply_ws
7e6416b fix: directory paths in dry_run must end with /
7d31579 feat: dry_run output spec
3102c17 docs: update backup design
7650b7d feat: per-contentid backup dirs, stability checks, workspace-aware OperationsPage
```
