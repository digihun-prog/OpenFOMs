from __future__ import annotations
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QFrame, QSizePolicy,
)

from ..models.qpr_schema import QPR_COLUMNS, MANDATORY_COLUMNS, CAUSE_COLUMNS

_STATUS_COLORS = {
    "ok":          "#27AE60",
    "missing":     "#E74C3C",
    "invalid_ref": "#E67E22",
    "warning":     "#F39C12",
}

_STATUS_LABELS = {
    "ok":          "정상",
    "missing":     "필수 누락",
    "invalid_ref": "참조 오류",
    "warning":     "경고",
}


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 상단 상태 레이블
        self._status_label = QLabel("CSV 파일과 매핑을 설정하면 유효성 상태가 표시됩니다.")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # 유효성 트리
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["QPR 컬럼", "상태", "비고"])
        self._tree.setColumnWidth(0, 120)
        self._tree.setColumnWidth(1, 80)
        self._tree.setColumnWidth(2, 300)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._tree)

        # 생성 결과 패널 (숨김 상태로 시작)
        self._result_frame = QFrame()
        self._result_frame.setFrameShape(QFrame.Shape.StyledPanel)
        result_layout = QVBoxLayout(self._result_frame)
        result_layout.setContentsMargins(8, 8, 8, 8)

        self._result_title = QLabel()
        bold = QFont()
        bold.setBold(True)
        self._result_title.setFont(bold)
        result_layout.addWidget(self._result_title)

        self._result_stats = QLabel()
        self._result_stats.setWordWrap(True)
        result_layout.addWidget(self._result_stats)

        self._result_frame.setVisible(False)
        layout.addWidget(self._result_frame)

    def update_summary(self, summary: dict[str, str]) -> None:
        """매핑 유효성 상태 업데이트."""
        self._result_frame.setVisible(False)
        self._tree.clear()

        error_count = sum(1 for s in summary.values() if s in ("missing", "invalid_ref"))
        warn_count  = sum(1 for s in summary.values() if s == "warning")

        if error_count:
            self._status_label.setText(f"오류 {error_count}개를 해결해야 QPR을 생성할 수 있습니다.")
            self._status_label.setStyleSheet("color: #E74C3C;")
        elif warn_count:
            self._status_label.setText(f"경고 {warn_count}개가 있습니다. QPR 생성은 가능합니다.")
            self._status_label.setStyleSheet("color: #E67E22;")
        else:
            self._status_label.setText("모든 필수 컬럼이 매핑되었습니다. QPR 생성 가능.")
            self._status_label.setStyleSheet("color: #27AE60;")

        for col in QPR_COLUMNS:
            status = summary.get(col, "ok")
            note = ""
            if col in MANDATORY_COLUMNS and status == "missing":
                note = "필수 컬럼"
            elif col in CAUSE_COLUMNS:
                note = "요인 컬럼 (0개 이상)"

            item = QTreeWidgetItem([col, _STATUS_LABELS.get(status, status), note])
            color = QColor(_STATUS_COLORS.get(status, "#888888"))
            item.setForeground(1, QBrush(color))
            self._tree.addTopLevelItem(item)

    def show_success(
        self,
        output_path: str,
        stats,  # BuildStats
    ) -> None:
        """QPR 생성 완료 결과 표시."""
        self._result_frame.setVisible(True)

        filename = os.path.basename(output_path)
        self._result_title.setText(f"QPR 생성 완료: {filename}")
        self._result_title.setStyleSheet("color: #27AE60;")

        bd = stats.cause_breakdown
        lines = [
            f"출력 파일: {output_path}",
            f"작업 수: {stats.total_work_items}개",
            f"  ├─ 주행:  {stats.total_main_rows}행",
            f"  └─ 요인행: {stats.total_cause_rows}행",
            f"     ├─ 비가동:  {bd.get('비가동', 0)}행",
            f"     ├─ 부적합:  {bd.get('부적합', 0)}행",
            f"     └─ 불량:   {bd.get('불량', 0)}행",
        ]
        if stats.warnings:
            lines.append(f"경고: {len(stats.warnings)}건")

        self._result_stats.setText("\n".join(lines))
        self._status_label.setText("QPR 파일이 생성되었습니다.")
        self._status_label.setStyleSheet("color: #27AE60;")
