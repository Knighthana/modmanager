# 工作状态

- [ ] （挂起）TODO-10: 前端空输入校验；挂起原因：开发阶段需要等待后端API各项问题充分暴露之后再做前端侧的输入校验；
- [ ] （待讨论）TODO-51: 统一界面视觉——各选项卡标题位置/大小标准化；code字体路径；按钮大小字边距，规则概览和计算准备中浅按钮颜色提示
- [ ] （待讨论）TODO-52: 浅色 深色 手动指定切换时刻 跟随系统 根据当地日出日落时间自动调整 主题切换——从文档开始
- [ ] （待讨论）TODO-53: 日志文件整洁——wsl_steam_scan.log生产者调查 + 日志目录规划 + 按照大小条数时间等规则自动清理
- [ ] TODO-66: 规则概览 — preview 图片加载。需要新增 `POST /api/rules/preview { path }` 端点，返回图片二进制。前端以 fit-cover 正方形裁剪展示。
- [ ] TODO-67: 规则概览 — README 文件内容查看。需要新增 `POST /api/rules/readme { path }` 端点，返回文本内容。前端点 README 文件名弹出内容对话框。
- [ ] TODO-68: 规则概览 — author 字段的键含义与展示方式待讨论。当前气泡遍历展示所有 key-value 作为占位。
- [ ] TODO-69: `inputs_hash` 实现不完整——当前仅 hash 规则集，文档要求 hash(database_path + rule_paths + branch_decisions + managed_entries)。需修正。
- [ ] TODO-70: 森林图仍然存在 小地图不能反映用户视觉看到的比例；右边的滚动条又冒出来了；放缩数值需要计算 的问题等待处理；
- [ ] TODO-71: trees到底存在哪；存还是不存，存在前端还是后端；