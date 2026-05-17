# repo_bkgd

> Status: active
> Authority: reference-only
> Read-Tier: on-demand
> Purpose: 存放“为什么”层的背景解释与机制推导，作为 repo_memo 规范文档的补充参考。

本目录不是默认实现输入目录。

## 读取规则
- 禁止以目录方式主动读取本目录内容。
- 禁止将本目录加入默认上下文或批量扫描集合。
- 仅允许通过上层索引（例如 repo_memo 文档中的显式链接）点读具体文件。
- 未被索引命中的背景文档默认忽略。

## 使用方式
1. 先阅读 repo_memo 中对应模块的权威规范文档（怎么做）。
2. 当且仅当需要追溯机制原因时，再按索引进入本目录指定文件（为什么）。
3. 背景文档与权威规范冲突时，以 repo_memo 的权威规范为准。

## 当前索引
- SVG 缩放机制背景: SVG_PAN_ZOOM.md
