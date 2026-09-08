# 2026-09-08 全量文件操作 SPEC 审计

> 审计人：arch（agent）
> 任务：TASK2609-0x1（states.md）
> 方法：7 份设计文档（BACKUP_OPS / RESTORE_OPS / BACKUP_DIR / APPLY_OPS / PREFLIGHT_APPLY / PLANNER / KMMIGNORE_RULES / RULE_VALIDATION / PATH_CASE）vs 10 个实现文件逐条核对 + 可执行探针验证（/tmp/opencode/audit_probe.py，6 组探针）
> 结论分级：🔴 实现 bug（含测试固化错误行为）｜🟠 设计缺陷/缺口｜🟡 文档漂移｜⚪ 次要

---

## 🔴 S 级 — 实机翻车头号嫌疑（全部有探针实锤）

### A1 bakignore 自匹配 → 默认配置下备份静默空转

- 位置：`orchestrator/fileops/planner/planner.py` §3.5（L138-154）
- 机制：`dir_basename.endswith(suffix)` 对**本次派生的新 backup_dir**（必然以 `baksuffix` 结尾）自匹配。默认 `user_config`（`baksuffix="kmmbackup"`、`bakignore=["kmmbackup"]`）+ `userconfig_ops.py:145-151` 的 baksuffix↔bakignore 联动同步 → 条件恒真。
- 探针 1：默认配置 BACKUP → `ok=True, backed_up=[], skipped=[]`，磁盘无 backup_dir，**PipelineResult.warnings=[]（警告被吞，见 A2）**。
- 探针 2：去掉 bakignore 键后同一场景备份正常。
- **测试固化**：`tests/test_planner_fileops.py::test_backup_filters_matching_suffix` 把"全部过滤"断言为正确行为。
- 语义错位：`DESIGN_KMMIGNORE_RULES.md` §七规定 bakignore 的语义是"**屏蔽旧备份目录**"（系统自动维护、仅 backup 生效），正确落点应是过滤**旧备份目录内容进入 tree/scope**，而非删除本次目标 backup_dir。
- 修复方向（需裁决）：① 过滤对象改为文件列表与树扫描中位于"bakignore 后缀目录"内的路径；② 同步修 `test_planner_fileops.py`、`prep.py`（prep 目前硬编码跳过 `.kmmbackup` 带点后缀，与默认无点 baksuffix 不一致，见 B4）；③ `DESIGN_KMMIGNORE_RULES.md` §七 补充精确落点。

### A2 Planner 警告在管线层被整体吞掉

- 位置：`orchestrator/fileops/__init__.py`
  - `_execute_backup_plan` 返回 `warnings=[]`（L166）
  - `_execute_apply_plan` 接受 `plan_warnings` 参数但**不使用**，L198 为 `result["warnings"] + []`
  - `_execute_restore_plan` 返回 `warnings=[]`
- 后果：`W_BACKUP_DIR_BUILD_NO_MATCH`（目标路径没匹配到任何 game 条目）、`W_IGNORE_FILTERED`、`W_BAKIGNORE_FILTERED`、`W_PREFLIGHT_FAILED` 全部对 API 消费者不可见。用户看到 `ok=true` 但文件没动——与 `DESIGN_RULE_VALIDATION.md` §一 描述的历史痛点（"静默跳过，用户看到结果不对但不知道原因"）完全同构。
- 修复：`plan.warnings` 透传进 PipelineResult.warnings。

### A3 CLI restore 必然崩溃

- 位置：`cli.py::_handle_restore`（L326-409）+ `backup_dir_builder.py:176-177`
- 机制：CLI restore 传 `database={"game":[],...}` → `build_backup_dirs()` 对全部 target 无匹配 → `raise ValueError("E_BACKUP_DIR_BUILD_NO_APPID")` → `dispatch()` 不捕获 → CLI 恒显 "restore failed"。
- 探针 3：直接复现 crash。
- 根因：restore 的 backup_dir 推导不该依赖 database（`DESIGN_RESTORE_OPS.md` §三 的执行输入本就只有 mapping/backup_dir/backupinfo）。CLI 已知 backup_dir 却仍走 planner 的 database 推导路径。
- 修复方向（需裁决）：RESTORE intent 的 planner 分支直接消费请求携带的 backup_dir（跳过 build_backup_dirs），或 CLI restore 改为直调 `restore_entries`。

### A4 多 backup_dir 时 prep 重扫全部目录，违反 §7.2"不重建树"

