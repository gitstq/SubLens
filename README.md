# SubLens

> 零依赖 · 离线优先 · 全确定性 —— 让每一帧字幕都精准到位

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#-特性)

🌐 语言：**[简体中文](README.md)** · [繁體中文](README.zh-TW.md) · [English](README.en.md)

---

## 🎉 介绍

**SubLens** 是一个纯 Python 标准库实现的字幕工具箱，专注于三件事：

1. **解析与互转** —— SRT / WebVTT / JSON 之间无损往返，自动处理 BOM、CRLF、宽松时间戳与 VTT 头部块；
2. **时间轴变换** —— 整体平移、比例缩放、**帧率重映射**（如 23.976→25）、**双锚点漂移校正**；
3. **质量审计** —— 16 条确定性规则，输出文本 / JSON / **SARIF 2.1.0**，可直接接入 CI 门禁。

它不下载任何东西、不联网、不依赖第三方包。所有时间内部以**毫秒整数**表示，保证「解析 → 变换 → 写回」全链路零浮点误差、完全可复现。

无论你是在做视频本地化、AI 字幕后处理，还是需要给字幕流水线加一道质量门禁，SubLens 都能作为一块可靠的基石。

---

## ✨ 特性

| 特性 | 说明 |
| --- | --- |
| 🧩 多格式解析 | SRT / WebVTT / JSON，自动探测格式，容错 BOM、CRLF、缺失序号、宽松时间戳 |
| 🔁 无损互转 | 解析→写出保真标识符、cue settings、STYLE/NOTE 头部块；确定性输出便于版本控制 |
| ⏱️ 帧率重映射 | 按帧序号对齐（23.976 / 24 / 25 / 29.97 / 30 / 50 / 59.94 / 60 及自定义分数） |
| 📐 漂移校正 | 双锚点线性映射，消除片头对准、片尾超前的累积不同步 |
| 🔍 16 条审计规则 | 覆盖时长、重叠、顺序、阅读速度、标签配对等，可配置阈值与启停 |
| 📊 SARIF 2.1.0 | 原生输出，无缝接入 GitHub Code Scanning 等 CI 体系 |
| 🔧 自动修复 | 仅修复低风险问题（重排序号、删空行、钳制时长、合并重叠），全程可追踪 |
| 🪶 零依赖 | 仅用 Python 标准库，Python 3.9+，单文件即可运行 |
| 🎯 全确定性 | 毫秒整数运算，相同输入恒得相同输出，快照测试友好 |

---

## 🚀 快速开始

无需安装，直接运行：

```bash
# 检测格式
python3 -m sublens detect examples/demo.srt

# 审计并打分
python3 -m sublens audit examples/demo.srt

# SRT 转 WebVTT
python3 -m sublens convert examples/demo.srt demo.vtt --to vtt

# 整体延后 1.5 秒
python3 -m sublens shift examples/demo.srt shifted.srt --ms 1500
```

也可以安装为命令行工具：

```bash
pip install .
sublens --version
```

> 本项目**运行时零依赖**，无论直接运行还是安装，都不需要下载任何第三方包。

---

## 📖 使用指南

### 作为 Python 库

```python
from sublens import parse, audit, shift, retime_fps, write

# 1) 解析
with open("examples/demo.srt", encoding="utf-8") as f:
    sub = parse(f.read())           # 自动探测 SRT / WebVTT

# 2) 审计
report = audit(sub)
print(report.score, report.passed)  # 100 True
for finding in report.findings:
    print(finding)

# 3) 变换：延后 500ms，再做 23.976 -> 25 帧率重映射
sub = shift(sub, 500)
sub = retime_fps(sub, "23.976", "25")

# 4) 写出
open("out.vtt", "w", encoding="utf-8").write(write(sub, "vtt"))
```

### 命令行子命令

| 命令 | 用途 | 示例 |
| --- | --- | --- |
| `detect` | 探测输入格式 | `sublens detect input.srt` |
| `inspect` | 输出结构化摘要（JSON） | `sublens inspect input.srt` |
| `convert` | 格式互转 | `sublens convert in.srt out.vtt --to vtt` |
| `shift` | 整体平移（毫秒） | `sublens shift in.srt out.srt --ms -200` |
| `scale` | 比例缩放 | `sublens scale in.srt out.srt --factor 1.05` |
| `fps` | 帧率重映射 | `sublens fps in.srt out.srt --from 23.976 --to-fps 25` |
| `drift` | 双锚点漂移校正 | `sublens drift in.srt out.srt --a1 1000 --b1 1000 --a2 60000 --b2 59500` |
| `audit` | 质量审计 | `sublens audit in.srt --report sarif --strict` |
| `repair` | 自动修复 | `sublens repair in.srt out.srt` |

