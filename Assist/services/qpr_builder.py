from __future__ import annotations
import csv
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

from ..models.qpr_schema import QPR_COLUMNS, KEY_COLUMNS, CAUSE_COLUMNS, CAUSE_PAIRS
from ..models.mapping_rule import MappingMode, MappingRuleSet, CauseMapping

_NUMERIC_COLS: frozenset[str] = frozenset([
    "실적수량", "계획수량", "작업시간", "효율", "C/T",
    "비가동시간", "부적합수량", "불량수량",
])

_DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%y%m%d", "%Y%m%d", "%Y년%m월%d일"]


def _try_parse_date(val: str) -> bool:
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(val.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def _validate_row(qpr_row: dict, row_index: int, stats: "BuildStats") -> None:
    date_val = qpr_row.get("일자", "")
    if date_val and not _try_parse_date(date_val):
        stats.warnings.append(f"행 {row_index}: 날짜 형식 오류 — 일자={date_val!r}")

    for col in _NUMERIC_COLS:
        val = qpr_row.get(col, "")
        if val:
            try:
                float(val)
            except (ValueError, TypeError):
                stats.warnings.append(f"행 {row_index}: 숫자 변환 실패 — {col}={val!r}")


@dataclass
class BuildStats:
    total_work_items: int = 0
    total_main_rows:  int = 0
    total_cause_rows: int = 0
    cause_breakdown: dict[str, int] = field(default_factory=lambda: {
        "비가동": 0, "부적합": 0, "불량": 0
    })
    warnings: list[str] = field(default_factory=list)


_NON_CAUSE_COLS = [c for c in QPR_COLUMNS if c not in CAUSE_COLUMNS]


def _resolve_non_cause_row(src_row: dict, ruleset: MappingRuleSet) -> dict:
    """13개 비요인 컬럼만 변환한 QPR 행 반환."""
    qpr: dict[str, str] = {c: "" for c in QPR_COLUMNS}
    for col in _NON_CAUSE_COLS:
        rule = ruleset.get(col)
        if rule is None or rule.mode == MappingMode.BLANK:
            qpr[col] = ""
        elif rule.mode == MappingMode.DEFAULT:
            if rule.value == "__copy_actual__":
                qpr[col] = qpr.get("실적수량", "")
            else:
                qpr[col] = rule.value or ""
        elif rule.mode == MappingMode.COLUMN:
            val = src_row.get(rule.value) if rule.value else None
            qpr[col] = val if val is not None else ""
    return qpr


def _expand_source_row(
    src_row: dict,
    ruleset: MappingRuleSet,
    cause_mapping: CauseMapping,
) -> list[dict]:
    """원천 1행 → Main Row 1개 + 추가 요인 슬롯별 Detail Row 목록 반환."""
    main_row = _resolve_non_cause_row(src_row, ruleset)
    detail_rows: list[dict] = []

    for cause_type, (qpr_cause_col, qpr_qty_col) in CAUSE_PAIRS.items():
        for slot_idx, pair in enumerate(cause_mapping.get_pairs(cause_type)):
            if pair.is_empty():
                continue
            cause_val = src_row.get(pair.cause_src, "") if pair.cause_src else ""
            qty_val   = src_row.get(pair.qty_src,   "") if pair.qty_src   else ""
            if not cause_val and not qty_val:
                continue  # 원천 데이터 자체가 비어있으면 생략
            if slot_idx == 0:
                main_row[qpr_cause_col] = cause_val
                main_row[qpr_qty_col]   = qty_val
            else:
                detail: dict[str, str] = {c: "" for c in QPR_COLUMNS}
                for kc in KEY_COLUMNS:
                    detail[kc] = main_row[kc]
                detail[qpr_cause_col] = cause_val
                detail[qpr_qty_col]   = qty_val
                detail_rows.append(detail)

    return [main_row] + detail_rows


def _resolve_row(src_row: dict, ruleset: MappingRuleSet) -> dict:
    """source row 한 행을 QPR 19컬럼 dict으로 변환.
    QPR_COLUMNS 순서대로 처리 — 실적수량(No.9)이 계획수량(No.10)보다 앞이므로
    __copy_actual__ sentinel을 단일 패스에서 처리할 수 있다.
    """
    qpr: dict[str, str] = {}
    for col in QPR_COLUMNS:
        rule = ruleset.get(col)
        if rule is None or rule.mode == MappingMode.BLANK:
            qpr[col] = ""
        elif rule.mode == MappingMode.DEFAULT:
            if rule.value == "__copy_actual__":
                # 실적수량은 이미 처리됨 (No.9 < No.10)
                qpr[col] = qpr.get("실적수량", "")
            else:
                qpr[col] = rule.value or ""
        elif rule.mode == MappingMode.COLUMN:
            val = src_row.get(rule.value) if rule.value else None
            qpr[col] = val if val is not None else ""
    return qpr


def _make_key(qpr_row: dict) -> tuple:
    return tuple(qpr_row.get(col, "") for col in KEY_COLUMNS)


def _is_main_row(qpr_row: dict) -> bool:
    return bool(qpr_row.get("실적수량") or qpr_row.get("계획수량"))


def _cause_type(qpr_row: dict) -> str | None:
    """요인행의 유형(비가동/부적합/불량) 반환. 해당 없으면 None."""
    return next(
        (ct for ct, (col, _) in CAUSE_PAIRS.items() if qpr_row.get(col)),
        None,
    )


class QPRBuilder:
    def build(
        self,
        source_rows: list[dict],
        ruleset: MappingRuleSet,
        cause_mapping: CauseMapping | None = None,
    ) -> tuple[list[dict], BuildStats]:
        """
        source_rows → QPR 행 목록 + 통계.
        복합 키로 그룹핑 후 주행 먼저, 요인행 이후 순으로 출력.
        cause_mapping이 있으면 1행 → N행 확장 경로 사용.
        """
        stats = BuildStats()

        # 1단계: 모든 source row → QPR row 변환 (다중 요인 슬롯 시 확장)
        if cause_mapping and not cause_mapping.is_empty():
            converted: list[dict] = []
            for src in source_rows:
                converted.extend(_expand_source_row(src, ruleset, cause_mapping))
        else:
            converted = [_resolve_row(src, ruleset) for src in source_rows]

        # 숫자/날짜 변환 실패 검증 (§13)
        for i, row in enumerate(converted):
            _validate_row(row, i + 1, stats)

        # 2단계: 복합 키로 그룹핑
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for row in converted:
            groups[_make_key(row)].append(row)

        # 3단계: 그룹별 주행 + 요인행 정렬 후 출력
        output: list[dict] = []
        for key, rows in groups.items():
            stats.total_work_items += 1

            main_rows  = [r for r in rows if _is_main_row(r)]
            cause_rows = [r for r in rows if not _is_main_row(r)]

            if not main_rows:
                # 규칙 5.1: 주행 없는 그룹은 비정상 — 건너뜀
                stats.warnings.append(
                    f"복합키 {key}: 주행(실적수량/계획수량)이 없습니다. 해당 그룹을 건너뜁니다."
                )
                continue
            elif len(main_rows) > 1:
                stats.warnings.append(
                    f"복합키 {key}: 주행이 {len(main_rows)}개입니다. 첫 번째만 사용."
                )
                cause_rows = main_rows[1:] + cause_rows
                main_rows = [main_rows[0]]

            output.extend(main_rows)
            stats.total_main_rows += len(main_rows)

            for cr in cause_rows:
                output.append(cr)
                stats.total_cause_rows += 1
                if ct := _cause_type(cr):
                    stats.cause_breakdown[ct] = stats.cause_breakdown.get(ct, 0) + 1

        return output, stats

    def write_csv(
        self,
        qpr_rows: list[dict],
        output_path: str,
        encoding: str = "utf-8-sig",
    ) -> None:
        """QPR 19컬럼 CSV 파일 저장. BOM 포함 UTF-8로 Excel 한국어 호환."""
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=QPR_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(qpr_rows)
