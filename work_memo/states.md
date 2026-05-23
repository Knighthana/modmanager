# 工作状态

> arch 维护。

## Schema/Code 对齐审计 — 待办

> 2026-05-23 schema vs 实现审计产出。按 Wave 划分。

### Wave 1 — 文档（4 条）

- [ ] DOC-01 `DESIGN_BOOTSTRAP.md` §1.2 — 补首次创建默认值（baksuffix/ignore/rule_sources/path_alias/workspace_dir）+ source_path 入参/出参约定 + workspace_dir 固化规则
- [ ] DOC-02 `DESIGN_BACKUP_OPS.md` 行66/101/183 — type/value → hashtype/hashvalue
- [ ] DOC-03 `DESIGN_BACKUP_DIR.md` + `DESIGN_BACKUP_OPS.md` + `backupinfo.schema.json` — snapshot_time → tree_created_time + last_modified_time
- [ ] DOC-04 `DESIGN_RULE_AGGREGATOR.md` — into_type required + from_type 参数说明

### Wave 2 — 基础设施（新模块 + Schema）

- [ ] MOD-01 `path_normalizer.py` — DSL 路径归一化（补/、值域校验）+ `tests/test_path_normalizer.py`
- [ ] MOD-02 `rule_validator.py` — 接上 `kmm_rule.schema.json` 校验（两层漏斗）
- [ ] MOD-03 `userconfig_ops.py` — `userconfig_init(path)`（补空值键）+ `userconfig_save(index, data)`（前端编辑）
- [ ] SCH-01 `backupinfo.schema.json` — 删多余 `version`；`schema_version` 改 const
- [ ] SCH-02 `user_config.schema.json` — 加 `bakignore` 字段（array[string]，默认空）
- [ ] SCH-03 `user_config.schema.json` — `rule_sources` 改为 `{name: {paths: [...]}}`（与 databases 一致）
- [ ] SCH-04 `user_config.schema.json` — `required` 扩容为 9 键（P22）

### Wave 3 — 核心修正

- [ ] CORE-01 bootstrap 拆分（P21）— `discover_user_config` 拆为：bootstrap 探测+校验 → 不完整则调 userconfig_init → 前端修改走 userconfig_save；`source_path` → `config_index`
- [ ] CORE-02 bakignore 联动 baksuffix — init/save 写时同步；planner 仅 backup 时筛
- [ ] CORE-03 rule_sources 改为 name→paths 解析 — 前端只传名字；后端 `userconfig_ops` 按名找路径列表
- [ ] CORE-04 恢复 `_flatten_tree_file_hashes()` + 补测试（C5：inspect_conflict 崩溃修复）
- [ ] CORE-05 修正 `_tree_node_is_backuped` — 区分"不存在"和"未备份" + `W_BACKUP_NODE_NOT_IN_TREE`（C3）
- [ ] CORE-06 `snapshot_time` → `tree_created_time` 迁移 — prep 写一次；backup_ops 不覆盖（C4）

### Wave 4 — 清扫

- [ ] CLN-01 `_target_for` nwname→target_rel，删 from_type 参数 + 硬编码（engine.py）
- [ ] CLN-02 删除 aggregator 中 nwname 透传
- [ ] CLN-03 `/config/save` → 改为调 `userconfig_save(config_index, data)`；移除 bootstrap 对 save 的参与
- [ ] CLN-04 `user_config.json.example` 补全所有默认字段
- [ ] CLN-05 `DESIGN_PATH_CASE.md` — P0 normalize_path() 实施（待 bootstrap 拆分后推进）

- [ ] (pending)TASK2605-0x1 [user] 前端空输入校验，“待后端端点均符合预期后再开展”
- [ ] (pending)TASK2605-0x2 [user] 统一界面视觉效果: 字体 按钮
- [ ] (pending)TASK2605-0x3 [user] 主题切换，根据日出日落/系统主题自动切换界面亮暗效果
- [ ] (pending)TASK2605-0x4 [user] 自动输出日志文件到规定位置整洁
- [ ] (pending)TASK2605-0x5 [user] 规则概览 — preview 图片加载；设计就绪（`DESIGN_EXT_RESOURCE.md`），待 `ext_resource` 包实现
- [ ] (pending)TASK2605-0x6 [user] 规则概览 — README 文件内容查看；同上
- [ ] (pending)TASK2605-0x7 [user] 规则概览 — author 字段的键含义与展示方式待讨论
- [x] TASK2605-0x9 [user] 检查bootstrap目前使用什么样的逻辑进行自动发现；提供“steam没有安装在默认目录”场景下手动指定`steam.exe`位置(更推荐，因为主vdf的路径可以通过`steam.exe`位置推算)或手动指定主vdf文件的途径；让bootstrap对macOS进行支持；针对Linux/Windows/macOS三套系统写出详细的“默认路径”方案；
- [ ] TASK2605-0xA [user] 应当显式增加路径大小写的检查/模糊开关，而不是仅仅根据DataBase进行判断；→ `DESIGN_PATH_CASE.md` 已出规则文档；待实施（P0-P3 四步）