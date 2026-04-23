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

# 2026-04-23

- 任务: Phase 1-1 ClaimReference 权威 claim-证据链接模型落地
- 变更文件:
	- src/schemas/claim.py
	- src/schemas/state.py
	- tests/test_claim_reference_schema.py
	- teach/phase1_1_claim_reference_schema_2026_04_23.md
- 变更原因: 在 EvidenceAtom 与后续 HypothesisState / ActionCandidate 之间建立显式、可验证、可追溯的 claim-to-evidence 链接对象；通过严格校验阻断无证据 claim、id 混用和对象自引用。
- 验证方式: `python -m pytest -q tests/test_claim_reference_schema.py` 与 `python -m pytest -q`。

- 任务: Phase 1-1 ClaimReference 语义边界澄清与原子文本约束
- 变更文件:
	- src/schemas/claim.py
	- tests/test_claim_reference_schema.py
	- teach/phase1_1_claim_reference_schema_2026_04_23.md
- 变更原因: 明确 strength 表示 claim-to-target relation 强度（非诊断置信度）；明确 claim_ref_id 与 claim_key 角色分离；为 claim_text 增加 max_length=300 以降低长段解释文本污染结构化状态的风险。
- 验证方式: `python -m pytest -q tests/test_claim_reference_schema.py`。

- 任务: Phase 1-1 HypothesisState 权威候选假设账本模型落地
- 变更文件:
	- src/schemas/hypothesis.py
	- src/schemas/state.py
	- tests/test_hypothesis_state_schema.py
	- teach/phase1_1_hypothesis_state_schema_2026_04_23.md
- 变更原因: 新增 stage-aware 且可追溯的候选假设对象，强制通过 claim_ref_id 分桶关联 supporting/refuting/missing-information 证据主张，避免 direct evidence 引用绕过 ClaimReference，并显式承载 status/confidence/rank/test_hint 以支撑后续阶段化修订。
- 验证方式: `python -m pytest -q tests/test_hypothesis_state_schema.py` 与 `python -m pytest -q`。

- 任务: Phase 1-1 HypothesisState 边界收敛（暂不引入 kind）
- 变更文件:
	- src/schemas/hypothesis.py
	- tests/test_hypothesis_state_schema.py
	- teach/phase1_1_hypothesis_state_schema_2026_04_23.md
- 变更原因: 与 StageContext/EvidenceAtom/ClaimReference 保持当前阶段的一致建模风格，暂不引入判别字段 kind，避免在未进入多类型联合状态容器前提前扩张 schema 表面。
- 验证方式: `python -m pytest -q tests/test_hypothesis_state_schema.py` 与 `python -m pytest -q`。

- 任务: Phase 1-1 HypothesisState 语义去混淆（id/key 分离 + status 重命名）
- 变更文件:
	- src/schemas/hypothesis.py
	- tests/test_hypothesis_state_schema.py
	- teach/phase1_1_hypothesis_state_schema_2026_04_23.md
- 变更原因: 将 hypothesis_id 收敛为对象实例 id，同时新增 hypothesis_key 承载跨阶段语义对齐；将 ACTIVE 替换为 UNDER_CONSIDERATION/PRIORITIZED，避免与疾病活动性语义串线。
- 验证方式: `python -m pytest -q tests/test_hypothesis_state_schema.py` 与 `python -m pytest -q`。

- 任务: Phase 1-1 ActionCandidate 权威候选行动对象模型落地
- 变更文件:
	- src/schemas/action.py
	- src/schemas/state.py
	- tests/test_action_candidate_schema.py
	- teach/phase1_1_action_candidate_schema_2026_04_23.md
- 变更原因: 新增 stage-aware 且 claim-reference-based 的候选行动对象，显式分离 supporting/refuting/missing-information/safety-concern 依据桶，阻断 direct evidence 引用，并通过 blocked 状态约束防止无阻断依据的状态写入。
- 验证方式: `python -m pytest -q tests/test_action_candidate_schema.py` 与 `python -m pytest -q`。

- 任务: Phase 1-1 ActionCandidate 语义轴对齐与概念去重
- 变更文件:
	- src/schemas/action.py
	- tests/test_action_candidate_schema.py
	- teach/phase1_1_action_candidate_schema_2026_04_23.md
- 变更原因: 将 ActionStatus 与 HypothesisStatus 对齐到统一优先级语义轴（under_consideration/prioritized/deprioritized），保留 blocked 作为动作层特有状态；移除与 status 语义冲突的 ActionType defer_pending_information；将 start_or_adjust_treatment_trial 重命名为更中性的 start_or_adjust_treatment，避免过早引入 trial 语义负担。
- 验证方式: `python -m pytest -q tests/test_action_candidate_schema.py` 与 `python -m pytest -q`。

