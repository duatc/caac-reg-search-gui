"""
CAAC-RegSearch GUI 启动器
直接运行此文件启动图形界面
"""
import sys, os

# 确保能找到 rank_bm25 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PyQt5.QtWidgets import QApplication
from caac_reg_search.main_window import CAACSearchWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CAAC-RegSearch")
    app.setOrganizationName("duatc")
    app.setOrganizationDomain("caac.cn")

    # Windows 高 DPI 支持
    from PyQt5.QtCore import Qt
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    window = CAACSearchWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
