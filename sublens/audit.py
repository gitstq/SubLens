"""字幕质量审计引擎。

规则集全部为确定性、可解释、零依赖。每条规则返回若干 :class:`Finding`，
包含稳定规则 ID、严重级别、定位（cue 序号）与可读消息，便于 CI 门禁与 SARIF 输出。

设计原则：
- 审计只读，不修改字幕；
- 规则之间互相独立，便于单独启用/禁用；
- 阈值可通过 :class:`AuditConfig` 调整。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .models import Cue, Subtitle

__all__ = [
    "Finding",
    "AuditConfig",
    "AuditReport",
    "audit",
    "RULES",
    "SEVERITY_ORDER",
]

SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}


@dataclass
class Finding:
    """单条审计发现。"""

    rule_id: str
    severity: str  # info / warning / error
    message: str
    cue_index: Optional[int] = None

    def __str__(self) -> str:  # pragma: no cover - 便捷展示
        where = f"cue#{self.cue_index}" if self.cue_index is not None else "doc"
        return f"[{self.severity.upper()}] {self.rule_id} {where}: {self.message}"


@dataclass
class AuditConfig:
    """审计阈值配置。"""

    min_duration_ms: int = 500       # 最短显示时长
    max_duration_ms: int = 10000     # 最长显示时长
    max_cps: float = 20.0            # 最大字符/秒（阅读速度）
    max_lines: int = 2               # 单条最大行数
    max_line_chars: int = 42         # 单行最大字符数
    max_gap_ms: int = 5000           # 相邻 cue 最大空隙
    overlap_tolerance_ms: int = 0    # 允许的轻微重叠
    enabled: Optional[set] = None    # 启用的规则 ID 集合，None 表示全部

    def is_enabled(self, rule_id: str) -> bool:
        return self.enabled is None or rule_id in self.enabled


@dataclass
class AuditReport:
    """审计结果集合。"""

    findings: List[Finding] = field(default_factory=list)
    cue_count: int = 0
    config: Optional[AuditConfig] = None

    def by_severity(self, severity: str) -> List[Finding]:
        return [f for f in self.findings if f.severity == severity]

    @property
    def error_count(self) -> int:
        return len(self.by_severity("error"))

    @property
    def warning_count(self) -> int:
        return len(self.by_severity("warning"))

    @property
    def info_count(self) -> int:
        return len(self.by_severity("info"))

    @property
    def passed(self) -> bool:
        """无 error 即视为通过（warning 不阻断）。"""
        return self.error_count == 0

    @property
    def score(self) -> int:
        """质量分 0-100：从 100 扣分，error 扣 10、warning 扣 3、info 扣 1。"""
        penalty = self.error_count * 10 + self.warning_count * 3 + self.info_count
        return max(0, 100 - penalty)


# ---- 规则实现 -----------------------------------------------------------

def _rule(cfg: AuditConfig) -> List[Finding]:  # pragma: no cover - 占位
    return []


def _idx(cue: Cue, pos: int) -> int:
    return cue.index if cue.index is not None else pos


def r_nonpositive(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        if c.duration_ms <= 0:
            out.append(
                Finding("SUB001", "error", f"时长非正（{c.duration_ms}ms）", _idx(c, i + 1))
            )
    return out


def _valid_time(ts) -> bool:
    """检查时间戳字段是否越界。"""
    return (
        ts.minutes < 60
        and ts.seconds < 60
        and ts.millis < 1000
        and ts.hours >= 0
    )


def r_bad_timestamp(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        if not _valid_time(c.start) or not _valid_time(c.end):
            out.append(Finding("SUB002", "error", "时间戳字段越界", _idx(c, i + 1)))
    return out


def r_empty_text(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        if not c.text.strip():
            out.append(Finding("SUB003", "warning", "字幕正文为空", _idx(c, i + 1)))
    return out


def r_too_short(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        if 0 < c.duration_ms < cfg.min_duration_ms:
            out.append(
                Finding(
                    "SUB004",
                    "warning",
                    f"显示过短（{c.duration_ms}ms < {cfg.min_duration_ms}ms）",
                    _idx(c, i + 1),
                )
            )
    return out


def r_too_long(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        if c.duration_ms > cfg.max_duration_ms:
            out.append(
                Finding(
                    "SUB005",
                    "warning",
                    f"显示过长（{c.duration_ms}ms > {cfg.max_duration_ms}ms）",
                    _idx(c, i + 1),
                )
            )
    return out


def r_overlap(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    cues = sorted(sub.cues, key=lambda c: c.start_ms)
    for prev, nxt in zip(cues, cues[1:]):
        overlap = prev.end_ms - nxt.start_ms
        if overlap > cfg.overlap_tolerance_ms:
            out.append(
                Finding(
                    "SUB006",
                    "warning",
                    f"与下一条重叠 {overlap}ms",
                    _idx(prev, sub.cues.index(prev) + 1),
                )
            )
    return out


def r_out_of_order(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i in range(1, len(sub.cues)):
        if sub.cues[i].start_ms < sub.cues[i - 1].start_ms:
            out.append(
                Finding(
                    "SUB007", "warning", "起始时间早于上一条（顺序颠倒）", _idx(sub.cues[i], i + 1)
                )
            )
    return out


def r_duplicate_time(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    seen: Dict[tuple, int] = {}
    out = []
    for i, c in enumerate(sub.cues):
        key = (c.start_ms, c.end_ms)
        if key in seen:
            out.append(
                Finding(
                    "SUB008", "warning", f"与 cue#{seen[key]} 时间完全相同", _idx(c, i + 1)
                )
            )
        else:
            seen[key] = _idx(c, i + 1)
    return out


def r_reading_speed(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        if c.duration_ms <= 0:
            continue
        # 统计可见字符（剔除标签与空白）
        clean = re.sub(r"<[^>]+>", "", c.text)
        chars = len("".join(clean.split()))
        cps = chars * 1000.0 / c.duration_ms
        if cps > cfg.max_cps:
            out.append(
                Finding(
                    "SUB009",
                    "warning",
                    f"阅读速度过快（{cps:.1f} cps > {cfg.max_cps}）",
                    _idx(c, i + 1),
                )
            )
    return out


def r_max_lines(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        lines = [ln for ln in c.text.split("\n") if ln.strip()]
        if len(lines) > cfg.max_lines:
            out.append(
                Finding(
                    "SUB010",
                    "info",
                    f"行数过多（{len(lines)} > {cfg.max_lines}）",
                    _idx(c, i + 1),
                )
            )
    return out


def r_long_line(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        for ln in c.text.split("\n"):
            if len(ln.strip()) > cfg.max_line_chars:
                out.append(
                    Finding(
                        "SUB011",
                        "info",
                        f"单行过长（{len(ln.strip())} > {cfg.max_line_chars} 字符）",
                        _idx(c, i + 1),
                    )
                )
                break
    return out


def r_large_gap(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    cues = sorted(sub.cues, key=lambda c: c.start_ms)
    for prev, nxt in zip(cues, cues[1:]):
        gap = nxt.start_ms - prev.end_ms
        if gap > cfg.max_gap_ms:
            out.append(
                Finding(
                    "SUB012", "info", f"相邻字幕间隔过大（{gap}ms）", _idx(nxt, sub.cues.index(nxt) + 1)
                )
            )
    return out


def r_missing_index(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues):
        if c.index is None:
            out.append(Finding("SUB013", "info", "缺少序号", i + 1))
    return out


def r_bad_index(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    out = []
    for i, c in enumerate(sub.cues, start=1):
        if c.index is not None and c.index != i:
            out.append(Finding("SUB014", "info", f"序号不连续（期望 {i}，实际 {c.index}）", c.index))
    return out


def r_unbalanced_tag(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    """检测未闭合的 VTT/HTML 类标签（如 <i>、<b>、<u>、<font>）。"""
    tags = ("i", "b", "u")
    out = []
    for i, c in enumerate(sub.cues):
        for tag in tags:
            opens = len(re.findall(rf"<{tag}(?:\s[^>]*)?>", c.text, flags=re.I))
            closes = len(re.findall(rf"</{tag}>", c.text, flags=re.I))
            if opens != closes:
                out.append(
                    Finding(
                        "SUB015",
                        "warning",
                        f"<{tag}> 标签开闭不匹配（{opens} 开 / {closes} 闭）",
                        _idx(c, i + 1),
                    )
                )
    return out


def r_leading_zero(sub: Subtitle, cfg: AuditConfig) -> List[Finding]:
    """提示从 0 开始编号的 cue（部分播放器不兼容）。"""
    out = []
    for i, c in enumerate(sub.cues):
        if c.index == 0:
            out.append(Finding("SUB016", "info", "序号为 0，某些播放器不兼容", i + 1))
    return out


# ---- 规则注册表 ---------------------------------------------------------

RULES: List[Callable[[Subtitle, AuditConfig], List[Finding]]] = [
    r_nonpositive,
    r_bad_timestamp,
    r_empty_text,
    r_too_short,
    r_too_long,
    r_overlap,
    r_out_of_order,
    r_duplicate_time,
    r_reading_speed,
    r_max_lines,
    r_long_line,
    r_large_gap,
    r_missing_index,
    r_bad_index,
    r_unbalanced_tag,
    r_leading_zero,
]

RULE_IDS = {
    r_nonpositive: "SUB001",
    r_bad_timestamp: "SUB002",
    r_empty_text: "SUB003",
    r_too_short: "SUB004",
    r_too_long: "SUB005",
    r_overlap: "SUB006",
    r_out_of_order: "SUB007",
    r_duplicate_time: "SUB008",
    r_reading_speed: "SUB009",
    r_max_lines: "SUB010",
    r_long_line: "SUB011",
    r_large_gap: "SUB012",
    r_missing_index: "SUB013",
    r_bad_index: "SUB014",
    r_unbalanced_tag: "SUB015",
    r_leading_zero: "SUB016",
}


def audit(sub: Subtitle, config: Optional[AuditConfig] = None) -> AuditReport:
    """对字幕执行全部启用规则，返回 :class:`AuditReport`。"""
    cfg = config or AuditConfig()
    findings: List[Finding] = []
    for rule in RULES:
        rid = RULE_IDS[rule]
        if cfg.is_enabled(rid):
            findings.extend(rule(sub, cfg))
    # 稳定排序：严重级别降序 -> 规则 ID -> cue 序号
    findings.sort(
        key=lambda f: (
            -SEVERITY_ORDER[f.severity],
            f.rule_id,
            f.cue_index if f.cue_index is not None else -1,
        )
    )
    return AuditReport(findings=findings, cue_count=len(sub.cues), config=cfg)
