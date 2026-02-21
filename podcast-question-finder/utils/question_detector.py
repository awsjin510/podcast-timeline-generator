"""章節偵測模組 — 使用 Anthropic Claude 分析逐字稿，產出 YouTube 時間軸章節。"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import anthropic

from utils.transcriber import TranscriptSegment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_TEMPERATURE = 0.2
MAX_TOKENS = 4096

SYSTEM_PROMPT = """\
你是一位專業的 Podcast 內容分析師。你的任務是分析一整集 Podcast 的逐字稿，
然後產出適合放在 YouTube 影片描述欄的**章節時間軸**。

─── 你的目標 ─────────────────────────────────────────────────
根據逐字稿的內容，辨識出這集節目的主要段落與話題轉換點，
為每個段落產出一個時間戳和簡短的章節標題。

─── 章節標題規範 ─────────────────────────────────────────────
• 每個標題 5-20 個中文字，簡潔有力
• 用觀眾能理解的語言，不要太學術
• 反映該段落的核心主題或討論重點
• 如果是訪談，標題可以反映討論的具體議題
• 風格範例：
  - 「主持人開場與來賓介紹」
  - 「如何判斷獵頭的專業度」
  - 「選擇對的領域與賽道的獵頭」
  - 「裸辭的風險與考量」
  - 「節目尾聲：最喜歡的一句話」

─── 章節數量建議 ─────────────────────────────────────────────
• 10 分鐘以內的節目：3-5 個章節
• 10-30 分鐘的節目：5-10 個章節
• 30-60 分鐘的節目：8-15 個章節
• 60 分鐘以上的節目：12-20 個章節

第一個章節的時間戳必須是 00:00:00（節目開場）。

─── 輸入格式 ─────────────────────────────────────────────────
你會收到完整的逐字稿文字，每行包含時間區間與對應的文字。

─── 輸出格式 ─────────────────────────────────────────────────
只回傳 JSON 陣列（不要 markdown 標記、不要任何說明文字）。
每個元素必須是：
  {
    "start_seconds": <float — 該章節開始的秒數>,
    "title":         <string — 章節標題>
  }

陣列必須按時間排序，第一個元素的 start_seconds 必須是 0。
"""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Chapter:
    """一個節目章節。"""

    start_seconds: float
    timestamp: str      # HH:MM:SS
    title: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "title": self.title,
        }


def _format_hhmmss(seconds: float) -> str:
    """秒數 → HH:MM:SS"""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _build_transcript_text(segments: list[TranscriptSegment]) -> str:
    """將 segments 轉為帶時間的純文字，供 LLM 分析。"""
    lines = []
    for seg in segments:
        start_ts = _format_hhmmss(seg.start_time)
        end_ts = _format_hhmmss(seg.end_time)
        lines.append(f"[{start_ts} → {end_ts}] {seg.text}")
    return "\n".join(lines)


def _parse_llm_response(raw: str) -> list[dict]:
    """安全解析 LLM 回傳的 JSON。"""
    cleaned = raw.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM 回傳的 JSON 無效:\n%s", raw[:500])
        return []

    if isinstance(parsed, dict):
        for key in ("chapters", "results", "data"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
        return []

    if not isinstance(parsed, list):
        return []

    return parsed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_chapters(
    transcript_segments: list[TranscriptSegment],
    *,
    model: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    api_key: Optional[str] = None,
    on_progress: Optional[callable] = None,
) -> list[dict]:
    """分析逐字稿，產出 YouTube 章節時間軸。

    Parameters
    ----------
    transcript_segments:
        來自 ``transcribe_audio()`` 的 segments。
    model:
        Anthropic 模型名稱。
    temperature:
        取樣溫度。
    api_key:
        Anthropic API key。
    on_progress:
        進度回呼 ``(step, message) -> None``。

    Returns
    -------
    list[dict]
        每個 dict 包含 ``{"timestamp": "00:00:00", "title": "章節標題"}``。
    """
    if not transcript_segments:
        return []

    model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    key = api_key or os.getenv("ANTHROPIC_API_KEY")

    if not key:
        raise EnvironmentError(
            "找不到 Anthropic API key。請設定 ANTHROPIC_API_KEY 環境變數。"
        )

    client = anthropic.Anthropic(api_key=key)

    # 建立完整逐字稿文字
    if on_progress:
        on_progress(30, "整理逐字稿中⋯")

    transcript_text = _build_transcript_text(transcript_segments)

    # 如果逐字稿太長，截取關鍵部分（Claude 的上下文夠大，通常不需要）
    # 但為了安全起見，限制在約 100k 字元
    if len(transcript_text) > 100000:
        transcript_text = transcript_text[:100000] + "\n\n[⋯ 後續內容已截斷]"

    if on_progress:
        on_progress(50, "Claude 分析節目結構中⋯")

    # 呼叫 Claude
    try:
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "請分析以下 Podcast 逐字稿，產出 YouTube 章節時間軸。\n\n"
                        + transcript_text
                    ),
                },
            ],
        )
    except Exception as exc:
        logger.exception("Claude API 呼叫失敗")
        raise RuntimeError(f"Claude API 呼叫失敗：{exc}") from exc

    if on_progress:
        on_progress(80, "解析結果中⋯")

    content = ""
    for block in response.content:
        if block.type == "text":
            content += block.text

    raw_chapters = _parse_llm_response(content or "[]")

    # 轉換為 Chapter 物件
    chapters: list[Chapter] = []
    for item in raw_chapters:
        start = item.get("start_seconds", 0.0)
        title = item.get("title", "").strip()
        if title:
            chapters.append(
                Chapter(
                    start_seconds=start,
                    timestamp=_format_hhmmss(start),
                    title=title,
                )
            )

    # 確保按時間排序
    chapters.sort(key=lambda c: c.start_seconds)

    # 確保第一個是 00:00:00
    if chapters and chapters[0].start_seconds != 0:
        chapters.insert(
            0,
            Chapter(start_seconds=0, timestamp="00:00:00", title="節目開場"),
        )

    if on_progress:
        on_progress(100, f"完成 — 產出 {len(chapters)} 個章節。")

    logger.info("產出 %d 個章節。", len(chapters))
    return [c.to_dict() for c in chapters]


def format_youtube_chapters(chapters: list[dict]) -> str:
    """格式化為可直接貼到 YouTube 描述欄的文字。"""
    if not chapters:
        return ""
    return "\n".join(f'{c["timestamp"]} {c["title"]}' for c in chapters)


# ---------------------------------------------------------------------------
# Outline matching
# ---------------------------------------------------------------------------

OUTLINE_MATCH_PROMPT = """\
你是一位專業的 Podcast 內容分析師。使用者會提供一份「訪綱」（訪談大綱），
以及一份帶有時間戳的 Podcast 逐字稿。

