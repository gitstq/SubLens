# SubLens

> Zero-dependency · Offline-first · Fully deterministic — every frame of your subtitles, precisely in place

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#-features)

🌐 Language: [简体中文](README.md) · [繁體中文](README.zh-TW.md) · **[English](README.en.md)**

---

## 🎉 Introduction

**SubLens** is a subtitle toolkit built on nothing but the Python standard library. It does three things well:

1. **Parse & convert** — lossless round-trips between SRT, WebVTT and JSON, with graceful handling of BOMs, CRLF, lenient timestamps and VTT header blocks;
2. **Transform timelines** — whole-track shifting, proportional scaling, **frame-rate retiming** (e.g. 23.976→25) and **two-anchor drift correction**;
3. **Audit quality** — 16 deterministic rules emitting text, JSON or **SARIF 2.1.0**, ready to slot straight into a CI gate.

It downloads nothing, never touches the network and pulls in no third-party packages. All timestamps are stored internally as **integer milliseconds**, so the entire parse → transform → serialize pipeline is free of floating-point drift and completely reproducible.

Whether you're localizing video, post-processing AI-generated captions, or adding a quality gate to a subtitle pipeline, SubLens is a foundation you can trust.

---

## ✨ Features

| Feature | Description |
| --- | --- |
| 🧩 Multi-format parsing | SRT / WebVTT / JSON with auto-detection; tolerant of BOM, CRLF, missing indices and loose timestamps |
| 🔁 Lossless conversion | Round-trips preserve cue identifiers, settings and STYLE/NOTE headers; deterministic output is diff-friendly |
| ⏱️ Frame-rate retiming | Snaps to frame numbers (23.976 / 24 / 25 / 29.97 / 30 / 50 / 59.94 / 60 plus custom fractions) |
| 📐 Drift correction | Two-anchor linear mapping removes cumulative sync drift — aligned at the head, drifting at the tail |
| 🔍 16 audit rules | Duration, overlap, ordering, reading speed, tag pairing and more, with configurable thresholds and toggles |
| 📊 SARIF 2.1.0 | Native output plugs into GitHub Code Scanning and other CI scanners |
| 🔧 Safe auto-repair | Fixes only low-risk issues (renumber, drop empties, clamp durations, merge overlaps), all tracked |
| 🪶 Zero dependencies | Standard library only, Python 3.9+, runs from a single command |
| 🎯 Fully deterministic | Integer-millisecond math; identical input always yields identical output, ideal for snapshot tests |

---

## 🚀 Quick Start

No installation needed — just run it:

```bash
# Detect the format
python3 -m sublens detect examples/demo.srt

# Audit and print a quality score
python3 -m sublens audit examples/demo.srt

# Convert SRT to WebVTT
python3 -m sublens convert examples/demo.srt demo.vtt --to vtt

# Shift everything 1.5 seconds later
python3 -m sublens shift examples/demo.srt shifted.srt --ms 1500
```

Or install it as a CLI:

```bash
pip install .
sublens --version
```

> The project has **zero runtime dependencies** — whether you run it directly or install it, nothing is downloaded.

---

## 📖 Usage Guide

### As a Python library

```python
from sublens import parse, audit, shift, retime_fps, write

# 1) Parse
with open("examples/demo.srt", encoding="utf-8") as f:
    sub = parse(f.read())           # auto-detects SRT / WebVTT

# 2) Audit
report = audit(sub)
print(report.score, report.passed)  # 100 True
for finding in report.findings:
    print(finding)

# 3) Transform: delay 500 ms, then retime 23.976 -> 25 fps
sub = shift(sub, 500)
sub = retime_fps(sub, "23.976", "25")

# 4) Serialize
open("out.vtt", "w", encoding="utf-8").write(write(sub, "vtt"))
```

### CLI subcommands

