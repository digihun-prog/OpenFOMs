from __future__ import annotations
from dataclasses import dataclass

from ..models.qpr_schema import (
    QPR_COLUMNS, MANDATORY_COLUMNS, COLUMN_DEFAULTS, CAUSE_COLUMNS
)
from ..models.mapping_rule import MappingMode, MappingRule, MappingRuleSet


@dataclass
class ValidationError:
    qpr_col: str
    message: str
    severity: str  # "error" | "warning"


class MappingService:
    def __init__(self, source_headers: list[str]):
        self.source_headers = source_headers

    def make_default_ruleset(self) -> MappingRuleSet:
        """QPR 19개 컬럼을 기본 규칙으로 초기화."""
        ruleset: MappingRuleSet = {}
        for col in QPR_COLUMNS:
            if col in MANDATORY_COLUMNS:
                ruleset[col] = MappingRule.make_blank()
            elif col in COLUMN_DEFAULTS:
                default_val = COLUMN_DEFAULTS[col]
                if default_val is None:
                    ruleset[col] = MappingRule.make_blank()
                else:
                    ruleset[col] = MappingRule.make_default(default_val)
            else:
                ruleset[col] = MappingRule.make_blank()
        return ruleset

    def auto_match(self, ruleset: MappingRuleSet) -> MappingRuleSet:
        """원천 헤더와 QPR 컬럼명이 동일하면 COLUMN 자동 지정 (BLANK인 경우만)."""
        header_set = set(self.source_headers)
        updated = dict(ruleset)
        for col in QPR_COLUMNS:
            rule = updated.get(col)
            if rule and rule.mode == MappingMode.BLANK and col in header_set:
                updated[col] = MappingRule.make_column(col)
        return updated

    def validate(self, ruleset: MappingRuleSet) -> list[ValidationError]:
        errors: list[ValidationError] = []
        header_set = set(self.source_headers)

        for col in QPR_COLUMNS:
            rule = ruleset.get(col)
            if rule is None:
                if col in MANDATORY_COLUMNS:
                    errors.append(ValidationError(col, f"'{col}' 매핑 누락", "error"))
                continue

            if rule.mode == MappingMode.BLANK and col in MANDATORY_COLUMNS:
                errors.append(ValidationError(col, f"'{col}'는 필수 컬럼입니다", "error"))

            if rule.mode == MappingMode.COLUMN:
                if not rule.value:
                    errors.append(ValidationError(col, "원천 컬럼이 선택되지 않음", "error"))
                elif rule.value not in header_set:
                    errors.append(ValidationError(
                        col, f"원천 컬럼 '{rule.value}'이 없음", "warning"
                    ))

        return errors

    def validation_summary(self, ruleset: MappingRuleSet) -> dict[str, str]:
        """각 QPR 컬럼의 상태를 반환: "ok" | "missing" | "invalid_ref" | "warning"."""
        errors = self.validate(ruleset)
        error_map = {e.qpr_col: e for e in errors}
        summary: dict[str, str] = {}

        for col in QPR_COLUMNS:
            if col in error_map:
                e = error_map[col]
                if e.severity == "error":
                    summary[col] = "missing" if "필수" in e.message else "invalid_ref"
                else:
                    summary[col] = "warning"
            else:
                summary[col] = "ok"
        return summary
