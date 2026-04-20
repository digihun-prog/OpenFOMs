import sys
import os

# PySide6 고해상도 지원
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

# d:/OpenFOMs 를 sys.path에 추가 — "Assist" 패키지를 찾을 수 있도록
_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from Assist.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("FOM Assist")

    # 한국어 폰트 지정 (Windows)
    font = QFont("Malgun Gothic", 9)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
