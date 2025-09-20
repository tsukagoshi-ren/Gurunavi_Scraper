@echo off
title Beyond Gurunavi Scraper ビルド

echo ========================================
echo   Beyond Gurunavi Scraper
echo   自動ビルド & パッケージング
echo ========================================
echo.

REM Python環境確認
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Pythonがインストールされていません
    pause
    exit /b 1
)

REM PyInstallerインストール確認
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstallerをインストール中...
    pip install pyinstaller
)

REM ビルドスクリプト実行
python build_package.py

pause