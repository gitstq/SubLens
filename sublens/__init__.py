"""SubLens — 零依赖、离线优先的字幕解析、时间轴变换与质量审计工具箱。

典型用法::

    from sublens import parse, audit, shift, write

    sub = parse(srt_text)
    report = audit(sub)
    if report.passed:
        out = write(shift(sub, 500), "vtt")

设计目标：纯标准库、全确定性、可审计、CI 友好。
"""

from .audit import AuditConfig, AuditReport, Finding, audit
from .models import Cue, Subtitle, Timestamp
from .parsers import FormatError, detect_format, parse, parse_srt, parse_vtt
from .repair import RepairStats, repair
from .reports import render
from .timing import correct_drift, resolve_fps, retime_fps, scale, shift
from .writers import write, write_json, write_srt, write_vtt

__version__ = "1.0.0"

__all__ = [
    "__version__",
    # 模型
    "Timestamp",
    "Cue",
    "Subtitle",
    # 解析
    "parse",
    "parse_srt",
    "parse_vtt",
    "detect_format",
    "FormatError",
    # 变换
    "shift",
    "scale",
    "retime_fps",
    "correct_drift",
    "resolve_fps",
    # 审计
    "audit",
    "AuditConfig",
    "AuditReport",
    "Finding",
    "render",
    # 修复
    "repair",
    "RepairStats",
    # 写出
    "write",
    "write_srt",
    "write_vtt",
    "write_json",
]
