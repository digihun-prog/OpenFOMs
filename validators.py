from __future__ import annotations

from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. 문자열 전처리
# ---------------------------------------------------------------------------

def clean_value(value: str) -> Optional[str]:
    """trim 후 빈 문자열이면 None 반환."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    stripped = value.strip()
    return stripped if stripped else None


# ---------------------------------------------------------------------------
# 2. 숫자 변환
# ---------------------------------------------------------------------------
    
def to_float(value: Optional[str]) -> Optional[float]:
    """
    문자열을 float으로 변환한다.
    반환: (변환값, 경고메시지 or None)
    """
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def to_int(value: Optional[str]) -> Optional[int]:
    """
    문자열을 int로 변환한다. float 경유 후 truncate.
    반환: (변환값, 경고메시지 or None)
    """
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None

# ---------------------------------------------------------------------------
# 3. Main Row 판별
# ---------------------------------------------------------------------------

def is_main_row(plan_qty: Optional[str], actual_qty: Optional[str]) -> bool:
    """
    clean_value 이후 값 기준으로 Main Row 여부 판별.
    계획수량 또는 실적수량 중 하나라도 값이 존재하면 Main Row.
    """
    return plan_qty is not None or actual_qty is not None


# ---------------------------------------------------------------------------
# 4. 컬럼 존재 검증
# ---------------------------------------------------------------------------

def validate_required_columns(headers: List[str], config: dict) -> List[str]:
    """
    필수 컬럼 누락 여부 검증.
    반환: 누락된 컬럼명 리스트 (빈 리스트면 정상)

    config 구조 예시:
        {
            "process_hierarchy": ["대분류", "중분류", "소분류"],
            "machine_col": "설비",
            "product_col": "제품",
            "worker_col": "작업자",
            "date_col": "일자",
            "shift_col": "Shift",
        }
    """
    required: List[str] = [
        config.get("date_col", "일자"),
        config.get("shift_col", "Shift"),
        config.get("machine_col", "설비"),
        config.get("product_col", "제품"),
        config.get("worker_col", "작업자"),
    ]
    process_cols = config.get("process_hierarchy")
    if not process_cols:
        return ["process_hierarchy (config missing)"]

    required += process_cols

    header_set = set(headers)
    return [col for col in required if col not in header_set]


# ---------------------------------------------------------------------------
# 5. Row 데이터 정제
# ---------------------------------------------------------------------------

def normalize_row(row: dict) -> dict:
    """
    모든 컬럼 값에 clean_value를 적용한다.
    숫자 컬럼도 이 단계에서는 문자열 유지 (parser에서 형변환).
    """
    return {key: clean_value(str(val)) if val is not None else None
            for key, val in row.items()}


# ---------------------------------------------------------------------------
# 6. 경고 메시지 헬퍼
# ---------------------------------------------------------------------------

def warn_no_main_row(key_repr: str) -> str:
    return f"W010: Main Row 없음 - {key_repr}"


def warn_multiple_main_rows(key_repr: str, count: int) -> str:
    return f"W011: Main Row {count}개 - 첫 번째 행의 대표 필드를 사용 - {key_repr}"


def warn_missing_columns(missing: List[str]) -> str:
    return f"W001: 필수 컬럼 누락 - {missing}"


def warn_float_conversion(col: str, value: str) -> str:
    return f"W002: float 변환 실패 - 컬럼={col!r}, 값={value!r}"


def warn_int_conversion(col: str, value: str) -> str:
    return f"W003: int 변환 실패 - 컬럼={col!r}, 값={value!r}"


def warn_encoding_failed(path: str) -> str:
    return f"W004: 인코딩 실패 (UTF-8, EUC-KR 모두 실패) - {path}"
