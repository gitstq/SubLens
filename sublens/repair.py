"""自动修复模块。

仅修复「无损或低风险」的问题，不擅自改写字幕文本语义：
- 重排序号（缺失/不连续/从 0 开始）；
- 删除完全空正文的 cue；
- 钳制负时长（end < start 时把 end 对齐到 start + 1ms）；
- 合并可容忍范围内的轻微重叠（后一条 start 对齐到前一条 end）。

所有操作返回新文档；``RepairStats`` 记录实际改动，便于审计追踪。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .models import Cue, Subtitle, Timestamp

__all__ = ["repair", "RepairStats"]


@dataclass
class RepairStats:
    """修复统计。"""

    renumbered: int = 0
    removed_empty: int = 0
    clamped_duration: int = 0
    merged_overlap: int = 0

    @property
    def total(self) -> int:
        return (
            self.renumbered
            + self.removed_empty
            + self.clamped_duration
            + self.merged_overlap
        )

    def summary(self) -> str:
        return (
            f"修复 {self.total} 项：重排序号 {self.renumbered}、"
            f"删除空行 {self.removed_empty}、钳制时长 {self.clamped_duration}、"
            f"合并重叠 {self.merged_overlap}"
        )


def repair(
    sub: Subtitle,
    remove_empty: bool = True,
    clamp_duration: bool = True,
    merge_overlap: bool = True,
    renumber: bool = True,
) -> tuple:
    """执行自动修复，返回 ``(新字幕, 统计)``。"""
    stats = RepairStats()
    cues: List[Cue] = list(sub.cues)

    # 1) 删除空正文
    if remove_empty:
        before = len(cues)
        cues = [c for c in cues if c.text.strip()]
        stats.removed_empty = before - len(cues)

    # 2) 钳制非正时长
    if clamp_duration:
        fixed: List[Cue] = []
        for c in cues:
            if c.duration_ms <= 0:
                new_end = Timestamp.from_millis(c.start_ms + 1)
                fixed.append(
                    Cue(
                        start=c.start,
                        end=new_end,
                        text=c.text,
                        index=c.index,
                        settings=c.settings,
                        identifier=c.identifier,
                    )
                )
                stats.clamped_duration += 1
            else:
                fixed.append(c)
        cues = fixed

    # 3) 合并重叠（基于排序后的时间轴，仅前移到不重叠）
    if merge_overlap and cues:
        ordered = sorted(enumerate(cues), key=lambda pair: pair[1].start_ms)
        merged: List[Cue] = []
        last_end = -1
        for _, c in ordered:
            if last_end >= 0 and c.start_ms < last_end:
                c = Cue(
                    start=Timestamp.from_millis(last_end),
                    end=Timestamp.from_millis(max(last_end + 1, c.end_ms)),
                    text=c.text,
                    index=c.index,
                    settings=c.settings,
                    identifier=c.identifier,
                )
                stats.merged_overlap += 1
            merged.append(c)
            last_end = c.end_ms
        cues = merged

    # 4) 重排序号：统一按 1..N
    if renumber:
        cues = [
            Cue(
                start=c.start,
                end=c.end,
                text=c.text,
                index=i,
                settings=c.settings,
                identifier=c.identifier,
            )
            for i, c in enumerate(cues, start=1)
        ]
        stats.renumbered = len(cues)

    out = Subtitle(cues=cues, source_format=sub.source_format, preamble=sub.preamble)
    return out, stats
