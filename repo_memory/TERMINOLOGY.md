# Terminology Freeze

## 1. 主 VDF 发现点
- 术语：主 VDF 发现点
- 定义：某个 `steamapps` 路径下存在 `libraryfolders.vdf`，可用于扩展发现全部 Steam 库。
- 主字段：`contains_libraryfolders_vdf`（boolean）
- 废弃别名：`islbfdvdflocate`、`islbfvdflocate`

## 2. 路径风格
- `workingpathstyle`：当前运行环境路径风格（linux/windows）
- `steamlibpathstyle`：steam 库原始路径风格（linux/windows）

## 3. 库内游戏集合
- 术语：库内已安装游戏列表
- 主字段：`steamlib[].game`
- 元素：`appid` 字符串

## 4. 游戏下 mod 集合
- 术语：游戏已安装工坊条目
- 主字段：`game[].mods_found`
- 元素：`modid/contentid` 字符串

## 5. 组合标识
- 术语：组合标识
- 主字段：`mixed_id`
- 格式：`appid:modid`
- 废弃别名：`appitemid`

## 6. 命名原则
- 每个概念只有一个主名
- 历史名只允许在迁移说明中出现，不允许继续写入示例数据

## 7. 备份目录命名与过滤
- `bakprefix`：备份目录名前缀（默认建议 `kmmbackup_`）
- `bakignore`：备份/恢复扫描时的忽略规则集合（路径/通配）
- 约束：`backup_ops` 只消费最终目录字符串，不负责生成规则

## 8. 规则元数据
- `rule_meta_tag`：规则级元数据容器（不直接表达替换动作）
- `action_meta_tag`：动作级元数据容器（用于溯源与辅助决议）
- `source_trace_map`：聚合输出的侧车溯源结构，与 `aggregated_rule_set` 并行存在

## 9. 作者与规则名回退
- `mainauthor` 为空：`anonymousauthor`
- `rulename` 为空：`unknownrulename`

## 10. 执行顺序辅助字段
- `actionorder`：仅用于树生成后的分支辅助决议
- 可为空；为空、相等或不可判定时，必须回退人工拍板
