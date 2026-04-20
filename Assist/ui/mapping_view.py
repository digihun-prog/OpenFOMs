from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QPoint, QTimer
from PySide6.QtGui import QPen, QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QDialog, QDialogButtonBox, QButtonGroup, QRadioButton,
    QComboBox, QLineEdit, QStackedWidget, QScrollArea, QSizePolicy,
)

from ..models.qpr_schema import QPR_COLUMNS, MANDATORY_COLUMNS, CAUSE_COLUMNS, COLUMN_LABELS, CAUSE_PAIRS
from ..models.mapping_rule import MappingMode, MappingRule, MappingRuleSet, CausePairMapping, CauseMapping

_LEFT_W      = 220
_RIGHT_W     = 310
_ITEM_H      = 30
_ITEM_GAP    = 4
_ITEM_STRIDE = _ITEM_H + _ITEM_GAP
_HEADER_H    = 24

# CauseGroupPanel 치수
_CAUSE_PANEL_HEADER_H = 28
_CAUSE_SLOT_H         = 30
_CAUSE_SLOT_GAP       = 3
_CAUSE_PANEL_PADDING  = 6  # 하단 패딩

_COLOR_LINE_NORMAL   = QColor("#4A90D9")
_COLOR_LINE_CAUSE    = QColor("#F5A623")
_COLOR_LINE_DEFAULT  = QColor("#95A5A6")
_PEN_NORMAL   = QPen(_COLOR_LINE_NORMAL,  1.5, Qt.PenStyle.SolidLine)
_PEN_CAUSE    = QPen(_COLOR_LINE_CAUSE,   1.5, Qt.PenStyle.DashLine)
_PEN_CAUSE_QTY = QPen(_COLOR_LINE_CAUSE,  1.0, Qt.PenStyle.DotLine)
_PEN_DEFAULT  = QPen(_COLOR_LINE_DEFAULT, 1.5, Qt.PenStyle.DashLine)

_STATUS_COLORS = {
    "ok":          "#27AE60",
    "missing":     "#E74C3C",
    "invalid_ref": "#E67E22",
    "warning":     "#F39C12",
    "":            "#AAAAAA",
}

# QPR 패널에서 요인 수량 컬럼은 CauseGroupPanel 내부에서 처리 — 별도 행 생성 안 함
_CAUSE_QTY_COLS = {"비가동시간", "부적합수량", "불량수량"}
_CAUSE_LEAD_COLS = {"비가동", "부적합", "불량"}


# ---------------------------------------------------------------------------
# 매핑 다이얼로그 (비요인 컬럼용)
# ---------------------------------------------------------------------------

