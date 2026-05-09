# 工作状态

## TODO
- [ ] TODO-10: （挂起）空输入校验
- [x] TODO-15: ✅ 全部完成（自适应宽度缩放 + svg-pan-zoom 迁移 + 重置按钮 + 小地图）
- [ ] TODO-19: （挂起）为重复待选择 radio 的 game 和 mod 提供显眼的视觉提示，解决冲突后消除
- [ ] TODO-20: 选项卡解耦——【第一步】先做全面审查，摸底当前各选项卡间的耦合情况；【第二步】各选项卡独立设计，避免互相影响
- [x] TODO-21: "发现模式"偏好保存应在"扫描 Steam 库"按钮按下后执行前端持久化 (1行, onScan加saveToCache)
- [ ] TODO-22: 三项迁移：①移除"Forest可视化"选项卡中的 Database JSON 栏，排查所有涉及到的接口和数据存储有无孤儿接口或孤儿存储，之后只保留"设置"页面中的"数据库JSON"一处权威的"当前数据库JSON显示/修改提交界面"；②"Forest可视化"界面的 Rule paths 移入"规则概览页面"，并改为支持分别通过 `[]/path/to/file` 或 `/path/to/search/` 两种方式指定 rules 来源，将所有 rules 汇总到一个大列表中，提供显示和操作的方式；③去除"Forest可视化"选项卡的"user config路径"，移到"设置"页面的单独一栏，排查接口和存储有无跟着迁移，有无孤儿接口或存储行为
- [ ] TODO-28: 【新】前端 database 副本合并——当前 database 被分散在 3 个 localStorage key（datasource / datasource-db / forest-store）中，各自独立读写。需合并为单一副本，统一存取路径，规定"前端仅一份 database，始终同步自后端"，且修改对应的文档对此同步性与一致性课题做严格定义和要求；
- [ ] TODO-23: user config 路径迁入"设置"；启动时未配置则导航到设置页并提示填写；已配置则前往用户偏好的"默认开始页"
- [ ] TODO-24: backup dir 语义澄清——backup dir 由 `build_backup_dir()` 自动推导（见 DESIGN_BACKUP.md），非用户自由填写；当前 ForestPage 上的 backup_dir 输入框需审查
- [ ] TODO-25: "Forest 可视化"中的 dry run 和"应用流水线"功能迁入"文件操作"选项卡，并且测试文件操作相关功能是否符合预期(目前不符合)；
- [ ] TODO-26: "手动路径"→"手动路径列表"，支持多路径输入（空格正常传输），做好列表内去重与自动发现路径的去重，后端接收列表
- [ ] TODO-27: 【新】pipeline compute 数据流修复——当前前端传 database dict 给后端，违反"以后端为准"原则。需改 orchestrator + routes + ForestPage 联动，后端自行从文件读 database；同步更新 DESIGN_STORAGE.md / DESIGN_ORCHESTRATOR.md 中的相关描述
- [ ] TODO-29: 【新】Settings 页 Database JSON 保存按钮修复——缺 `output_path` 参数（应从 `form.databaseOutputPath` 读取），保存成功后未消费 `resp.data.database` 更新本地副本（违反单副本原则）
- [ ] TODO-30: 【新】GUI 页面实现策略——讨论是否应先以 mock 数据实现 GUI 布局与交互，最后再接入实际数据接口。优点：前后端并行开发，降低耦合
