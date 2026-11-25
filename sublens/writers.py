"""字幕序列化器：将 :class:`~sublens.models.Subtitle` 写回 SRT / WebVTT / JSON。

序列化是确定性的：相同输入恒产生逐字节相同的输出（换行统一为 ``\\n``，
末尾保留单个换行），便于哈希校验与版本控制。
"""

from __future__ import annotations

import json
from typing import Dict, List

from .models import Cue, Subtitle

__all__ = ["write", "write_srt", "write_vtt", "write_json"]


def _clean_text(text: str) -> str:
    """规整正文：去除行尾空白，但保留内部换行。"""
    return "\n".join(line.rstrip() for line in text.split("\n")).strip("\n")


def write_srt(sub: Subtitle, renumber: bool = False) -> str:
    """序列化为 SRT 文本。

    :param renumber: 为 ``True`` 时按 1..N 重新编号，否则沿用 cue.index。
    """
    chunks: List[str] = []
    for i, cue in enumerate(sub.cues, start=1):
        index = i if renumber else (cue.index if cue.index is not None else i)
        chunks.append(
            f"{index}\n{cue.start.to_srt()} --> {cue.end.to_srt()}\n{_clean_text(cue.text)}\n"
        )
    return "\n".join(chunks)


def write_vtt(sub: Subtitle, include_header: bool = True) -> str:
    """序列化为 WebVTT 文本。

    VTT 的 cue 不使用纯数字序号；若 cue 含 ``identifier`` 则写出该标识符。
    cue settings 原样附加在结束时间之后。
    """
    parts: List[str] = []
    if include_header:
        header = "WEBVTT"
        if sub.preamble:
            header += "\n" + sub.preamble
        parts.append(header)

    for cue in sub.cues:
        block: List[str] = []
        if cue.identifier:
            block.append(cue.identifier)
        timing = f"{cue.start.to_vtt()} --> {cue.end.to_vtt()}"
        if cue.settings:
            timing += " " + cue.settings.strip()
        block.append(timing)
        block.append(_clean_text(cue.text))
        parts.append("\n".join(block))
    return "\n\n".join(parts) + "\n"


def _cue_to_dict(cue: Cue, idx: int) -> Dict[str, object]:
    return {
        "index": cue.index if cue.index is not None else idx,
        "start_ms": cue.start_ms,
        "end_ms": cue.end_ms,
        "start": cue.start.to_vtt(),
        "end": cue.end.to_vtt(),
        "duration_ms": cue.duration_ms,
        "text": cue.text,
        "settings": cue.settings,
        "identifier": cue.identifier,
    }


def write_json(sub: Subtitle, pretty: bool = True) -> str:
    """序列化为结构化 JSON，适合下游程序消费与快照测试。"""
    doc = {
        "format": "sublens-1",
        "source_format": sub.source_format,
        "cue_count": len(sub.cues),
        "duration_ms": sub.duration_ms,
        "cues": [_cue_to_dict(c, i) for i, c in enumerate(sub.cues, start=1)],
    }
    if pretty:
        return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"


def write(sub: Subtitle, fmt: str, **kwargs) -> str:
    """按 ``fmt``（``srt``/``vtt``/``json``）序列化。"""
    fmt = fmt.lower().lstrip(".")
    if fmt == "srt":
        return write_srt(sub, renumber=bool(kwargs.get("renumber", False)))
    if fmt in ("vtt", "webvtt"):
        return write_vtt(sub, include_header=bool(kwargs.get("include_header", True)))
    if fmt == "json":
        return write_json(sub, pretty=bool(kwargs.get("pretty", True)))
    raise ValueError(f"不支持的输出格式: {fmt!r}")
