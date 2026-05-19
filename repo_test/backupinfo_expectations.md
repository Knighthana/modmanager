# backupinfo 正例规范

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 为测试组定义 backup_dir、backupinfo 与 restore 主路径“应该是什么样”，不覆盖反例与故障注入设计

## 一、使用范围

本文档只给测试组提供正例规范。

本文档不负责：

- 设计反例
- 设计异常构造
- 规定产品层操作限制

## 二、backup_dir 应满足的正例

- 每个 `backup_dir` 根目录应包含 `backupinfo.json`
- `backupinfo.json` 固定放在 `backup_dir` 根目录
- `backup_dir` 中应包含本次备份产生的实体文件

## 三、backupinfo 根结构应满足的正例

`backupinfo.json` 根对象应且只应包含：

- `snapshot_time`
- `last_modified_time`
- `schema_version`
- `tree`

补充要求：

- 四个字段缺一不可
- 不应存在额外根字段

## 四、tree 节点结构应满足的正例

### 4.1 根节点

- `tree` 根节点必须是 `dir`
- 根节点应有 `name`、`type`、`children`

### 4.2 目录节点

- 目录节点 `type` 必须为 `dir`
- 目录节点应有 `children`
- 目录节点不应带 `hashvalue`

### 4.3 文件节点

- 文件节点 `type` 必须为 `file`
- 文件节点必须带 `isbackuped`
- 文件节点必须带 `hashtype`
- 文件节点必须带 `hashvalue`
- 文件节点不应带 `children`

## 五、命名规范应满足的正例

- backupinfo 目录语义统一使用 `dir`

## 六、restore 主路径应满足的正例

- restore 只处理当前 mapping 命中的文件
- mapping 只决定本次 restore 的命中集合
- `backupinfo.json` 只决定结构与 hash truth
- 命中=true 的文件进入 restore 执行
- 命中=false 的文件不参与 restore
- `force=true` 时直接跳过 hash 计算并执行文件操作，不改变 backupinfo 权威性

## 七、warning 与 error 的正例语义

- 找不到可恢复实体时，应有 warning 或 skip 结果，不应伪装为成功恢复
- 复制失败时，应进入 error 列表
- restore 返回结果中应能区分 `restored`、`skipped`、`errors`、`warnings`

## 八、权威来源

测试组如需理解这些正例的契约来源，优先阅读：

- `repo_spec/backupinfo.schema.json`
- `repo_memo/DESIGN_BACKUP_DIR.md`
- `repo_memo/DESIGN_BACKUP_OPS.md`
- `repo_memo/DESIGN_RESTORE_OPS.md`
- `repo_memo/TERMS_FIELD_FREEZE.md`
- `repo_memo/TERMS_ERROR_CODES.md`

反例、非法输入和故障场景由测试组自行扩展。