class MappingDialog(QDialog):
    def __init__(
        self,
        qpr_col: str,
        current_rule: MappingRule,
        source_headers: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"매핑 설정: {qpr_col}")
        self.setMinimumWidth(380)
        self._qpr_col = qpr_col
        self._source_headers = source_headers
        self._result_rule: MappingRule | None = None

        layout = QVBoxLayout(self)

        desc = COLUMN_LABELS.get(qpr_col, "")
        if desc:
            desc_label = QLabel(f"<i>{desc}</i>")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        if qpr_col in MANDATORY_COLUMNS:
            req_label = QLabel("★ 필수 컬럼 — 반드시 매핑해야 합니다.")
            req_label.setStyleSheet("color: #E74C3C;")
            layout.addWidget(req_label)

        mode_group_widget = QWidget()
        mode_layout = QHBoxLayout(mode_group_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_col     = QRadioButton("컬럼 매핑")
        self._btn_default = QRadioButton("고정값")
        self._btn_blank   = QRadioButton("공백")
        mode_layout.addWidget(self._btn_col)
        mode_layout.addWidget(self._btn_default)
        mode_layout.addWidget(self._btn_blank)
        layout.addWidget(mode_group_widget)

        self._stack = QStackedWidget()

        col_page = QWidget()
        col_layout = QVBoxLayout(col_page)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_label = QLabel("원천 컬럼:")
        self._combo = QComboBox()
        if source_headers:
            self._combo.addItems(source_headers)
        else:
            self._combo.addItem("(CSV를 먼저 불러오세요)")
            self._combo.setEnabled(False)
        col_layout.addWidget(col_label)
        col_layout.addWidget(self._combo)
        self._stack.addWidget(col_page)

        def_page = QWidget()
        def_layout = QVBoxLayout(def_page)
        def_layout.setContentsMargins(0, 0, 0, 0)
        def_label = QLabel("고정 값:")
        self._line_edit = QLineEdit()
        def_layout.addWidget(def_label)
        def_layout.addWidget(self._line_edit)
        self._stack.addWidget(def_page)

        blank_page = QWidget()
        blank_layout = QVBoxLayout(blank_page)
        blank_layout.setContentsMargins(0, 0, 0, 0)
        blank_layout.addWidget(QLabel("이 컬럼은 항상 빈 값으로 처리됩니다."))
        self._stack.addWidget(blank_page)

        layout.addWidget(self._stack)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._btn_col.toggled.connect(lambda c: self._stack.setCurrentIndex(0) if c else None)
        self._btn_default.toggled.connect(lambda c: self._stack.setCurrentIndex(1) if c else None)
        self._btn_blank.toggled.connect(lambda c: self._stack.setCurrentIndex(2) if c else None)

        self._apply_rule(current_rule)

    def _apply_rule(self, rule: MappingRule) -> None:
        if rule.mode == MappingMode.COLUMN:
            self._btn_col.setChecked(True)
            self._stack.setCurrentIndex(0)
            if rule.value and self._combo.isEnabled():
                idx = self._combo.findText(rule.value)
                if idx >= 0:
                    self._combo.setCurrentIndex(idx)
        elif rule.mode == MappingMode.DEFAULT:
            self._btn_default.setChecked(True)
            self._stack.setCurrentIndex(1)
            v = rule.value or ""
            self._line_edit.setText("" if v == "__copy_actual__" else v)
        else:
            self._btn_blank.setChecked(True)
            self._stack.setCurrentIndex(2)

    def _on_ok(self) -> None:
        if self._btn_col.isChecked():
            if not self._source_headers:
                self._result_rule = MappingRule.make_blank()
            else:
                self._result_rule = MappingRule.make_column(self._combo.currentText())
        elif self._btn_default.isChecked():
            self._result_rule = MappingRule.make_default(self._line_edit.text())
        else:
            self._result_rule = MappingRule.make_blank()
        self.accept()

    def get_rule(self) -> MappingRule | None:
        return self._result_rule


# ---------------------------------------------------------------------------
# QPR 컬럼 아이템 (우측 패널 — 비요인 컬럼용)
# ---------------------------------------------------------------------------

class QPRColumnWidget(QFrame):
    clicked = Signal(str)

    def __init__(self, qpr_col: str):
        super().__init__()
        self._qpr_col = qpr_col
        self.setFixedSize(_RIGHT_W, _ITEM_H)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(3)

        self._name = QLabel(qpr_col)
        self._name.setFixedWidth(70)
        self._name.setFont(QFont("Malgun Gothic", 8))
        layout.addWidget(self._name)

        self._badge = QLabel("BLK")
        self._badge.setFixedWidth(28)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            "font-size: 8px; border-radius: 3px; padding: 1px 2px;"
            "background: #CCCCCC; color: #333;"
        )
        layout.addWidget(self._badge)

        self._value = QLabel("")
        self._value.setFont(QFont("Malgun Gothic", 8))
        self._value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._value)

        self._status = QLabel("●")
        self._status.setFixedWidth(14)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        self.update_rule(MappingRule.make_blank(), "")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._qpr_col)
        super().mousePressEvent(event)

    def update_rule(self, rule: MappingRule, status: str) -> None:
        self._badge.setText(rule.mode_badge())
        badge_colors = {
            "COL": ("background:#4A90D9; color:white;", "font-size:8px;border-radius:3px;padding:1px 2px;"),
            "DEF": ("background:#7F8C8D; color:white;", "font-size:8px;border-radius:3px;padding:1px 2px;"),
            "BLK": ("background:#CCCCCC; color:#333;",  "font-size:8px;border-radius:3px;padding:1px 2px;"),
        }
        badge_style, _ = badge_colors.get(rule.mode_badge(), badge_colors["BLK"])
        self._badge.setStyleSheet(badge_style + "font-size:8px;border-radius:3px;padding:1px 2px;")
        self._value.setText(rule.display_label())

        color = _STATUS_COLORS.get(status, "#AAAAAA")
        self._status.setStyleSheet(f"color: {color};")

        if self._qpr_col in MANDATORY_COLUMNS:
            self._name.setStyleSheet("font-weight: bold;")
        else:
            self._name.setStyleSheet("")