你的任務是：找出訪綱中每一個題目在 Podcast 中**實際被討論到的時間點**。

─── 規則 ─────────────────────────────────────────────────────
1. 對訪綱中的每一個題目，找出逐字稿中最接近開始討論該題目的時間戳。
2. 時間戳必須精確到秒（使用逐字稿中最接近的段落時間）。
3. 如果某個題目在節目中沒有被討論到，仍然列出，但標記 "not_found": true。
4. 保持訪綱的原始順序。

─── 輸出格式 ─────────────────────────────────────────────────
只回傳 JSON 陣列（不要 markdown 標記、不要說明文字）。
每個元素必須是：
  {
    "outline_item":  <string — 訪綱題目原文>,
    "start_seconds": <float — 開始討論的秒數>,
    "not_found":     <boolean — 如果節目中未討論到則為 true>
  }
"""


def match_outline_to_timecodes(
    transcript_segments: list[TranscriptSegment],
    outline_text: str,
    *,
    model: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    api_key: Optional[str] = None,
    on_progress: Optional[callable] = None,
) -> list[dict]:
    """根據訪綱內容，從逐字稿中找出對應的時間點。

    Parameters
    ----------
    transcript_segments:
        逐字稿 segments。
    outline_text:
        使用者輸入的訪綱文字（每行一個題目）。
    model:
        Anthropic 模型名稱。

    Returns
    -------
    list[dict]
        每個 dict 包含 {"timestamp", "title", "not_found"}。
    """
    if not transcript_segments or not outline_text.strip():
        return []

    model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    key = api_key or os.getenv("ANTHROPIC_API_KEY")

    if not key:
        raise EnvironmentError("找不到 ANTHROPIC_API_KEY 環境變數。")

    client = anthropic.Anthropic(api_key=key)

    if on_progress:
        on_progress(30, "整理逐字稿中...")

    transcript_text = _build_transcript_text(transcript_segments)
    if len(transcript_text) > 100000:
        transcript_text = transcript_text[:100000]

    if on_progress:
        on_progress(50, "Claude 比對訪綱與逐字稿中...")

    user_message = (
        f"以下是訪綱內容：\n\n{outline_text.strip()}\n\n"
        f"以下是 Podcast 逐字稿：\n\n{transcript_text}"
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=temperature,
            system=OUTLINE_MATCH_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as exc:
        raise RuntimeError(f"Claude API 呼叫失敗：{exc}") from exc

    if on_progress:
        on_progress(80, "解析結果中...")

    content = ""
    for block in response.content:
        if block.type == "text":
            content += block.text

    raw_items = _parse_llm_response(content or "[]")

    results = []
    for item in raw_items:
        start = item.get("start_seconds", 0.0)
        not_found = item.get("not_found", False)
        results.append({
            "timestamp": _format_hhmmss(start) if not not_found else "--:--:--",
            "title": item.get("outline_item", "").strip(),
            "not_found": not_found,
        })

    if on_progress:
        on_progress(100, f"完成 — 比對了 {len(results)} 個訪綱題目。")

    return results
