from __future__ import annotations
import os
import sys

_BACKEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ""))

if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from parser import load_csv_rows
from validators import normalize_row


def _load_excel_rows(file_path: str) -> tuple[list[str], list[dict], list[str]]:
    """
    XLS/XLSX 파일을 읽어 (headers, rows, warnings) 반환.
    XLSX → openpyxl, XLS → xlrd 사용.
    """
    warnings: list[str] = []
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".xls":
        try:
            import xlrd
        except ImportError:
            raise ImportError(
                "XLS 파일을 읽으려면 xlrd 패키지가 필요합니다.\n"
                "pip install xlrd 로 설치하세요."
            )
        wb = xlrd.open_workbook(file_path)
        ws = wb.sheet_by_index(0)
        if ws.nrows == 0:
            return [], [], ["파일이 비어 있습니다."]
        headers = [str(ws.cell_value(0, c)).strip() for c in range(ws.ncols)]
        rows: list[dict] = []
        for r in range(1, ws.nrows):
            row = {}
            for c, h in enumerate(headers):
                val = ws.cell_value(r, c)
                # xlrd는 숫자를 float로 반환 — 정수처럼 보이면 정수형 문자열로
                if isinstance(val, float) and val == int(val):
                    row[h] = str(int(val))
                else:
                    row[h] = str(val) if val is not None else ""
            rows.append(row)

    else:  # .xlsx / .xlsm
        try:
            import openpyxl
        except ImportError:
            raise ImportError(
                "XLSX 파일을 읽으려면 openpyxl 패키지가 필요합니다.\n"
                "pip install openpyxl 로 설치하세요."
            )
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active
        raw = list(ws.iter_rows(values_only=True))
        wb.close()
        if not raw:
            return [], [], ["파일이 비어 있습니다."]
        headers = [str(c).strip() if c is not None else "" for c in raw[0]]
        rows = []
        for raw_row in raw[1:]:
            row = {}
            for h, val in zip(headers, raw_row):
                if val is None:
                    row[h] = ""
                elif isinstance(val, float) and val == int(val):
                    row[h] = str(int(val))
                else:
                    row[h] = str(val)
            rows.append(row)

    if not headers:
        warnings.append("헤더 행을 찾을 수 없습니다.")
    return headers, rows, warnings


class SourceFileLoader:
    def __init__(self):
        self.delimiter = ","

    def load(
        self,
        file_path: str,
        delimiter: str = ",",
    ) -> tuple[list[str], list[dict], list[str]]:
        """
        CSV / XLS / XLSX 파일을 읽어 (headers, normalized_rows, warnings) 반환.
        """
        self.delimiter = delimiter
        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".xls", ".xlsx", ".xlsm"):
            headers, rows, warnings = _load_excel_rows(file_path)
        else:
            rows, headers, warnings = load_csv_rows(file_path, delimiter=delimiter)
            headers = list(headers)

        normalized = [normalize_row(row) for row in rows]
        return headers, normalized, warnings