# ---------------------------------------------------------------------------
# 원천 컬럼 아이템 (좌측 패널)
# ---------------------------------------------------------------------------

class SourceColumnWidget(QPushButton):
    def __init__(self, col_name: str):
        super().__init__(col_name)
        self.setFixedSize(_LEFT_W, _ITEM_H)
        self.setStyleSheet(
            "text-align: left; padding: 2px 8px;"
            "font-family: 'Malgun Gothic'; font-size: 8pt;"
        )
        self._col_name = col_name
        self._connected = False

    def set_connected(self, connected: bool) -> None:
        if self._connected != connected:
            self._connected = connected
            style = (
                "text-align:left; padding:2px 8px;"
                "font-family:'Malgun Gothic'; font-size:8pt;"
                "background:#D6EAF8; border:1px solid #4A90D9;"
                if connected else
                "text-align:left; padding:2px 8px;"
                "font-family:'Malgun Gothic'; font-size:8pt;"
            )
            self.setStyleSheet(style)


# ---------------------------------------------------------------------------
# CauseGroupPanel — 요인 유형 1개의 다중 슬롯 편집 패널
# ---------------------------------------------------------------------------

class CauseGroupPanel(QFrame):
    """비가동/부적합/불량 중 하나의 요인 유형에 대한 다중 슬롯 패널.

    슬롯 위젯은 중간 컨테이너 없이 _layout에 헤더(index 0) 뒤에 직접 추가된다.
    이렇게 해야 QGraphicsProxyWidget 안에서 레이아웃 업데이트가 즉시 반영된다.
    """

    slots_changed = Signal(str, list)  # (cause_type, list[CausePairMapping])

    _QTY_LABEL: dict[str, str] = {"비가동": "시간", "부적합": "수량", "불량": "수량"}

    _HDR_H  = 26   # 헤더 행 고정 높이
    _SLOT_H = 30   # 슬롯 행 고정 높이
    _GAP    = 3    # 슬롯 간격
    _PAD_V  = 6    # 상하 패딩 합계 (top 2 + bottom 4)

    def __init__(self, cause_type: str, source_headers: list[str], parent=None):
        super().__init__(parent)
        self._cause_type = cause_type
        self._source_headers = source_headers
        self._pairs: list[CausePairMapping] = []

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: #FFF8EE; border: 1px solid #F5A623; border-radius: 4px; }"
        )

        # 단일 QVBoxLayout — 헤더(idx=0) + 슬롯들(idx=1,2,...)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 2, 4, 4)
        self._layout.setSpacing(self._GAP)

        # 헤더 행
        hdr = QWidget()
        hdr.setFixedHeight(self._HDR_H)
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(4)

        title = QLabel(f"<b>{cause_type}</b>")
        title.setFont(QFont("Malgun Gothic", 8))
        badge = QLabel("0..*")
        badge.setFixedWidth(30)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("font-size:7px; border-radius:3px; padding:1px 2px; background:#F5A623; color:white;")
        self._status_dot = QLabel("●")
        self._status_dot.setFixedWidth(14)
        self._status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_dot.setStyleSheet("color: #AAAAAA;")
        add_btn = QPushButton("+ 슬롯")
        add_btn.setFixedHeight(20)
        add_btn.setStyleSheet(
            "font-size:8px; padding:1px 6px; background:#F5A623; color:white;"
            "border:none; border-radius:3px;"
        )
        add_btn.clicked.connect(self._add_slot)

        hdr_layout.addWidget(title)
        hdr_layout.addWidget(badge)
        hdr_layout.addStretch()
        hdr_layout.addWidget(self._status_dot)
        hdr_layout.addWidget(add_btn)
        self._layout.addWidget(hdr)

        self._refresh_size()

    # ------------------------------------------------------------------
    def set_source_headers(self, headers: list[str]) -> None:
        self._source_headers = headers
        for i, row_w in enumerate(self._slot_widgets()):
            self._refresh_slot_combos(row_w, i)

    def set_pairs(self, pairs: list[CausePairMapping]) -> None:
        self._pairs = list(pairs)
        self._rebuild_slots()

    def update_status(self, status: str) -> None:
        self._status_dot.setStyleSheet(f"color: {_STATUS_COLORS.get(status, '#AAAAAA')};")

    def panel_height(self) -> int:
        n = len(self._pairs)
        if n == 0:
            return self._HDR_H + self._PAD_V
        return self._HDR_H + self._PAD_V + n * self._SLOT_H + (n - 1) * self._GAP + self._GAP

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(_RIGHT_W, self.panel_height())

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(_RIGHT_W, self.panel_height())

    def slot_center_y(self, slot_idx: int) -> float:
        """슬롯 idx의 중심 y (패널 내부 기준)."""
        top = self._PAD_V // 2 + self._HDR_H + self._GAP
        return top + slot_idx * (self._SLOT_H + self._GAP) + self._SLOT_H / 2

    # ------------------------------------------------------------------
    def _slot_widgets(self) -> list[QWidget]:
        """레이아웃 index 1 이후의 슬롯 위젯 목록."""
        result = []
        for i in range(1, self._layout.count()):
            item = self._layout.itemAt(i)
            if item and item.widget():
                result.append(item.widget())
        return result

    def _rebuild_slots(self) -> None:
        # 헤더(index 0) 이후 모두 제거
        while self._layout.count() > 1:
            item = self._layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        for i, pair in enumerate(self._pairs):
            row_w = self._make_slot_widget(i, pair)
            row_w.setParent(self)
            self._layout.addWidget(row_w)
            row_w.show()
        self._refresh_size()

    def _make_slot_widget(self, idx: int, pair: CausePairMapping) -> QWidget:
        qty_label = self._QTY_LABEL.get(self._cause_type, "수량")
        row = QWidget()
        row.setFixedHeight(self._SLOT_H)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(2, 0, 2, 0)
        rl.setSpacing(3)

        num = QLabel(f"[{idx + 1}]")
        num.setFixedWidth(18)
        num.setFont(QFont("Malgun Gothic", 7))
        num.setStyleSheet("color:#888;")

        cause_lbl = QLabel("요인:")
        cause_lbl.setFont(QFont("Malgun Gothic", 7))
        cause_combo = QComboBox()
        cause_combo.setFixedHeight(22)
        cause_combo.setFont(QFont("Malgun Gothic", 7))
        cause_combo.addItem("(없음)")
        cause_combo.addItems(self._source_headers)
        if pair.cause_src:
            ci = cause_combo.findText(pair.cause_src)
            if ci >= 0:
                cause_combo.setCurrentIndex(ci)

        qty_lbl = QLabel(f"{qty_label}:")
        qty_lbl.setFont(QFont("Malgun Gothic", 7))
        qty_combo = QComboBox()
        qty_combo.setFixedHeight(22)
        qty_combo.setFont(QFont("Malgun Gothic", 7))
        qty_combo.addItem("(없음)")
        qty_combo.addItems(self._source_headers)
        if pair.qty_src:
            qi = qty_combo.findText(pair.qty_src)
            if qi >= 0:
                qty_combo.setCurrentIndex(qi)

        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setStyleSheet(
            "font-size:10px; border:none; background:#E74C3C; color:white; border-radius:3px;"
        )

        rl.addWidget(num)
        rl.addWidget(cause_lbl)
        rl.addWidget(cause_combo, 1)
        rl.addWidget(qty_lbl)
        rl.addWidget(qty_combo, 1)
        rl.addWidget(remove_btn)

        cause_combo.currentTextChanged.connect(lambda _, i=idx: self._on_combo_changed(i))
        qty_combo.currentTextChanged.connect(lambda _, i=idx: self._on_combo_changed(i))
        remove_btn.clicked.connect(lambda _, i=idx: self._remove_slot(i))

        row.setProperty("cause_combo", cause_combo)
        row.setProperty("qty_combo", qty_combo)
        return row

    def _refresh_slot_combos(self, row_w: QWidget, idx: int) -> None:
        cause_combo: QComboBox = row_w.property("cause_combo")
        qty_combo:   QComboBox = row_w.property("qty_combo")
        if not cause_combo or not qty_combo:
            return
        pair = self._pairs[idx] if idx < len(self._pairs) else CausePairMapping(None, None)
        for combo, current in [(cause_combo, pair.cause_src), (qty_combo, pair.qty_src)]:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(없음)")
            combo.addItems(self._source_headers)
            if current:
                ci = combo.findText(current)
                if ci >= 0:
                    combo.setCurrentIndex(ci)
            combo.blockSignals(False)

    def _refresh_size(self) -> None:
        h = self.panel_height()
        self.setFixedSize(_RIGHT_W, h)
        self.layout().activate()   # 레이아웃 즉시 재배치
        self.updateGeometry()

    def _add_slot(self) -> None:
        self._pairs.append(CausePairMapping(None, None))
        row_w = self._make_slot_widget(len(self._pairs) - 1, self._pairs[-1])
        row_w.setParent(self)      # 명시적 부모 설정
        self._layout.addWidget(row_w)
        row_w.show()               # QGraphicsProxyWidget 안에서 자동 show 안 됨
        self._refresh_size()
        self.slots_changed.emit(self._cause_type, list(self._pairs))

    def _remove_slot(self, idx: int) -> None:
        if idx < len(self._pairs):
            self._pairs.pop(idx)
        self._rebuild_slots()
        self.slots_changed.emit(self._cause_type, list(self._pairs))

    def _on_combo_changed(self, idx: int) -> None:
        slot_widgets = self._slot_widgets()
        if idx >= len(slot_widgets):
            return
        row_w = slot_widgets[idx]
        cause_combo: QComboBox = row_w.property("cause_combo")
        qty_combo:   QComboBox = row_w.property("qty_combo")
        cause_txt = cause_combo.currentText() if cause_combo else ""
        qty_txt   = qty_combo.currentText()   if qty_combo   else ""
        cause_src = None if cause_txt in ("", "(없음)") else cause_txt
        qty_src   = None if qty_txt   in ("", "(없음)") else qty_txt
        if idx < len(self._pairs):
            self._pairs[idx] = CausePairMapping(cause_src=cause_src, qty_src=qty_src)
        self.slots_changed.emit(self._cause_type, list(self._pairs))


