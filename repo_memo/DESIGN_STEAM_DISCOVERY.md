# Steam Discovery Contract

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: Steam 自动发现合约；定义从本机 Steam 安装中发现库路径、appid 与工坊条目的流程

## 目标
从本机 Steam 安装中自动发现：
- 所有 Steam 库路径
- 每个库的已安装游戏 appid 列表
- 每个游戏的工坊条目列表

## 默认流程（非贪婪）
1. 先定位候选 `steamapps` 目录（Windows/Linux/WSL 常见位置）
2. 在候选目录中识别 `contains_libraryfolders_vdf=true` 的主发现点
3. 解析主 `libraryfolders.vdf`
4. 从 VDF 扩展得到全部库路径（包含非默认盘）
5. 对每个库扫描 `appmanifest_*.acf` 构建游戏信息
6. 默认仅对在 `steamlib[].game` 范围内的 appid 继续解析 `appworkshop_*.acf`

## 输入
- `libraryfolders.vdf`
- `appmanifest_*.acf`
- `appworkshop_*.acf`

## 输出落位
- `OS.steamlibpathstyle`
- `steamlib[].path`
- `steamlib[].contains_libraryfolders_vdf`
- `steamlib[].game`
- `game[].appid`
- `game[].mods_found`

## 失败处理
- 若无任何可用库：抛出错误并终止生成
- 若单个库解析失败：记录并跳过该库，不影响其他库
- 若单个 ACF 无效：记录并跳过该文件

## 手动指定模式（强制能力）
1. 永远允许用户手动指定 `steamapps` 目录。
2. 自动发现失败时，必须回退到手动指定并继续流程。
3. 不以“完整/不完整”作为自动发现判定条件；仅当无可用工作目录时才要求用户介入。
4. 自动发现结果与手动指定结果可合并，按路径去重；同路径冲突时以手动指定为准。

## 当前策略
- `greedy_parsing` 默认关闭
- 未进入 `steamlib[].game` 范围的 appid，不默认进入 mod 解析

## 策略细化
1. `greedy_parsing=false`：
	- 仅当 appid 出现在对应库的 `steamlib[].game` 中时，才执行该游戏的 mod 解析。
	- 范围外 appid 可保留游戏元数据，但 `mods_found` 默认不解析。
2. `greedy_parsing=true`：
	- 放宽过滤，允许对范围外 appid 继续解析 mod。
3. 两种模式都不得影响主 VDF 扩展发现库路径的行为。

## 数据维护接口（规划冻结）
- `steamlib`：必须提供 CRUD（增、删、改、查）接口。
- `liveupdate`：根据 `steamlib` 变化增量更新 `game`、`mod`。
- `regen`：清空 `game`、`mod` 后，按最新 `steamlib` 全量重建。
