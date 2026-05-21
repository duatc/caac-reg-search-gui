"""
CAAC-RegSearch 图形交互界面 - 主窗口
基于 PyQt5，支持 Windows/macOS/Linux
"""
import sys, os, json, re, threading
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTextBrowser,
    QLabel, QSplitter, QFrame, QScrollArea, QStatusBar,
    QMenuBar, QMenu, QAction, QToolBar, QComboBox,
    QApplication, QMainWindow, QDockWidget, QListView,
    QGraphicsOpacityEffect, QSizePolicy, QSpacerItem,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QTextCharFormat, QTextCursor, QPainter, QBrush, QPen, QLinearGradient

# ===================== 资源路径 =====================
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
INDEX_FILE = os.path.join(DATA_DIR, "docs.json")
FRONTEND_DIR = os.path.join(APP_DIR, "frontend")


# ===================== 搜索后端（分词 + BM25）=====================
import jieba
from rank_bm25 import BM25Okapi

jieba.setLogLevel(jieba.logging.INFO)

_tokenizer_cache = None
_bm25_cache = None
_docs_cache = None


def tokenize(text: str):
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9\s]", " ", text)
    return [w.strip() for w in jieba.cut(text) if w.strip() and len(w.strip()) > 1]


def load_index():
    global _bm25_cache, _docs_cache
    if _bm25_cache is None:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _docs_cache = data["docs"]
        tokenized = data["tokenized"]
        _bm25_cache = BM25Okapi(tokenized)
    return _bm25_cache, _docs_cache


def search_backend(query: str, top_k: int = 10):
    if not query or not query.strip():
        return []
    try:
        bm25, docs = load_index()
    except Exception:
        return []
    query_tokens = tokenize(query)
    scores = bm25.get_scores(query_tokens)
    ranked = sorted(zip(scores, docs), key=lambda x: -x[0])
    results = []
    for score, doc in ranked[:top_k]:
        if score <= 0:
            continue
        snippet = _extract_snippet(doc["content"], query_tokens)
        results.append({
            "title": doc["title"],
            "content": snippet,
            "full_content": doc["content"],
            "source_file": doc["source"],
            "score": round(float(score), 4),
        })
    return results


