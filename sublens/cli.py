"""SubLens 命令行界面。

零依赖，基于 argparse。所有子命令遵循统一约定：
- 输入 ``-`` 表示标准输入，省略输出路径时写到标准输出；
- 出错时打印到 stderr 并返回非零退出码，便于 CI 使用；
- ``audit --strict`` 在存在 error 时返回退出码 1。
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .audit import AuditConfig, audit
from .models import Subtitle
from .parsers import FormatError, detect_format, parse
from .repair import repair
from .reports import render
from .timing import correct_drift, resolve_fps, retime_fps, scale, shift
from .writers import write


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return fh.read()


def _write(text: str, path: Optional[str]) -> None:
    if not path or path == "-":
        sys.stdout.write(text)
        return
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _load(path: str, fmt: Optional[str]) -> Subtitle:
    text = _read(path)
    try:
        return parse(text, fmt)
    except FormatError as exc:
        raise SystemExit(f"解析失败: {exc}")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sublens",
        description="SubLens — 零依赖字幕解析、时间轴变换与质量审计工具箱",
    )
    p.add_argument("-V", "--version", action="version", version=f"SubLens {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_input(sp, help_text="输入字幕文件，- 表示标准输入"):
        sp.add_argument("input", help=help_text)

    def add_fmt(sp):
        sp.add_argument("--format", choices=["srt", "vtt"], help="强制输入格式")

    # detect
    sp = sub.add_parser("detect", help="检测字幕格式")
    add_input(sp)
    sp.add_argument("--format", choices=["srt", "vtt"], help="强制输入格式")

    # inspect
    sp = sub.add_parser("inspect", help="输出字幕结构化摘要（JSON）")
    add_input(sp)
    add_fmt(sp)

    # convert
    sp = sub.add_parser("convert", help="转换字幕格式（srt/vtt/json）")
    add_input(sp)
    sp.add_argument("output", help="输出文件，- 表示标准输出")
    add_fmt(sp)
    sp.add_argument("--to", default="srt", choices=["srt", "vtt", "json"])
    sp.add_argument("--renumber", action="store_true", help="输出 SRT 时重新编号")

    # shift
    sp = sub.add_parser("shift", help="整体平移时间轴（毫秒）")
    add_input(sp)
    sp.add_argument("output")
    add_fmt(sp)
    sp.add_argument("--ms", type=int, required=True, help="平移毫秒数，可为负")
    sp.add_argument("--to", default="srt", choices=["srt", "vtt", "json"])

    # scale
    sp = sub.add_parser("scale", help="按比例缩放时间轴")
    add_input(sp)
    sp.add_argument("output")
    add_fmt(sp)
    sp.add_argument("--factor", type=float, required=True, help="缩放系数")
    sp.add_argument("--origin", type=int, default=0, help="缩放原点（毫秒）")
    sp.add_argument("--to", default="srt", choices=["srt", "vtt", "json"])

    # fps
    sp = sub.add_parser("fps", help="帧率重映射（如 23.976 -> 25）")
    add_input(sp)
    sp.add_argument("output")
    add_fmt(sp)
    sp.add_argument("--from", dest="src_fps", required=True, help="源帧率，如 23.976 或 24000/1001")
    sp.add_argument("--to-fps", dest="dst_fps", required=True, help="目标帧率")
    sp.add_argument("--out-format", default="srt", choices=["srt", "vtt", "json"])

    # drift
    sp = sub.add_parser("drift", help="双锚点线性漂移校正")
    add_input(sp)
    sp.add_argument("output")
    add_fmt(sp)
    sp.add_argument("--a1", type=int, required=True, help="源锚点1（毫秒）")
    sp.add_argument("--b1", type=int, required=True, help="目标锚点1（毫秒）")
    sp.add_argument("--a2", type=int, required=True, help="源锚点2（毫秒）")
    sp.add_argument("--b2", type=int, required=True, help="目标锚点2（毫秒）")
    sp.add_argument("--to", default="srt", choices=["srt", "vtt", "json"])

    # audit
    sp = sub.add_parser("audit", help="字幕质量审计")
    add_input(sp)
    add_fmt(sp)
    sp.add_argument("--report", default="text", choices=["text", "json", "sarif"])
    sp.add_argument("--strict", action="store_true", help="存在 error 时退出码为 1")
    sp.add_argument("--min-duration", type=int, default=500)
    sp.add_argument("--max-duration", type=int, default=10000)
    sp.add_argument("--max-cps", type=float, default=20.0)

    # repair
    sp = sub.add_parser("repair", help="自动修复低风险问题")
    add_input(sp)
    sp.add_argument("output")
    add_fmt(sp)
    sp.add_argument("--to", default="srt", choices=["srt", "vtt", "json"])
    sp.add_argument("--no-remove-empty", action="store_true")
    sp.add_argument("--no-clamp", action="store_true")
    sp.add_argument("--no-merge-overlap", action="store_true")
    sp.add_argument("--no-renumber", action="store_true")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    cmd = args.command

    if cmd == "detect":
        fmt = args.format or detect_format(_read(args.input))
        print(fmt)
        return 0

    if cmd == "inspect":
        sub = _load(args.input, args.format)
        import json

        doc = {
            "format": sub.source_format,
            "cue_count": len(sub.cues),
            "duration_ms": sub.duration_ms,
            "first_start_ms": sub.cues[0].start_ms if sub.cues else None,
            "last_end_ms": sub.cues[-1].end_ms if sub.cues else None,
            "preamble_lines": len(sub.preamble.splitlines()) if sub.preamble else 0,
        }
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return 0

    if cmd == "convert":
        sub = _load(args.input, args.format)
        _write(write(sub, args.to, renumber=args.renumber), args.output)
        return 0

    if cmd == "shift":
        sub = _load(args.input, args.format)
        _write(write(shift(sub, args.ms), args.to), args.output)
        return 0

    if cmd == "scale":
        sub = _load(args.input, args.format)
        _write(write(scale(sub, args.factor, args.origin), args.to), args.output)
        return 0

    if cmd == "fps":
        sub = _load(args.input, args.format)
        try:
            out = retime_fps(sub, args.src_fps, args.dst_fps)
        except ValueError as exc:
            raise SystemExit(str(exc))
        _write(write(out, args.out_format), args.output)
        return 0

    if cmd == "drift":
        sub = _load(args.input, args.format)
        try:
            out = correct_drift(sub, args.a1, args.b1, args.a2, args.b2)
        except ValueError as exc:
            raise SystemExit(str(exc))
        _write(write(out, args.to), args.output)
        return 0

    if cmd == "audit":
        sub = _load(args.input, args.format)
        cfg = AuditConfig(
            min_duration_ms=args.min_duration,
            max_duration_ms=args.max_duration,
            max_cps=args.max_cps,
        )
        report = audit(sub, cfg)
        sys.stdout.write(render(report, args.report))
        return 1 if (args.strict and not report.passed) else 0

    if cmd == "repair":
        sub = _load(args.input, args.format)
        out, stats = repair(
            sub,
            remove_empty=not args.no_remove_empty,
            clamp_duration=not args.no_clamp,
            merge_overlap=not args.no_merge_overlap,
            renumber=not args.no_renumber,
        )
        print(stats.summary(), file=sys.stderr)
        _write(write(out, args.to), args.output)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
