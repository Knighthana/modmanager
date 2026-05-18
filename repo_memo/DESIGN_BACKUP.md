# DESIGN_BACKUP — Backup 实现设计

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 backup_dir 推导、备份恢复流程与 backup 子系统的职责边界
> Last-Updated: 2026-05-18

> 来源：DESIGN_P1_BACKUP.md + BACKUP_DIR_BUILDER_DESIGN.md（合并）
> 实现状态：已落地并持续生效

---

## 一、概览

### 目标
将备份目录字符串生成过程与 `backup_ops` 解耦。

### 设计原则
- `backup_ops` 只消费目录字符串并做合法性/完整性检查。
- builder 负责命名规则、id 查找、时间转换、路径拼装。
- **每个 contentid 独立备份**，各自在自己的根目录下建备份目录。
- **不同 Steam 库中的相同 contentid 独立处理**，各自从本库的 ACF 文件中获取时间戳。
- backup 目录名后缀（`baksuffix`）严格从 `user_config.baksuffix` 读取，不使用硬编码默认值。

### 输入
- `baksuffix`（从 `user_config` 读取，照抄原值）
- `final_mapping` 列表
- `database`（game 列表，含 basepath / modpath / steamlib 信息）

### 输出
- 若干 backup_dir 路径（每个 app / contentid 一个）

---

## 二、时间戳来源与稳定性检查

### 2.1 appid（游戏本体，modid==0，走 basepath）

| 步骤 | 操作 | 来源 |
|------|------|------|
| 1 | 读取 `StateFlags` | `steamapps/appmanifest_{appid}.acf` → `AppState.StateFlags` |
| 2 | 稳定性判定 | 若 `StateFlags` 不在允许列表 `{4}` 中 → **跳过，记录警告** |
| 3 | 读取 `buildid` | `AppState.buildid` |
| 4 | 计算 hex | `format(int(buildid), 'x')`（小写 ascii） |

**StateFlags 说明**：
- `4`：StateFullyInstalled（环境绝对稳定）
- `6` / `1026`：游戏正在运行
- `8` / `12` / `1032`：需要更新 / 正在下载 / 更新被暂停
- 允许列表当前仅 `{4}`，未来可扩展

### 2.2 contentid（Workshop MOD，走 modpath）

| 步骤 | 操作 | 来源 |
|------|------|------|
| 1 | 读取 T_local | `steamapps/workshop/appworkshop_{appid}.acf` → `AppWorkshop.WorkshopItemsInstalled.{contentid}.timeupdated` |
| 2 | 读取 T_remote | 同文件 → `AppWorkshop.WorkshopItemDetails.{contentid}.latest_timeupdated` |
| 3 | 稳定性判定 | 若 T_local < T_remote → **跳过，记录警告**（版本滞后，等待 Steam 更新） |
| 4 | 计算 hex | `format(int(T_remote), 'x')`（小写 ascii） |

**稳定性判定细节**：
- T_local ≥ T_remote：本地版本已落实，稳定，以 T_remote 为 backup_id
- T_local < T_remote：服务器有新版本但本地未下载完，不稳定，拒绝备份
- 字段缺失：记录警告，跳过该 contentid

### 2.3 custom mod（无 ACF）

| 步骤 | 操作 |
|------|------|
| 1 | 取源目录所有文件的最新 mtime |
| 2 | `format(max_mtime, 'x')` |

---

## 三、备份目录命名与位置规则

### 3.1 通用规则

备份目录名格式：`{id}.{timestamphex}.{baksuffix}/`

- `baksuffix`：严格从 `user_config.baksuffix` 读取，原样照抄
- `id`：appid 或 contentid
- `timestamphex`：见 §2 的稳定性检查结果

### 3.2 游戏本体（appid）备份目录

```
位置：{basepath}/{appid}.{hex(buildid)}.{baksuffix}/
示例：/.../steamapps/common/RunningWithRifles/270150.6a0a3379.kmmbackup/
```

### 3.3 Workshop MOD（contentid）备份目录

```
位置：{modpath}/{contentid}/{contentid}.{hex(T_remote)}.{baksuffix}/
示例：/.../steamapps/workshop/content/270150/2606099273/2606099273.69fc415f.kmmbackup/
```

### 3.4 文件映射规则

mapping 中路径 `/.../workshop/content/270150/2606099273/some/path/fileA` 的备份：
- 写入 `{备份根目录}/some/path/fileA`
- 即去掉 `{modpath}/{contentid}/` 前缀后的相对路径

### 3.5 dry_run 返回格式

`run_differential_backup` 在 `dry_run=True` 时，`backed_up` 列表中每条记录含：

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | `"copy"` | 操作类型，备份统一为拷贝 |
| `path` | `str` | 源文件绝对路径 |
| `backup_path` | `str` | 文件在备份目录内的相对路径 |
| `size` | `int` | 文件字节数 |
| `mtime` | `float` | 修改时间 |
| `is_dir` | `bool` | 是否为目录 |

`apply_final_mapping` 在 `dry_run=True` 时，`applied` 列表中每条记录：

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | `"create"` / `"replace"` / `"delete"` | 来自 `final_mapping[].request.action` |
| `source` | `str` | 源路径 |
| `target` | `str` | 目标绝对路径 |
| `size` | `int` | 源文件字节数 |
| `mtime` | `float` | 修改时间 |
| `is_dir` | `bool` | 是否为目录 |

---

## 四、多库同名场景

### 4.1 同库、同 appid、不同 contentid

