历史草案，不作为实现依据。

目录职责：
1. `description/` 仅用于 user 与 Plan 的沟通与草案整理。
2. implement 默认忽略 `description/`，不得据此推导实现规则。
3. 仅当 Plan 任务单明确要求时，implement 才可在 `description/` 写入指定文件。

执行入口：
1. 实现约束与契约请转向 `repo_memo/README.md`。
2. 若 `description/` 与 `repo_memo/` 内容冲突，以 `repo_memo/` 为准。
3. `json.example` 的维护采用单向同步：`repo_memo/` -> `description/`。
4. 若 Plan 明确授权例外，可临时引用 `description/` 作为补充背景；例外流程与回收要求以 `repo_memo/README.md` 为准。
