from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class QPRKey:
    date: str
    shift: str
    process_hierarchy: Tuple[str, ...]
    machine: str
    product: str
    worker: str

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "shift": self.shift,
            "process_hierarchy": self.process_hierarchy,
            "machine": self.machine,
            "product": self.product,
            "worker": self.worker,
        }

    def __repr__(self) -> str:
        hierarchy = "/".join(self.process_hierarchy)
        return (
            f"QPRKey(date={self.date!r}, shift={self.shift!r}, "
            f"hierarchy={hierarchy!r}, machine={self.machine!r}, "
            f"product={self.product!r}, worker={self.worker!r})"
        )


@dataclass
class DowntimeItem:
    cause: str
    duration: Optional[float] = None
    row_index: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "cause": self.cause,
            "duration": self.duration,
        }


@dataclass
class NonconformityItem:
    cause: str
    qty: Optional[int] = None
    row_index: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "cause": self.cause,
            "qty": self.qty,
        }


@dataclass
class DefectItem:
    cause: str
    qty: Optional[int] = None
    row_index: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "cause": self.cause,
            "qty": self.qty,
        }


@dataclass
class ParsedRecord:
    key: QPRKey
    plan_qty: Optional[float] = None
    actual_qty: Optional[float] = None
    work_time: Optional[float] = None
    efficiency: Optional[float] = None
    cycle_time: Optional[float] = None
    source_row_count: int = 0
    downtime_items: List[DowntimeItem] = field(default_factory=list)
    nonconformity_items: List[NonconformityItem] = field(default_factory=list)
    defect_items: List[DefectItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key.to_dict(),
            "plan_qty": self.plan_qty,
            "actual_qty": self.actual_qty,
            "work_time": self.work_time,
            "efficiency": self.efficiency,
            "cycle_time": self.cycle_time,
            "source_row_count": self.source_row_count,
            "downtime_items": [item.to_dict() for item in self.downtime_items],
            "nonconformity_items": [item.to_dict() for item in self.nonconformity_items],
            "defect_items": [item.to_dict() for item in self.defect_items],
            "warnings": self.warnings,
        }


@dataclass
class ParseResult:
    records: List[ParsedRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "records": [record.to_dict() for record in self.records],
            "warnings": self.warnings,
        }
