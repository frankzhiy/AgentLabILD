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

- 任务: Phase 1-1 HypothesisBoardInit 阶段作用域 board 根对象落地
- 变更文件:
	- src/schemas/board.py
	- src/schemas/state.py
	- tests/test_hypothesis_board_init.py
	- teach/phase1_1_hypothesis_board_init_schema_2026_04_23.md
- 变更原因: 增加轻量、stage-aware 的 board 初始化根对象，明确 board 对 evidence/hypothesis/action 的 id-only 引用边界，并通过结构化校验阻断空 hypothesis 集合、非法排序子集与自引用 parent_board 关系。
- 验证方式: `python -m pytest -q tests/test_hypothesis_board_init.py` 与 `python -m pytest -q`。

- 任务: Phase 1-1 HypothesisBoardInit 约束强化（case_id + 生命周期 + source-parent 联动）
- 变更文件:
	- src/schemas/board.py
	- tests/test_hypothesis_board_init.py
	- teach/phase1_1_hypothesis_board_init_schema_2026_04_23.md
- 变更原因: 补齐 board root 的 id 约束对称性（新增 case_id pattern），将 BoardStatus 扩展为最小生命周期集合，并新增 init_source 与 parent_board_id 的跨字段一致性校验，避免阶段演化语义漂移。
- 验证方式: `python -m pytest -q tests/test_hypothesis_board_init.py` 与 `python -m pytest -q`。

- 任务: Phase 1-1 StateValidationReport 与 Phase1StateEnvelope 根状态封装落地
- 变更文件:
	- src/schemas/common.py
	- src/schemas/validation.py
	- src/schemas/state.py
	- tests/test_phase1_state_envelope.py
	- docs/devlog.md
	- teach/phase1_1_state_envelope_validation_report_2026_04_23.md
- 变更原因: 在 Phase 1-1 收口阶段补齐“结构化校验报告对象 + 根状态封装对象”，并在 envelope 层实现 stage_id 对齐、重复 id、缺失 claim/evidence 引用、ranked hypothesis 存在性等一致性校验，确保状态写入前具备可审计的机制边界。
- 验证方式: `python -m pytest -q tests/test_phase1_state_envelope.py` 与 `python -m pytest -q`（本次运行结果：10 passed / 109 passed）。

- 任务: Phase 1-1 Direction A 语义收敛（ValidationIssue/StateValidationReport/common/envelope）
- 变更文件:
	- src/schemas/common.py
	- src/schemas/validation.py
	- src/schemas/state.py
	- src/schemas/stage.py
	- src/schemas/evidence.py
	- src/schemas/claim.py
	- src/schemas/hypothesis.py
	- src/schemas/action.py
	- src/schemas/board.py
	- tests/test_phase1_state_envelope.py
	- tests/test_stage_context.py
	- tests/test_evidence_schema.py
	- tests/test_claim_reference_schema.py
	- tests/test_hypothesis_state_schema.py
	- tests/test_action_candidate_schema.py
	- tests/test_hypothesis_board_init.py
	- teach/phase1_1_direction_a_validation_refinement_2026_04_23.md
- 变更原因: 按 Direction A 消除语义错位（envelope 仍做硬结构校验并抛异常，validation_report 变为可选外部报告），并将 ValidationIssue/StateValidationReport 扩展为 target-aware、blocking-aware、stage/case identity-aware 的可审计结构；同时以最小改动为主要对象加入固定 kind 自描述标签。
- 验证方式: `python -m pytest -q tests/test_phase1_state_envelope.py tests/test_stage_context.py tests/test_evidence_schema.py tests/test_claim_reference_schema.py tests/test_hypothesis_state_schema.py tests/test_action_candidate_schema.py tests/test_hypothesis_board_init.py`（116 passed）；`python -m pytest -q`（118 passed）。

- 任务: Phase 1-1 状态层结构闭环修复（claim 双向绑定 + board 集合闭环 + state_id）
- 变更文件:
	- src/schemas/common.py
	- src/schemas/stage.py
	- src/schemas/evidence.py
	- src/schemas/claim.py
	- src/schemas/hypothesis.py
	- src/schemas/action.py
	- src/schemas/board.py
	- src/schemas/validation.py
	- src/schemas/state.py
	- tests/test_claim_reference_schema.py
	- tests/test_phase1_state_envelope.py
	- tests/test_common_id_patterns.py
	- teach/phase1_1_structural_closure_refinement_2026_04_23.md