- 位置：`planner.py` L91-102（needs_tree_build 是"任一目录缺树"的布尔）+ `fileops/__init__.py` L89-91（`if plan.needs_tree_build: for backup_dir in plan.backup_dirs: prep_backup_dir(...)`）
- 后果：任一目录首次备份时，**已有 tree 的目录被无条件重扫重写**：isbackuped 归零、文件重新拷贝、tree_created_time 重写。
- 探针 6：两 content 目录，round1 备份 modA，round2 增备 modA+modB → modA 的 a.txt 在 round2 重新出现在 backed_up（而非 skipped）→ 树被擦除重拷。
- 影响：已备份状态被周期性抹除（中断窗口内 restore 会报 W_RESTORE_INVALID_HASH 跳过）；大树场景 I/O 翻倍。
- 修复：needs_tree_build 改为 per-dir 集合语义，只 prep 缺 tree 的目录。

---

## 🟠 A 级 — 行为/语义分歧

### B1 restore 的 hash 计算无 I/O 防护（Windows 实机高危）

- `restore_ops.py::_sha256_hex`（L199-208）直接 `open()` 无 try；对照 `backup_ops.py::_sha256_file`（OSError → "0"）。
- Windows 文件被占用/权限问题 → 整个 restore 中断，违背"单条失败继续"的批处理精神。与用户 Windows/WSL2 实机环境直接相关。
- 修复：对齐 `_sha256_file` 的容错语义（或按 §5.2 记 error 后继续）。

### B2 mod 目录内的 `.kmmignore` 在生产路径完全不生效

- `planner.py::_derive_source_roots`（L199-206）只返回 `game["basepath"]`；mod 目标（`workshop/content/...`）的祖先目录不 startswith 任何 source root → `collect_rules(relevant_paths=...)` 对 mod 目录**零收集**（`ignore_rules.py` L62-72 的 while 循环直接不进入）。
- 只有 `relevant_paths` 为空的 fallback 分支（测试路径）才会全树遍历。
- 后果：mod 作者放在 mod 内的 `.kmmignore` 在真实管线中被静默忽略——"该忽略的没忽略"。
- 修复：`_derive_source_roots` 同时返回 basepath 与 modpath（或由 final_mapping 目标推导）。

### B3 bakignore 在 prep 树扫描中未按配置生效

- `prep.py:92` 硬编码 `child.name.endswith(".kmmbackup")`（带点）；默认 `baksuffix="kmmbackup"`（无点）→ 旧备份目录（`xxx.kmmbackup`）**会进入 tree**。自定义 baksuffix 时同样失控。
- 与 A1 是同一语义问题的两个破损面，应一并裁决 bakignore 落点。

### B4 dry-run 与实跑结果不一致（信任度问题）

- **backup dry_run 完全不消费 tree**（`backup_ops.py` L373-417 无 tree 检查）：实跑中 `isbackuped=true` 会跳过的文件，dry run 仍报告"将会备份"。
- apply dry_run：delete 不执行 `_assert_is_file`；replace/create 不验证 source 存在（L62-94）→ dry run 报 applied、实跑报 E_APPLY_MISSING_SOURCE。违反 `DESIGN_APPLY_OPS.md` §6.2"共享尽可能一致"。
- 修复：dry run 分支复用与实跑相同的判定链（仅跳过写盘）。

### B5 规则校验漏斗的两处精度/一致性问题

- `rule_validator.py` C4/C5 用子串 `".." in fp`（"a..b.txt" 误杀）；`path_normalizer.py` 用组件级 `entry.split("/")` 精确匹配——两层不一致。
- `path_normalizer.py`：from-dir 保留 glob 字符（L120），into-dir **不**保留（L137）→ into 含 glob 会被错误追加尾斜杠；`entry.endswith(".")` 的 "." 豁免同样匹配 "a." 之类的名字。
- `path_normalizer` 的 `ValueError("E_INVALID_TYPE")` 不在 TERMS；若漏斗被尊重（validator 先拒 "path"）则不可达——冗余但无害，建议降级为防御性注释或统一码表。

### B6 大小写专项裁决（TASK2609-0x1 重点）

- 事实链：`normalize_path()`（P0）已存在但**零调用方**；全系统使用 `normalize_posix`（仅 L1 风格归一化）。PATH_CASE P1（入口归一化）P2（比较点替换）P3（不变式验证）未做，I1-I4 无保障。
- 现存大小写敏感比较点：`build_backup_dirs` 的 `startswith`（L112/126）、`collect_rules` 的 root 前缀匹配（L67/107）、`should_ignore` 的 gitignore 匹配、`_relative_to_backup_root` 的 removeprefix。
- 现存防护：树查找 `.lower()`（backup_ops L683/707、restore_ops L174）——仅覆盖树内查找。
- **历史实机大小写故障与此直接相关**（规则 into 大小写与文件系统不一致 → 在 Linux 语义下产生独立路径）。
- 裁决建议：
  1. 大小写校验**位置**：维持 PATH_CASE §1.2"手写路径保持原样、作者负责"原则，但在 `verifier`（有 database 上下文）增加 **W 级警告**：规则 into/from 与 database 中实际路径大小写不匹配时提示作者——不改写、只警告，与"不自动归一化掩盖意图"的设计决策一致；
  2. P1（入口归一化）应从"待推进"提级为高优：WSL2/Windows 场景下它是 I1-I4 的前提；
  3. P2/P3 依赖 P1 完成，保持原排期。

