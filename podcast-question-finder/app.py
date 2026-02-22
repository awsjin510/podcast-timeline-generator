"""Podcast 時間軸產生器 — 霓虹燈風格 UI"""

import os
import shutil
import streamlit as st
import pandas as pd

from utils.audio import save_upload_to_disk, AudioValidationError, format_timestamp
from utils.transcriber import transcribe_audio
from utils.question_detector import extract_chapters, format_youtube_chapters, match_outline_to_timecodes

# ---------------------------------------------------------------------------
# Load API key from Streamlit Cloud secrets or env var
# ---------------------------------------------------------------------------

try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass  # No secrets.toml, use env var instead

st.set_page_config(
    page_title="Podcast 時間軸產生器",
    page_icon="🎙️",
    layout="wide",
)

if shutil.which("ffmpeg") is None:
    try:
        import imageio_ffmpeg
        _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        os.environ["PATH"] = os.path.dirname(_ffmpeg_exe) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

if shutil.which("ffmpeg") is None:
    st.error(
        "⚠️ 系統找不到 **FFmpeg**，Whisper 需要它來處理音訊檔案。\n\n"
        "- **Streamlit Cloud**：請確認 `packages.txt` 包含 `ffmpeg`\n"
        "- **Windows**：`winget install Gyan.FFmpeg`\n"
        "- **macOS**：`brew install ffmpeg`\n"
        "- **Linux**：`sudo apt install ffmpeg`"
    )
    st.stop()

