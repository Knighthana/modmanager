# Steam Discovery Contract

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