---

## 🟡 B 级 — 文档漂移

### C1 错误码/警告码与 TERMS_ERROR_CODES.md 严重脱节

TERMS 仅 19 行。以下代码实际产生但未登记：`E_APPLY_NOT_FILE`、`E_APPLY_PERMISSION`、`E_APPLY_FAILED`、`E_APPLY_DIRECTORY_NOT_ALLOWED`、`E_RESTORE_DELETE_FAILED`、`E_RESTORE_PERMISSION`、`E_RESTORE_FAILED`、`W_RESTORE_NOT_BACKED_UP`、`W_RESTORE_INVALID_HASH`、`W_RESTORE_NO_BACKUP_COPY`、`W_BACKUP_DIR_BUILD_NO_MATCH`、`W_IGNORE_FILTERED`、`W_BAKIGNORE_FILTERED`、`W_PREFLIGHT_FAILED`、`W_PATH_TRAILING_SLASH_ADDED`、`E_BAD_INTENT`、`E_BACKUP_COPY_FAILED`（已登记）、`W_BACKUP_NODE_NOT_IN_TREE`（DESIGN_BACKUP_OPS §十二 列出但 TERMS 缺失）。

反向：`DESIGN_APPLY_OPS.md` §九 列出的 `E_APPLY_MISSING_TARGET`、`W_APPLY_DIR_NO_MATCHED_ENTRIES` 代码均未产生（空 target 实际落到 E_APPLY_MISSING_SOURCE，见 ⚪D1）。

### C2 DESIGN_PLANNER §六 解耦断言 vs 原语防御性 import

文档测试断言"原语不 import planner_fileops、preflight、ignore_rules"；`backup_ops.py:291/542` 两处防御性 import `planner.check_backup_gate`（注释称"Acceptable coupling per arch review"）。需裁决：改文档（承认二级防御门）或改代码。

### C3 kmmignore 跨文件否定语义未定义

`should_ignore` 实现"最深优先、首次匹配即胜"（ignore_rules.py L105-116）；gitignore 规范是"最后匹配胜"，跨文件 negation（父目录 `!keep` 被子目录规则压制）语义与文档 §四"子目录优先级更高"的粗粒度表述之间有未定义空间。建议文档补一条精确语义。

### C4 restore §5.1 "backup_dir 无法通过可恢复性检查 → 该目录整体跳过（warning）"

实现为 `E_BACKUP_INFO_MISSING`（error）+ 整目录跳过（restore_ops.py L56-58）。行为近似但级别与文档不符。

---

## ⚪ D 级 — 次要

- D1 `apply_ops._is_file_path("")` 返回 True（空串不以 `/` 结尾）→ 空 target 走到 `os.remove("")` → 错码误导为 E_APPLY_MISSING_SOURCE。
- D2 planner 分组（L107-112）中未匹配任何 backup_dir 的条目被静默丢弃（A2 透传修复后应补 per-entry warning）。
- D3 backup 逐文件全量回写 backupinfo.json（L480-486 在拷贝循环内）：大树 + DrvFs 上 O(N²) I/O。设计 §10.1"每次更新后写回"如此规定（为中断安全），可裁决折中：按批量/时间窗回写，中断时多备份幂等无害。
- D4 `run_differential_backup` 失败路径副作用：`dest.parent.mkdir` 先于 `_assert_is_file`（L464-465）→ 目录条目失败时在 backup_dir 内留下空目录。
- D5 CLI restore 把 tree 中 isbackuped=false 的文件也构造进 final_mapping（运行时靠 W_RESTORE_NOT_BACKED_UP 跳过，噪音）。

---

## ✅ 核对一致的关键断言（正面清单）

