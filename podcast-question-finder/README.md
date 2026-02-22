# Podcast 時間軸產生器

上傳 Podcast 音檔，AI 自動產出 YouTube 章節時間軸。

## 功能

- **AI 自動產生時間軸** — 上傳音檔後，自動分析節目結構並產出章節時間軸
- **訪綱比對時間軸** — 輸入訪談大綱，AI 從逐字稿中找出每個題目對應的時間點
- **YouTube 格式輸出** — 可直接複製貼上到 YouTube 描述欄
- **下載 TXT / CSV** — 方便後續使用

## 本地運行（Mac Mini）

### 一鍵安裝啟動

```bash
cd podcast-question-finder
chmod +x setup_and_run.sh
./setup_and_run.sh
```

腳本會自動：
1. 檢查 Python 與 FFmpeg
2. 建立虛擬環境並安裝依賴
3. 提示輸入 Anthropic API Key（如果尚未設定）
4. 啟動 Flask 本地伺服器（http://localhost:5000）

### 手動安裝

```bash
# 安裝 FFmpeg（必要）
brew install ffmpeg

# 安裝 Python 依賴
pip install -r requirements.txt

# 設定 API Key
export ANTHROPIC_API_KEY="sk-ant-..."

# 啟動
python flask_app.py
```

開啟瀏覽器前往 http://localhost:5000 即可使用。

## 技術架構

- **Flask** — 本地 Web 伺服器
- **faster-whisper** — 語音轉文字（本地執行，不需雲端）
- **Anthropic Claude** — AI 分析節目結構與訪綱比對
- **FFmpeg** — 音訊處理