所有命令的输入参数支持 `-` 表示标准输入，输出支持 `-` 表示标准输出，方便管道组合：

```bash
cat in.srt | sublens shift - - --ms 1000 | sublens audit - --report json
```

### 审计规则一览

| ID | 规则 | 级别 |
| --- | --- | --- |
| SUB001 | 时长非正（结束早于或等于开始） | error |
| SUB002 | 时间戳字段越界 | error |
| SUB003 | 字幕正文为空 | warning |
| SUB004 | 显示时长过短 | warning |
| SUB005 | 显示时长过长 | warning |
| SUB006 | 相邻 cue 重叠 | warning |
| SUB007 | 起始时间顺序颠倒 | warning |
| SUB008 | 时间点重复 | warning |
| SUB009 | 阅读速度过快（cps 超标） | warning |
| SUB010 | 单条行数过多 | info |
| SUB011 | 单行字符过多 | info |
| SUB012 | 相邻间隔过大 | info |
| SUB013 | 缺少序号 | info |
| SUB014 | 序号不连续 | info |
| SUB015 | 标签开闭不匹配 | warning |
| SUB016 | 序号为 0（兼容性提示） | info |

### CI 门禁

```bash
# 存在 error 时退出码为 1，可阻断流水线
sublens audit input.srt --strict

# 生成 SARIF 供代码扫描平台消费
sublens audit input.srt --report sarif > sublens.sarif
```

---

## 💡 设计迭代

SubLens 从「只解析 SRT」的朴素思路演进而来，关键迭代如下：

- **v0.1** —— 最初的动机只是想把一个 SRT 文件整体平移几秒。很快发现市面工具要么依赖 ffmpeg，要么用浮点秒累加，长时间轴会漂移。
- **v0.2** —— 引入**毫秒整数**内部表示，彻底消除浮点误差；加入自动格式探测与 BOM/CRLF 容错。
- **v0.3** —— 增加**帧率重映射**。核心洞察是：按「帧序号」换算而非直接乘比例，可避免 23.976 这类循环小数在长视频上的累积误差。
- **v0.4** —— 增加**双锚点漂移校正**，解决「片头对准、片尾却超前」的实际痛点，用一条线性映射统一修正。
- **v0.5** —— 审计引擎成型。把「一条字幕好不好」的模糊判断拆成 16 条可解释、可开关、可配置阈值的确定性规则。
- **v1.0** —— 补齐 SARIF 输出、自动修复、三语文档与 31 项单元测试，形成完整闭环。

**与同类工具的区别**：多数字幕库只做「解析 + 写出」，SubLens 把**时间轴的数学严谨性**和**质量的机器可判定性**放在同等重要的位置——这使它不仅能处理字幕，还能成为自动化流水线里可被信任的一环。

---

## 📦 打包部署

本项目为**库 + CLI**，无需平台二进制打包。

```bash
# 安装（可编辑模式用于开发）
pip install -e .

# 构建分发包
pip install build
python -m build          # 产出 dist/*.whl 与 dist/*.tar.gz

# 直接以模块运行（零安装）
python3 -m sublens --help
```

- **运行环境**：Python 3.9+，任意平台（Windows / macOS / Linux）。
- **集成示例**：见上文「作为 Python 库」与 `examples/demo.srt`。
- **提示**：`pyproject.toml` 已声明 `sublens` 控制台入口，安装后可直接调用 `sublens` 命令。

---

## 🤝 贡献

欢迎提交 Issue 与 Pull Request！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。

我们尤其欢迎：新的审计规则、更多字幕格式（ASS / MicroDVD）的支持，以及真实场景中的边界案例。请遵循 Angular 提交规范，并附上单元测试结果。

---

## 📄 协议

本项目基于 [MIT License](LICENSE) 开源，可自由用于商业与非商业项目。

Copyright © 2026 gitstq