- backup §六.2/§十四：树上无结点 → `W_BACKUP_NODE_NOT_IN_TREE` + 跳过，不改树 ✓
- 树状态机不可逆约束（isbackuped/hashtype/hashvalue 单向）✓（`_update_tree_node` 三重守卫）
- prep 建树初始状态（isbackuped=False / invalid / "0"）与 backupinfo 五根字段、原子写 ✓
- 首次备份 = 建树 + 备份衔接（单目录场景）✓（探针 4）
- restore_entries §四 核心流程（删除/跳过/hash 比对/批量回拷）与 §六 force 语义 ✓
- preflight manifest 契约字段完整；restore preflight 仅查存在；空输入 trivially pass ✓
- check_backup_gate 位于 planner ✓；kmmignore 原地规则（无物理拷贝代码）✓
- 树查找 `.lower()` safety net 与 PATH_CASE §2.7 一致 ✓

---

## 建议的修复排期（待用户裁决）

1. **第一波（解除静默失败）**：A1 + A2 + B2 + B3（同一语义域：bakignore 落点重裁决 + 警告透传 + kmmignore 收集范围），同步修 `test_planner_fileops.py`；
2. **第二波（restore 可用性）**：A3 + A4 + B1；
3. **第三波（大小写）**：B6 裁决执行（verifier W 警告 + P1 提级）；
4. **第四波（文档对齐）**：C1-C4 + D 级随手修；
5. 之后进入 TASK2609-0x2（沙盒生命周期场景矩阵），期望值以本审计裁决后的行为为准。

---

## 裁决记录与执行结果（2026-09-08，与用户逐项确认）

| # | 裁决 | 执行 |
|---|------|------|
| 1 | bakignore 只作用于源内容侧（prep 扫描后缀排除 + planner 条目/文件列表过滤）；删除输出目录侧过滤；列表内容归自动联动机制，代码不做豁免（用户否决了"显式豁免目标目录"方案——会掩盖问题） | ✅ 第一波 |
| 2 | restore 显式优先：调用方提供 backup_dirs（CLI `--backup-dir`；Web 读工作区 `backup_dirs.json`），缺省回退"当前版本查询"推导 | ✅ 第二波 |
| 3 | 工作区=游戏+MOD 组合的规则容器（版本无关）；版本由 backup_dir 命名承载；推导=当前版本查询确立为明文；旧版本备份惰性保留 | ✅ 第二波文档 |
| 4 | 治理规则：文档只写执行语义；被否决的行为进 `repo_test` 作否定测试 | ✅ 全程执行 |
| 5 | 大小写：`W_PATH_CASE_MISMATCH` 只报告不改写、督促作者自行修正；P1 入口归一化提级但须先补 Windows 工作风格条款（见 DESIGN_PATH_CASE §七注记） | ✅ 第三波（P1 挂起待条款） |
| 6 | 版本绑定是设计预期（用户裁定）：跨版本恢复不可达是特性；选项 B（自动发现旧备份目录）被否决——恰会在版本更迭后把旧文件铺到新版本上 | ✅ 第二波负测试 |

**执行产出**（全部 646 tests pass，0 skip / 0 fail）：

- 代码：`planner.py`（bakignore 源侧重写 + modpath 收集 + per-dir prep + RESTORE 显式分组）、`prep.py`（bakignore 扫描排除）、`fileops/__init__.py`（警告透传 + RUN intent prep + backup_result 带 backup_dirs）、`data_port.py` / `resolver.py` / `workspacemanager.py`（backup_dirs 存取）、`restore_ops.py`（hash I/O 防护 + E_RESTORE_NOT_FILE 守卫）、`apply_ops.py`（空目标 + dry-run 保真 + 源类型区分）、`backup_ops.py`（dry-run 消费 tree + mkdir 顺序）、`engine.py`（`_probe_case_mismatch` + W_PATH_CASE_MISMATCH 两处接线）、`rule_validator.py`（组件级 `..`）、`path_normalizer.py`（into-dir glob/`.` 对称）、`cli.py`（restore 显式 backup_dirs + 缺失 import 修复 + asdict 输出修复 + isbackuped 过滤）、`modmgr_web/routes/workspace.py`（backup 路由 output_type）
- 测试：重写 `test_planner_fileops.py`（6）、新增 `test_restore_backupdir_contract.py`（8，含跨版本恢复被拒负测试）、新增 `test_case_mismatch_warning.py`（3）
- 文档：`DESIGN_KMMIGNORE_RULES.md` §七重写、`DESIGN_RESTORE_OPS.md` §三/§5、`DESIGN_BACKUP_DIR.md` §3.0、`DESIGN_WORKSPACE_MODEL.md` §3.4.1、`DESIGN_PLANNER.md` §六、`DESIGN_PATH_CASE.md` §2.0/§七、`TERMS_ERROR_CODES.md` 补登 20 码
- 挂起：P1 入口归一化（待 Windows 风格条款）；D3 逐文件回写性能（设计裁决项）；审计新发现 D6（RUN intent 无 prep）已随第二波修复
