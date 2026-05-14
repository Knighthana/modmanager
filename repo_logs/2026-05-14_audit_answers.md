先给总判断：  
不是零风险，但风险已经收敛到“少量架构决策待拍板”，不是“实现方向混乱”。  
权威优先级请继续按 DOCUMENT_GOVERNANCE.md 执行，审计日志属于建议与记录，不直接压过权威设计。

下面是逐条答复包含建议：

1. workspace 字段命名 camelCase vs snake_case  
结论：应统一到 camelCase（尤其是冻结字段 managedEntries、branchDecisions、selectedRulePaths、lastComputeSummary）。  

2. useWorkspaceStore 唯一写者  
结论：方向正确，建议收敛为唯一写者。  
余地：现在做还是下一迭代做。  
建议：persistence 作为底层工具保留，workspace store 调用它，不是替代关系；useComputeStore 可作为后续收敛项，不必和 workspace store 强绑定同一批次上线。

3. selectedRulePaths vs aggregatedRuleSet  
结论：本地只存 selectedRulePaths，不存完整 aggregatedRuleSet，符合审计意图。   
建议：selectedRulePaths 来自用户实际勾选的规则文件；aggregatedRuleHash 继续保留（用于一致性与快速失效判断）。

4. uiState 并入 workspace  
结论：可以并入，方向合理。  
建议：按高价值字段先迁移，并加写入节流（例如 200ms 级）避免频繁刷 localStorage。

5. pipeline 端点 EVOLVING  
结论：你们最近对 compute 的改动属于 EVOLVING 范围内正常迭代。  
是否拍板：通常不需要，除非要恢复旧 fallback。  
建议：不要主动恢复 kmm_rule_paths fallback，除非明确有兼容需求和退场计划。

6. 文档清理残留  
结论：权威文档应只保留现状定义；迁移历史放审计日志或归档。   
建议：DESIGN_FOREST_MODEL 这类文件中可保留极少“历史背景”到专门历史区，但主段落不要再出现迁移口径。

7. TERMS_FIELD_FREEZE 新增 4 字段  
结论：应补齐，且可直接按现有审计格式冻结。   
建议：managedEntries 现有格式可直接确认冻结。

8. DESIGN_REST_API 状态  
结论：文档级别保持 partially-stable 是正确的。  
建议：文内用端点分组表明确 STABLE 与 EVOLVING，避免“一个状态覆盖全部”。

9. 前端 Transport Abstraction  
结论：不是当前阻塞项，但建议尽早做薄封装，降低后续迁移成本。  
余地：现在做（P1）还是 Tauri 前做。
建议：先抽象 apiPost 与 streamSse 的统一入口，组件层不再直接绑定传输细节。

10. 审计与 work_memo 可能不一致  
结论：确实存在，需要一次性对齐裁决。  
需要讨论：要拍板“以哪份命名与分层为最终文本”。  
建议：做一份“对齐裁决记录”，把冲突点明确写入 repo_memo，再由团队执行，避免双轨口径。
  
若审计建议与权威设计冲突，先改权威文档再改代码，不允许直接按审计文本落地。

参考依据：  
DOCUMENT_GOVERNANCE.md  
DESIGN_GUI_WORKSPACE.md  
DESIGN_REST_API.md  
TERMS_FIELD_FREEZE.md  
2026-05-14_Architecture-Design-Freeze-and-Cleanup.md