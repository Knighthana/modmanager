# P1：Backup 实现 — 设计文档

创建：2026-05-06
状态：设计完成，待确认
来源：`work_memo/TODO.md` P1（B1-B7）
前置参考：`repo_memo/BACKUP_DIR_BUILDER_DESIGN.md`、`repo_memo/user_config.json.example`

---

## 0. 前置状态

| 已有能力 | 位置 | 状态 |
|----------|------|------|
| 差异备份执行 | `backup_ops.run_differential_backup()` | ✅ |
| 替换执行 | `backup_ops.apply_final_mapping()` | ✅ |
| 从备份恢复 | `backup_ops.restore_from_backup()` | ✅ |
| 备份门禁 | `backup_ops.check_backup_gate()` | ✅ |
| 备份目录生命周期 | `backup_ops.init_backup_dir()` / `finalize_backup_dir()` | ✅ |
| 脏数据/冲突检测 | `backup_ops.detect_dirty_state()` / `inspect_conflict()` | ✅ |
| game backup_id | `backup_ops.get_game_backup_id()` (common ACF LastUpdated) | ✅ |
| user_config 中的 bakprefix/bakignore 字段 | `user_config.json.example` | ✅ schema 有，无消费代码 |

## 1. 目标

补齐备份目录命名规则生成能力，将 `backup_dir` 路径的构造从调用方手工指定变为自动推导。同时补齐备份循环防护、workshop 时间源和 `.kmmbakignore` 支持。

## 2. 架构决策

### 2.1 模块位置

新增独立模块：**`src/modmanager/backup_dir_builder.py`**

理由：
- `backup_ops` 的契约是"只消费最终目录字符串"，不能污染
- `bootstrap` 负责环境初始化（config 发现、database 生成），与备份目录命名无关
- `orchestrator` 负责流水线调度，命名规则是独立关注点
- 独立模块便于测试、便于未来扩展（如自定义命名策略）

```
CLI / Web GUI
    │
    ├─ 调用 backup_dir_builder.build_backup_dir(...) → 得到 backup_dir 字符串
    │
    └─ 传给 orchestrator.run(..., backup_dir=backup_dir)
            │
            └─ 传给 backup_ops.run_differential_backup(backup_dir, ...)
```

### 2.2 builder 的职责边界

| 做什么 | 不做什么 |
|--------|---------|
| 从 database + final_mapping 推导目标 appid | 不修改 database |
| 读取 ACF 文件获取时间戳 | 不写文件 |
| 按命名规则拼接目录路径 | 不创建目录 |
| 返回最终的 backup_dir 字符串 | 不验证目录是否已存在 |
| 加载 user_config 的 bakprefix/bakignore | 不负责 user_config 三级搜索（由 bootstrap 提供路径） |

### 2.3 时间戳来源（扩展 B2）

| 来源类型 | 时间源 | ACF 文件 | 字段 | 实现 |
|----------|--------|----------|------|------|
| common（游戏本体） | appmanifest | `steamapps/appmanifest_{appid}.acf` | `LastUpdated` | 已有 `get_game_backup_id()` |
| workshop（已发布 mod） | appworkshop | `steamapps/appworkshop_{appid}.acf` | `timeupdated` | **新增** `get_workshop_backup_id()` |
| custom mod（本地 mod） | 文件 mtime | 无 ACF | 源目录最新 mtime | **新增** `get_custom_backup_id()` |

### 2.4 备份目录位置规则（B4）

| 目标文件所在区域 | backup_dir 位置 |
|-----------------|----------------|
| common 游戏目录下 | `<steamapps>/common/<GameName>/<bakprefix><appid>_<hex>/` |
| workshop mod 目录下 | `<steamapps>/workshop/content/<appid>/<contentid>/<bakprefix><contentid>_<hex>/` |
| 其他（custom path） | 源目录下 `<bakprefix>custom_<hex>/` |

**推断逻辑**：分析 `final_mapping` 中所有目标路径，判断它们落在哪个 Steam 库的哪个区域（common/workshop/other），以多数为准选择备份位置。

---

## 3. 核心函数设计

### 3.1 `build_backup_dir()`

