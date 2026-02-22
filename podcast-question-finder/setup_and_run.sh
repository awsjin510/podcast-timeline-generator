#!/bin/bash
# ============================================================
# Podcast 時間軸產生器 — 一鍵設定與啟動腳本（Flask 本地版）
# 使用方式：在 podcast-question-finder 資料夾內執行
#   chmod +x setup_and_run.sh
#   ./setup_and_run.sh
# ============================================================

set -e

echo "=========================================="
echo " Podcast 時間軸產生器 安裝程式"
echo "=========================================="
echo ""

# ── 1. 檢查 Python ──────────────────────────
echo "🔍 檢查 Python..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
    PIP=pip3
elif command -v python &> /dev/null; then
    PYTHON=python
    PIP=pip
else
    echo "❌ 找不到 Python，請先安裝 Python 3.10+"
    echo "   https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)
echo "   ✅ $PY_VERSION"

# ── 2. 檢查 FFmpeg ──────────────────────────
echo "🔍 檢查 FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    echo "   ✅ FFmpeg 已安裝"
else
    echo "❌ 找不到 FFmpeg，請先安裝："
    echo "   macOS:   brew install ffmpeg"
    echo "   Ubuntu:  sudo apt install ffmpeg"
    echo "   Windows: choco install ffmpeg"
    exit 1
fi

# ── 3. 建立虛擬環境 ─────────────────────────
echo "📦 建立虛擬環境..."
if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
    echo "   ✅ 虛擬環境已建立"
else
    echo "   ✅ 虛擬環境已存在"
fi

source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# ── 4. 安裝依賴套件 ─────────────────────────
echo "📥 安裝套件（首次可能需要幾分鐘）..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "   ✅ 套件安裝完成"

# ── 5. 檢查 API Key ─────────────────────────
echo ""
if [ -z "$ANTHROPIC_API_KEY" ]; then
    # 嘗試從 .env 讀取
    if [ -f ".env" ]; then
        source .env 2>/dev/null
    fi

    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "⚠️  未偵測到 ANTHROPIC_API_KEY"
        echo "   請輸入你的 Anthropic API Key（sk-ant-... 開頭）："
        read -r ANTHROPIC_API_KEY
        export ANTHROPIC_API_KEY
    fi
fi

echo "   ✅ API Key 已設定（${ANTHROPIC_API_KEY:0:12}...）"

# ── 6. 啟動 ─────────────────────────────────
echo ""
echo "=========================================="
echo " 🚀 啟動 Podcast 時間軸產生器"
echo " 瀏覽器開啟 http://localhost:5000"
echo " 按 Ctrl+C 停止"
echo "=========================================="
echo ""

$PYTHON flask_app.py
