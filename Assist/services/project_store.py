from __future__ import annotations
import json
import os

from ..models.mapping_rule import MappingMode, MappingRule, MappingRuleSet, CausePairMapping, CauseMapping
from ..models.project_config import ProjectConfig

_PROJECTS_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "projects")
)

# QPR 컬럼 → config.json 키 매핑 (parser.py가 직접 소비하는 구조)
# None 값은 process_hierarchy 배열로 순서대로 처리됨
_QPR_TO_CONFIG_KEY: dict[str, str | None] = {
    "일자":       "date_col",
    "Shift":     "shift_col",
    "대분류":    None,          # → process_hierarchy[0]
    "중분류":    None,          # → process_hierarchy[1]
    "소분류":    None,          # → process_hierarchy[2]
    "설비":      "machine_col",
    "제품":      "product_col",
    "작업자":    "worker_col",
    "계획수량":  "plan_qty_col",
    "실적수량":  "actual_qty_col",
    "작업시간":  "work_time_col",
    "효율":      "efficiency_col",
    "C/T":      "cycle_time_col",
    "비가동":    "downtime_col",
    "비가동시간": "downtime_time_col",
    "부적합":    "nonconformity_col",
    "부적합수량": "nonconformity_qty_col",
    "불량":      "defect_col",
    "불량수량":  "defect_qty_col",
}


_CAUSE_TYPE_TO_FLAT: dict[str, tuple[str, str]] = {
    "비가동": ("비가동", "비가동시간"),
    "부적합": ("부적합", "부적합수량"),
    "불량":   ("불량",   "불량수량"),
}


def _migrate_v1_cause_rules(rules: MappingRuleSet) -> CauseMapping:
    """v1 flat 규칙에서 단일 슬롯 CauseMapping 생성."""
    def _extract(cause_col: str, qty_col: str) -> list[CausePairMapping]:
        cr = rules.get(cause_col)
        qr = rules.get(qty_col)
        cause_src = cr.value if cr and cr.mode == MappingMode.COLUMN else None
        qty_src   = qr.value if qr and qr.mode == MappingMode.COLUMN else None
        if cause_src or qty_src:
            return [CausePairMapping(cause_src=cause_src, qty_src=qty_src)]
        return []

    return CauseMapping(
        downtime=      _extract("비가동", "비가동시간"),
        nonconformity= _extract("부적합", "부적합수량"),
        defect=        _extract("불량",   "불량수량"),
    )


def _rule_to_col_value(rule: MappingRule, rules: MappingRuleSet) -> str | None:
    """
    MappingRule을 config.json이 기대하는 값(원천 컬럼명 또는 리터럴)으로 변환한다.
    - COLUMN  → 원천 컬럼명 그대로 반환
    - DEFAULT → 고정값 반환 (단, __copy_actual__ sentinel은 실적수량 컬럼명으로 치환)
    - BLANK   → None
    """
    if rule.mode == MappingMode.COLUMN:
        return rule.value
    if rule.mode == MappingMode.DEFAULT:
        if rule.value == "__copy_actual__":
            actual_rule = rules.get("실적수량")
            if actual_rule and actual_rule.mode == MappingMode.COLUMN:
                return actual_rule.value
        return rule.value
    return None  # BLANK


