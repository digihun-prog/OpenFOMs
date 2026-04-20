from __future__ import annotations
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFileDialog, QMessageBox,
    QDockWidget, QToolBar, QStatusBar, QDialog, QInputDialog,
    QTabWidget, QSplitter,
)

from ..models.mapping_rule import MappingRule, MappingRuleSet
from ..models.project_config import ProjectConfig
from ..services.file_loader import SourceFileLoader
from ..services.mapping_service import MappingService
from ..services.qpr_builder import QPRBuilder
from ..services.project_store import ProjectStore
from .mapping_view import MappingView
from .result_view import ResultView
from .preview_view import PreviewView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FOM Assist")
        self.resize(1100, 780)

        # 서비스
        self._loader  = SourceFileLoader()
        self._store   = ProjectStore()
        self._builder = QPRBuilder()
        self._service: MappingService | None = None

        # 상태
        self._source_headers: list[str] = []
        self._source_rows:    list[dict] = []
        self._source_path:    str = ""
        self._project:        ProjectConfig | None = None
        self._ruleset:        MappingRuleSet = {}

        self._setup_toolbar()
        self._setup_central()
        self._setup_docks()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("CSV 파일을 불러오거나 프로젝트를 선택하세요.")

    # ------------------------------------------------------------------
    # 레이아웃 구성
    # ------------------------------------------------------------------

    def _setup_toolbar(self) -> None:
        tb = QToolBar("도구")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_csv = tb.addAction("📂 CSV 불러오기")
        act_csv.setToolTip("원천 데이터 CSV 파일을 불러옵니다")
        act_csv.triggered.connect(self._on_load_csv)

        tb.addSeparator()

        act_proj_load = tb.addAction("🗂 프로젝트 불러오기")
        act_proj_load.setToolTip("저장된 매핑 규칙을 불러옵니다")
        act_proj_load.triggered.connect(self._on_load_project)

        act_proj_save = tb.addAction("💾 프로젝트 저장")
        act_proj_save.setToolTip("현재 매핑 규칙을 프로젝트에 저장합니다")
        act_proj_save.triggered.connect(self._on_save_project)

        tb.addSeparator()

        act_auto = tb.addAction("✨ 자동 매핑")
        act_auto.setToolTip("원천 컬럼명과 QPR 컬럼명이 동일하면 자동 연결합니다")
        act_auto.triggered.connect(self._on_auto_match)

        tb.addSeparator()

        act_gen = tb.addAction("▶ QPR 생성")
        act_gen.setToolTip("매핑 규칙을 적용해 QPR CSV 파일을 생성합니다")
        act_gen.triggered.connect(self._on_generate_qpr)

    def _setup_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._mapping_view = MappingView()
        self._mapping_view.rule_changed.connect(self._on_rule_changed)
        self._mapping_view.cause_mapping_changed.connect(self._on_cause_mapping_changed)

        self._tabs = QTabWidget()
        self._preview_view = PreviewView()
        self._tabs.addTab(self._preview_view, "미리보기")

        splitter.addWidget(self._mapping_view)
        splitter.addWidget(self._tabs)
        splitter.setSizes([700, 380])

        self.setCentralWidget(splitter)

    def _setup_docks(self) -> None:
        self._result_view = ResultView()
        dock = QDockWidget("유효성 / 생성 결과", self)
        dock.setWidget(self._result_view)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)

    # ------------------------------------------------------------------
    # 슬롯
    # ------------------------------------------------------------------

    def _on_load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "원천 파일 불러오기", "",
            "지원 파일 (*.csv *.xlsx *.xlsm *.xls);;CSV (*.csv);;Excel (*.xlsx *.xlsm *.xls);;모든 파일 (*)"
        )
        if not path:
            return
        try:
            headers, rows, warnings = self._loader.load(path)
        except Exception as e:
            QMessageBox.critical(self, "파일 로드 오류", str(e))
            return

        self._source_headers = headers
        self._source_rows    = rows
        self._source_path    = path
        self._service = MappingService(headers)

        # 기존 룰셋 없으면 기본값으로 초기화
        if not self._ruleset:
            self._ruleset = self._service.make_default_ruleset()

        self._mapping_view.set_source_columns(headers)
        self._mapping_view.set_ruleset(self._ruleset)
        self._refresh_validation()
        self._preview_view.show_source(headers, rows)

        fname = os.path.basename(path)
        msg = f"'{fname}' 로드 완료 — {len(rows)}행, {len(headers)}개 컬럼"
        if warnings:
            msg += f" | 경고 {len(warnings)}건"
        self.statusBar().showMessage(msg)

    def _on_load_project(self) -> None:
        projects = self._store.list_projects()
        if not projects:
            QMessageBox.information(self, "프로젝트 없음", "저장된 프로젝트가 없습니다.")
            return

        name, ok = QInputDialog.getItem(
            self, "프로젝트 선택", "프로젝트:", projects, 0, False
        )
        if not ok or not name:
            return

        config = self._store.load(name)
        if config is None:
            QMessageBox.warning(self, "로드 실패", f"프로젝트 '{name}'을 찾을 수 없습니다.")
            return

        self._project = config
        if config.rules:
            self._ruleset = config.rules
            self._mapping_view.set_ruleset(self._ruleset)
        self._mapping_view.set_cause_mapping(config.cause_mapping)
        self._refresh_validation()
        self.statusBar().showMessage(f"프로젝트 '{name}' 불러오기 완료.")

    def _on_save_project(self) -> None:
        if not self._ruleset:
            QMessageBox.information(self, "저장 불가", "매핑 규칙이 없습니다.")
            return

        if self._project:
            name = self._project.name
        else:
            projects = self._store.list_projects()
            name, ok = QInputDialog.getText(
                self, "프로젝트 저장", "프로젝트 이름:",
                text="Project_A"
            )
            if not ok or not name.strip():
                return
            name = name.strip()

        if self._project is None or self._project.name != name:
            self._project = self._store.create_project(name)

        self._project.rules = dict(self._ruleset)
        self._store.save(self._project)
        self.statusBar().showMessage(f"프로젝트 '{name}' 저장 완료.")

    def _on_auto_match(self) -> None:
        if not self._service:
            QMessageBox.information(self, "자동 매핑 불가", "CSV 파일을 먼저 불러오세요.")
            return
        self._ruleset = self._service.auto_match(self._ruleset)
        self._mapping_view.set_ruleset(self._ruleset)
        self._refresh_validation()
        self.statusBar().showMessage("자동 매핑 완료.")

    def _on_rule_changed(self, qpr_col: str, rule: MappingRule) -> None:
        self._ruleset[qpr_col] = rule
        self._refresh_validation()

    def _on_cause_mapping_changed(self, cm) -> None:
        if self._project:
            self._project.cause_mapping = cm
        self._refresh_validation()

    def _refresh_validation(self) -> None:
        if not self._service:
            return
        summary = self._service.validation_summary(self._ruleset)
        self._result_view.update_summary(summary)
        self._mapping_view.update_validation(summary)

    def _on_generate_qpr(self) -> None:
        if not self._source_rows:
            QMessageBox.warning(self, "생성 불가", "CSV 파일을 먼저 불러오세요.")
            return
        if not self._service:
            return

        errors = self._service.validate(self._ruleset)
        hard_errors = [e for e in errors if e.severity == "error"]
        if hard_errors:
            msg = "다음 오류를 먼저 해결하세요:\n\n"
            msg += "\n".join(f"• [{e.qpr_col}] {e.message}" for e in hard_errors)
            QMessageBox.warning(self, "유효성 오류", msg)
            return

        # 출력 경로 결정
        if self._project and self._source_path:
            out_path = self._store.output_path(self._project.name, self._source_path)
        else:
            out_path, _ = QFileDialog.getSaveFileName(
                self, "QPR 저장 위치", "output_qpr.csv", "CSV 파일 (*.csv)"
            )
            if not out_path:
                return

        try:
            cause_mapping = self._project.cause_mapping if self._project else None
            qpr_rows, stats = self._builder.build(self._source_rows, self._ruleset, cause_mapping)
            self._builder.write_csv(qpr_rows, out_path)
        except Exception as e:
            QMessageBox.critical(self, "생성 오류", str(e))
            return

        # config.json 자동 생성/갱신 (§8, §14)
        self._save_config_after_generate(out_path)

        # 결과 표시
        self._result_view.show_success(out_path, stats)

        # 미리보기 업데이트
        from collections import defaultdict
        from ..models.qpr_schema import KEY_COLUMNS
        groups: dict = defaultdict(list)
        for row in qpr_rows:
            key = tuple(row.get(c, "") for c in KEY_COLUMNS)
            groups[key].append(row)
        self._preview_view.show_qpr(qpr_rows, dict(groups))

        self.statusBar().showMessage(
            f"QPR 생성 완료: {stats.total_work_items}개 작업, "
            f"{stats.total_main_rows}행 주행, {stats.total_cause_rows}행 요인"
        )

    def _save_config_after_generate(self, qpr_output_path: str) -> None:
        """QPR 생성 성공 직후 config.json을 프로젝트 폴더에 저장한다 (§8.1)."""
        import os as _os
        from ..models.project_config import ProjectConfig

        if self._project:
            config = self._project
        else:
            project_dir = _os.path.dirname(qpr_output_path)
            config = ProjectConfig(name="(unnamed)", project_dir=project_dir)

        config.rules = dict(self._ruleset)
        config.source_file = self._source_path
        config.source_headers = list(self._source_headers)

        try:
            self._store.save_config(
                config,
                qpr_output_path,
                delimiter=getattr(self._loader, "delimiter", ","),
            )
        except Exception as e:
            self.statusBar().showMessage(
                self.statusBar().currentMessage() + f"  ⚠ config.json 저장 실패: {e}"
            )
