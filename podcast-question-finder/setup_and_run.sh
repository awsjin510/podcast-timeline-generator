#!/bin/bash
# ============================================================
# Podcast Question Extractor — 一鍵設定與啟動腳本
# 使用方式：在 podcast-question-finder 資料夾內執行
#   chmod +x setup_and_run.sh
#   ./setup_and_run.sh
# ============================================================

set -e

echo "=========================================="
echo " Podcast Question Extractor 安裝程式"
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
if [ -z "$OPENAI_API_KEY" ]; then
    # 嘗試從 .env 讀取
    if [ -f ".env" ]; then
        source .env 2>/dev/null
    fi

    # 嘗試從 ~/.openclaw/openclaw.json 讀取
    if [ -z "$OPENAI_API_KEY" ] && [ -f "$HOME/.openclaw/openclaw.json" ]; then
        echo "🔑 嘗試從 ~/.openclaw/openclaw.json 讀取 API Key..."
        KEY=$(python3 -c "
import json, sys
try:
    with open('$HOME/.openclaw/openclaw.json') as f:
        data = json.load(f)
    # 常見的 key 路徑
    for k in ['openai_api_key', 'OPENAI_API_KEY', 'api_key', 'apiKey']:
        if k in data:
            print(data[k])
            sys.exit(0)
    # 搜尋巢狀結構
    for v in data.values():
        if isinstance(v, str) and v.startswith('sk-'):
            print(v)
            sys.exit(0)
        if isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, str) and vv.startswith('sk-'):
                    print(vv)
                    sys.exit(0)
except Exception:
    pass
" 2>/dev/null)

        if [ -n "$KEY" ]; then
            export OPENAI_API_KEY="$KEY"
            echo "   ✅ 已從 openclaw.json 取得 API Key"
        fi
    fi

    if [ -z "$OPENAI_API_KEY" ]; then
        echo "⚠️  未偵測到 OPENAI_API_KEY"
        echo "   請輸入你的 OpenAI API Key（sk-... 開頭）："
        read -r OPENAI_API_KEY
        export OPENAI_API_KEY
    fi
fi

echo "   ✅ API Key 已設定（${OPENAI_API_KEY:0:8}...）"

# ── 6. 啟動 ─────────────────────────────────
echo ""
echo "=========================================="
echo " 🚀 啟動 Podcast Question Extractor"
echo " 瀏覽器將自動開啟 http://localhost:8501"
echo " 按 Ctrl+C 停止"
echo "=========================================="
echo ""

streamlit run app.py