def _extract_snippet(content: str, query_tokens, window=150):
    content_lower = content.lower()
    first_pos = -1
    for token in query_tokens:
        pos = content_lower.find(token.lower())
        if pos != -1 and (first_pos == -1 or pos < first_pos):
            first_pos = pos
    if first_pos == -1:
        return content[:300].strip()
    start = max(0, first_pos - window)
    end = min(len(content), first_pos + window)
    snippet = content[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."
    return snippet


# ===================== 法规分类数据 =====================
REG_CATEGORIES = {
    "全部": None,
    "管制运行": ["CCAR-93 空中交通管理规则.md", "CCAR-70 管制培训管理规则.md"],
    "情报通信": ["CCAR-82 情报工作规则.md", "CCAR-115 通信导航监视工作规则.md"],
    "航空器运行": ["CCAR-91 一般运行和飞行规则.md", "CCAR-92 无人驾驶航空器运行安全管理规则.md"],
    "维修管理": ["CCAR-66 维修执照规则.md"],
    "安全管理": ["CCAR-140 民用航空安全管理规定.md", "CCAR-339SB 民用航空安全检查规则.md"],
    "通航经营": ["CCAR-339SA 通用航空经营许可管理规定.md"],
}


# ===================== 配色方案（民航专业风格）=====================
COLOR_BG = "#f0f4f8"           # 浅灰蓝背景
COLOR_SIDEBAR = "#0d2137"      # 深蓝导航栏
COLOR_SIDEBAR_HOVER = "#1a3a5c"
COLOR_ACCENT = "#1a5fa8"       # 航空蓝
COLOR_ACCENT_LIGHT = "#3a8ae8"
COLOR_TEXT_PRIMARY = "#1a1a2e" # 深色正文
COLOR_TEXT_SECONDARY = "#5a6a7a"
COLOR_TEXT_LIGHT = "#e8eef4"   # 侧边栏浅色文字
COLOR_BORDER = "#d0dae8"
COLOR_CARD_BG = "#ffffff"
COLOR_CARD_HOVER = "#f5f8fc"
COLOR_SCORE_HIGH = "#e84040"   # 高分红色
COLOR_SCORE_LOW = "#4caf50"    # 低分绿色
COLOR_MATCH_HIGHLIGHT = "#fff3cd"
COLOR_TOOLBAR_BG = "#1a3a6b"
COLOR_STATUS_BG = "#0d2137"


# ===================== 主窗口 =====================
class CAACSearchWindow(QMainWindow):
    search_requested = pyqtSignal(str, str)   # (query, category)
    search_finished = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.current_results = []
        self.current_query = ""
        self.selected_index = -1
        self.is_loading = False
        self.filtered_results = []

        self._init_ui()
        self._init_signals()
        self._check_index()

    # ── 界面构建 ────────────────────────────────────────────
    def _init_ui(self):
        self.setWindowTitle("CAAC-RegSearch 民航法规智能检索系统")
        self.setMinimumSize(1200, 760)
        self.resize(1400, 840)

        # 居中显示
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move((geo.width() - self.width()) // 2, (geo.height() - self.height()) // 2 - 30)

        # 设置样式
        self.setStyleSheet(self._build_stylesheet())
        self.setFont(QFont("微软雅黑", 10))

        # 中央组件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧边栏
        self.sidebar = self._build_sidebar()
        main_layout.addWidget(self.sidebar, 0)

        # 右侧主区域（搜索框 + 结果列表 + 详情）
        content_widget = self._build_content_area()
        main_layout.addWidget(content_widget, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.status_bar.setFixedHeight(28)
        self.status_bar.setStyleSheet(
            f"QStatusBar {{ background:{COLOR_STATUS_BG}; color:{COLOR_TEXT_LIGHT}; font-size:12px; padding-left:10px; }}"
            f"QStatusBar::item {{ border: none; }}"
        )
        self.setStatusBar(self.status_bar)
        self._update_status("就绪")

    def _build_stylesheet(self) -> str:
        return f"""
        QMainWindow {{ background:{COLOR_BG}; }}
        /* 搜索框 */
        QLineEdit#searchInput {{
            border: 2px solid {COLOR_BORDER};
            border-radius: 8px;
            padding: 10px 16px;
            font-size: 15px;
            background: white;
            color: {COLOR_TEXT_PRIMARY};
            selection-background-color: {COLOR_ACCENT};
        }}
        QLineEdit#searchInput:focus {{
            border-color: {COLOR_ACCENT};
            background: #f8fbff;
        }}
        QLineEdit#searchInput::placeholder {{
            color: {COLOR_TEXT_SECONDARY};
        }}
        /* 搜索按钮 */
        QPushButton#searchBtn {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_ACCENT}, stop:1 {COLOR_ACCENT_LIGHT});
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 24px;
            font-size: 15px;
            font-weight: bold;
            min-width: 100px;
        }}
        QPushButton#searchBtn:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_ACCENT_LIGHT}, stop:1 #5aa0f8); }}
        QPushButton#searchBtn:disabled {{ background: #b0c8e0; color: #d0dde8; }}
        /* 分类按钮 */
        QPushButton#categoryBtn {{
            background: transparent;
            color: {COLOR_TEXT_LIGHT};
            border: none;
            border-radius: 6px;
            padding: 8px 14px;
            font-size: 13px;
            text-align: left;
        }}
        QPushButton#categoryBtn:hover {{ background: {COLOR_SIDEBAR_HOVER}; }}
        QPushButton#categoryBtn.active {{
            background: {COLOR_ACCENT};
            font-weight: bold;
        }}
        /* 结果列表项 */
        QListWidget#resultsList {{
            border: none;
            background: transparent;
            outline: none;
            padding: 8px;
        }}
        QListWidget#resultsList::item {{
            padding: 0;
            margin-bottom: 8px;
            border: none;
            background: transparent;
        }}
        /* 结果卡片 */
        QFrame#resultCard {{
            background: {COLOR_CARD_BG};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
        }}
        QFrame#resultCard:hover {{
            border-color: {COLOR_ACCENT};
            background: {COLOR_CARD_HOVER};
        }}
        /* 详情面板 */
        QTextBrowser#detailView {{
            border: none;
            background: {COLOR_CARD_BG};
            color: {COLOR_TEXT_PRIMARY};
            font-size: 14px;
            line-height: 1.8;
            padding: 20px;
        }}
        /* 分类下拉框 */
        QComboBox {{
            background: rgba(255,255,255,0.1);
            color: {COLOR_TEXT_LIGHT};
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13px;
        }}
        QComboBox:hover {{ background: rgba(255,255,255,0.15); }}
        QComboBox::dropDown {{ border: none; color: {COLOR_TEXT_LIGHT}; }}
        QComboBox::downArrow {{ image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid {COLOR_TEXT_LIGHT}; }}
        QComboBox QAbstractItemView {{
            background: {COLOR_SIDEBAR};
            color: {COLOR_TEXT_LIGHT};
            selection-background-color: {COLOR_ACCENT};
            border: 1px solid rgba(255,255,255,0.1);
            padding: 4px;
        }}
        /* 滚动条 */
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 4px 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLOR_BORDER};
            border-radius: 4px;
            min-height: 40px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {COLOR_TEXT_SECONDARY}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        /* 工具栏 */
        QToolBar {{
            background: {COLOR_TOOLBAR_BG};
            border: none;
            padding: 4px 12px;
            spacing: 8px;
        }}
        QToolBar QLabel {{
            color: white;
            font-size: 15px;
            font-weight: bold;
        }}
        """

    # ── 侧边栏 ────────────────────────────────────────────
    def _build_sidebar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedWidth(260)
        frame.setStyleSheet(f"background:{COLOR_SIDEBAR};")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部 Logo 区
        logo_widget = QFrame()
        logo_widget.setFixedHeight(80)
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(20, 16, 20, 8)
        logo_title = QLabel("CAAC-RegSearch")
        logo_title.setStyleSheet(f"color:white; font-size:18px; font-weight:bold;")
        logo_sub = QLabel("民航法规智能检索系统")
        logo_sub.setStyleSheet(f"color:{COLOR_ACCENT_LIGHT}; font-size:11px; margin-top:2px;")
        logo_layout.addWidget(logo_title)
        logo_layout.addWidget(logo_sub)
        layout.addWidget(logo_widget)

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:rgba(255,255,255,0.08);")
        layout.addWidget(sep)

        # 搜索框区
        search_frame = QFrame()
        search_frame.setFixedHeight(110)
        s_layout = QVBoxLayout(search_frame)
        s_layout.setContentsMargins(16, 14, 16, 8)
        s_layout.setSpacing(8)

        self.sidebar_search = QLineEdit()
        self.sidebar_search.setObjectName("searchInput")
        self.sidebar_search.setPlaceholder("输入关键词搜索...")
        self.sidebar_search.setFixedHeight(40)
        self.sidebar_search.setStyleSheet(f"""
            QLineEdit#searchInput {{
                background: rgba(255,255,255,0.1);
                color: white;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
            }}
            QLineEdit#searchInput:focus {{
                border-color: {COLOR_ACCENT_LIGHT};
                background: rgba(255,255,255,0.12);
            }}
            QLineEdit#searchInput::placeholder {{ color: rgba(255,255,255,0.45); }}
        """)

        self.sidebar_search_btn = QPushButton("🔍  开始检索")
        self.sidebar_search_btn.setObjectName("searchBtn")
        self.sidebar_search_btn.setFixedHeight(36)
        self.sidebar_search_btn.setCursor(Qt.PointingHandCursor)
        self.sidebar_search_btn.setStyleSheet(f"""
            QPushButton#searchBtn {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {COLOR_ACCENT}, stop:1 {COLOR_ACCENT_LIGHT});
                color:white; border:none; border-radius:6px;
                font-size:13px; font-weight:bold;
            }}
            QPushButton#searchBtn:hover {{ background: {COLOR_ACCENT_LIGHT}; }}
        """)

        s_layout.addWidget(self.sidebar_search)
        s_layout.addWidget(self.sidebar_search_btn)
        layout.addWidget(search_frame)

        # 法规分类
        cat_label = QLabel("法规分类")
        cat_label.setStyleSheet(f"color:rgba(255,255,255,0.45); font-size:11px; font-weight:bold; padding:8px 16px 4px;")
        layout.addWidget(cat_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("border:none; background:transparent;")
        scroll.setFixedHeight(280)

        cat_widget = QWidget()
        cat_layout = QVBoxLayout(cat_widget)
        cat_layout.setContentsMargins(10, 4, 10, 4)
        cat_layout.setSpacing(2)

        self.category_buttons = {}
        for name in ["全部", "管制运行", "情报通信", "航空器运行", "维修管理", "安全管理", "通航经营"]:
            btn = QPushButton(f"  {name}")
            btn.setObjectName("categoryBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            if name == "全部":
                btn.setChecked(True)
                btn.setStyleSheet(f"""
                    QPushButton#categoryBtn {{
                        background:{COLOR_ACCENT};
                        color:white;
                        border:none; border-radius:6px;
                        padding:8px 14px; font-size:13px; text-align:left; font-weight:bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton#categoryBtn {{
                        background:transparent; color:rgba(255,255,255,0.75);
                        border:none; border-radius:6px;
                        padding:8px 14px; font-size:13px; text-align:left;
                    }}
                    QPushButton#categoryBtn:hover {{ background:{COLOR_SIDEBAR_HOVER}; }}
                """)
            btn.category_name = name
            btn.clicked.connect(self._on_category_clicked)
            self.category_buttons[name] = btn
            cat_layout.addWidget(btn)

        cat_layout.addStretch()
        scroll.setWidget(cat_widget)
        layout.addWidget(scroll)

        # 底部信息
        layout.addStretch()
        info_frame = QFrame()
        info_frame.setFixedHeight(50)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 6, 16, 8)
        v = QLabel("v1.0 | 民航法规知识库")
        v.setStyleSheet("color:rgba(255,255,255,0.3); font-size:10px;")
        info_layout.addWidget(v)
        layout.addWidget(info_frame)

        return frame

    # ── 主内容区 ────────────────────────────────────────────
    def _build_content_area(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"background:{COLOR_BG};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        toolbar = QToolBar()
        toolbar.setFixedHeight(46)
        toolbar.setStyleSheet(f"QToolBar {{ background:{COLOR_TOOLBAR_BG}; border:none; padding:0 16px; }}")
        tb_label = QLabel("  🔍 民航法规智能检索系统")
        tb_label.setStyleSheet("color:white; font-size:15px; font-weight:bold; padding:0 8px;")
        toolbar.addWidget(tb_label)
        toolbar.addSeparator()

        self.count_label = QLabel("共 0 条法规")
        self.count_label.setStyleSheet("color:rgba(255,255,255,0.7); font-size:12px; padding:0 8px;")
        toolbar.addWidget(self.count_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        self.index_status = QLabel("● 索引未加载")
        self.index_status.setStyleSheet("color:#ff6b6b; font-size:12px; padding:0 8px;")
        toolbar.addWidget(self.index_status)

        layout.addWidget(toolbar)

        # 搜索框（主内容区顶部）
        top_bar = QFrame()
        top_bar.setFixedHeight(72)
        top_bar.setStyleSheet(f"background:white; border-bottom:1px solid {COLOR_BORDER};")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(20, 12, 20, 12)
        tb_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholder("输入法规名称、关键词或条款内容，例如：跑道侵入、执照申请、流量管理...")
        self.search_input.setFixedHeight(48)

        self.search_btn = QPushButton("🔍  搜索")
        self.search_btn.setObjectName("searchBtn")
        self.search_btn.setFixedSize(110, 48)
        self.search_btn.setCursor(Qt.PointingHandCursor)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFixedSize(60, 48)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{ background:{COLOR_BG}; color:{COLOR_TEXT_SECONDARY};
                           border:1px solid {COLOR_BORDER}; border-radius:8px;
                           font-size:13px; }}
            QPushButton:hover {{ background:{COLOR_CARD_HOVER}; color:{COLOR_TEXT_PRIMARY}; }}
        """)

        tb_layout.addWidget(self.search_input, 1)
        tb_layout.addWidget(self.search_btn)
        tb_layout.addWidget(self.clear_btn)
        layout.addWidget(top_bar)

        # 结果区和详情面板（可分割）
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：结果列表
        self.results_list = QListWidget()
        self.results_list.setObjectName("resultsList")
        self.results_list.setSpacing(0)
        self.results_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.results_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.results_list.setItemDelegate(_ResultItemDelegate())
        self.results_list.itemClicked.connect(self._on_result_clicked)
        self.results_list.itemDoubleClicked.connect(self._on_result_double_clicked)

        left_panel = QWidget()
        left_panel.setStyleSheet(f"background:{COLOR_BG};")
        lp_layout = QVBoxLayout(left_panel)
        lp_layout.setContentsMargins(12, 8, 8, 0)
        lp_layout.setSpacing(0)
        lp_layout.addWidget(self.results_list)

        # 右侧：详情面板
        right_panel = QFrame()
        right_panel.setFrameShape(QFrame.StyledPanel)
        right_panel.setMinimumWidth(400)
        right_panel.setMaximumWidth(600)
        rp_layout = QVBoxLayout(right_panel)
        rp_layout.setContentsMargins(0, 0, 0, 0)

        detail_header = QFrame()
        detail_header.setFixedHeight(44)
        detail_header.setStyleSheet(f"background:white; border-bottom:2px solid {COLOR_ACCENT};")
        dh_layout = QHBoxLayout(detail_header)
        dh_layout.setContentsMargins(16, 0, 12, 0)
        dh_title = QLabel("📋  条款详情")
        dh_title.setStyleSheet(f"color:{COLOR_ACCENT}; font-size:14px; font-weight:bold;")
        dh_layout.addWidget(dh_title)
        dh_layout.addStretch()

        self.copy_btn = QPushButton("复制全文")
        self.copy_btn.setFixedHeight(28)
        self.copy_btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLOR_ACCENT}; color:white; border:none;
                border-radius:4px; padding:0 12px; font-size:12px;
            }}
            QPushButton:hover {{ background:{COLOR_ACCENT_LIGHT}; }}
        """)

        dh_layout.addWidget(self.copy_btn)

        self.detail_view = QTextBrowser()
        self.detail_view.setObjectName("detailView")
        self.detail_view.setOpenExternalLinks(True)
        self.detail_view.setPlaceholderText(
            "⬅️ 请从左侧搜索结果中选择一条，查看条款详情\n\n"
            "支持快速定位相关条款，复制所需内容"
        )
        self.detail_view.setStyleSheet(f"""
            QTextBrowser#detailView {{
                border: none;
                background: {COLOR_CARD_BG};
                color: {COLOR_TEXT_PRIMARY};
                font-size: 14px;
                line-height: 1.9;
                padding: 16px 20px;
                font-family: "微软雅黑", "宋体", serif;
            }}
        """)

        rp_layout.addWidget(detail_header)
        rp_layout.addWidget(self.detail_view, 1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setHandleWidth(4)

        layout.addWidget(splitter, 1)

        return widget

    # ── 信号连接 ────────────────────────────────────────────
    def _init_signals(self):
        self.search_btn.clicked.connect(self._do_search)
        self.sidebar_search_btn.clicked.connect(self._do_search)
        self.sidebar_search.returnPressed.connect(self._do_search)
        self.search_input.returnPressed.connect(self._do_search)
        self.search_input.textChanged.connect(self._on_input_changed)
        self.clear_btn.clicked.connect(self._clear_results)
        self.copy_btn.clicked.connect(self._copy_detail)

    # ── 索引检查 ────────────────────────────────────────────
    def _check_index(self):
        def check():
            if os.path.exists(INDEX_FILE):
                try:
                    size = os.path.getsize(INDEX_FILE) / 1024
                    self._update_index_status(f"● 索引已就绪 ({size:.0f} KB)", ok=True)
                    # 预加载索引
                    import threading
                    t = threading.Thread(target=load_index)
                    t.daemon = True
                    t.start()
                except Exception as e:
                    self._update_index_status(f"● 索引加载失败")
            else:
                self._update_index_status("⚠ 索引文件不存在，请先构建索引", ok=False)

        QTimer.singleShot(200, check)

    @QtCore.pyqtSlot(str)
    def _update_index_status(self, text: str, ok: bool = True):
        self.index_status.setText(text)
        if ok:
            self.index_status.setStyleSheet("color:#6ee3a3; font-size:12px; padding:0 8px;")
        else:
            self.index_status.setStyleSheet("color:#ff6b6b; font-size:12px; padding:0 8px;")

    @QtCore.pyqtSlot(str)
    def _update_status(self, text: str):
        self.status_bar.showMessage(f"  {text}", 3000)

    # ── 搜索 ────────────────────────────────────────────
    @QtCore.pyqtSlot()
    def _do_search(self):
        query = self.search_input.text().strip()
        if not query:
            query = self.sidebar_search.text().strip()
        if not query:
            self._update_status("请输入搜索关键词")
            return

        if self.is_loading:
            return

        self.current_query = query
        self.is_loading = True
        self.search_input.setEnabled(False)
        self.sidebar_search.setEnabled(False)
        self.search_btn.setEnabled(False)
        self._update_status(f"正在检索：「{query}」...")
        self._update_index_status("⏳ 检索中...", ok=True)

        # 后台线程搜索
        thread = threading.Thread(target=self._search_worker, args=(query, self.current_category), daemon=True)
        thread.start()

    def _search_worker(self, query, category):
        results = search_backend(query, top_k=20)

        # 按分类过滤
        if category and category != "全部":
            target_files = REG_CATEGORIES.get(category, [])
            if target_files:
                results = [r for r in results if r["source_file"] in target_files]

        self.filtered_results = results
        QMetaObject.invokeMethod(self, "_on_search_done", Qt.QueuedConnection,
                                 Q_ARG(list, results))

    @QtCore.pyqtSlot(list)
    def _on_search_done(self, results):
        self.is_loading = False
        self.search_input.setEnabled(True)
        self.sidebar_search.setEnabled(True)
        self.search_btn.setEnabled(True)
        self.current_results = results
        self._render_results(results)
        self._update_index_status("● 索引已就绪", ok=True)
        self._update_status(f"检索完成，共找到 {len(results)} 条相关条款")

    current_category = "全部"

    @QtCore.pyqtSlot()
    def _on_category_clicked(self):
        btn = self.sender()
        name = btn.category_name
        self.current_category = name

        for n, b in self.category_buttons.items():
            if n == name:
                b.setChecked(True)
                b.setStyleSheet(f"""
                    QPushButton#categoryBtn {{
                        background:{COLOR_ACCENT};
                        color:white; border:none; border-radius:6px;
                        padding:8px 14px; font-size:13px; text-align:left; font-weight:bold;
                    }}
                """)
            else:
                b.setChecked(False)
                b.setStyleSheet(f"""
                    QPushButton#categoryBtn {{
                        background:transparent; color:rgba(255,255,255,0.75);
                        border:none; border-radius:6px;
                        padding:8px 14px; font-size:13px; text-align:left;
                    }}
                    QPushButton#categoryBtn:hover {{ background:{COLOR_SIDEBAR_HOVER}; }}
                """)

        if self.current_results:
            self._do_search()

    def _render_results(self, results):
        self.results_list.clear()
        if not results:
            item_widget = QWidget()
            layout = QVBoxLayout(item_widget)
            layout.setContentsMargins(20, 30, 20, 30)
            empty = QLabel("未找到相关法规条款\n\n请尝试更换关键词，或检查索引文件是否已构建")
            empty.setStyleSheet(
                f"color:{COLOR_TEXT_SECONDARY}; font-size:14px; "
                "text-align:center; padding:20px; background:transparent;"
            )
            empty.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty)
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(200, 100))
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, item_widget)
            self.count_label.setText("共 0 条法规")
            return

        self.count_label.setText(f"共 {len(results)} 条法规")
        for i, r in enumerate(results):
            list_item = QListWidgetItem()
            list_item.setData(Qt.UserRole, i)
            card = _ResultCard(r, i + 1, self.current_query)
            list_item.setSizeHint(card.sizeHint())
            self.results_list.addItem(list_item)
            self.results_list.setItemWidget(list_item, card)

    @QtCore.pyqtSlot()
    def _on_input_changed(self):
        pass  # 可扩展：实时搜索

    @QtCore.pyqtSlot(QListWidgetItem)
    def _on_result_clicked(self, item):
        idx = item.data(Qt.UserRole)
        if idx is None or idx < 0 or idx >= len(self.current_results):
            return
        self.selected_index = idx
        self._show_detail(self.current_results[idx])

    @QtCore.pyqtSlot(QListWidgetItem)
    def _on_result_double_clicked(self, item):
        self._on_result_clicked(item)

    def _show_detail(self, result):
        title = result["title"]
        source = result["source_file"]
        content = result.get("full_content", result["content"])
        score = result["score"]

        # 生成高亮版内容（关键词标红）
        highlighted = self._highlight_text(content, self.current_query)

        html = f"""
        <div style="font-family:'微软雅黑','宋体',serif; line-height:1.9; color:{COLOR_TEXT_PRIMARY};">
            <div style="background:linear-gradient(135deg,#1a3a6b,#1a5fa8); color:white;
                        padding:16px 20px; border-radius:8px 8px 0 0; margin:-16px -20px 20px -20px;">
                <div style="font-size:17px; font-weight:bold; margin-bottom:6px;">{title}</div>
                <div style="font-size:12px; opacity:0.8;">📁 {source}</div>
            </div>
            <div style="font-size:13px; color:{COLOR_TEXT_SECONDARY}; margin-bottom:16px;">
                相关度评分：<span style="color:{COLOR_ACCENT}; font-weight:bold;">{score}</span>
            </div>
            <hr style="border:none; border-top:1px solid {COLOR_BORDER}; margin:12px 0;">
            <div style="font-size:14px; color:{COLOR_TEXT_PRIMARY}; white-space:pre-wrap; text-align:justify;">
                {highlighted}
            </div>
        </div>
        """
        self.detail_view.setHtml(html)
        self.detail_view.moveCursor(QTextCursor.Start)

    def _highlight_text(self, text, query) -> str:
        if not query:
            return text
        tokens = tokenize(query)
        if not tokens:
            return text
        pattern = "|".join(re.escape(t) for t in tokens if len(t) > 1)
        if not pattern:
            return text
        highlighted = re.sub(
            f"({pattern})",
            r'<span style="background:#fff3cd; color:#c0392b; font-weight:bold; '
            'padding:0 2px; border-radius:3px;">\\1</span>',
            text,
            flags=re.IGNORECASE
        )
        return highlighted

    @QtCore.pyqtSlot()
    def _clear_results(self):
        self.search_input.clear()
        self.sidebar_search.clear()
        self.results_list.clear()
        self.current_results = []
        self.filtered_results = []
        self.detail_view.clear()
        self.detail_view.setPlaceholderText(
            "⬅️ 请从左侧搜索结果中选择一条，查看条款详情\n\n"
            "支持快速定位相关条款，复制所需内容"
        )
        self.count_label.setText("共 0 条法规")
        self._update_status("已清空搜索结果")

    @QtCore.pyqtSlot()
    def _copy_detail(self):
        cursor = self.detail_view.textCursor()
        text = cursor.selectedText() if cursor.hasSelection() else self.detail_viewtoPlainText()
        if not text:
            plain = self.detail_view.toPlainText()
            if plain and "请从左侧" not in plain:
                QApplication.clipboard().setText(plain)
                self._update_status("已复制到剪贴板")
                return
        QApplication.clipboard().setText(text)
        self._update_status("已复制到剪贴板")

    def _detail_viewtoPlainText(self):
        return self.detail_view.toPlainText()


# ===================== 结果卡片组件 =====================
class _ResultCard(QFrame):
    def __init__(self, result, rank, query=""):
        super().__init__()
        self.result = result
        self.rank = rank
        self.query = query
        self._init_ui()

    def sizeHint(self):
        return QSize(400, 160)

    def _init_ui(self):
        self.setObjectName("resultCard")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # 顶部：排名 + 标题 + 得分
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        rank_label = QLabel(f"#{self.rank}")
        rank_label.setFixedWidth(32)
        rank_label.setStyleSheet(
            f"color:{COLOR_ACCENT_LIGHT}; font-size:13px; font-weight:bold; "
            f"background:{COLOR_BG}; border-radius:4px; padding:2px 6px;"
        )

        title_label = QLabel(self.result["title"])
        title_label.setStyleSheet(f"color:{COLOR_TEXT_PRIMARY}; font-size:14px; font-weight:bold;")
        title_label.setWordWrap(True)

        top_layout.addWidget(rank_label)
        top_layout.addWidget(title_label, 1)
        top_layout.addStretch()

        # 得分标签
        score = self.result["score"]
        score_label = QLabel(f"{score:.1f}")
        score_label.setFixedWidth(50)
        score_color = COLOR_SCORE_HIGH if score > 15 else (COLOR_ACCENT if score > 5 else COLOR_SCORE_LOW)
        score_label.setStyleSheet(
            f"color:white; background:{score_color}; border-radius:4px; "
            f"padding:2px 8px; font-size:12px; font-weight:bold;"
        )

        top_layout.addWidget(score_label)
        layout.addLayout(top_layout)

        # 来源文件
        source_label = QLabel(f"📁 {self.result['source_file']}")
        source_label.setStyleSheet(f"color:{COLOR_TEXT_SECONDARY}; font-size:11px;")
        layout.addWidget(source_label)

        # 摘要
        snippet = self.result["content"]
        if self.query:
            snippet = self._highlight(snippet)
        else:
            snippet = f'<span style="color:{COLOR_TEXT_SECONDARY};">{snippet[:200]}...</span>'

        snippet_label = QLabel()
        snippet_label.setText(snippet)
        snippet_label.setWordWrap(True)
        snippet_label.setStyleSheet("font-size:13px; color:#444; line-height:1.7; padding:4px 0;")
        snippet_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(snippet_label)

    def _highlight(self, text) -> str:
        tokens = tokenize(self.query)
        if not tokens:
            return f'<span style="color:{COLOR_TEXT_SECONDARY};">{text[:200]}...</span>'
        pattern = "|".join(re.escape(t) for t in tokens if len(t) > 1)
        if not pattern:
            return f'<span style="color:{COLOR_TEXT_SECONDARY};">{text[:200]}...</span>'
        highlighted = re.sub(
            f"({pattern})",
            r'<span style="background:#fff3cd; color:#c0392b; font-weight:bold; padding:0 2px;">\\1</span>',
            text[:300], flags=re.IGNORECASE
        )
        return highlighted + (f'<span style="color:{COLOR_TEXT_SECONDARY};">...</span>' if len(text) > 300 else "")


# ===================== 结果列表代理（自定义间距）=====================
class _ResultItemDelegate(QAbstractItemView):
    pass


# ===================== 入口函数 =====================
def main():
    from PyQt5.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    app.setApplicationName("CAAC-RegSearch")
    window = CAACSearchWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
