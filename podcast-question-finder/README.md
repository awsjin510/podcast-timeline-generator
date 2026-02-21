# Podcast 時間軸產生器

上傳 Podcast 音檔，AI 自動產出 YouTube 章節時間軸。

## 功能

- **AI 自動產生時間軸** — 上傳音檔後，自動分析節目結構並產出 10 個章節時間軸
- **訪綱比對時間軸** — 輸入訪談大綱，AI 從逐字稿中找出每個題目對應的時間點
- **YouTube 格式輸出** — 可直接複製貼上到 YouTube 描述欄
- **下載 TXT / CSV** — 方便後續使用

## 部署到 Streamlit Cloud

1. Fork 或 clone 這個 repo
2. 前往 [share.streamlit.io](https://share.streamlit.io)
3. 選擇這個 repo，主檔案設為 `app.py`
4. 在 **Secrets** 中加入：
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-api03-..."
   ```
5. 點擊 Deploy

## 本地運行

```bash
# 安裝 FFmpeg（必要）
# Windows: winget install Gyan.FFmpeg
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg

pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-key-here"
streamlit run app.py
```

## 技術架構

- **Streamlit** — Web UI
- **OpenAI Whisper** — 語音轉文字
- **Anthropic Claude** — AI 分析節目結構與訪綱比對
- **FFmpeg** — 音訊處理
