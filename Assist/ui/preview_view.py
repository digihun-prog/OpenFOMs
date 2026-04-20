from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QSizePolicy,
)

from ..models.qpr_schema import CAUSE_PAIRS

MAX_WORK_ITEMS = 50

_CAUSE_COLORS = {
    "비가동": "#2980B9",
    "부적합": "#8E44AD",
    "불량":   "#C0392B",
}


class PreviewView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._header = QLabel("미리보기가 없습니다.")
        layout.addWidget(self._header)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["작업", "값"])
        self._tree.setColumnWidth(0, 300)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._tree)

    def show_source(self, headers: list[str], rows: list[dict]) -> None:
        """원천 CSV 미리보기."""
        self._tree.clear()
        self._tree.setHeaderLabels(headers[:10])  # 최대 10컬럼
        for i, row in enumerate(rows[:100]):
            values = [str(row.get(h, "")) for h in headers[:10]]
            self._tree.addTopLevelItem(QTreeWidgetItem(values))
        self._header.setText(f"원천 데이터 미리보기 ({len(rows)}행)")

    def show_qpr(
        self,
        qpr_rows: list[dict],
        groups: dict[tuple, list[dict]] | None = None,
    ) -> None:
        """QPR 출력 미리보기 — 작업별 트리 구조."""
        self._tree.clear()
        self._tree.setHeaderLabels(["작업 / 요인", "상세"])

        if groups is None:
            self._show_flat(qpr_rows)
            return

        bold = QFont()
        bold.setBold(True)
        shown = 0

        for key, rows in list(groups.items())[:MAX_WORK_ITEMS]:
            main_rows  = [r for r in rows if r.get("실적수량") or r.get("계획수량")]
            cause_rows = [r for r in rows if not (r.get("실적수량") or r.get("계획수량"))]

            main = main_rows[0] if main_rows else (rows[0] if rows else {})
            date     = main.get("일자", "")
            machine  = main.get("설비", "")
            product  = main.get("제품", "")
            actual   = main.get("실적수량", "")

            label = f"{date}  |  {machine}  |  {product}  |  실적: {actual}"
            if not cause_rows:
                label += "  (요인 없음)"

            parent_item = QTreeWidgetItem([label, ""])
            parent_item.setFont(0, bold)
            self._tree.addTopLevelItem(parent_item)
            parent_item.setExpanded(True)

            for cr in cause_rows:
                for cause_type, (cause_col, qty_col) in CAUSE_PAIRS.items():
                    cause_val = cr.get(cause_col)
                    qty_val   = cr.get(qty_col)
                    if cause_val:
                        unit = "분" if cause_type == "비가동" else "개"
                        child_label = f"[{cause_type}]  {cause_val}"
                        child_detail = f"{qty_val}{unit}" if qty_val else ""
                        child = QTreeWidgetItem([child_label, child_detail])
                        color = QColor(_CAUSE_COLORS.get(cause_type, "#555555"))
                        child.setForeground(0, QBrush(color))
                        parent_item.addChild(child)

            shown += 1

        total = len(groups)
        note = f" (최대 {MAX_WORK_ITEMS}개 표시)" if total > MAX_WORK_ITEMS else ""
        self._header.setText(f"QPR 미리보기 — 작업 {total}개{note}")

    def _show_flat(self, qpr_rows: list[dict]) -> None:
        for row in qpr_rows[:100]:
            label = f"{row.get('일자','')} | {row.get('설비','')} | {row.get('제품','')}"
            self._tree.addTopLevelItem(QTreeWidgetItem([label, ""]))
        self._header.setText(f"QPR 미리보기 ({len(qpr_rows)}행)")
