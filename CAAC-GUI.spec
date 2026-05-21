# -*- mode: python ; coding: utf-8 -*-
import sys, os

block_cipher = None

# 收集数据文件
datas = []
data_src = os.path.join(os.path.dirname(SPECPATH), "src", "data")
if os.path.exists(data_src):
    datas.append((data_src, "data"))

frontend_src = os.path.join(os.path.dirname(SPECPATH), "src", "frontend")
if os.path.exists(frontend_src):
    datas.append((frontend_src, "frontend"))

a = Analysis(
    ["run_gui.py"],
    pathex=[os.path.dirname(SPECPATH)],
    binaries=[],
    datas=datas,
    hiddenimports=["jieba", "rank_bm25", "PyQt5", "PyQt5.QtCore", "PyQt5.QtWidgets", "PyQt5.QtGui"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CAAC-RegSearch-GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # 无控制台窗口（纯GUI）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # 可自行替换 icon.ico
    version="version_info.txt",
)