```python
def build_backup_dir(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
) -> str:
    """根据 final_mapping 的内容自动推导 backup_dir 路径。

    推导逻辑：
    1. 加载 bakprefix（默认 "kmmbackup_"）
    2. 收集 final_mapping 中所有目标路径
    3. 对每个目标路径，在 database 中匹配其所属的 steamlib + game
    4. 判断目标路径属于 common 还是 workshop 区域
    5. 选择匹配数最多的 appid 作为主导 appid
    6. 根据区域选择对应的 backup_id（get_game_backup_id 或 get_workshop_backup_id）
    7. 按命名规则拼接最终路径

    Returns:
        备份目录的绝对路径字符串
    Raises:
        ValueError: 无法确定 appid 或 backup_id 时
    """
```

### 3.2 `get_workshop_backup_id()`

```python
def get_workshop_backup_id(steamapps_path: str, appid: str) -> str:
    """从 appworkshop_{appid}.acf 读取 timeupdated 字段并转为 hex。

    appworkshop ACF 结构：
      "WorkshopItemsInstalled" {
          "<appid>" {
              "timeupdated" "1234567890"
          }
      }

    若文件不存在或 timeupdated 缺失 → 返回 "0"。

    Returns:
        timeupdated 的小写 hex 字符串，或 "0"
    """
```

### 3.3 `get_custom_backup_id()`

```python
def get_custom_backup_id(source_paths: list[str]) -> str:
    """对自定义 mod（无 ACF），取所有源文件的最新 mtime 转为 hex。

    遍历 source_paths，取 max(mtime) → hex。
    若路径均为空或不存在 → 返回当前时间的 hex。

    Returns:
        mtime 的小写 hex 字符串
    """
```

### 3.4 `load_bakignore_rules()`

```python
def load_bakignore_rules(
    user_config: dict[str, Any],
    backup_dir: str,
) -> list[str]:
    """合并 user_config.bakignore 与 backup_dir 下的 .kmmbakignore 规则。

    1. 从 user_config 读取 bakignore 字段（list[str]），若不存在则默认 ["kmmbackup_"]
    2. 检查 backup_dir 下是否存在 .kmmbakignore 文件
    3. 若存在，逐行读取（忽略空行和 # 注释行），追加到规则列表
    4. 返回合并后的规则列表

    .kmmbakignore 语法（仿 .gitignore）：
      - 每行一个 glob 模式
      - # 开头的行为注释
      - 空行忽略
      - 支持 * 和 ** 通配符
    """
```

### 3.5 `.kmmbakignore` 示例

```
# kmm backup ignore rules
kmmbackup_*
*.log
__pycache__/
temp/
```

---

## 4. 循环备份防护（B7）

### 4.1 硬编码防护

在 `backup_ops.py` 的以下函数中加入硬编码的 `kmmbackup_` 前缀过滤：

| 函数 | 改动 |
|------|------|
| `_collect_backup_original_paths()` | 扫描备份目录内容时跳过 `kmmbackup_` 前缀的文件/目录 |
| `build_filefoldertree_with_hashes()` | 建树时跳过 `kmmbackup_` 前缀的目录 |
| `run_differential_backup()` | 备份文件时，若目标路径下存在 `kmmbackup_` 子目录则跳过 |

关键：即使 user_config 中没有 bakprefix/bakignore 配置，`kmmbackup_` 前缀也必须被硬编码跳过，防止备份过程把自己备份了。

### 4.2 实现方式

在 `backup_ops.py` 中新增常量：
```python
_HARDCODED_BACKUP_SKIP_PREFIX = "kmmbackup_"
```

在相关扫描/遍历循环中加入前缀检查。

---

## 5. 与现有流程的集成

### 5.1 CLI 集成

当前 CLI 的 backup/apply 命令要求用户手动指定 `--backup-dir`。改为可选参数：

```
modmanager-cli run --database db.json --rules rules/ --config user_config.json
    # backup_dir 自动推导

modmanager-cli run --database db.json --rules rules/ --config user_config.json --backup-dir /custom/path
    # 手动指定覆盖自动推导
```

### 5.2 Web API 集成

`POST /api/pipeline/run` 的 `backup_dir` 参数改为可选：
- 未提供 → 调用 `build_backup_dir()` 自动推导
- 已提供 → 使用提供的值

### 5.3 前端 ForestPage 集成

ForestPage 的 PipelineForm 中：
- "备份目录"输入框改为可选，placeholder 显示"自动推导"
- 若用户留空 → 发送请求时 `backup_dir` 为 `null`
- 若用户填写 → 发送指定值

---

## 6. 错误码与告警

