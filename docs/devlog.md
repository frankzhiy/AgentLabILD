# 2026-04-22

- 任务: Phase 1-1 StageContext 显式阶段上下文模型落地
- 变更文件:
	- src/schemas/stage.py
	- src/schemas/state.py
	- tests/test_stage_context.py
	- teach/phase1_1_stage_context_schema.md
- 变更原因: 将阶段边界从占位状态提升为可验证的 Pydantic typed schema，明确阶段可见性与上下文边界，并避免诊断/证据对象混入阶段对象。
- 验证方式: `python -m pytest -q`（新增 StageContext 构造、枚举校验、父阶段规则、非权威备注行为、序列化回环测试）。

- 任务: Phase 1-1 StageContext 语义细化（TriggerType 与 InfoModality）
- 变更文件:
	- src/schemas/stage.py
	- tests/test_stage_context.py
	- teach/phase1_1_stage_context_refinement_2026_04_22.md
- 变更原因: 将触发器细化到临床事件级别，将模态从文档导向改为临床语义导向；并将“非 initial 必须 parent”从 schema 层下沉到后续 validator/gate。
- 验证方式: `python -m pytest -q`。

- 任务: Phase 1-1 StageContext 本体边界细化（focus/question/visibility 解耦）
- 变更文件:
	- src/schemas/stage.py
	- tests/test_stage_context.py
	- teach/phase1_1_stage_context_ontology_boundary_refinement_2026_04_22.md
- 变更原因: 保持“一字段一语义维度”，将 StageFocus 收敛为阶段运营焦点；新增 clinical_question_tags 承载病例特异问题标签；将 VisibilityPolicyHint 收敛为纯可见性语义。
- 验证方式: `python -m pytest -q`（13 passed）。

- 任务: Phase 1-1 EvidenceAtom 最小权威证据原子模型落地
- 变更文件:
	- src/schemas/evidence.py
	- src/schemas/state.py
	- tests/test_evidence_schema.py
	- teach/phase1_1_evidence_atom_schema_2026_04_22.md
- 变更原因: 为分阶段 ILD-MDT 推理提供最小、可追溯、可验证的证据事实原子对象，明确证据层边界并避免诊断/行动逻辑混入。
- 验证方式: `python -m pytest -q`（25 passed）。

- 任务: Phase 1-1 EvidenceAtom 语义重构与一致性校验强化
- 变更文件:
	- src/schemas/evidence.py
	- tests/test_evidence_schema.py
	- teach/phase1_1_evidence_atom_semantic_refinement_2026_04_22.md
- 变更原因: 将 id 防混用逻辑从“三字段不得相等”改为命名模式校验；将 category/certainty/temporality/subject 调整为更一致的临床语义分层；新增 category-modality 一致性校验，防止语义冲突对象进入状态层。
- 验证方式: `python -m pytest -q`（32 passed）。