# ---------------------------------------------------------------------------
# Neon CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=IBM+Plex+Mono:wght@400;500;600&family=Orbitron:wght@400;700;900&display=swap');

    /* ── Neon color palette ───────────────────────────── */
    :root {
        --neon-cyan: #00e5ff;
        --neon-cyan-dim: #00a5b8;
        --neon-pink: #ff2d95;
        --neon-pink-dim: #b8205a;
        --neon-purple: #b44dff;
        --glow-cyan: 0 0 7px #00e5ff, 0 0 15px #00e5ff, 0 0 30px #00e5ff44;
        --glow-cyan-strong: 0 0 7px #00e5ff, 0 0 15px #00e5ff, 0 0 30px #00e5ff, 0 0 60px #00e5ff44;
        --glow-pink: 0 0 7px #ff2d95, 0 0 15px #ff2d95, 0 0 30px #ff2d9544;
        --glow-purple: 0 0 7px #b44dff, 0 0 15px #b44dff, 0 0 30px #b44dff44;
        --bg-dark: #0a0a12;
        --bg-brick: #0d0e16;
        --surface: rgba(10, 10, 20, 0.7);
    }

    /* ── Dark brick-wall background ───────────────────── */
    .stApp {
        background:
            repeating-linear-gradient(
                0deg,
                transparent,
                transparent 48px,
                rgba(30,32,45,0.3) 48px,
                rgba(30,32,45,0.3) 50px
            ),
            repeating-linear-gradient(
                90deg,
                transparent,
                transparent 98px,
                rgba(30,32,45,0.2) 98px,
                rgba(30,32,45,0.2) 100px
            ),
            linear-gradient(180deg, #0a0a14 0%, #0d0e18 50%, #0a0c14 100%);
        color: #c8ccd4;
    }

    /* ── Neon title ───────────────────────────────────── */
    .neon-title {
        font-family: 'Noto Sans TC', sans-serif;
        font-size: 2.8rem;
        font-weight: 900;
        color: var(--neon-cyan);
        text-shadow: var(--glow-cyan-strong);
        margin-bottom: 0.15rem;
        letter-spacing: 0.05em;
        line-height: 1.3;
    }
    .neon-subtitle {
        font-family: 'Noto Sans TC', sans-serif;
        font-weight: 400;
        color: var(--neon-cyan-dim);
        font-size: 1rem;
        text-shadow: 0 0 8px #00e5ff44;
        margin-bottom: 2.2rem;
        opacity: 0.85;
    }

    /* ── Section labels ───────────────────────────────── */
    .neon-label {
        font-family: 'Noto Sans TC', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.18em;
        color: var(--neon-pink);
        text-shadow: var(--glow-pink);
        text-transform: uppercase;
        margin-bottom: 0.6rem;
        padding-bottom: 0.45rem;
        border-bottom: 1px solid rgba(255,45,149,0.2);
    }

    /* ── Metric cards (neon bordered) ─────────────────── */
    .neon-card {
        background: var(--surface);
        border: 1px solid var(--neon-cyan);
        box-shadow: var(--glow-cyan), inset 0 0 20px rgba(0,229,255,0.03);
        border-radius: 12px;
        padding: 1.3rem 1.4rem;
        text-align: center;
        transition: box-shadow 0.3s;
    }
    .neon-card:hover {
        box-shadow: var(--glow-cyan-strong), inset 0 0 30px rgba(0,229,255,0.06);
    }
    .neon-card .value {
        font-family: 'Orbitron', 'IBM Plex Mono', monospace;
        font-size: 2rem;
        font-weight: 700;
        color: var(--neon-cyan);
        text-shadow: var(--glow-cyan);
    }
    .neon-card .label {
        font-family: 'Noto Sans TC', sans-serif;
        font-size: 0.75rem;
        color: #667;
        margin-top: 0.3rem;
        letter-spacing: 0.06em;
    }

    /* ── Chapter rows ─────────────────────────────────── */
    .ch-row {
        display: flex;
        align-items: center;
        gap: 1.2rem;
        padding: 0.8rem 0;
        border-bottom: 1px solid rgba(0,229,255,0.06);
        font-family: 'Noto Sans TC', sans-serif;
        transition: background 0.2s;
    }
    .ch-row:hover {
        background: rgba(0,229,255,0.03);
    }
    .ch-row:last-child { border-bottom: none; }

    .ch-num {
        font-family: 'Orbitron', monospace;
        font-size: 0.65rem;
        color: var(--neon-purple);
        text-shadow: var(--glow-purple);
        width: 1.6rem;
        text-align: right;
        flex-shrink: 0;
        font-weight: 700;
    }
    .ch-ts {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--neon-cyan);
        text-shadow: 0 0 6px #00e5ff88;
        background: rgba(0,229,255,0.06);
        border: 1px solid rgba(0,229,255,0.15);
        padding: 0.25rem 0.65rem;
        border-radius: 5px;
        white-space: nowrap;
        flex-shrink: 0;
        letter-spacing: 0.04em;
    }
    .ch-title {
        font-size: 1rem;
        color: #d0d4dc;
        line-height: 1.45;
        text-shadow: 0 0 1px rgba(255,255,255,0.1);
    }

    /* ── YouTube code box ─────────────────────────────── */
    .stCodeBlock {
        border: 1px solid rgba(0,229,255,0.2) !important;
        box-shadow: 0 0 10px rgba(0,229,255,0.1) !important;
    }

    /* ── Upload area ──────────────────────────────────── */
    div[data-testid="stFileUploader"] {
        border: 2px dashed var(--neon-cyan-dim) !important;
        border-radius: 12px;
        padding: 0.5rem;
        box-shadow: 0 0 15px rgba(0,229,255,0.08);
        transition: box-shadow 0.3s;
    }
    div[data-testid="stFileUploader"]:hover {
        box-shadow: 0 0 25px rgba(0,229,255,0.15);
    }

    /* ── Primary button → neon pink ───────────────────── */
    .stButton > button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {
        background: transparent !important;
        color: var(--neon-pink) !important;
        border: 2px solid var(--neon-pink) !important;
        box-shadow: var(--glow-pink) !important;
        font-family: 'Noto Sans TC', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        letter-spacing: 0.08em !important;
        border-radius: 8px !important;
        transition: all 0.3s !important;
    }
    .stButton > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background: rgba(255,45,149,0.1) !important;
        box-shadow: 0 0 10px #ff2d95, 0 0 25px #ff2d95, 0 0 50px #ff2d9566 !important;
    }

    /* ── Download buttons → neon cyan ─────────────────── */
    .stDownloadButton > button {
        background: transparent !important;
        color: var(--neon-cyan) !important;
        border: 1px solid var(--neon-cyan) !important;
        box-shadow: 0 0 5px #00e5ff44 !important;
        font-family: 'Noto Sans TC', sans-serif !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        transition: all 0.3s !important;
    }
    .stDownloadButton > button:hover {
        background: rgba(0,229,255,0.08) !important;
        box-shadow: var(--glow-cyan) !important;
    }

    /* ── Sidebar ──────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #08080f 0%, #0c0d18 100%) !important;
        border-right: 1px solid rgba(0,229,255,0.1) !important;
    }
    section[data-testid="stSidebar"] .neon-label {
        color: var(--neon-cyan);
        text-shadow: 0 0 8px #00e5ff66;
        border-bottom-color: rgba(0,229,255,0.15);
    }

    /* ── Divider ──────────────────────────────────────── */
    hr {
        border-color: rgba(0,229,255,0.1) !important;
        box-shadow: 0 0 6px rgba(0,229,255,0.08);
    }

    /* ── Progress bar ─────────────────────────────────── */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, var(--neon-cyan), var(--neon-purple)) !important;
        box-shadow: 0 0 10px var(--neon-cyan) !important;
    }

    /* ── Scrollbar ────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0a0a14; }
    ::-webkit-scrollbar-thumb {
        background: var(--neon-cyan-dim);
        border-radius: 3px;
        box-shadow: 0 0 4px #00e5ff44;
    }

    /* ── Footer ───────────────────────────────────────── */
    .neon-footer {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        color: #334;
        text-align: center;
        margin-top: 2rem;
        letter-spacing: 0.05em;
    }

    /* ── Tabs ─────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid rgba(0,229,255,0.15);
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Noto Sans TC', sans-serif;
        font-weight: 600;
        color: #556;
        padding: 0.7rem 1.5rem;
        border: none;
        transition: all 0.3s;
    }
    .stTabs [aria-selected="true"] {
        color: var(--neon-cyan) !important;
        text-shadow: 0 0 8px #00e5ff66;
        border-bottom: 2px solid var(--neon-cyan) !important;
    }

    /* ── Textarea ─────────────────────────────────────── */
    .stTextArea textarea {
        background: rgba(10,10,20,0.8) !important;
        border: 1px solid rgba(0,229,255,0.2) !important;
        color: #d0d4dc !important;
        font-family: 'Noto Sans TC', sans-serif !important;
        border-radius: 8px !important;
    }
    .stTextArea textarea:focus {
        border-color: var(--neon-cyan) !important;
        box-shadow: 0 0 10px rgba(0,229,255,0.2) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown('<div class="neon-title">🎙️ Podcast 時間軸產生器</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="neon-subtitle">上傳 Podcast 音檔，AI 自動產出 YouTube 章節時間軸</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

for key, default in {
    "segments": None,
    "chapters": None,
    "outline_results": None,
    "processed": False,
    "audio_bytes": None,
    "filename": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<div class="neon-label">設定</div>', unsafe_allow_html=True)

    whisper_model = st.selectbox(
        "Whisper 模型",
        options=["tiny", "base", "small", "medium", "large"],
        index=1,
        help="模型越大轉錄越準確，但速度越慢。",
    )
    language = st.text_input(
        "語言代碼（選填）",
        placeholder="例如 zh、en、ja — 留空自動偵測",
    )
    llm_model = st.text_input(
        "Claude 模型",
        value="claude-sonnet-4-20250514",
        help="Anthropic 模型名稱。",
    )

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

col_upload, col_player = st.columns([1.2, 1])

with col_upload:
    st.markdown('<div class="neon-label">上傳音檔</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "將 Podcast 音檔拖曳至此",
        type=["mp3", "wav", "m4a", "ogg", "flac", "webm"],
        label_visibility="collapsed",
    )

with col_player:
    if uploaded_file is not None:
        st.markdown('<div class="neon-label">預覽播放</div>', unsafe_allow_html=True)
        audio_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        st.session_state.audio_bytes = audio_bytes
        st.session_state.filename = uploaded_file.name
        st.audio(audio_bytes, format=f"audio/{uploaded_file.name.rsplit('.', 1)[-1]}")
    elif st.session_state.audio_bytes:
        st.markdown('<div class="neon-label">預覽播放</div>', unsafe_allow_html=True)
        st.audio(
            st.session_state.audio_bytes,
            format=f"audio/{st.session_state.filename.rsplit('.', 1)[-1]}",
        )

# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------

if uploaded_file is not None or st.session_state.audio_bytes:
    st.markdown("")
    tab_auto, tab_outline = st.tabs([
        "\u26a1 AI \u81ea\u52d5\u7522\u751f\u6642\u9593\u8ef8",
        "\U0001f4dd \u8a2a\u7db1\u6bd4\u5c0d\u6642\u9593\u8ef8",
    ])

    # ── Tab 1: Auto chapters ──────────────────────────────
    with tab_auto:
        if uploaded_file is not None:
            process = st.button("\u26a1  \u7522\u751f\u6642\u9593\u8ef8", use_container_width=True, type="primary", key="btn_auto")

            if process:
                try:
                    audio_file = save_upload_to_disk(uploaded_file)
                except AudioValidationError as exc:
                    st.error(str(exc))
                    st.stop()

                st.markdown('<div class="neon-label">\u6b65\u9a5f 1 / 2 \u2014 \u8a9e\u97f3\u8f49\u6587\u5b57</div>', unsafe_allow_html=True)
                progress = st.progress(0, text="\u8f09\u5165 Whisper \u6a21\u578b\u4e2d\u22ef")

                try:
                    progress.progress(5, text="\u8f49\u9304\u4e2d\uff08\u4f7f\u7528 faster-whisper\uff0c\u8f03\u9577\u97f3\u6a94\u53ef\u80fd\u9700\u898130\u79d2\u81f3\u5e7e\u5206\u9418\uff09\u22ef")
                    segments = transcribe_audio(
                        str(audio_file.path),
                        model_name=whisper_model,
                        language=language or None,
                    )
                    progress.progress(50, text=f"\u8f49\u9304\u5b8c\u6210 \u2014 \u5171 {len(segments)} \u500b\u6bb5\u843d\u3002")
                    st.session_state.segments = segments
                except Exception as exc:
                    st.error(f"\u8f49\u9304\u5931\u6557\uff1a{exc}")
                    audio_file.cleanup()
                    st.stop()

                audio_file.cleanup()

                st.markdown('<div class="neon-label">\u6b65\u9a5f 2 / 2 \u2014 AI \u5206\u6790\u7bc0\u76ee\u7d50\u69cb</div>', unsafe_allow_html=True)

                def _on_progress(pct, msg):
                    progress.progress(50 + pct // 2, text=msg)

                try:
                    chapters = extract_chapters(
                        segments,
                        model=llm_model,
                        on_progress=_on_progress,
                    )
                    progress.progress(100, text=f"\u5b8c\u6210 \u2014 \u7522\u51fa {len(chapters)} \u500b\u7ae0\u7bc0\u3002")
                    st.session_state.chapters = chapters
                    st.session_state.processed = True
                except EnvironmentError as exc:
                    st.error(str(exc))
                    st.stop()
                except Exception as exc:
                    st.error(f"\u5206\u6790\u5931\u6557\uff1a{exc}")
                    st.stop()

    # ── Tab 2: Outline matching ───────────────────────────
    with tab_outline:
        st.markdown(
            '<div class="neon-subtitle" style="margin-bottom:1rem;">'
            '\u8f38\u5165\u8a2a\u7db1\u984c\u76ee\uff08\u6bcf\u884c\u4e00\u500b\uff09\uff0cAI \u6703\u5f9e\u9010\u5b57\u7a3f\u4e2d\u627e\u51fa\u6bcf\u500b\u984c\u76ee\u5c0d\u61c9\u7684\u6642\u9593\u9ede\u3002'
            '</div>',
            unsafe_allow_html=True,
        )
        outline_input = st.text_area(
            "\u8a2a\u7db1\u5167\u5bb9",
            placeholder="\u4f8b\u5982\uff1a\n\u8acb\u5148\u81ea\u6211\u4ecb\u7d39\n\u7576\u521d\u70ba\u4ec0\u9ebc\u6703\u9032\u5165\u9019\u500b\u7522\u696d\uff1f\n\u65b0\u624b\u6700\u5e38\u72af\u7684\u932f\u8aa4\u662f\u4ec0\u9ebc\uff1f\n\u5c0d\u807d\u773e\u7684\u5efa\u8b70",
            height=200,
            label_visibility="collapsed",
        )

        if uploaded_file is not None and outline_input.strip():
            match_btn = st.button(
                "\U0001f50d  \u6bd4\u5c0d\u8a2a\u7db1\u6642\u9593\u9ede",
                use_container_width=True,
                type="primary",
                key="btn_outline",
            )

            if match_btn:
                # Transcribe if not already done
                if st.session_state.segments is None:
                    try:
                        audio_file = save_upload_to_disk(uploaded_file)
                    except AudioValidationError as exc:
                        st.error(str(exc))
                        st.stop()

                    st.markdown('<div class="neon-label">\u6b65\u9a5f 1 / 2 \u2014 \u8a9e\u97f3\u8f49\u6587\u5b57</div>', unsafe_allow_html=True)
                    progress_o = st.progress(0, text="\u8f09\u5165 Whisper \u6a21\u578b\u4e2d\u22ef")

                    try:
                        progress_o.progress(5, text="\u8f49\u9304\u4e2d\uff08\u4f7f\u7528 faster-whisper\uff0c\u8f03\u9577\u97f3\u6a94\u53ef\u80fd\u9700\u898130\u79d2\u81f3\u5e7e\u5206\u9418\uff09\u22ef")
                        segments = transcribe_audio(
                            str(audio_file.path),
                            model_name=whisper_model,
                            language=language or None,
                        )
                        progress_o.progress(50, text=f"\u8f49\u9304\u5b8c\u6210 \u2014 \u5171 {len(segments)} \u500b\u6bb5\u843d\u3002")
                        st.session_state.segments = segments
                    except Exception as exc:
                        st.error(f"\u8f49\u9304\u5931\u6557\uff1a{exc}")
                        audio_file.cleanup()
                        st.stop()

                    audio_file.cleanup()
                else:
                    progress_o = st.progress(50, text="\u5df2\u6709\u9010\u5b57\u7a3f\uff0c\u8df3\u904e\u8f49\u9304\u3002")

                st.markdown('<div class="neon-label">\u6b65\u9a5f 2 / 2 \u2014 AI \u6bd4\u5c0d\u8a2a\u7db1</div>', unsafe_allow_html=True)

                def _on_outline_progress(pct, msg):
                    progress_o.progress(50 + pct // 2, text=msg)

                try:
                    outline_results = match_outline_to_timecodes(
                        st.session_state.segments,
                        outline_input,
                        model=llm_model,
                        on_progress=_on_outline_progress,
                    )
                    progress_o.progress(100, text=f"\u5b8c\u6210 \u2014 \u6bd4\u5c0d\u4e86 {len(outline_results)} \u500b\u8a2a\u7db1\u984c\u76ee\u3002")
                    st.session_state.outline_results = outline_results
                except EnvironmentError as exc:
                    st.error(str(exc))
                    st.stop()
                except Exception as exc:
                    st.error(f"\u6bd4\u5c0d\u5931\u6557\uff1a{exc}")
                    st.stop()
        elif uploaded_file is not None:
            st.info("\u8acb\u5728\u4e0a\u65b9\u8f38\u5165\u8a2a\u7db1\u5167\u5bb9\uff0c\u7136\u5f8c\u9ede\u64ca\u6bd4\u5c0d\u6309\u9215\u3002")

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

if st.session_state.processed and st.session_state.chapters is not None:
    chapters = st.session_state.chapters
    segments = st.session_state.segments

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f'<div class="neon-card"><div class="value">{len(chapters)}</div>'
            f'<div class="label">章節數</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        duration = segments[-1].end_time if segments else 0
        st.markdown(
            f'<div class="neon-card"><div class="value">{format_timestamp(duration)}</div>'
            f'<div class="label">音檔長度</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    if chapters:
        st.markdown('<div class="neon-label">📋 章節時間軸</div>', unsafe_allow_html=True)

        rows_html = ""
        for i, ch in enumerate(chapters, 1):
            rows_html += (
                f'<div class="ch-row">'
                f'  <span class="ch-num">{i:02d}</span>'
                f'  <span class="ch-ts">{ch["timestamp"]}</span>'
                f'  <span class="ch-title">{ch["title"]}</span>'
                f'</div>'
            )
        st.markdown(rows_html, unsafe_allow_html=True)

        st.markdown("")

        st.markdown('<div class="neon-label">📎 YouTube 描述欄格式（複製貼上即可）</div>', unsafe_allow_html=True)
        yt_text = format_youtube_chapters(chapters)
        st.code(yt_text, language=None)

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "📥  下載 TXT",
                data=yt_text.encode("utf-8"),
                file_name="youtube_時間軸.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_dl2:
            df = pd.DataFrame(chapters)
            df.columns = ["時間戳", "章節標題"]
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥  下載 CSV",
                data=csv,
                file_name="podcast_章節.csv",
                mime="text/csv",
                use_container_width=True,
            )
    else:
        st.info("無法辨識出章節結構，請嘗試使用較大的 Whisper 模型重新處理。")

# ---------------------------------------------------------------------------
# Outline results
# ---------------------------------------------------------------------------

if st.session_state.outline_results is not None:
    ol_results = st.session_state.outline_results

    st.divider()

    st.markdown('<div class="neon-label">\U0001f4dd 訪綱比對結果</div>', unsafe_allow_html=True)

    rows_html = ""
    yt_lines = []
    for i, item in enumerate(ol_results, 1):
        is_missing = item.get("not_found", False)
        ts_class = "ch-ts" if not is_missing else "ch-ts" 
        ts_style = ' style="opacity:0.3;"' if is_missing else ""
        title_extra = ' <span style="color:#ff2d95; font-size:0.75rem;">(未提及)</span>' if is_missing else ""

        rows_html += (
            f'<div class="ch-row"{ts_style}>'
            f'  <span class="ch-num">{i:02d}</span>'
            f'  <span class="{ts_class}">{item["timestamp"]}</span>'
            f'  <span class="ch-title">{item["title"]}{title_extra}</span>'
            f'</div>'
        )
        if not is_missing:
            yt_lines.append(f'{item["timestamp"]} {item["title"]}')

    st.markdown(rows_html, unsafe_allow_html=True)

    if yt_lines:
        st.markdown("")
        st.markdown('<div class="neon-label">\U0001f4ce YouTube 描述欄格式（複製貼上即可）</div>', unsafe_allow_html=True)
        yt_text = "\n".join(yt_lines)
        st.code(yt_text, language=None)

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "\U0001f4e5  下載 TXT",
                data=yt_text.encode("utf-8"),
                file_name="youtube_訪綱時間軸.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_outline_txt",
            )
        with col_dl2:
            df = pd.DataFrame([r for r in ol_results if not r.get("not_found")])
            if not df.empty:
                df = df[["timestamp", "title"]]
                df.columns = ["時間戳", "訪綱題目"]
                csv = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "\U0001f4e5  下載 CSV",
                    data=csv,
                    file_name="podcast_訪綱比對.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_outline_csv",
                )

st.markdown("---")
st.markdown(
    '<div class="neon-footer">POWERED BY  STREAMLIT · WHISPER · ANTHROPIC CLAUDE</div>',
    unsafe_allow_html=True,
)
