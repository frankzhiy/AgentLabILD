"""ILD 病例数据结构

嵌套结构对应 assets/case_schema.json，覆盖 ILD-MDT 所需的全部临床信息维度。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════
# 1. Basic Clinical Background
# ══════════════════════════════════════════════════════════════

class SmokingHistory(BaseModel):
    smoking_status: str | None = None
    smoking_description: str | None = None

class OccupationalHistory(BaseModel):
    occupation: str | None = None
    description_of_occupational_exposure: str | None = None

class EnvironmentalAndAntigenExposureHistory(BaseModel):
    bird_or_poultry_exposure: str | None = None
    mold_or_damp_environment_exposure: str | None = None
    dust_exposure: str | None = None
    pet_contact: str | None = None
    recent_renovation_or_move_to_a_new_home: str | None = None
    other_suspected_exposures: str | None = None

class PastSignificantMedicalHistory(BaseModel):
    hypertension: str | None = None
    diabetes_mellitus: str | None = None
    coronary_artery_disease_or_cardiovascular_disease: str | None = None
    previous_pulmonary_diseases: str | None = None
    previous_rheumatic_or_autoimmune_diseases: str | None = None
    other_significant_medical_history: str | None = None

class RelevantFamilyHistory(BaseModel):
    family_history_of_pulmonary_disease: str | None = None
    family_history_of_rheumatic_or_autoimmune_disease: str | None = None
    other_relevant_family_history: str | None = None

class BasicClinicalBackground(BaseModel):
    age: str | None = None
    sex: str | None = None
    smoking_history: SmokingHistory | None = None
    occupational_history: OccupationalHistory | None = None
    environmental_and_antigen_exposure_history: EnvironmentalAndAntigenExposureHistory | None = None
    past_significant_medical_history: PastSignificantMedicalHistory | None = None
    relevant_family_history: RelevantFamilyHistory | None = None


# ══════════════════════════════════════════════════════════════
# 2. Symptoms and Disease Course
# ══════════════════════════════════════════════════════════════

class RespiratorySymptoms(BaseModel):
    cough: str | None = None
    sputum_production: str | None = None
    chest_tightness: str | None = None
    shortness_of_breath_or_dyspnea: str | None = None
    chest_pain: str | None = None
    hemoptysis: str | None = None
    fever: str | None = None

class ExtrapulmonaryManifestations(BaseModel):
    dry_mouth_or_dry_eyes: str | None = None
    joint_pain_or_morning_stiffness: str | None = None
    myalgia_or_muscle_weakness: str | None = None
    raynaud_phenomenon: str | None = None
    skin_rash: str | None = None
    mechanics_hands_or_gottrons_sign_and_other_myositis_related_manifestations: str | None = None
    other_extrapulmonary_manifestations: str | None = None

class CourseCharacteristics(BaseModel):
    onset_pattern: str | None = None
    progressive_worsening: str | None = None
    acute_exacerbation: str | None = None
    summary_of_present_illness: str | None = None

class SymptomsAndDiseaseCourse(BaseModel):
    chief_complaint: str | None = None
    respiratory_symptoms: RespiratorySymptoms | None = None
    extrapulmonary_manifestations: ExtrapulmonaryManifestations | None = None
    course_characteristics: CourseCharacteristics | None = None


# ══════════════════════════════════════════════════════════════
# 3. Autoimmune-Related Clues
# ══════════════════════════════════════════════════════════════

class SerologicTests(BaseModel):
    ana: str | None = Field(None, alias="ANA")
    ena_or_autoantibody_panel: str | None = None
    anca_and_related_antibodies: str | None = None
    rf_or_ccp: str | None = None
    myositis_antibody_panel: str | None = None
    complement_or_immunoglobulins: str | None = None
    other_immunologic_tests: str | None = None

    model_config = {"populate_by_name": True}

class AutoimmuneRelatedClues(BaseModel):
    summary_of_clinical_clues: str | None = None
    serologic_tests: SerologicTests | None = None
    evidence_supporting_a_definite_connective_tissue_disease: str | None = None
    rheumatologic_or_autoimmune_tendency: str | None = None


# ══════════════════════════════════════════════════════════════
# 4. Imaging
# ══════════════════════════════════════════════════════════════

class KeyImagingFindings(BaseModel):
    reticulation: str | None = None
    ground_glass_opacity: str | None = None
    honeycombing: str | None = None
    traction_bronchiectasis: str | None = None
    consolidation: str | None = None
    nodules: str | None = None
    mosaic_attenuation_or_air_trapping: str | None = None
    pleural_effusion: str | None = None
    mediastinal_or_hilar_lymph_nodes: str | None = None
    other_important_findings: str | None = None

class ImagingPatternTendency(BaseModel):
    uip_pattern_tendency: str | None = None
    nsip_pattern_tendency: str | None = None
    op_pattern_tendency: str | None = None
    hp_pattern_tendency: str | None = None
    other_patterns_or_atypical_findings: str | None = None

class Imaging(BaseModel):
    summary_of_chest_ct_or_hrct: str | None = None
    distribution_of_lesions: str | None = None
    key_imaging_findings: KeyImagingFindings | None = None
    imaging_pattern_tendency: ImagingPatternTendency | None = None


# ══════════════════════════════════════════════════════════════
# 5. Pulmonary Function and Oxygenation
# ══════════════════════════════════════════════════════════════

class PulmonaryFunctionSummary(BaseModel):
    ventilatory_function: str | None = None
    diffusion_function: str | None = None
    lung_volumes_or_other_results: str | None = None

class HypoxemiaAndRespiratorySupport(BaseModel):
    presence_of_hypoxemia: str | None = None
    summary_of_blood_gas_analysis: str | None = None
    summary_of_oxygenation_status: str | None = None
    presence_of_respiratory_failure: str | None = None
    oxygen_therapy_or_respiratory_support_modality: str | None = None

class PulmonaryFunctionAndOxygenation(BaseModel):
    pulmonary_function_summary: PulmonaryFunctionSummary | None = None
    hypoxemia_and_respiratory_support: HypoxemiaAndRespiratorySupport | None = None


# ══════════════════════════════════════════════════════════════
# 6. Laboratory and Other Ancillary Examinations
# ══════════════════════════════════════════════════════════════

class InflammationAndInfectionRelatedFindings(BaseModel):
    complete_blood_count_summary: str | None = None
    crp_esr_pct_il6_etc: str | None = None
    microbiological_tests: str | None = None
    viral_or_fungal_related_tests: str | None = None
    other_infectious_clues: str | None = None

class BiochemistryAndOrganFunction(BaseModel):
    liver_and_renal_function: str | None = None
    albumin: str | None = None
    cardiac_biomarkers_or_nt_probnp: str | None = None
    d_dimer: str | None = None
    other_important_results: str | None = None

class CardiacAndVascularAssessment(BaseModel):
    echocardiography_summary: str | None = None
    clues_suggestive_of_pulmonary_hypertension: str | None = None
    clues_suggestive_of_pulmonary_embolism: str | None = None
    other_circulatory_system_assessments: str | None = None

class LaboratoryAndOtherAncillaryExaminations(BaseModel):
    inflammation_and_infection_related_findings: InflammationAndInfectionRelatedFindings | None = None
    biochemistry_and_organ_function: BiochemistryAndOrganFunction | None = None
    cardiac_and_vascular_assessment: CardiacAndVascularAssessment | None = None


# ══════════════════════════════════════════════════════════════
# 7. BAL, Pathology, and Other Key Evidence
# ══════════════════════════════════════════════════════════════

class BALPathologyAndOtherKeyEvidence(BaseModel):
    bronchoscopy_summary: str | None = None
    bal_results_summary: str | None = None
    pathology_summary: str | None = None
    other_key_evidence_helpful_for_classification: str | None = None


# ══════════════════════════════════════════════════════════════
# 8. Integrated Clinical Assessment
# ══════════════════════════════════════════════════════════════

class EtiologicOrClassificationTendency(BaseModel):
    ctd_ild_tendency: str | None = None
    ipf_or_other_iip_tendency: str | None = None
    hp_tendency: str | None = None
    op_tendency: str | None = None
    infection_or_other_alternative_explanations: str | None = None
    possibility_of_unclassifiable_ild: str | None = None

class IntegratedClinicalAssessment(BaseModel):
    whether_fibrotic_ild_is_present: str | None = None
    etiologic_or_classification_tendency: EtiologicOrClassificationTendency | None = None
    current_major_comorbid_or_concurrent_problems: list[str] | None = None
    current_clinical_diagnosis_or_preliminary_diagnosis: list[str] | None = None


# ══════════════════════════════════════════════════════════════
# 9. Treatment Course and Response
# ══════════════════════════════════════════════════════════════

class MainTreatmentsDuringThisHospitalization(BaseModel):
    anti_infective_treatment: str | None = None
    glucocorticoid_treatment: str | None = None
    immunosuppressive_treatment: str | None = None
    antifibrotic_treatment: str | None = None
    anticoagulation_treatment: str | None = None
    oxygen_therapy_or_respiratory_support: str | None = None
    other_treatments: str | None = None

class TreatmentCourseAndResponse(BaseModel):
    previous_main_treatments: str | None = None
    main_treatments_during_this_hospitalization: MainTreatmentsDuringThisHospitalization | None = None
    changes_after_treatment: str | None = None
    current_disease_status: str | None = None


# ══════════════════════════════════════════════════════════════
# 顶层：CaseData
# ══════════════════════════════════════════════════════════════

class CaseData(BaseModel):
    """一个 ILD 病例的完整结构化数据，与 assets/case_schema.json 对齐。

    各板块均为可选——并非每个病例都有完整信息。
    case_id 为必填字段，用于唯一标识病例。
    """

    case_id: str = Field(..., description="病例唯一标识")

    basic_clinical_background: BasicClinicalBackground | None = None
    symptoms_and_disease_course: SymptomsAndDiseaseCourse | None = None
    autoimmune_related_clues: AutoimmuneRelatedClues | None = None
    imaging: Imaging | None = None
    pulmonary_function_and_oxygenation: PulmonaryFunctionAndOxygenation | None = None
    laboratory_and_other_ancillary_examinations: LaboratoryAndOtherAncillaryExaminations | None = None
    bal_pathology_and_other_key_evidence: BALPathologyAndOtherKeyEvidence | None = None
    integrated_clinical_assessment: IntegratedClinicalAssessment | None = None
    treatment_course_and_response: TreatmentCourseAndResponse | None = None

    def to_text(self) -> str:
        """递归遍历所有非空字段，生成可读的 Markdown 格式文本"""
        lines: list[str] = [f"# Case {self.case_id}"]
        section_labels = {
            "basic_clinical_background": "Basic Clinical Background",
            "symptoms_and_disease_course": "Symptoms and Disease Course",
            "autoimmune_related_clues": "Autoimmune-Related Clues",
            "imaging": "Imaging",
            "pulmonary_function_and_oxygenation": "Pulmonary Function and Oxygenation",
            "laboratory_and_other_ancillary_examinations": "Laboratory and Other Ancillary Examinations",
            "bal_pathology_and_other_key_evidence": "BAL, Pathology, and Other Key Evidence",
            "integrated_clinical_assessment": "Integrated Clinical Assessment",
            "treatment_course_and_response": "Treatment Course and Response",
        }
        for field_name, label in section_labels.items():
            section = getattr(self, field_name)
            if section is not None:
                section_text = self._section_to_text(section, depth=2)
                if section_text:
                    lines.append(f"\n## {label}")
                    lines.append(section_text)
        return "\n".join(lines)

    @staticmethod
    def _section_to_text(obj: BaseModel, depth: int) -> str:
        """将嵌套的 Pydantic 模型递归转为可读文本"""
        parts: list[str] = []
        prefix = "#" * (depth + 1)
        for name, field_info in obj.__class__.model_fields.items():
            value = getattr(obj, name)
            if value is None:
                continue
            label = name.replace("_", " ").title()
            if isinstance(value, BaseModel):
                sub = CaseData._section_to_text(value, depth + 1)
                if sub:
                    parts.append(f"{prefix} {label}")
                    parts.append(sub)
            elif isinstance(value, list):
                non_empty = [v for v in value if v]
                if non_empty:
                    parts.append(f"- **{label}**: {'; '.join(str(v) for v in non_empty)}")
            else:
                parts.append(f"- **{label}**: {value}")
        return "\n".join(parts)


class GroundTruth(BaseModel):
    """金标准诊断"""

    case_id: str
    diagnosis: str = Field(..., description="MDT 共识诊断亚型")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="诊断置信度")
    treatment_direction: str | None = None
    reasoning: str | None = Field(None, description="诊断理由简述")
