# 工作状态

- [ ] （进行中）TODO-58: GUI-P0 扫描模式语义修复（仅自动/全部/仅手动参数映射）
- [ ] （进行中）TODO-59: GUI-P0 compute 参数契约统一（aggregated_rule_set）
- [ ] （进行中）TODO-60: GUI-P0 计算结果计数字段对齐（避免 0 树 0 映射假成功）
- [ ] （进行中）TODO-61: GUI-P0 ForestPage 职责边界修复（移除计算/运行触发）

- [ ] （挂起）TODO-10: 前端空输入校验；挂起原因：开发阶段需要等待后端API各项问题充分暴露之后再做前端侧的输入校验；
- [ ] （待讨论）TODO-51: 统一界面视觉——各选项卡标题位置/大小标准化；code字体路径；按钮大小字边距，规则概览和计算准备中浅按钮颜色提示
- [ ] （待讨论）TODO-52: 浅色 深色 手动指定切换时刻 跟随系统 根据当地日出日落时间自动调整 主题切换——从文档开始
- [ ] （待讨论）TODO-53: 日志文件整洁——wsl_steam_scan.log生产者调查 + 日志目录规划 + 按照大小条数时间等规则自动清理
- [x] TODO-54: 工具文件治理 → 已裁定。user_config 由 first_use 自动创建；database 由扫描写入。`tools/test_wsl_crossover.py` 产生日志。
- [x] TODO-56: 刷新后 Database 数据丢失 → 已修正。DataSourcePage/AdvancedPage/ForestPage 的 onMounted 自动调 `/api/database/read` 恢复数据。
- [x] TODO-57: manual 模式缓存返回旧数据 → 已修正。`bootstrap.py` 中 manual 模式跳过缓存，强制重新扫描。