- 变更原因: 修复 Phase1StateEnvelope 在结构关系上的单向校验缺口，新增 claim_ref 使用方与 ClaimReference 目标回指的一致性校验；将 board_init 三组 id 与 envelope 实体集合做闭环一致性校验；新增 ActionCandidate.linked_hypothesis_ids 的实体存在性校验；补齐 state_id 并增加 parent_state_id 自环阻断；同时集中并复用核心 id pattern，降低规则分散带来的漂移风险。
- 验证方式: `python -m pytest -q tests/test_claim_reference_schema.py tests/test_phase1_state_envelope.py tests/test_common_id_patterns.py`（51 passed）；`python -m pytest -q`（144 passed）。

- 任务: Phase 1-2 provenance 包（PROV-lite）落地与兼容挂接
- 变更文件:
	- src/provenance/model.py
	- src/provenance/__init__.py
	- src/schemas/evidence.py
	- src/schemas/claim.py
	- tests/test_provenance_model.py
	- docs/devlog.md
	- teach/phase1_2_provenance_package_2026_04_23.md
- 变更原因: 在不重构现有 EvidenceAtom/ClaimReference 主体结构的前提下，新增最小 provenance 机制对象（SourceAnchor、ExtractionActivity、EvidenceProvenance、ClaimProvenance），并通过可选字段挂接实现向后兼容，避免 free-text provenance blob，强化 stage-aware 可追溯性。
- 验证方式: `python -m pytest -q tests/test_provenance_model.py tests/test_evidence_schema.py tests/test_claim_reference_schema.py`（46 passed）；`python -m pytest -q`（158 passed）。

- 任务: Phase 1-2 provenance checking（checker + validator）
- 变更文件:
	- src/provenance/checker.py
	- src/validators/provenance_validator.py
	- src/validators/__init__.py
	- tests/test_provenance_checker.py
	- tests/test_provenance_validator.py
	- docs/devlog.md
	- teach/phase1_2_provenance_checking_2026_04_23.md
- 变更原因: 新增外部机制化 provenance 检查链路，覆盖 source span 完整性与顺序、stage/case 对齐、source_doc 可见性、claim provenance 与 ClaimReference.evidence_ids 一致性、orphan/missing provenance，并输出可直接转换为 StateValidationReport 的结构化 issue；保持 schema 与 pipeline 语义不变。
- 验证方式: `python -m pytest -q tests/test_provenance_checker.py tests/test_provenance_validator.py`（13 passed）；`python -m pytest -q`（全量回归通过）。

- 任务: Phase 1-2 EvidenceAtom flat source 与 EvidenceProvenance 权威源收敛
- 变更文件:
	- src/schemas/evidence.py
	- src/provenance/checker.py
	- tests/test_provenance_checker.py
	- tests/test_provenance_validator.py
	- docs/devlog.md
	- teach/phase1_2_evidence_provenance_authority_rule_2026_04_23.md
- 变更原因: 修复 EvidenceAtom flat source 字段与 EvidenceProvenance 并存造成的双权威风险，明确 authority rule（provenance 缺失时保留 legacy flat 模式；provenance 存在时以 provenance 为权威，flat 字段仅兼容镜像），并在 checker 中新增显式对齐检查（不自动修复、不变异状态）。
- 验证方式: `python -m pytest -q tests/test_provenance_checker.py tests/test_provenance_validator.py`（21 passed）；`python -m pytest -q`（179 passed）。

- 任务: Phase 1-2 provenance checker 四文件结构拆分（行为保持）
- 变更文件:
	- src/provenance/issues.py
	- src/provenance/evidence_checks.py
	- src/provenance/claim_checks.py
	- src/provenance/checker.py
	- docs/devlog.md
	- teach/phase1_2_provenance_checker_structural_split_2026_04_23.md
- 变更原因: 将 monolithic provenance checker 进行职责拆分（issue 定义、evidence 检查、claim 检查、编排器），在不改变 issue_code、blocking 语义、兼容模式和公共 validator 行为的前提下提升模块边界清晰度。
- 验证方式: `python -m pytest -q tests/test_provenance_checker.py tests/test_provenance_validator.py`（21 passed）；`python -m pytest -q`（179 passed）。

- 任务: Phase 1-3 write-gate contract layer（WriteDecisionStatus / WritePolicy / WriteDecision）
- 变更文件:
	- src/state/write_status.py
	- src/state/write_policy.py
	- src/state/write_decision.py
	- src/state/__init__.py
	- tests/test_write_contracts.py
	- docs/devlog.md
	- teach/phase1_3_write_gate_contract_layer_2026_04_23.md
