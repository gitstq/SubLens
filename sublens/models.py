"""SubLens 核心数据模型。

本模块定义字幕领域的最小不可变值对象：Timestamp（时间戳）、Cue（字幕块）、
Subtitle（字幕文档）。所有时间内部统一以毫秒整数存储，避免浮点误差，
保证解析 -> 变换 -> 写回的全链路确定性。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

__all__ = ["Timestamp", "Cue", "Subtitle", "MS_PER_SECOND"]

MS_PER_SECOND = 1000
MS_PER_MINUTE = 60 * MS_PER_SECOND
MS_PER_HOUR = 60 * MS_PER_MINUTE


@dataclass(frozen=True)
class Timestamp:
    """不可变时间戳，精确到毫秒。

    ``hours/minutes/seconds/millis`` 均为规范化后的非负整数，
    通过 :meth:`from_millis` 构造可自动处理进位。
    """

    hours: int
    minutes: int
    seconds: int
    millis: int

    # ---- 构造 -----------------------------------------------------------
    @classmethod
    def from_millis(cls, total_ms: int) -> "Timestamp":
        """由总毫秒数构造时间戳（负数会被钳制为 0）。"""
        if total_ms < 0:
            total_ms = 0
        hours, rem = divmod(total_ms, MS_PER_HOUR)
        minutes, rem = divmod(rem, MS_PER_MINUTE)
        seconds, millis = divmod(rem, MS_PER_SECOND)
        return cls(hours, minutes, seconds, millis)

    @classmethod
    def zero(cls) -> "Timestamp":
        """返回零点时间戳。"""
        return cls(0, 0, 0, 0)

    # ---- 转换 -----------------------------------------------------------
    def to_millis(self) -> int:
        """返回自 00:00:00.000 起的总毫秒数。"""
        return (
            self.hours * MS_PER_HOUR
            + self.minutes * MS_PER_MINUTE
            + self.seconds * MS_PER_SECOND
            + self.millis
        )

    def to_srt(self) -> str:
        """SRT 格式：``HH:MM:SS,mmm``。"""
        return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d},{self.millis:03d}"

    def to_vtt(self) -> str:
        """WebVTT 格式：``HH:MM:SS.mmm``（小时恒显示两位）。"""
        return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}.{self.millis:03d}"

    def to_vtt_short(self) -> str:
        """WebVTT 简写：小时为 0 时省略小时位。"""
        core = f"{self.minutes:02d}:{self.seconds:02d}.{self.millis:03d}"
        return core if self.hours == 0 else f"{self.hours:02d}:{core}"

    # ---- 比较 -----------------------------------------------------------
    def __str__(self) -> str:  # pragma: no cover - 便捷展示
        return self.to_srt()

    def __lt__(self, other: "Timestamp") -> bool:
        return self.to_millis() < other.to_millis()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            return NotImplemented
        return self.to_millis() == other.to_millis()

    def __hash__(self) -> int:
        return hash(self.to_millis())


@dataclass
class Cue:
    """单条字幕块（cue）。

    ``index`` 为原始序号，解析缺失时可为 ``None``；``settings`` 保存
    WebVTT cue settings 或 ASS 覆盖字段，保证往返转换不丢失信息。
    """

    start: Timestamp
    end: Timestamp
    text: str
    index: Optional[int] = None
    settings: str = ""
    identifier: str = ""

    @property
    def duration_ms(self) -> int:
        """本 cue 的时长（毫秒），结束早于开始时返回负值。"""
        return self.end.to_millis() - self.start.to_millis()

    @property
    def start_ms(self) -> int:
        return self.start.to_millis()

    @property
    def end_ms(self) -> int:
        return self.end.to_millis()

    def shifted(self, delta_ms: int) -> "Cue":
        """返回一个起止时间整体平移 ``delta_ms`` 的新 cue。"""
        return Cue(
            start=Timestamp.from_millis(self.start_ms + delta_ms),
            end=Timestamp.from_millis(self.end_ms + delta_ms),
            text=self.text,
            index=self.index,
            settings=self.settings,
            identifier=self.identifier,
        )

    def scaled(self, factor: float, origin_ms: int = 0) -> "Cue":
        """返回一个以 ``origin_ms`` 为原点缩放时间轴的新 cue。

        公式：``new = origin + (old - origin) * factor``，结果四舍五入到毫秒。
        """
        o = origin_ms
        s = o + round((self.start_ms - o) * factor)
        e = o + round((self.end_ms - o) * factor)
        return Cue(
            start=Timestamp.from_millis(s),
            end=Timestamp.from_millis(e),
            text=self.text,
            index=self.index,
            settings=self.settings,
            identifier=self.identifier,
        )

    # ---- 展示 -----------------------------------------------------------
    def __str__(self) -> str:  # pragma: no cover - 便捷展示
        idx = self.index if self.index is not None else "?"
        return f"[{idx}] {self.start.to_srt()} --> {self.end.to_srt()} | {self.text!r}"


@dataclass
class Subtitle:
    """字幕文档，持有有序 cue 列表与来源格式元信息。"""

    cues: List[Cue] = field(default_factory=list)
    source_format: str = "srt"
    # WebVTT 头部备注（如 NOTE 块、STYLE 块），保真往返用
    preamble: str = ""

    def __len__(self) -> int:
        return len(self.cues)

    def __iter__(self):  # noqa: D105
        return iter(self.cues)

    def __getitem__(self, item):  # noqa: D105
        return self.cues[item]

    @property
    def duration_ms(self) -> int:
        """文档覆盖的时间跨度：最后结束 - 最早开始，空文档返回 0。"""
        if not self.cues:
            return 0
        start = min(c.start_ms for c in self.cues)
        end = max(c.end_ms for c in self.cues)
        return max(0, end - start)

    def sorted(self) -> "Subtitle":
        """返回按开始时间稳定排序后的新文档。"""
        cues = sorted(self.cues, key=lambda c: (c.start_ms, c.end_ms))
        return Subtitle(cues=cues, source_format=self.source_format, preamble=self.preamble)

    def renumber(self, start: int = 1) -> "Subtitle":
        """返回重新连续编号的新文档。"""
        cues = []
        for i, cue in enumerate(self.cues, start=start):
            cues.append(
                Cue(
                    start=cue.start,
                    end=cue.end,
                    text=cue.text,
                    index=i,
                    settings=cue.settings,
                    identifier=cue.identifier,
                )
            )
        return Subtitle(cues=cues, source_format=self.source_format, preamble=self.preamble)
