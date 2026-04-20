from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class MappingMode(str, Enum):
    COLUMN  = "column"   # 원천 컬럼명 → QPR 컬럼값
    DEFAULT = "default"  # 모든 행에 고정 문자열 사용
    BLANK   = "blank"    # 항상 빈 값


@dataclass
class MappingRule:
    mode:  MappingMode
    value: str | None

    def to_dict(self) -> dict:
        return {"mode": self.mode.value, "value": self.value}

    @classmethod
    def from_dict(cls, d: dict) -> MappingRule:
        return cls(mode=MappingMode(d["mode"]), value=d.get("value"))

    @classmethod
    def make_blank(cls) -> MappingRule:
        return cls(mode=MappingMode.BLANK, value=None)

    @classmethod
    def make_default(cls, value: str) -> MappingRule:
        return cls(mode=MappingMode.DEFAULT, value=value)

    @classmethod
    def make_column(cls, col_name: str) -> MappingRule:
        return cls(mode=MappingMode.COLUMN, value=col_name)

    def display_label(self) -> str:
        if self.mode == MappingMode.COLUMN:
            return self.value or ""
        if self.mode == MappingMode.DEFAULT:
            v = self.value or ""
            return f'"{v}"' if v != "__copy_actual__" else "= 실적수량"
        return "(공백)"

    def mode_badge(self) -> str:
        return {"column": "COL", "default": "DEF", "blank": "BLK"}[self.mode.value]


# 전체 매핑 상태: QPR 컬럼명 → 규칙
MappingRuleSet = dict[str, MappingRule]


@dataclass
class CausePairMapping:
    """요인 유형 1슬롯 = (요인컬럼명, 수량/시간컬럼명) 쌍"""
    cause_src: str | None  # 요인 레이블용 원천 컬럼명
    qty_src:   str | None  # 수량/시간용 원천 컬럼명

    def is_empty(self) -> bool:
        return not self.cause_src and not self.qty_src

    def to_dict(self) -> dict:
        return {"cause_src": self.cause_src, "qty_src": self.qty_src}

    @classmethod
    def from_dict(cls, d: dict) -> "CausePairMapping":
        return cls(cause_src=d.get("cause_src"), qty_src=d.get("qty_src"))


@dataclass
class CauseMapping:
    """3개 요인 유형의 다중 슬롯 매핑"""
    downtime:      list[CausePairMapping] = field(default_factory=list)  # 비가동
    nonconformity: list[CausePairMapping] = field(default_factory=list)  # 부적합
    defect:        list[CausePairMapping] = field(default_factory=list)  # 불량

    def get_pairs(self, cause_type: str) -> list[CausePairMapping]:
        return {"비가동": self.downtime, "부적합": self.nonconformity, "불량": self.defect}[cause_type]

    def is_empty(self) -> bool:
        return not (self.downtime or self.nonconformity or self.defect)

    def to_dict(self) -> dict:
        return {
            "downtime":      [p.to_dict() for p in self.downtime],
            "nonconformity": [p.to_dict() for p in self.nonconformity],
            "defect":        [p.to_dict() for p in self.defect],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CauseMapping":
        return cls(
            downtime=      [CausePairMapping.from_dict(x) for x in d.get("downtime", [])],
            nonconformity= [CausePairMapping.from_dict(x) for x in d.get("nonconformity", [])],
            defect=        [CausePairMapping.from_dict(x) for x in d.get("defect", [])],
        )
