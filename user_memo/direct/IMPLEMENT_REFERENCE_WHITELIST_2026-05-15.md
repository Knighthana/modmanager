# Implement 参考白名单（2026-05-15）

> Status: active
> Authority: user-guidance
> Purpose: 给 implement 提供 direct 目录的可参考范围，避免读取已判定冲突文档

## 使用规则
- direct 仅作为用户需求与实施提示，非实现权威。
- 实现契约始终以 repo_memo 为准。
- 若 direct 与 repo_memo 冲突：立即以 repo_memo 覆盖，并将 direct 视为历史记录。

## 可直接参考（C 类）
- GUI_MANAGEMENT_PLAYBOOK_2026-05-15.md
- GUI_STABILIZATION_IMPLEMENT_PLAN_2026-05-15.md
- MIGRATE-svg-pan-zoom.md
- ENHANCE-minimap-and-reset.md
- HOTFIX-path-trailing-slash-and-managed.md
- HOTFIX2-managed-frontend-sync.md
- HOTFIX3-managed-semantics-closure.md
- HOTFIX4-v2-duplicate-cleanup-and-svg-height.md

## 可参考但需先对齐契约（B 类）
- PHASE1-data-layer-fixes.md
- PHASE2-api-layer-fixes.md
- PHASE4-auto-restore-and-cache-fix.md
- PHASE5-workspace-aggregation.md
- TODO-15-step1-svg-fit-viewport.md

对齐检查清单：
1. compute/run 参数口径是否为 aggregated_rule_set。
2. 是否保持 Forest 只展示、ComputePrep 触发计算。
3. localStorage 是否保持单键 modmanager:workspace。
4. 是否引入了 repo_memo 未冻结的新 REST 端点。

## 已归档，不得作为实现依据（A 类 + superseded）
已移动到 user_memo/archive/2026-05-15_contract_cleanup/：
- TODO-22-migrate-fields.md
- TODO-20-decoupling-review.md
- PHASE3-frontend-fixes.md
- REFACTOR-database-path-and-workspace-cleanup.md
- DOCFIX-v2-plan-b-documents.md
- DOCFIX-document-responsibility-cleanup.md
- HOTFIX4-duplicate-cleanup-and-svg-height.md

## 交接指令（给 implement）
- 读取顺序：repo_memo -> 此白名单 -> 具体 direct 文档。
- 开工前先确认 repo_memo/DOCUMENT_GOVERNANCE.md 与 repo_memo/DESIGN_GUI_WORKSPACE.md。
- 遇到新需求先写对齐裁决，再改代码。