| Command | Purpose | Example |
| --- | --- | --- |
| `detect` | Detect input format | `sublens detect input.srt` |
| `inspect` | Emit a structured JSON summary | `sublens inspect input.srt` |
| `convert` | Convert between formats | `sublens convert in.srt out.vtt --to vtt` |
| `shift` | Shift all cues (milliseconds) | `sublens shift in.srt out.srt --ms -200` |
| `scale` | Scale the timeline | `sublens scale in.srt out.srt --factor 1.05` |
| `fps` | Frame-rate retiming | `sublens fps in.srt out.srt --from 23.976 --to-fps 25` |
| `drift` | Two-anchor drift correction | `sublens drift in.srt out.srt --a1 1000 --b1 1000 --a2 60000 --b2 59500` |
| `audit` | Quality audit | `sublens audit in.srt --report sarif --strict` |
| `repair` | Auto-repair | `sublens repair in.srt out.srt` |

Every command accepts `-` for stdin and `-` as the output path for stdout, so you can pipe them together:

```bash
cat in.srt | sublens shift - - --ms 1000 | sublens audit - --report json
```

### Audit rules at a glance

| ID | Rule | Severity |
| --- | --- | --- |
| SUB001 | Non-positive duration (end not after start) | error |
| SUB002 | Timestamp field out of range | error |
| SUB003 | Empty cue text | warning |
| SUB004 | Display duration too short | warning |
| SUB005 | Display duration too long | warning |
| SUB006 | Adjacent cues overlap | warning |
| SUB007 | Out-of-order start times | warning |
| SUB008 | Duplicate timestamps | warning |
| SUB009 | Reading speed too high (cps exceeded) | warning |
| SUB010 | Too many lines in one cue | info |
| SUB011 | Line too long (characters) | info |
| SUB012 | Excessive gap between cues | info |
| SUB013 | Missing index | info |
| SUB014 | Non-sequential index | info |
| SUB015 | Unbalanced tags | warning |
| SUB016 | Index is zero (compatibility hint) | info |

### CI gate

```bash
# Exit code 1 on any error — use it to fail a pipeline
sublens audit input.srt --strict

# Emit SARIF for a code-scanning platform
sublens audit input.srt --report sarif > sublens.sarif
```

---

## 💡 Design Iterations

SubLens grew out of a naive idea — "just shift an SRT file by a few seconds". Key iterations along the way:

- **v0.1** — The initial goal was only to shift an SRT file. It quickly became clear that existing tools either depended on ffmpeg or accumulated floating-point seconds, drifting over long timelines.
- **v0.2** — Introduced an **integer-millisecond** internal representation, eliminating float error entirely; added format auto-detection and BOM/CRLF tolerance.
- **v0.3** — Added **frame-rate retiming**. The key insight: converting by *frame number* instead of multiplying by a ratio avoids accumulated error from repeating decimals like 23.976 over long videos.
- **v0.4** — Added **two-anchor drift correction** for the real-world pain point of "synced at the opening, ahead by the credits", fixed with a single linear mapping.
- **v0.5** — The audit engine took shape. The vague question "is this cue good?" was broken into 16 explainable, toggleable, configurable deterministic rules.
- **v1.0** — Rounded it out with SARIF output, auto-repair, trilingual docs and 31 unit tests, closing the loop.

**How it differs from similar tools**: most subtitle libraries stop at "parse and write". SubLens treats **mathematical rigor of the timeline** and **machine-decidable quality** as equally first-class concerns — which makes it not just a subtitle processor, but a component you can trust inside an automated pipeline.

---

## 📦 Packaging & Deployment

This project ships as a **library + CLI**; no platform-specific binary packaging is required.

```bash
# Install (editable mode for development)
pip install -e .

# Build distributions
pip install build
python -m build          # produces dist/*.whl and dist/*.tar.gz

# Run directly as a module (zero install)
python3 -m sublens --help
```

- **Runtime**: Python 3.9+, any platform (Windows / macOS / Linux).
- **Integration example**: see "As a Python library" above and `examples/demo.srt`.
- **Note**: `pyproject.toml` declares the `sublens` console entry point, so the `sublens` command is available after installation.

---

## 🤝 Contributing

Issues and pull requests are welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

We especially welcome new audit rules, support for more subtitle formats (ASS / MicroDVD) and edge cases from real-world use. Follow Angular commit conventions and include your unit-test results.

---

## 📄 License

Released under the [MIT License](LICENSE). Free for commercial and non-commercial use.

Copyright © 2026 gitstq
