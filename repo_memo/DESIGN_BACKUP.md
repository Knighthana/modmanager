# DESIGN_BACKUP — Backup 实现设计

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 backup_dir 推导、备份恢复流程与 backup 子系统的职责边界

> 来源：DESIGN_P1_BACKUP.md + BACKUP_DIR_BUILDER_DESIGN.md（合并）
> 实现状态：已落地并持续生效

---

## 一、Backup Dir Builder 概览（BACKUP_DIR_BUILDER_DESIGN.md）

### 目标
将备份目录字符串生成过程与 `backup_ops` 解耦。

### 设计原则
- `backup_ops` 只消费目录字符串并做合法性/完整性检查。
- builder 负责命名规则、id 查找、时间转换、路径拼装。

### 输入
- `bakprefix`（默认建议 `kmmbackup_`）
- 标识来源（appid/contentid/custom_id）
- 更新时间（可转 hex）
- 可选 base path

### 输出
- 最终目录字符串（可绝对路径或相对路径）

### 处理流程
1. 解析配置与标识选择。
2. 查询 id。
3. 获取更新时间并转换为 `updatetimehex`。
4. 按 `{prefix}{id}_{updatetimehex}` 拼接名称。
5. 结合可选 base path 形成最终目录字符串。

### bakignore 接入点
- 由编排层/扫描层使用 `bakignore` 过滤路径。
- builder 不承担扫描，只提供命名产物。

### 错误处理
- id 缺失、时间转换失败、路径非法时返回结构化错误。
- 不在 builder 内做文件系统写操作。

### 时间戳来源

| 来源类型 | 时间源 | 说明 |
|----------|--------|------|
| common（游戏本体目录） | `appmanifest_{appid}.acf` → `LastUpdated` → hex | 已实现 `get_game_backup_id()` |
| workshop（已发布 mod） | `appworkshop_{appid}.acf` → `timeupdated` → hex | 已实现 ✅ |
| custom mod（本地 mod） | 文件 mtime（fallback） | 长期计划：kmm 标准自述文件 |

### 备份目录位置

| 类型 | 位置 |
|------|------|
| common 中的文件 | `<steamapps>/common/<GameName>/kmmbackup_{appid}_{updatetimehex}/` |
| workshop 中的文件 | `<steamapps>/workshop/content/<appid>/<contentid>/kmmbackup_{contentid}_{updatetimehex}/` |

### user_config 配置项
- `bakprefix`：备份目录名前缀（默认 `kmmbackup_`）
- `bakignore`：备份/恢复扫描时忽略的路径/通配规则集合

### 硬编码防护
- `backup_ops` 内部硬编码始终忽略 `kmmbackup_` 前缀的目录（即使 user_config 缺失）
- 备份目录下检测 `.kmmbakignore` 文件（仿 `.gitignore` 语法）作为额外的忽略规则

---

## 二、详细实现方案（DESIGN_P1_BACKUP.md）

### 前置状态

| 已有能力 | 位置 | 状态 |
|----------|------|------|
| 差异备份执行 | `backup_ops.run_differential_backup()` | ✅ |
| 替换执行 | `backup_ops.apply_final_mapping()` | ✅ |
| 从备份恢复 | `backup_ops.restore_from_backup()` | ✅ |
| 备份门禁 | `backup_ops.check_backup_gate()` | ✅ |
| 备份目录生命周期 | `backup_ops.init_backup_dir()` / `finalize_backup_dir()` | ✅ |
| 脏数据/冲突检测 | `backup_ops.detect_dirty_state()` / `inspect_conflict()` | ✅ |
| game backup_id | `backup_ops.get_game_backup_id()` (common ACF LastUpdated) | ✅ |

### 架构决策

#### 模块位置

新增独立模块：**`src/modmanager/backup_dir_builder.py`**

```
CLI / Web GUI
    │
    ├─ 调用 backup_dir_builder.build_backup_dir(...) → 得到 backup_dir 字符串
    │
    └─ 传给 orchestrator.run(..., backup_dir=backup_dir)
            │
            └─ 传给 backup_ops.run_differential_backup(backup_dir, ...)
```

#### builder 的职责边界

| 做什么 | 不做什么 |
|--------|---------|
| 从 database + final_mapping 推导目标 appid | 不修改 database |
| 读取 ACF 文件获取时间戳 | 不写文件 |
| 按命名规则拼接目录路径 | 不创建目录 |
| 返回最终的 backup_dir 字符串 | 不验证目录是否已存在 |
| 加载 user_config 的 bakprefix/bakignore | 不负责 user_config 三级搜索 |

#### 时间戳来源（扩展 B2）

| 来源类型 | 时间源 | ACF 文件 | 字段 | 实现 |
|----------|--------|----------|------|------|
| common（游戏本体） | appmanifest | `steamapps/appmanifest_{appid}.acf` | `LastUpdated` | `get_game_backup_id()` ✅ |
| workshop（已发布 mod） | appworkshop | `steamapps/appworkshop_{appid}.acf` | `timeupdated` | `get_workshop_backup_id()` ✅ |
| custom mod（本地 mod） | 文件 mtime | 无 ACF | 源目录最新 mtime | `get_custom_backup_id()` ✅ |