# ---------------------------------------------------------------------------
# 연결선 그리기 위젯 (left/right 스크롤 영역 사이)
# ---------------------------------------------------------------------------

class LineArea(QWidget):
    """두 스크롤 영역 사이에서 매핑 연결선을 그리는 위젯.

    connections 목록: (src_w|None, src_cy, qpr_w, qpr_cy, pen)
    - src_w=None 이면 DEFAULT 규칙 — 가로 단축선만 그림
    - src_cy / qpr_cy 는 각 위젯 내부 로컬 y 좌표
    mapToGlobal / mapFromGlobal 을 사용하므로 스크롤 위치가 자동 반영됨.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(88)
        self._connections: list[tuple] = []

    def set_connections(self, conns: list[tuple]) -> None:
        self._connections = conns
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for src_w, src_cy, qpr_w, qpr_cy, pen in self._connections:
            painter.setPen(pen)
            if src_w is None:
                # DEFAULT: 오른쪽 위젯 높이 기준 가로 선
                g = qpr_w.mapToGlobal(QPoint(0, qpr_cy))
                y = self.mapFromGlobal(g).y()
                painter.drawLine(0, y, self.width(), y)
            else:
                g_src = src_w.mapToGlobal(QPoint(src_w.width(), src_cy))
                g_qpr = qpr_w.mapToGlobal(QPoint(0, qpr_cy))
                p_src = self.mapFromGlobal(g_src)
                p_qpr = self.mapFromGlobal(g_qpr)
                painter.drawLine(p_src.x(), p_src.y(), p_qpr.x(), p_qpr.y())


# ---------------------------------------------------------------------------
# 메인 매핑 뷰
# ---------------------------------------------------------------------------

class MappingView(QWidget):
    rule_changed          = Signal(str, object)   # (qpr_col, MappingRule)
    cause_mapping_changed = Signal(object)         # CauseMapping

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_headers: list[str] = []
        self._ruleset: MappingRuleSet = {}
        self._validation: dict[str, str] = {}
        self._cause_mapping: CauseMapping = CauseMapping()

        # ── 좌측: 원천 컬럼 스크롤 영역 ─────────────────────────────
        self._left_scroll = QScrollArea()
        self._left_scroll.setWidgetResizable(True)
        self._left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._left_scroll.setFixedWidth(_LEFT_W + 22)

        self._left_container = QWidget()
        self._left_layout = QVBoxLayout(self._left_container)
        self._left_layout.setContentsMargins(2, 2, 2, 2)
        self._left_layout.setSpacing(_ITEM_GAP)
        self._left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._left_scroll.setWidget(self._left_container)

        # ── 중앙: 연결선 영역 ────────────────────────────────────────
        self._line_area = LineArea(self)

        # ── 우측: QPR 컬럼 스크롤 영역 ──────────────────────────────
        self._right_scroll = QScrollArea()
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._right_scroll.setFixedWidth(_RIGHT_W + 22)

        self._right_container = QWidget()
        self._right_layout = QVBoxLayout(self._right_container)
        self._right_layout.setContentsMargins(2, 2, 2, 2)
        self._right_layout.setSpacing(_ITEM_GAP)
        self._right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._right_scroll.setWidget(self._right_container)

        # ── 메인 레이아웃 ─────────────────────────────────────────────
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self._left_scroll)
        main_layout.addWidget(self._line_area)
        main_layout.addWidget(self._right_scroll)
        main_layout.addStretch()

        # 스크롤 시 연결선 재렌더링
        self._left_scroll.verticalScrollBar().valueChanged.connect(self._line_area.update)
        self._right_scroll.verticalScrollBar().valueChanged.connect(self._line_area.update)

        # 레지스트리
        self._src_widgets:  dict[str, SourceColumnWidget] = {}
        self._qpr_widgets:  dict[str, QPRColumnWidget]    = {}
        self._cause_panels: dict[str, CauseGroupPanel]    = {}

        self._build_qpr_panel()

    # ------------------------------------------------------------------
    def _build_qpr_panel(self) -> None:
        hdr = QLabel("QPR 컬럼")
        hdr.setFont(QFont("Malgun Gothic", 8, QFont.Weight.Bold))
        hdr.setFixedHeight(_HEADER_H)
        self._right_layout.addWidget(hdr)

        for col in QPR_COLUMNS:
            if col in _CAUSE_QTY_COLS:
                continue
            elif col in _CAUSE_LEAD_COLS:
                panel = CauseGroupPanel(col, self._source_headers)
                panel.slots_changed.connect(self._on_cause_slots_changed)
                self._right_layout.addWidget(panel)
                self._cause_panels[col] = panel
            else:
                widget = QPRColumnWidget(col)
                widget.clicked.connect(self._on_qpr_col_clicked)
                self._right_layout.addWidget(widget)
                self._qpr_widgets[col] = widget

    # ------------------------------------------------------------------
    def set_source_columns(self, headers: list[str]) -> None:
        self._source_headers = headers

        # 기존 좌측 패널 초기화
        while self._left_layout.count():
            item = self._left_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._src_widgets.clear()

        hdr = QLabel("원천 컬럼")
        hdr.setFont(QFont("Malgun Gothic", 8, QFont.Weight.Bold))
        hdr.setFixedHeight(_HEADER_H)
        self._left_layout.addWidget(hdr)

        for col in headers:
            w = SourceColumnWidget(col)
            self._left_layout.addWidget(w)
            self._src_widgets[col] = w

        for panel in self._cause_panels.values():
            panel.set_source_headers(headers)

        self._rebuild_lines()

    def set_ruleset(self, ruleset: MappingRuleSet) -> None:
        self._ruleset = ruleset
        self._apply_ruleset_to_widgets()
        self._rebuild_lines()

    def set_cause_mapping(self, cm: CauseMapping) -> None:
        self._cause_mapping = cm
        for cause_type, panel in self._cause_panels.items():
            panel.set_pairs(cm.get_pairs(cause_type))
        QTimer.singleShot(0, self._rebuild_lines)

    def update_validation(self, summary: dict[str, str]) -> None:
        self._validation = summary
        for col, w in self._qpr_widgets.items():
            rule = self._ruleset.get(col, MappingRule.make_blank())
            w.update_rule(rule, summary.get(col, ""))
        for cause_type, panel in self._cause_panels.items():
            panel.update_status(summary.get(cause_type, ""))
        self._rebuild_lines()

    # ------------------------------------------------------------------
    def _apply_ruleset_to_widgets(self) -> None:
        connected_src: set[str] = set()
        for col, w in self._qpr_widgets.items():
            rule = self._ruleset.get(col, MappingRule.make_blank())
            w.update_rule(rule, self._validation.get(col, ""))
            if rule.mode == MappingMode.COLUMN and rule.value:
                connected_src.add(rule.value)
        for col, w in self._src_widgets.items():
            w.set_connected(col in connected_src)

    def _rebuild_lines(self) -> None:
        connections: list[tuple] = []
        connected_src: set[str] = set()

        # 비요인 컬럼 연결선
        for qpr_col, qpr_w in self._qpr_widgets.items():
            rule = self._ruleset.get(qpr_col)
            if not rule:
                continue
            qpr_cy = qpr_w.height() // 2
            if rule.mode == MappingMode.COLUMN and rule.value:
                src_w = self._src_widgets.get(rule.value)
                if src_w:
                    connections.append((src_w, src_w.height() // 2, qpr_w, qpr_cy, _PEN_NORMAL))
                    connected_src.add(rule.value)
            elif rule.mode == MappingMode.DEFAULT:
                connections.append((None, 0, qpr_w, qpr_cy, _PEN_DEFAULT))

        # 요인 패널 다중 슬롯 연결선
        for cause_type, panel in self._cause_panels.items():
            pairs = self._cause_mapping.get_pairs(cause_type)
            for slot_idx, pair in enumerate(pairs):
                slot_cy = int(panel.slot_center_y(slot_idx))
                if pair.cause_src and pair.cause_src in self._src_widgets:
                    src_w = self._src_widgets[pair.cause_src]
                    connections.append((src_w, src_w.height() // 2, panel, slot_cy, _PEN_CAUSE))
                    connected_src.add(pair.cause_src)
                if pair.qty_src and pair.qty_src in self._src_widgets:
                    src_w = self._src_widgets[pair.qty_src]
                    connections.append((src_w, src_w.height() // 2, panel, slot_cy, _PEN_CAUSE_QTY))
                    connected_src.add(pair.qty_src)

        self._line_area.set_connections(connections)

        for col, w in self._src_widgets.items():
            w.set_connected(col in connected_src)

    # ------------------------------------------------------------------
    def _on_qpr_col_clicked(self, qpr_col: str) -> None:
        rule = self._ruleset.get(qpr_col, MappingRule.make_blank())
        dlg = MappingDialog(qpr_col, rule, self._source_headers, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_rule = dlg.get_rule()
            if new_rule is not None:
                self.rule_changed.emit(qpr_col, new_rule)

    def _on_cause_slots_changed(self, cause_type: str, pairs: list) -> None:
        self._cause_mapping.get_pairs(cause_type)[:] = pairs
        self._rebuild_lines()
        # 패널 크기 변경 후 레이아웃 재배치가 끝나면 선 위치도 재갱신
        QTimer.singleShot(0, self._line_area.update)
        self.cause_mapping_changed.emit(self._cause_mapping)
