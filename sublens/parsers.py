"""字幕格式解析器。

支持 SRT (SubRip) 与 WebVTT，含以下容错能力：
- 自动识别 BOM、CRLF/LF 混用；
- 宽松时间轴（省略小时、点号/逗号混用）；
- VTT 标识符、cue settings、NOTE/STYLE 块保真提取。

解析器完全离线、零依赖，仅使用标准库。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .models import Cue, Subtitle, Timestamp

__all__ = ["parse", "parse_srt", "parse_vtt", "FormatError", "detect_format"]

# 宽松时间戳：HH:MM:SS,mmm / HH:MM:SS.mmm / MM:SS.mmm
_TS_RE = re.compile(
    r"^\s*(?:(?P<h>\d{1,3}):)?(?P<m>\d{1,2}):(?P<s>\d{2})[,.]?(?P<ms>\d{1,3})?\s*$"
)
_ARROW_RE = re.compile(r"(-{2,}>|\u27fa|\u2192)")  # "-->" / ⟶ / →
_NUM_RE = re.compile(r"^\s*(\d+)\s*$")


class FormatError(ValueError):
    """输入不是可识别的字幕格式。"""


def detect_format(text: str) -> str:
    """根据文本首部特征返回 ``'vtt'`` 或 ``'srt'``。"""
    head = text.lstrip("\ufeff").lstrip()[:64].upper()
    if head.startswith("WEBVTT"):
        return "vtt"
    return "srt"


def _parse_timestamp(raw: str) -> Timestamp:
    """解析单个时间戳字符串，失败抛 :class:`FormatError`。"""
    m = _TS_RE.match(raw)
    if not m:
        raise FormatError(f"无法解析时间戳: {raw!r}")
    h = int(m.group("h") or 0)
    mm = int(m.group("m") or 0)
    s = int(m.group("s") or 0)
    ms_raw = m.group("ms") or "0"
    # 毫秒位按小数处理：'5' -> 50ms, '50' -> 50ms? 这里统一补齐到 3 位
    ms = int(ms_raw.ljust(3, "0")[:3])
    total = ((h * 60 + mm) * 60 + s) * 1000 + ms
    return Timestamp.from_millis(total)


def _split_time_line(line: str) -> Optional[Tuple[str, str, str]]:
    """拆分时间行，返回 ``(start_raw, end_raw, trailing_settings)``。"""
    for arrow in _ARROW_RE.finditer(line):
        left = line[: arrow.start()].strip()
        right_full = line[arrow.end() :].strip()
        # 右侧可能附带 VTT settings，按空白切出第一段作为结束时间
        parts = right_full.split(None, 1)
        end_raw = parts[0] if parts else ""
        settings = parts[1] if len(parts) > 1 else ""
        if left and end_raw:
            return left, end_raw, settings
    return None


def _parse_blocks(text: str) -> List[dict]:
    """按空行切块并解析，返回内部字典列表。"""
    # 统一换行符并剥离 BOM
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    raw_blocks = re.split(r"\n{2,}", text.strip("\n"))
    blocks: List[dict] = []
    for raw in raw_blocks:
        lines = [ln for ln in raw.split("\n")]
        if not lines or not any(ln.strip() for ln in lines):
            continue
        # 去掉块首尾空行
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            continue

        idx: Optional[int] = None
        identifier = ""
        time_line_pos = -1
        # 若首行是纯数字，视为 SRT 序号
        m = _NUM_RE.match(lines[0])
        if m:
            idx = int(m.group(1))
            time_line_pos = 1
        else:
            time_line_pos = 0
            # WebVTT cue 标识符：首行非数字、非时间行，但下一行是时间行
            if (
                len(lines) >= 2
                and _split_time_line(lines[0]) is None
                and _split_time_line(lines[1]) is not None
            ):
                identifier = lines[0].strip()
                time_line_pos = 1

        if time_line_pos >= len(lines):
            continue
        timing = _split_time_line(lines[time_line_pos])
        if timing is None:
            continue
        start_raw, end_raw, settings = timing
        try:
            start = _parse_timestamp(start_raw)
            end = _parse_timestamp(end_raw)
        except FormatError:
            continue

        text_lines = lines[time_line_pos + 1 :]
        body = "\n".join(text_lines).strip("\n")
        blocks.append(
            {
                "index": idx,
                "start": start,
                "end": end,
                "text": body,
                "settings": settings,
                "identifier": identifier,
            }
        )
    return blocks


def _build_subtitle(blocks: List[dict], source_format: str, preamble: str = "") -> Subtitle:
    cues: List[Cue] = []
    for b in blocks:
        cues.append(
            Cue(
                start=b["start"],
                end=b["end"],
                text=b["text"],
                index=b["index"],
                settings=b.get("settings", ""),
                identifier=b.get("identifier", ""),
            )
        )
    return Subtitle(cues=cues, source_format=source_format, preamble=preamble)


def parse_srt(text: str) -> Subtitle:
    """解析 SRT 文本为 :class:`Subtitle`。

    即使序号缺失或不连续也不会报错——这些属于审计问题，由 audit 模块负责报告。
    只有完全找不到任何有效时间行时才抛 :class:`FormatError`。
    """
    blocks = _parse_blocks(text)
    if not blocks:
        raise FormatError("未找到任何有效的 SRT 字幕块")
    return _build_subtitle(blocks, "srt")


def parse_vtt(text: str) -> Subtitle:
    """解析 WebVTT 文本为 :class:`Subtitle`。

    保留文件头（WEBVTT 行之后、首个 cue 之前的 NOTE/STYLE 等）到 ``preamble``，
    并支持 cue 前的标识符行。
    """
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    if not text.lstrip().upper().startswith("WEBVTT"):
        raise FormatError("WebVTT 文件必须以 WEBVTT 开头")

    # 按空行切块：首个含时间箭头（--> / ⟶ / →）的块之前的内容都视为头部
    # （WEBVTT 行、NOTE、STYLE、REGION 等），保真写入 preamble。
    normalized = text.strip("\n")
    raw_blocks = re.split(r"\n{2,}", normalized)
    preamble_blocks: List[str] = []
    cue_blocks: List[str] = []
    seen_cue = False
    for raw in raw_blocks:
        has_timing = any(_ARROW_RE.search(ln) for ln in raw.split("\n"))
        if not seen_cue and not has_timing:
            preamble_blocks.append(raw.strip("\n"))
        else:
            seen_cue = True
            cue_blocks.append(raw.strip("\n"))

    preamble = "\n\n".join(b for b in preamble_blocks if b.strip())
    body = "\n\n".join(cue_blocks)
    if not body.strip():
        return Subtitle(cues=[], source_format="vtt", preamble=preamble)

    blocks = _parse_blocks(body)
    if not blocks:
        return Subtitle(cues=[], source_format="vtt", preamble=preamble)

    return _build_subtitle(blocks, "vtt", preamble)


def parse(text: str, fmt: Optional[str] = None) -> Subtitle:
    """自动检测并解析字幕文本。``fmt`` 可强制指定 ``'srt'``/``'vtt'``。"""
    fmt = fmt or detect_format(text)
    if fmt == "vtt":
        return parse_vtt(text)
    if fmt == "srt":
        return parse_srt(text)
    raise FormatError(f"不支持的字幕格式: {fmt!r}")