- 变更原因: 启动 Phase 1-3，补齐 validator-gated state write 的核心合同对象，明确 accepted/rejected/manual_review 判定、策略化 should_persist 计算与阻断语义；保持 Direction A 不变（envelope 结构失败仍为硬失败，外部 validator 继续输出 StateValidationReport）。
- 验证方式: `python -m pytest -q tests/test_write_contracts.py tests/test_phase1_state_envelope.py tests/test_provenance_validator.py`。

# 2026-04-27

- 任务: Phase 1-3 Issue 2（Phase1StateEnvelope schema validator + conservative temporal validator）
- 变更文件:
	- src/validators/schema_validator.py
	- src/validators/temporal_validator.py
	- src/validators/__init__.py
	- tests/test_schema_validator.py
	- tests/test_temporal_validator.py
	- docs/devlog.md
	- teach/phase1_3_schema_temporal_validators_2026_04_27.md
- 变更原因: 将 Phase 1 结构校验能力从模型构造异常外化为可复用 `StateValidationReport` 机制模块，并新增 Phase 1-3 范围内保守时序校验，为后续 write-gate 组合验证做准备；本次不引入 pipeline/writer/event-log/unsupported-claim 逻辑，保持 Direction A 现状。
- 验证方式: `python -m pytest -q tests/test_schema_validator.py tests/test_temporal_validator.py tests/test_provenance_validator.py`。

- 任务: Phase 1-3 validator hardening（统一时间源 + model_error 判定稳健化 + fallback id 收口）
- 变更文件:
	- src/utils/__init__.py
	- src/utils/time.py
	- src/validators/constants.py
	- src/validators/schema_validator.py
	- src/validators/temporal_validator.py
	- src/validators/provenance_validator.py
	- tests/test_schema_validator.py
	- tests/test_temporal_validator.py
	- tests/test_provenance_validator.py
	- docs/devlog.md
	- teach/phase1_3_validator_hardening_2026_04_27.md
- 变更原因: 避免 `datetime.utcnow()` 继续扩散，新增统一 `utc_now()` 以降低后续 naive/aware 时间策略切换成本；将 schema validator 的 fallback id 迁移到共享常量，降低未来 id pattern 调整导致 report 构造失败的风险；放宽 `schema.model_error` 识别规则并增加回归测试，降低 model_validator 一致性错误被误分为 field_error 的概率。
- 验证方式: `python -m pytest -q tests/test_schema_validator.py tests/test_temporal_validator.py tests/test_provenance_validator.py tests/test_phase1_state_envelope.py`（45 passed）。

- 任务: Phase 1-3 Issue 3（conservative unsupported-claim validator for Phase1StateEnvelope）
- 变更文件:
	- src/validators/unsupported_claims.py
	- src/validators/__init__.py
	- tests/test_unsupported_claims.py
	- docs/devlog.md
	- teach/phase1_3_unsupported_claim_validator_2026_04_27.md
- 变更原因: 新增独立可执行的 unsupported-claim 机制校验器，在不引入 LLM/NLI/指南推理的前提下，对 claim 的“缺失证据引用、不可用证据引用、target 绑定失效”进行阻断式结构化报告，并对“强 claim 仅由弱/不确定/reported 证据支撑”输出非阻断 warning，满足 Direction A 的可审计与确定性要求；同时明确 `invalid_target_binding`/`missing_evidence_reference` 属于 claim-level review lens（不是 envelope closure 替代），并把 evidence 可用性判定拆为 policy hook（默认 `strict_current_stage_only`，预留历史权威证据模式）。
- 验证方式: `python -m pytest -q tests/test_unsupported_claims.py tests/test_schema_validator.py tests/test_temporal_validator.py tests/test_provenance_validator.py`。

- 任务: Phase 1-3 Issue 4（unified validation pipeline for Phase1StateEnvelope candidate）
- 变更文件:
	- src/validators/pipeline.py
	- src/validators/__init__.py
	- tests/test_validation_pipeline.py
	- docs/devlog.md
	- teach/phase1_3_validation_pipeline_2026_04_27.md
- 变更原因: 新增统一 validator 编排层，按固定顺序执行 schema/provenance/temporal/unsupported_claim，并在 schema 失败时短路下游校验；输出结构化 pipeline 结果（candidate_envelope、ordered reports、has_blocking_issue、summary、execution_order）用于后续 state writer 接入，同时明确该模块仅做验证编排，不承担持久化或 accept/reject 写入行为。
- 验证方式: `python -m pytest -q tests/test_validation_pipeline.py tests/test_schema_validator.py tests/test_provenance_validator.py tests/test_temporal_validator.py tests/test_unsupported_claims.py tests/test_write_contracts.py`（48 passed）。

