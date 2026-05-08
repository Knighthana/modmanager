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

## 8. 本地路径别名与动作引用
- `path_alias`：本地用户配置中的路径别名列表
- `path_handle`：路径别名项中的引用句柄；当前无消费者（`provenance_ref` 已改用绝对路径），保留供未来扩展
- `path_target`：路径别名项对应的本地文件系统根目录
- `rule_meta_tag`：规则级元数据容器（不直接表达替换动作），仅存在于 kmm_rule 文件中
- `provenance_ref`：动作级来源引用，值为 kmm_rule 源文件的**绝对路径**（由聚合器填入）
- `sidecar_ref`：动作级外置扩展引用；缺失或空值时回退为 `404` 并记录 warning

## 9. 作者与规则名回退
- `rulenamespace` 为空：`anonymousnamespace`
- `rulename` 为空：`unknownrulename`

## 10. 执行顺序辅助字段
- `action_order`：聚合器或 GUI 在运行时注入的动作顺序，类型必须为 int
- 默认值为 `0`，表示未指定或不可靠，不做猜测补全
- 命中过程冲突且 `action_order` 相等，或任一冲突方的 `action_order=0` 时，必须直接抛错

## 11. 聚合器输出
- `operation[]` — 聚合后的 mod 操作列表（key: `"operation"`，替代旧 `"mod"`）
- action 类型：`replace` / `create` / `delete`（`hold` 在聚合器阶段已过滤，不出现在输出中）
- `from_type` / `into_type`：`"file"` 或 `"path"`（path 时列表每项以 `/` 结尾）

## 12. 引擎输出
- `trees` — P0 后替代旧 `"forest"`，独立根+引用模型的森林
- `TreeNode` — 树结点：`root_path`、`destin_mixed_id`、`changerequest`、`refs`、`resolved_state`
- `changerequest` — 单个操作映射：`path`、`action`、`mixed_id`、`hashtype`、`hashvalue`
- `resolved_state` — `pending` / `kept` / `deleted` / `failed` / `skipped`
- `refs` — 此树引用的其他树根路径（独立根+引用模型）
- `final_mapping` — 决议后的最终文件映射列表

## 13. 数据库扩展
- `dommod[]` — mod 列表：`mixed_id`（appid:modid 格式）、`path`（以 / 结尾）、`localdate`