| contentid | 备份根目录 | T_remote 来源 |
|-----------|-----------|--------------|
| 2606099273 | `{modpath}/2606099273/2606099273.{hex1}.{baksuffix}/` | 本库 `appworkshop_270150.acf` 中 2606099273 条目 |
| 3428584891 | `{modpath}/3428584891/3428584891.{hex2}.{baksuffix}/` | 同一 ACF 文件中 3428584891 条目 |

两个 contentid 各自独立计算 backup_id、各自在自己的目录下创建备份。

### 4.2 不同库、同 appid、同 contentid

| 库 | 备份根目录 | T_remote 来源 |
|----|-----------|--------------|
| lib1 (`/mnt/A/steamapps/`) | `lib1/.../workshop/content/270150/2606099273/2606099273.{hex1}.{baksuffix}/` | `lib1/.../appworkshop_270150.acf` |
| lib2 (`/mnt/B/steamapps/`) | `lib2/.../workshop/content/270150/2606099273/2606099273.{hex2}.{baksuffix}/` | `lib2/.../appworkshop_270150.acf` |

即使 contentid 相同，两个库各自独立：backup_id 分别从各自的 ACF 文件计算。hex 值可能不同（安装状态不同步）。

### 4.3 同库、同 appid、同时命中 base 和 content

| 区域 | 备份根目录 | backup_id 来源 |
|------|-----------|---------------|
| base（appid） | `{basepath}/{appid}.{hex(buildid)}.{baksuffix}/` | `appmanifest_{appid}.acf` → `buildid` |
| content（某个 contentid） | `{modpath}/{contentid}/{contentid}.{hex(T_remote)}.{baksuffix}/` | `appworkshop_{appid}.acf` → `latest_timeupdated` |

二者路径不同、backup_id 计算方式不同、各自独立，不可混用。

---

## 五、循环备份防护

### 三层忽略规则

| 层 | 来源 | 粒度 | 说明 |
|----|------|------|------|
| 硬编码底线 | 引擎内部 `".kmmbackup"` | 目录名后缀 | 始终生效，不受 user_config 影响 |
| user_config | `user_config.bakignore`（list[str]） | 目录名后缀 | 用户自定义额外忽略后缀 |
| .kmmbakignore | 源目录下的 `.kmmbakignore` 文件 | gitignore 模式 | 文件级灵活忽略，用 `gitignore-parser` 解析 |

### .kmmbakignore 级联规则

拟合 git 行为：从文件所在目录往上走到 contentid 根目录，每层 `.kmmbakignore` 都参与判定。

```
contentid/
  .kmmbakignore          ← 第1层：对整个 contentid 生效
  sub/
    .kmmbakignore        ← 第2层：覆盖 / 追加上级规则
    file.mod              ← 判定时参考第1层 + 第2层
```

- 子目录规则优先级高于父目录（`!` 否定可覆盖父级忽略）
- 每个 `.kmmbakignore` 文件只解析一次，结果缓存
- 备份时：文件被判定忽略 → 不纳入备份
- 备份时：各级 `.kmmbakignore` 文件本身**一定被拷贝**进 backup_dir 对应位置
- 应用时：backup_dir 中所有 `.kmmbakignore` 覆盖回源目录对应位置

---

## 六、核心函数设计

### `get_game_backup_id()`

```python
def get_game_backup_id(steamlib_path: str, appid: str) -> tuple[bool, str | None, str]:
    """返回 (ok, backup_id_hex, error_msg)。
    读取 appmanifest_{appid}.acf，检查 StateFlags ∈ {4}，取 buildid → hex。
    """
```

### `get_workshop_timestamphex()`

```python
def get_workshop_timestamphex(steamapps_path: str, appid: str, contentid: str) -> tuple[bool, str | None, str]:
    """返回 (ok, timestamphex, warning_msg)。
    读取 appworkshop_{appid}.acf，比较 T_local (timeupdated) 与 T_remote (latest_timeupdated)。
    T_local ≥ T_remote → 返回 T_remote 的 hex；否则跳过。
    """
```

### `get_workshop_timeupdated()` / `get_workshop_latest_timeupdated()`

```python
def get_workshop_timeupdated(steamapps_path: str, appid: str, contentid: str | None = None) -> str:
    """读取 timeupdated；若指定 contentid 则针对性查找，否则取全体最大值。
    """

def get_workshop_latest_timeupdated(steamapps_path: str, appid: str, contentid: str) -> str:
    """读取 WorkshopItemDetails.{contentid}.latest_timeupdated。"""
```

### `build_backup_dirs()`

```python
def build_backup_dirs(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
) -> tuple[dict[str, list[str]], list[str]]:
    """返回 ({backup_dir: [file_paths]}, warnings)。
    根据 path prefix 匹配确定每个 target 归属的 app / contentid，调用对应的 backup_id 函数生成目录。
    baksuffix 从 user_config.baksuffix 读取。
    """
```

### `build_backup_dir()`（兼容 wrapper）

```python
def build_backup_dir(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
) -> str:
    """兼容旧接口：调用 build_backup_dirs 并返回第一个 backup_dir。"""
```

---

## 七、错误码

| 码 | 含义 |
|----|------|
| `E_BACKUP_DIR_BUILD_NO_APPID` | 无法从 final_mapping 推断 appid |
| `E_BACKUP_DIR_BUILD_NO_TIMESTAMP` | 无法获取 backup_id |
| `E_BACKUP_STATE_UNSTABLE` | app/contentid 处于不稳定状态，拒绝备份 |
| `E_BACKUP_VERSION_LAGGED` | contentid 版本滞后（T_local < T_remote） |
| `W_BACKUP_DIR_FALLBACK_CUSTOM` | 回退到 custom mtime |
| `W_BACKUP_CONTENTID_SKIPPED` | 某 contentid 因不稳定被跳过 |