class ProjectStore:
    def __init__(self, projects_root: str = _PROJECTS_ROOT):
        self.projects_root = projects_root

    def list_projects(self) -> list[str]:
        if not os.path.isdir(self.projects_root):
            return []
        return sorted(
            d for d in os.listdir(self.projects_root)
            if os.path.isdir(os.path.join(self.projects_root, d))
        )

    def load(self, project_name: str) -> ProjectConfig | None:
        """mapping_rules.json 읽기. 없으면 None 반환."""
        project_dir = os.path.join(self.projects_root, project_name)
        rules_path = os.path.join(project_dir, "mapping_rules.json")

        if not os.path.isfile(rules_path):
            return ProjectConfig(name=project_name, project_dir=project_dir)

        with open(rules_path, encoding="utf-8") as f:
            data = json.load(f)

        version = data.get("version", 1)
        raw_rules: dict = data.get("rules", {})
        rules: MappingRuleSet = {
            col: MappingRule.from_dict(r) for col, r in raw_rules.items()
        }
        if version >= 2 and "cause_mapping" in data:
            cause_mapping = CauseMapping.from_dict(data["cause_mapping"])
        else:
            cause_mapping = _migrate_v1_cause_rules(rules)
        return ProjectConfig(name=project_name, project_dir=project_dir,
                             rules=rules, cause_mapping=cause_mapping)

    def save(self, config: ProjectConfig) -> None:
        """mapping_rules.json 저장. output/ 폴더도 생성."""
        os.makedirs(config.project_dir, exist_ok=True)
        os.makedirs(config.output_dir(), exist_ok=True)

        # v2: 요인 6개 컬럼은 cause_mapping으로 관리 — rules에서 blank로 강제
        _CAUSE_COLS = {"비가동", "비가동시간", "부적합", "부적합수량", "불량", "불량수량"}
        rules_out = {
            col: (MappingRule.make_blank().to_dict() if col in _CAUSE_COLS else rule.to_dict())
            for col, rule in config.rules.items()
        }
        data = {
            "version": 2,
            "rules": rules_out,
            "cause_mapping": config.cause_mapping.to_dict(),
        }
        with open(config.mapping_rules_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_config(
        self,
        config: ProjectConfig,
        qpr_output_path: str,
        delimiter: str = ",",
    ) -> None:
        """
        QPR 생성 직후 호출. parser.py가 직접 소비할 수 있는 config.json을 생성한다.
        구조는 projects/Project_A/config.json 과 동일 (§8.1).
        """
        rules = config.rules
        cm = config.cause_mapping

        def _cause_src(cause_type: str) -> str | None:
            pairs = cm.get_pairs(cause_type)
            return pairs[0].cause_src if pairs else None

        def _qty_src(cause_type: str) -> str | None:
            pairs = cm.get_pairs(cause_type)
            return pairs[0].qty_src if pairs else None

        process_hierarchy: list[str | None] = []
        flat: dict[str, str | None] = {}

        _CAUSE_OVERRIDES: dict[str, str | None] = {
            "downtime_col":          _cause_src("비가동"),
            "downtime_time_col":     _qty_src("비가동"),
            "nonconformity_col":     _cause_src("부적합"),
            "nonconformity_qty_col": _qty_src("부적합"),
            "defect_col":            _cause_src("불량"),
            "defect_qty_col":        _qty_src("불량"),
        }

        for qpr_col, config_key in _QPR_TO_CONFIG_KEY.items():
            if config_key in _CAUSE_OVERRIDES:
                flat[config_key] = _CAUSE_OVERRIDES[config_key]
                continue
            rule = rules.get(qpr_col)
            value = _rule_to_col_value(rule, rules) if rule else None
            if config_key is None:
                process_hierarchy.append(value)
            else:
                flat[config_key] = value

        # Project_A/config.json 과 동일한 키 순서로 출력
        data: dict = {
            "delimiter":             delimiter,
            "date_col":              flat.get("date_col"),
            "shift_col":             flat.get("shift_col"),
            "process_hierarchy":     process_hierarchy,
            "machine_col":           flat.get("machine_col"),
            "product_col":           flat.get("product_col"),
            "worker_col":            flat.get("worker_col"),
            "plan_qty_col":          flat.get("plan_qty_col"),
            "actual_qty_col":        flat.get("actual_qty_col"),
            "work_time_col":         flat.get("work_time_col"),
            "efficiency_col":        flat.get("efficiency_col"),
            "cycle_time_col":        flat.get("cycle_time_col"),
            "downtime_col":          flat.get("downtime_col"),
            "downtime_time_col":     flat.get("downtime_time_col"),
            "nonconformity_col":     flat.get("nonconformity_col"),
            "nonconformity_qty_col": flat.get("nonconformity_qty_col"),
            "defect_col":            flat.get("defect_col"),
            "defect_qty_col":        flat.get("defect_qty_col"),
        }

        os.makedirs(config.project_dir, exist_ok=True)
        with open(config.config_json_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def output_path(self, project_name: str, source_filename: str) -> str:
        stem = os.path.splitext(os.path.basename(source_filename))[0]
        project_dir = os.path.join(self.projects_root, project_name)
        return os.path.join(project_dir, "output", f"{stem}_qpr.csv")

    def create_project(self, project_name: str) -> ProjectConfig:
        project_dir = os.path.join(self.projects_root, project_name)
        os.makedirs(project_dir, exist_ok=True)
        return ProjectConfig(name=project_name, project_dir=project_dir)
