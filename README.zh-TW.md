# SubLens

> 零依賴 · 離線優先 · 全決定性 —— 讓每一幀字幕都精準到位

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#-特性)

🌐 語言：**[繁體中文](README.zh-TW.md)** · [简体中文](README.md) · [English](README.en.md)

---

## 🎉 介紹

**SubLens** 是一款純 Python 標準庫打造的字幕工具箱，專注做三件事：

1. **解析與互轉** —— SRT / WebVTT / JSON 之間無損往返，自動處理 BOM、CRLF、寬鬆時間戳與 VTT 標頭區塊；
2. **時間軸變換** —— 整體平移、比例縮放、**幀率重映射**（如 23.976→25）、**雙錨點漂移校正**；
3. **品質稽核** —— 16 條決定性規則，輸出文字 / JSON / **SARIF 2.1.0**，可直接接上 CI 關卡。

它不下載任何東西、不連網、不依賴第三方套件。所有時間在內部都以**毫秒整數**表示，保證「解析 → 變換 → 寫回」全链路零浮點誤差、完全可重現。

不論你正在做影片在地化、AI 字幕後處理，或是想替字幕流程加一道品質關卡，SubLens 都能當成穩固的基石。

---

## ✨ 特性

| 特性 | 說明 |
| --- | --- |
| 🧩 多格式解析 | SRT / WebVTT / JSON，自動偵測格式，容錯 BOM、CRLF、缺序號、寬鬆時間戳 |
| 🔁 無損互轉 | 解析→寫回保留識別碼、cue settings、STYLE/NOTE 標頭；決定性輸出便於版本控管 |
| ⏱️ 幀率重映射 | 以幀序號對齊（23.976 / 24 / 25 / 29.97 / 30 / 50 / 59.94 / 60 及自訂分數） |
| 📐 漂移校正 | 雙錨點線性映射，消除片頭對準、片尾超前的累積不同步 |
| 🔍 16 條稽核規則 | 涵蓋時長、重疊、順序、閱讀速度、標籤配對等，閾值與開關皆可設定 |
| 📊 SARIF 2.1.0 | 原生輸出，無縫接入 GitHub Code Scanning 等 CI 體系 |
| 🔧 自動修復 | 只修低風險問題（重排序號、刪空行、鉗制時長、合併重疊），全程可追蹤 |
| 🪶 零依賴 | 僅用 Python 標準庫，Python 3.9+，單檔即可執行 |
| 🎯 全決定性 | 毫秒整數運算，相同輸入恆得相同輸出，快照測試友善 |

---

## 🚀 快速開始

無需安裝，直接執行：

```bash
# 偵測格式
python3 -m sublens detect examples/demo.srt

# 稽核並評分
python3 -m sublens audit examples/demo.srt

# SRT 轉 WebVTT
python3 -m sublens convert examples/demo.srt demo.vtt --to vtt

# 整體延後 1.5 秒
python3 -m sublens shift examples/demo.srt shifted.srt --ms 1500
```

也可以安裝成命令列工具：

```bash
pip install .
sublens --version
```

> 本專案**執行期零依賴**，不論直接執行或安裝，都不需要下載任何第三方套件。

---

## 📖 使用指南

### 當作 Python 函式庫

```python
from sublens import parse, audit, shift, retime_fps, write

# 1) 解析
with open("examples/demo.srt", encoding="utf-8") as f:
    sub = parse(f.read())           # 自動偵測 SRT / WebVTT

# 2) 稽核
report = audit(sub)
print(report.score, report.passed)  # 100 True
for finding in report.findings:
    print(finding)

# 3) 變換：延後 500ms，再做 23.976 -> 25 幀率重映射
sub = shift(sub, 500)
sub = retime_fps(sub, "23.976", "25")

# 4) 寫出
open("out.vtt", "w", encoding="utf-8").write(write(sub, "vtt"))
```

### 命令列子命令

| 命令 | 用途 | 範例 |
| --- | --- | --- |
| `detect` | 偵測輸入格式 | `sublens detect input.srt` |
| `inspect` | 輸出結構化摘要（JSON） | `sublens inspect input.srt` |
| `convert` | 格式互轉 | `sublens convert in.srt out.vtt --to vtt` |
| `shift` | 整體平移（毫秒） | `sublens shift in.srt out.srt --ms -200` |
| `scale` | 比例縮放 | `sublens scale in.srt out.srt --factor 1.05` |
| `fps` | 幀率重映射 | `sublens fps in.srt out.srt --from 23.976 --to-fps 25` |
| `drift` | 雙錨點漂移校正 | `sublens drift in.srt out.srt --a1 1000 --b1 1000 --a2 60000 --b2 59500` |
| `audit` | 品質稽核 | `sublens audit in.srt --report sarif --strict` |
| `repair` | 自動修復 | `sublens repair in.srt out.srt` |