- 任务: Phase 1-3 Issue 4 refinement（candidate identity + schema-first raw flow + policy hook）
- 变更文件:
	- src/validators/pipeline.py
	- src/validators/__init__.py
	- tests/test_validation_pipeline.py
	- teach/phase1_3_validation_pipeline_2026_04_27.md
	- docs/devlog.md
- 变更原因: 为对齐下一步 writer 边界，给 pipeline result 增加稳定 `candidate_state_id`（即使 schema-only 分支也可用）；将 raw payload 处理改为 schema-first 路径，消除 schema fail 场景中的重复 envelope 构造；新增 `ValidationPipelinePolicy` 作为策略收敛入口，避免后续继续扩张裸参数签名。
- 验证方式: `python -m pytest -q tests/test_validation_pipeline.py tests/test_schema_validator.py tests/test_provenance_validator.py tests/test_temporal_validator.py tests/test_unsupported_claims.py tests/test_write_contracts.py`。

- 任务: Phase 1-3 Issue 5（validator-gated state writer layer + sinks）
- 变更文件:
	- src/state/sinks.py
	- src/state/state_writer.py
	- src/state/__init__.py
	- tests/test_state_writer.py
	- docs/devlog.md
	- teach/phase1_3_state_writer_gate_2026_04_27.md
- 变更原因: 在既有 write contracts 与 validation pipeline 之上新增真实 write gate 路径：`candidate -> validation pipeline -> WriteDecision -> optional sink persistence`；并通过 `StateSink` 抽象提供 `NoOpStateSink`/`InMemoryStateSink`，确保仅在 `should_persist=True` 且存在 `accepted_envelope` 时持久化；保持非修复式、非事件源、非数据库集成的 Phase 1-3 边界。
- 验证方式: `python -m pytest -q tests/test_state_writer.py tests/test_write_contracts.py tests/test_validation_pipeline.py tests/test_skeleton_imports.py`（30 passed）。

- 任务: Phase 1-3 Issue 5 refinement（write-gate 语义收紧）
- 变更文件:
	- src/state/write_policy.py
	- src/state/write_decision.py
	- src/state/state_writer.py
	- src/state/sinks.py
	- tests/test_write_contracts.py
	- tests/test_state_writer.py
	- docs/devlog.md
	- teach/phase1_3_write_gate_semantic_tightening_2026_04_27.md
- 变更原因: 将 write-gate 进一步收敛为保守权威语义：manual_review 永不持久化；`accepted_envelope` 仅允许在 `ACCEPTED` 决策中存在；保持 sink 持久化异常向上抛出；并明确 `WriteDecision` 表达的是 validation-gate 判定结果而非持久化成功保证；同时澄清 `NoOpStateSink` 为“接收 persist 调用后丢弃状态”。
- 验证方式: `python -m pytest -q tests/test_write_contracts.py tests/test_state_writer.py tests/test_validation_pipeline.py tests/test_skeleton_imports.py`。

- 任务: Phase 1 raw-text intake layer（RawInputEvent / SourceDocument / source-evidence alignment）
- 变更文件:
	- src/schemas/intake.py
	- src/schemas/__init__.py
	- src/intake/__init__.py
	- src/intake/registry.py
	- src/intake/validators.py
	- src/intake/intake_gate.py
	- src/validators/provenance_validator.py
	- src/validators/__init__.py
	- tests/test_intake_schemas.py
	- tests/test_intake_gate.py
	- tests/test_source_document_evidence_alignment.py
	- teach/phase1_raw_text_intake_layer_2026_04_27.md
	- docs/devlog.md
- 变更原因: 在 authoritative Phase1StateEnvelope 写入前新增显式 raw intake 层，将外部自由文本先登记为 RawInputEvent，再固化为可引用 SourceDocument，并提供 source/evidence 对齐桥接校验，阻断 raw free-text 直接写入权威状态；同时明确“输入事件 != 临床阶段”，append/correction/replacement 不自动等于新 StageContext。
- 验证方式: `python -m pytest -q tests/test_intake_schemas.py tests/test_intake_gate.py tests/test_source_document_evidence_alignment.py`。
- 边界说明: 本次未重写 `Phase1StateEnvelope`，未改写 `attempt_phase1_write` 行为，仅新增前置 intake 与桥接校验能力。

