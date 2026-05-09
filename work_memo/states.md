# 工作状态

## TODO
- [ ] TODO-10: （挂起）空输入校验
- [ ] TODO-15: Forest SVG 自适应视窗缩放 + 视窗功能增强
- [ ] TODO-19: （挂起）为重复待选择 radio 的 game 和 mod 提供显眼的视觉提示，解决冲突后消除
- [ ] TODO-20: 选项卡解耦——各选项卡独立设计，避免互相影响
- [ ] TODO-21: "发现模式"偏好保存应在"扫描 Steam 库"按钮按下后执行前端持久化
- [ ] TODO-22: Database 路径 / Database JSON / Rule paths 迁入"数据源"选项卡
- [ ] TODO-23: user config 路径迁入"设置"；启动时未配置则导航到设置页并提示填写；已配置则前往用户偏好的"默认开始页"
- [ ] TODO-24: backup dir 语义澄清——backup dir 由 `build_backup_dir()` 自动推导（见 DESIGN_BACKUP.md），非用户自由填写；当前 ForestPage 上的 backup_dir 输入框需审查
- [ ] TODO-25: "Forest 可视化"中的 dry run 和"应用流水线"功能迁入"文件操作"选项卡，并且测试文件操作相关功能是否符合预期(目前不符合)；
- [ ] TODO-26: "手动路径"→"手动路径列表"，支持多路径输入（空格正常传输），做好列表内去重与自动发现路径的去重，后端接收列表
