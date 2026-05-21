@echo off
chcp 65001 >nul
echo ========================================
echo  CAAC-RegSearch GUI 构建脚本
echo ========================================

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

:: 创建虚拟环境（如果不存在）
if not exist venv (
    echo [1/4] 创建虚拟环境...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install --upgrade pip -q
) else (
    call venv\Scripts\activate.bat
)

:: 安装依赖
echo [2/4] 安装依赖...
pip install PyQt5 jieba rank-bm25 pyinstaller -q

:: 安装项目本身
pip install -e . -q

:: 构建
echo [3/4] 打包构建...
pyinstaller CAAC-GUI.spec --noconfirm

echo [4/4] 完成！
echo.
echo 可执行文件位于: dist\CAAC-RegSearch-GUI.exe
pause
