from __future__ import annotations

import csv
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from models import DefectItem, DowntimeItem, NonconformityItem, ParsedRecord, ParseResult, QPRKey
from validators import (
    is_main_row,
    normalize_row,
    to_float,
    to_int,
    validate_required_columns,
    warn_float_conversion,
    warn_int_conversion,
    warn_missing_columns,
    warn_multiple_main_rows,
    warn_no_main_row,
)


# ---------------------------------------------------------------------------
# 1. CSV 읽기
# ---------------------------------------------------------------------------

def load_csv_rows(
    file_path: str,
    delimiter: str = ",",
) -> Tuple[List[dict], List[str], List[str]]:
    """
    CSV 파일을 읽어 (rows, headers, warnings)를 반환한다.
    인코딩: UTF-8 우선, 실패 시 EUC-KR 재시도.
    """
    warnings: List[str] = []

    for encoding in ("utf-8-sig", "euc-kr"):
        try:
            with open(file_path, newline="", encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                headers = reader.fieldnames or []
                rows = [dict(row) for row in reader]
            return rows, headers, warnings
        except (UnicodeDecodeError, LookupError):
            continue

    raise ValueError(f"Encoding failed for file: {file_path}")

# ---------------------------------------------------------------------------
# 2. Row 정제
# ---------------------------------------------------------------------------

def preprocess_rows(rows: List[dict]) -> List[dict]:
    """모든 row에 normalize_row를 적용한다."""
    return [normalize_row(row) for row in rows]


# ---------------------------------------------------------------------------
# 3. 필수 컬럼 검증
# ---------------------------------------------------------------------------

def check_columns(headers: List[str], config: dict) -> List[str]:
    """
    필수 컬럼 누락 여부를 검증한다.
    반환: 누락 항목이 있으면 경고 문자열 리스트, 없으면 빈 리스트.
    """
    missing = validate_required_columns(headers, config)
    if missing:
        return [warn_missing_columns(missing)]
    return []


# ---------------------------------------------------------------------------
# 4. Key 생성
# ---------------------------------------------------------------------------

def build_key(row: dict, config: dict) -> QPRKey:
    """
    normalized row와 config를 기반으로 QPRKey 객체를 생성한다.
    config에 필요한 key가 없으면 ValueError 발생.
    """
    required_keys = ("date_col", "shift_col", "machine_col", "product_col", "worker_col", "process_hierarchy")
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(f"config에 필수 항목 없음: {missing}")

    process_hierarchy = tuple(
        row.get(col) for col in config["process_hierarchy"]
    )

    return QPRKey(
        date=row.get(config["date_col"]),
        shift=row.get(config["shift_col"]),
        process_hierarchy=process_hierarchy,
        machine=row.get(config["machine_col"]),
        product=row.get(config["product_col"]),
        worker=row.get(config["worker_col"]),
    )


# ---------------------------------------------------------------------------
# 5. Row 그룹핑
# ---------------------------------------------------------------------------

def group_rows_by_key(rows: List[dict], config: dict) -> Dict[QPRKey, List[dict]]:
    """
    normalized rows를 Key 기준으로 그룹핑한다.
    반환: {QPRKey: [row, ...]} — 입력 순서 유지
    """
    groups: Dict[QPRKey, List[dict]] = defaultdict(list)
    for row in rows:
        key = build_key(row, config)
        groups[key].append(row)
    return dict(groups)


# ---------------------------------------------------------------------------
# 6. Main Row 선택
# ---------------------------------------------------------------------------

def select_main_row(
    rows: List[dict],
    config: dict,
    key_repr: Optional[str] = None,
) -> Tuple[Optional[dict], List[str]]:
    """
    동일 Key 그룹에서 Main Row를 선택한다.
    반환: (main_row or None, warnings)
    """
    if key_repr is None:
        key_repr = "UNKNOWN_KEY"

    warnings: List[str] = []

    plan_col = config["plan_qty_col"]
    actual_col = config["actual_qty_col"]

    main_rows = [
        row for row in rows
        if is_main_row(row.get(plan_col), row.get(actual_col))
    ]

    if len(main_rows) == 0:
        warnings.append(warn_no_main_row(key_repr))
        return None, warnings

    if len(main_rows) >= 2:
        warnings.append(warn_multiple_main_rows(key_repr, len(main_rows)))

    return main_rows[0], warnings


# ---------------------------------------------------------------------------
# 7. 원인 추출
# ---------------------------------------------------------------------------

def extract_items(
    rows: List[dict],
    config: dict,
) -> Tuple[List[DowntimeItem], List[NonconformityItem], List[DefectItem], List[str]]:
    """
    동일 Key 그룹의 모든 row에서 비가동 / 부적합 / 불량 원인을 추출한다.
    Main Row / Detail Row 구분 없이 전체 rows 대상.
    """
    downtime_items: List[DowntimeItem] = []
    nonconformity_items: List[NonconformityItem] = []
    defect_items: List[DefectItem] = []
    warnings: List[str] = []

    try:
        dt_col   = config["downtime_col"]
        dt_t_col = config["downtime_time_col"]
        nc_col   = config["nonconformity_col"]
        nc_q_col = config["nonconformity_qty_col"]
        df_col   = config["defect_col"]
        df_q_col = config["defect_qty_col"]
    except KeyError as e:
        raise ValueError(f"config 누락: {e}")

    for idx, row in enumerate(rows):
        # (1) 비가동
        cause = row.get(dt_col)
        if cause:
            raw_duration = row.get(dt_t_col)
            duration = to_float(raw_duration)
            if raw_duration is not None and duration is None:
                warnings.append(warn_float_conversion(dt_t_col, raw_duration))
            downtime_items.append(DowntimeItem(cause=cause, duration=duration, row_index=idx))

        # (2) 부적합
        cause = row.get(nc_col)
        if cause:
            raw_qty = row.get(nc_q_col)
            qty = to_int(raw_qty)
            if raw_qty is not None and qty is None:
                warnings.append(warn_int_conversion(nc_q_col, raw_qty))
            nonconformity_items.append(NonconformityItem(cause=cause, qty=qty, row_index=idx))

        # (3) 불량
        cause = row.get(df_col)
        if cause:
            raw_qty = row.get(df_q_col)
            qty = to_int(raw_qty)
            if raw_qty is not None and qty is None:
                warnings.append(warn_int_conversion(df_q_col, raw_qty))
            defect_items.append(DefectItem(cause=cause, qty=qty, row_index=idx))

    return downtime_items, nonconformity_items, defect_items, warnings


# ---------------------------------------------------------------------------
# 8. ParsedRecord 생성
# ---------------------------------------------------------------------------

def _get_float_field(
    col_key: str,
    config: dict,
    row: dict,
    warnings: List[str],
) -> Optional[float]:
    """config 기반으로 row에서 float 필드를 추출한다. config 누락 시 ValueError."""
    col = config.get(col_key)
    if not col:
        raise ValueError(f"config 누락: {col_key}")
    raw = row.get(col)
    val = to_float(raw)
    if raw is not None and val is None:
        warnings.append(warn_float_conversion(col, raw))
    return val


def build_parsed_records(
    grouped: Dict[QPRKey, List[dict]],
    config: dict,
) -> ParseResult:
    """
    group_rows_by_key 결과를 ParsedRecord 리스트로 변환한다.
    """
    records: List[ParsedRecord] = []
    global_warnings: List[str] = []

    for key, rows in grouped.items():
        record_warnings: List[str] = []
        key_repr = repr(key)

        # 1. Main Row 선택
        main_row, w = select_main_row(rows, config, key_repr=key_repr)
        record_warnings.extend(w)

        if main_row is None:
            global_warnings.extend(record_warnings)
            continue

        # 2. 원인 추출 (전체 rows 대상)
        downtime_items, nonconformity_items, defect_items, w = extract_items(rows, config)
        record_warnings.extend(w)

        # 3. ParsedRecord 생성
        record = ParsedRecord(
            key=key,
            plan_qty=_get_float_field("plan_qty_col", config, main_row, record_warnings),
            actual_qty=_get_float_field("actual_qty_col", config, main_row, record_warnings),
            work_time=_get_float_field("work_time_col", config, main_row, record_warnings),
            efficiency=_get_float_field("efficiency_col", config, main_row, record_warnings),
            cycle_time=_get_float_field("cycle_time_col", config, main_row, record_warnings),
            downtime_items=downtime_items,
            nonconformity_items=nonconformity_items,
            defect_items=defect_items,
            source_row_count=len(rows),
            warnings=record_warnings,
        )
        records.append(record)
        global_warnings.extend(record_warnings)

    return ParseResult(records=records, warnings=global_warnings)


# ---------------------------------------------------------------------------
# 9. 전체 1단계 흐름
# ---------------------------------------------------------------------------

def parse_csv_stage1(
    file_path: str,
    config: dict,
) -> Tuple[List[dict], List[str]]:
    """
    Stage 1: CSV 읽기 → 컬럼 검증 → row normalize.

    config 구조 예시:
        {
            "delimiter": ",",
            "date_col": "일자",
            "shift_col": "Shift",
            "process_hierarchy": ["대분류", "중분류", "소분류"],
            "machine_col": "설비",
            "product_col": "제품",
            "worker_col": "작업자",
            "plan_qty_col": "계획수량",
            "actual_qty_col": "실적수량",
        }
    """
    delimiter = config.get("delimiter", ",")
    warnings: List[str] = []

    # 1. CSV 읽기 (인코딩 자동 재시도)
    rows, headers, load_warnings = load_csv_rows(file_path, delimiter=delimiter)
    warnings.extend(load_warnings)

    if not headers:
        raise ValueError("W100: 헤더 없음")

    # 2. 필수 컬럼 검증
    warnings.extend(check_columns(headers, config))

    if not rows:
        warnings.append("W101: 데이터 행 없음")
        return [], warnings

    # 3. Row normalize
    normalized = preprocess_rows(rows)

    return normalized, warnings
