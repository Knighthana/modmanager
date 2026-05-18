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
- backup 目录名前缀（`bakprefix`）严格从 `user_config.bakprefix` 读取，不使用硬编码默认值。

### 输入
- `bakprefix`（从 `user_config` 读取，照抄原值）
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

备份目录名格式：`{bakprefix}{id}_{timestamphex}/`

- `bakprefix`：严格从 `user_config.bakprefix` 读取，原样照抄（包括 `_` 字符的数量）
- `id`：appid 或 contentid
- `timestamphex`：见 §2 的稳定性检查结果

### 3.2 游戏本体（appid）备份目录

```
位置：{basepath}/kmmbackup_{appid}_{hex(buildid)}/
示例：/.../steamapps/common/RunningWithRifles/kmmbackup_270150_6a0a3379/
```

### 3.3 Workshop MOD（contentid）备份目录

```
位置：{modpath}/{contentid}/kmmbackup_{contentid}_{hex(T_remote)}/
示例：/.../steamapps/workshop/content/270150/2606099273/kmmbackup_2606099273_69fc415f/
```

### 3.4 文件映射规则

mapping 中路径 `/.../workshop/content/270150/2606099273/some/path/fileA` 的备份：
- 写入 `{备份根目录}/some/path/fileA`
- 即去掉 `{modpath}/{contentid}/` 前缀后的相对路径

---

## 四、多库同名场景

### 4.1 同库、同 appid、不同 contentid

| contentid | 备份根目录 | T_remote 来源 |
|-----------|-----------|--------------|
| 2606099273 | `{modpath}/2606099273/kmmbackup_2606099273_{hex1}/` | 本库 `appworkshop_270150.acf` 中 2606099273 条目 |
| 3428584891 | `{modpath}/3428584891/kmmbackup_3428584891_{hex2}/` | 同一 ACF 文件中 3428584891 条目 |

两个 contentid 各自独立计算 backup_id、各自在自己的目录下创建备份。

### 4.2 不同库、同 appid、同 contentid

| 库 | 备份根目录 | T_remote 来源 |
|----|-----------|--------------|
| lib1 (`/mnt/A/steamapps/`) | `lib1/.../workshop/content/270150/2606099273/kmmbackup_2606099273_{hex1}/` | `lib1/.../appworkshop_270150.acf` |
| lib2 (`/mnt/B/steamapps/`) | `lib2/.../workshop/content/270150/2606099273/kmmbackup_2606099273_{hex2}/` | `lib2/.../appworkshop_270150.acf` |

即使 contentid 相同，两个库各自独立：backup_id 分别从各自的 ACF 文件计算。hex 值可能不同（安装状态不同步）。

### 4.3 同库、同 appid、同时命中 base 和 content

| 区域 | 备份根目录 | backup_id 来源 |
|------|-----------|---------------|
| base（appid） | `{basepath}/kmmbackup_{appid}_{hex(buildid)}/` | `appmanifest_{appid}.acf` → `buildid` |
| content（某个 contentid） | `{modpath}/{contentid}/kmmbackup_{contentid}_{hex(T_remote)}/` | `appworkshop_{appid}.acf` → `latest_timeupdated` |

二者路径不同、backup_id 计算方式不同、各自独立，不可混用。

---

## 五、循环备份防护

- `backup_ops` 内部硬编码跳过 `kmmbackup_` 前缀的目录
- 备份目录下可放置 `.kmmbakignore` 文件（仿 `.gitignore` 语法）作为额外忽略规则
- `user_config.bakignore` 提供全局忽略列表

---

## 六、核心函数设计（待更新）

> 以下函数签名需按 §2-§4 的新规则重写。当前实现 `build_backup_dir` 仍为旧逻辑（单一 backup_dir 输出、`get_workshop_backup_id` 使用旧字段），参见实施计划。

### 需新增 / 重写的函数

| 函数 | 模块 | 说明 |
|------|------|------|
| `get_game_backup_id()` | `backup_ops.py` | 重写：加入 StateFlags 稳定性检查，改用 buildid |
| `get_workshop_timestamphex()` | `backup_ops.py` | 新增：输入 contentid，返回 (ok, hex, warnings)，含 T_local vs T_remote 比较 |
| `build_backup_dirs()` | `backup_dir_builder.py` | 重写：输出多个 backup_dir（每个 app / contentid 一个） |
| `get_workshop_timeupdated()` | `acf_parser.py` | 重写：同时提取 `timeupdated` 和 `latest_timeupdated` |

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