所有命令的輸入參數都支援 `-` 代表標準輸入，輸出支援 `-` 代表標準輸出，方便用管線組合：

```bash
cat in.srt | sublens shift - - --ms 1000 | sublens audit - --report json
```

### 稽核規則一覽

| ID | 規則 | 級別 |
| --- | --- | --- |
| SUB001 | 時長非正（結束早於或等於開始） | error |
| SUB002 | 時間戳欄位越界 | error |
| SUB003 | 字幕正文為空 | warning |
| SUB004 | 顯示時長過短 | warning |
| SUB005 | 顯示時長過長 | warning |
| SUB006 | 相鄰 cue 重疊 | warning |
| SUB007 | 起始時間順序顛倒 | warning |
| SUB008 | 時間點重複 | warning |
| SUB009 | 閱讀速度過快（cps 超標） | warning |
| SUB010 | 單則行數過多 | info |
| SUB011 | 單行字元過多 | info |
| SUB012 | 相鄰間隔過大 | info |
| SUB013 | 缺少序號 | info |
| SUB014 | 序號不連續 | info |
| SUB015 | 標籤開閉不相符 | warning |
| SUB016 | 序號為 0（相容性提示） | info |

### CI 關卡

```bash
# 出現 error 時退出碼為 1，可阻斷流程
sublens audit input.srt --strict

# 產生 SARIF 供程式碼掃描平台消費
sublens audit input.srt --report sarif > sublens.sarif
```

---

## 💡 設計迭代

SubLens 從「只解析 SRT」的樸素想法演進而來，關鍵迭代如下：

- **v0.1** —— 最初的動機只是想把一個 SRT 檔整體平移幾秒。很快發現市面工具不是依賴 ffmpeg，就是用浮點秒累加，長時間軸會漂移。
- **v0.2** —— 導入**毫秒整數**內部表示，徹底消除浮點誤差；加入自動格式偵測與 BOM/CRLF 容錯。
- **v0.3** —— 增加**幀率重映射**。核心洞察是：用「幀序號」換算而非直接乘比例，可避免 23.976 這類循環小數在長影片上的累積誤差。
- **v0.4** —— 增加**雙錨點漂移校正**，解決「片頭對準、片尾卻超前」的實際痛點，用一條線性映射統一修正。
- **v0.5** —— 稽核引擎成形。把「一則字幕好不好」的模糊判斷拆成 16 條可解釋、可開關、可設定閾值的決定性規則。
- **v1.0** —— 補齊 SARIF 輸出、自動修復、三語文件與 31 項單元測試，形成完整閉環。

**與同類工具的差異**：多數字幕函式庫只做「解析 + 寫出」，SubLens 把**時間軸的數學嚴謹性**與**品質的機器可判定性**放在同等重要的位置——這讓它不只處理字幕，還能成為自動化流程中可被信賴的一環。

---

## 📦 打包部署

本專案為**函式庫 + CLI**，無需平台二進位打包。

```bash
# 安裝（開發用可編輯模式）
pip install -e .

# 構建發行包
pip install build
python -m build          # 產出 dist/*.whl 與 dist/*.tar.gz

# 直接以模組執行（零安裝）
python3 -m sublens --help
```

- **執行環境**：Python 3.9+，跨平台（Windows / macOS / Linux）。
- **整合範例**：見上方「當作 Python 函式庫」與 `examples/demo.srt`。
- **提示**：`pyproject.toml` 已宣告 `sublens` 控制台入口，安裝後可直接呼叫 `sublens` 指令。

---

## 🤝 貢獻

歡迎提交 Issue 與 Pull Request！請先閱讀 [CONTRIBUTING.md](CONTRIBUTING.md)。

我們特別歡迎：新的稽核規則、更多字幕格式（ASS / MicroDVD）的支援，以及真實情境中的邊界案例。請遵循 Angular 提交規範，並附上單元測試結果。

---

## 📄 授權

本專案以 [MIT License](LICENSE) 開源，可自由用於商業與非商業專案。

Copyright © 2026 gitstq