| 码 | 含义 |
|----|------|
| `E_BACKUP_DIR_BUILD_NO_APPID` | 无法从 final_mapping 推断 appid |
| `E_BACKUP_DIR_BUILD_NO_TIMESTAMP` | 无法获取 backup_id（ACF 缺失且无 mtime） |
| `W_BACKUP_DIR_FALLBACK_CUSTOM` | workshop/common 时间源不可用，回退到 custom mtime |
| `W_BAKIGNORE_FILE_MISSING` | .kmmbakignore 文件不存在（非错误） |
| `W_BAKIGNORE_PARSE_ERROR` | .kmmbakignore 某行无法解析，已跳过 |

---

## 7. 测试策略

| # | 测试 | 说明 |
|---|------|------|
| T1 | `test_build_backup_dir_common` | common 游戏文件 → 正确命名 + 位置 |
| T2 | `test_build_backup_dir_workshop` | workshop mod 文件 → 正确命名 + 位置 |
| T3 | `test_get_workshop_backup_id_success` | 模拟 appworkshop ACF → 正确 hex |
| T4 | `test_get_workshop_backup_id_missing` | ACF 缺失 → 返回 "0" |
| T5 | `test_get_custom_backup_id_from_mtime` | 多个源文件 → 最新 mtime hex |
| T6 | `test_load_bakignore_from_config` | user_config 含 bakignore → 正确加载 |
| T7 | `test_load_bakignore_from_file` | .kmmbakignore 文件 → 正确解析 |
| T8 | `test_load_bakignore_combined` | config + 文件合并 |
| T9 | `test_backup_loop_protection_scan` | 扫描时跳过 kmmbackup_ 前缀目录 |
| T10 | `test_backup_loop_protection_tree` | 建树时跳过 kmmbackup_ 前缀目录 |
| T11 | `test_build_backup_dir_mixed_targets` | 目标跨多个 appid → 选主导 appid |
| T12 | `test_cli_auto_backup_dir` | CLI 不传 --backup-dir 时自动推导 |

---

## 8. 对现有代码的改动

| 模块 | 改动 |
|------|------|
| **新增** `backup_dir_builder.py` | 新增模块，约 150 行 |
| `backup_ops.py` | 增加 `_HARDCODED_BACKUP_SKIP_PREFIX` + 循环防护逻辑（3 处，约 20 行） |
| `acf_parser.py` | 新增 `get_workshop_timeupdated()` 辅助函数（约 15 行） |
| `orchestrator.py` | `run()` 中 backup_dir 参数改为可选（`str | None`），为 None 时自动调用 builder |
| `cli.py` | `--backup-dir` 参数改为可选 |
| `modmanager_web/schemas.py` | `RunRequest.backup_dir` 改为 `str | None` |
| `modmanager_web/routes/pipeline.py` | 若 backup_dir 为 None → 调用 builder |
| `frontend/src/types/index.ts` | `PipelineParams.backup_dir` 改为 `string | null` |
| `frontend/src/pages/ForestPage.vue` | 表单 backup_dir 字段改为可选 |
| `tests/` | 新增 `test_backup_dir_builder.py`（约 12 个测试） |

---

## 9. 任务分解

```
Step 1: acf_parser 扩展
  Task P1-01: 实现 get_workshop_timeupdated() 辅助函数
  Task P1-02: 测试

Step 2: backup_dir_builder 核心
  Task P1-03: 实现 get_workshop_backup_id()
  Task P1-04: 实现 get_custom_backup_id()
  Task P1-05: 实现 build_backup_dir()
  Task P1-06: 实现 load_bakignore_rules()
  Task P1-07: 核心函数单元测试

Step 3: 循环备份防护
  Task P1-08: backup_ops 硬编码 kmmbackup_ 前缀过滤
  Task P1-09: 防护测试

Step 4: 集成
  Task P1-10: orchestrator.run() backup_dir 可选化
  Task P1-11: CLI --backup-dir 可选化
  Task P1-12: Web API 适配
  Task P1-13: 前端适配
  Task P1-14: 集成测试

Step 5: 回归
  Task P1-15: Python 全量回归
  Task P1-16: 前端 Vitest + 构建
```

---

## 10. 验收标准

1. `build_backup_dir(final_mapping, database, user_config)` 对 common 和 workshop 目标均返回正确路径
2. workshop ACF 的 `timeupdated` → hex 正确
3. 自定义 mod 回退到 mtime，且 mtime hex 不为 "0"
4. `kmmbackup_` 前缀目录在扫描/建树/备份时被硬编码跳过
5. `.kmmbakignore` 规则正确加载并与 user_config.bakignore 合并
6. CLI 不传 `--backup-dir` 时自动推导成功
7. Web API backup_dir 为 null 时自动推导
8. 全量测试通过