#### 备份目录位置规则（B4）

| 目标文件所在区域 | backup_dir 位置 |
|-----------------|----------------|
| common 游戏目录下 | `<steamapps>/common/<GameName>/<bakprefix><appid>_<hex>/` |
| workshop mod 目录下 | `<steamapps>/workshop/content/<appid>/<contentid>/<bakprefix><contentid>_<hex>/` |
| 其他（custom path） | 源目录下 `<bakprefix>custom_<hex>/` |

**推断逻辑**：分析 `final_mapping` 中所有目标路径，判断它们落在哪个 Steam 库的哪个区域（common/workshop/other），以多数为准选择备份位置。

### 核心函数设计

#### `build_backup_dir()`

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
    3. 对每个目标路径，在 database 中匹配所属的 steamlib + game
    4. 判断目标路径属于 common 还是 workshop 区域
    5. 选择匹配数最多的 appid 作为主导 appid
    6. 根据区域选择对应的 backup_id
    7. 按命名规则拼接最终路径
    """
```

#### `get_workshop_backup_id()`

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
    """
```

#### `get_custom_backup_id()`

```python
def get_custom_backup_id(source_paths: list[str]) -> str:
    """对自定义 mod（无 ACF），取所有源文件的最新 mtime 转为 hex。
    
    遍历 source_paths，取 max(mtime) → hex。
    若路径均为空或不存在 → 返回当前时间的 hex。
    """
```

#### `load_bakignore_rules()`

```python
def load_bakignore_rules(
    user_config: dict[str, Any],
    backup_dir: str,
) -> list[str]:
    """合并 user_config.bakignore 与 backup_dir 下的 .kmmbakignore 规则。
    
    1. 从 user_config 读取 bakignore 字段，默认 ["kmmbackup_"]
    2. 检查 backup_dir 下是否存在 .kmmbakignore 文件
    3. 若存在，逐行读取（忽略空行和 # 注释行）
    4. 返回合并后的规则列表
    """
```

### 循环备份防护（B7）

硬编码防护：在 `backup_ops.py` 中加入 `kmmbackup_` 前缀过滤。

```python
_HARDCODED_BACKUP_SKIP_PREFIX = "kmmbackup_"
```

涉及函数：
- `_collect_backup_original_paths()` — 扫描时跳过 `kmmbackup_` 前缀
- `build_filefoldertree_with_hashes()` — 建树时跳过
- `run_differential_backup()` — 备份时跳过

### 与现有流程的集成

- **CLI**：`--backup-dir` 改为可选参数，未指定时自动推导
- **Web API**：`POST /api/pipeline/run` 的 `backup_dir` 参数改为可选
- **前端**：ForestPage 的 PipelineForm 中 "备份目录" 输入框改为可选

### 错误码与告警

| 码 | 含义 |
|----|------|
| `E_BACKUP_DIR_BUILD_NO_APPID` | 无法从 final_mapping 推断 appid |
| `E_BACKUP_DIR_BUILD_NO_TIMESTAMP` | 无法获取 backup_id |
| `W_BACKUP_DIR_FALLBACK_CUSTOM` | 回退到 custom mtime |
| `W_BAKIGNORE_FILE_MISSING` | .kmmbakignore 不存在 |
| `W_BAKIGNORE_PARSE_ERROR` | .kmmbakignore 解析错误 |

### 对现有代码的改动

| 模块 | 改动 |
|------|------|
| **新增** `backup_dir_builder.py` | 新增模块，约 150 行 |
| `backup_ops.py` | 增加 `_HARDCODED_BACKUP_SKIP_PREFIX` + 循环防护 |
| `acf_parser.py` | 新增 `get_workshop_timeupdated()` |
| `orchestrator.py` | `run()` backup_dir 可选化 |
| `cli.py` | `--backup-dir` 可选化 |
| Web API + 前端 | backup_dir 可选化适配 |
| `tests/` | 新增 `test_backup_dir_builder.py` |

### 任务分解

```
Step 1: acf_parser 扩展
  Task P1-01: get_workshop_timeupdated()
  Task P1-02: 测试

Step 2: backup_dir_builder 核心
  Task P1-03~P1-06: 四个核心函数实现
  Task P1-07: 单元测试

Step 3: 循环备份防护
  Task P1-08: backup_ops 硬编码过滤
  Task P1-09: 防护测试

Step 4: 集成
  Task P1-10~P1-13: orchestrator/CLI/Web/前端适配
  Task P1-14: 集成测试

Step 5: 回归
  Task P1-15: Python 全量回归
  Task P1-16: 前端 Vitest + 构建
```

### 验收标准

1. `build_backup_dir()` 对 common 和 workshop 目标均返回正确路径
2. workshop ACF 的 `timeupdated` 正确转换 hex
3. 自定义 mod 回退到 mtime
4. `kmmbackup_` 前缀目录被硬编码跳过
5. `.kmmbakignore` 规则正确加载并与 user_config.bakignore 合并
6. CLI 不传 `--backup-dir` 时自动推导成功
7. Web API backup_dir 为 null 时自动推导
