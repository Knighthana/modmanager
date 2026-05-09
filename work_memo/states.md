# 工作状态

## TODO
- [x] TODO-2: 清理 /tmp/ 运行时文件（存储规范已冻结 → DESIGN_STORAGE.md）
- [x] TODO-3: "仅分枝"空结果提示语修正
- [x] TODO-4: BackupPage GUI 审查
- [x] TODO-5: 全局路径显示规范
- [x] TODO-6: 下游路径门禁未强制执行
- [x] TODO-8: ConflictsPage branch decisions 刷新丢失
- [x] TODO-9: onDbPathBlur 静默失败
- [ ] TODO-10: （挂起）空输入校验
- [x] TODO-11: Rules / user_config 路径无 ~ 展开（aggregator 层）
- [x] TODO-12: Rules paths 前端无路径预检
- [x] TODO-13: i18n 预备：字符串集中映射
- [x] TODO-14: 数据 Schema 明确定义（8 份全部就位：aggregated_rule_set / backupinfo / branch_decisions / database / kmm_rule / mapping_output / sse_event / user_config）
- [ ] TODO-15: Forest SVG 自适应视窗缩放 + 视窗功能增强
- [x] TODO-16: 数据源页面去重功能未正确生效；game/mod 的 radio 未正确出现
- [x] TODO-17: 数据源页面表头应显示"可见性"而非眼睛 emoji
- [x] TODO-18: E_DUPLICATE_APPID + E_DUPLICATE_MIXED_ID；错误平铺展示
- [ ] TODO-19: （挂起）为重复待选择 radio 的 game 和 mod 提供显眼的视觉提示，解决冲突后消除
- [ ] TODO-20: 选项卡解耦——各选项卡独立设计，避免互相影响
- [ ] TODO-21: "发现模式"偏好保存应在"扫描 Steam 库"按钮按下后执行前端持久化
- [ ] TODO-22: Database 路径 / Database JSON / Rule paths 迁入"数据源"选项卡
- [ ] TODO-23: user config 路径迁入"设置"；启动时未配置则导航到设置页并提示填写；已配置则前往用户偏好的"默认开始页"
- [ ] TODO-24: backup dir 语义澄清——backup dir 由 `build_backup_dir()` 自动推导（见 DESIGN_BACKUP.md），非用户自由填写；当前 ForestPage 上的 backup_dir 输入框需审查
- [ ] TODO-25: "Forest 可视化"中的 dry run 和"应用流水线"功能迁入"文件操作"选项卡
- [ ] TODO-26: （挂起）"手动路径"→"手动路径列表"，支持多路径输入（空格正常传输），做好与自动发现路径的去重，后端接收字符串列表
