"""确定性时间轴变换引擎。

提供四类变换，全部返回新对象、不修改输入：

1. :func:`shift`          —— 整体平移（毫秒）；
2. :func:`scale`          —— 以任意原点缩放时间轴；
3. :func:`retime_fps`     —— 帧率重映射（如 23.976 -> 25），按帧对齐消除累积漂移；
4. :func:`correct_drift`  —— 基于双锚点的线性漂移校正（解决片头/片尾不同步）。

所有函数均为纯函数，保证相同输入 -> 相同输出。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .models import Cue, Subtitle, Timestamp

__all__ = [
    "shift",
    "scale",
    "retime_fps",
    "correct_drift",
    "FPS_PRESETS",
    "resolve_fps",
]

# 常见帧率预设：名称 -> 精确有理数 (分子, 分母)
FPS_PRESETS = {
    "23.976": (24000, 1001),
    "24": (24, 1),
    "25": (25, 1),
    "29.97": (30000, 1001),
    "30": (30, 1),
    "50": (50, 1),
    "59.94": (60000, 1001),
    "60": (60, 1),
}


def resolve_fps(value: str) -> Tuple[int, int]:
    """解析帧率字符串，返回 ``(分子, 分母)``。

    接受预设名（``'23.976'``）或自定义分数（``'24000/1001'``）。
    """
    key = value.strip()
    if key in FPS_PRESETS:
        return FPS_PRESETS[key]
    if "/" in key:
        num, _, den = key.partition("/")
        try:
            n, d = int(num), int(den)
        except ValueError as exc:  # pragma: no cover - 输入保护
            raise ValueError(f"无法解析帧率: {value!r}") from exc
        if d <= 0:
            raise ValueError("帧率分母必须为正数")
        return n, d
    try:
        f = float(key)
    except ValueError as exc:  # pragma: no cover - 输入保护
        raise ValueError(f"无法解析帧率: {value!r}") from exc
    if f <= 0:
        raise ValueError("帧率必须为正数")
    # 小数转近似有理数，优先匹配已知 NTSC 值
    for name, (n, d) in FPS_PRESETS.items():
        if abs(n / d - f) < 1e-3:
            return n, d
    return round(f * 1000), 1000


def _rebuild(cues: List[Cue], source: Subtitle) -> Subtitle:
    return Subtitle(cues=cues, source_format=source.source_format, preamble=source.preamble)


def shift(sub: Subtitle, delta_ms: int) -> Subtitle:
    """将所有 cue 整体平移 ``delta_ms``（可正可负）。

    平移后若 end < 0 会被钳制到 0；文本、序号与设置保持不变。
    """
    return _rebuild([c.shifted(delta_ms) for c in sub.cues], sub)


def scale(sub: Subtitle, factor: float, origin_ms: int = 0) -> Subtitle:
    """以 ``origin_ms`` 为原点按比例缩放时间轴。

    ``factor > 1`` 拉长时间轴，``factor < 1`` 压缩。常用于整体速度微调。
    """
    if factor <= 0:
        raise ValueError("缩放系数必须为正数")
    return _rebuild([c.scaled(factor, origin_ms) for c in sub.cues], sub)


def retime_fps(sub: Subtitle, src_fps: str, dst_fps: str) -> Subtitle:
    """帧率重映射：把按 ``src_fps`` 生成的时间轴换算到 ``dst_fps``。

    实现：将每个时间点换算为帧序号（四舍五入），再按目标帧率还原时间。
    相比直接乘比例，逐点对齐可避免长时间轴上的累积舍入漂移。

    ::

        frame = round(ms * src_num / src_den / 1000)
        new_ms = round(frame * dst_den / dst_num * 1000)
    """
    sn, sd = resolve_fps(src_fps)
    dn, dd = resolve_fps(dst_fps)
    if (sn, sd) == (dn, dd):
        return Subtitle(cues=list(sub.cues), source_format=sub.source_format, preamble=sub.preamble)

    def convert(ms: int) -> int:
        frame = round(ms * sn / sd / 1000.0)
        return round(frame * dd / dn * 1000.0)

    cues: List[Cue] = []
    for c in sub.cues:
        cues.append(
            Cue(
                start=Timestamp.from_millis(convert(c.start_ms)),
                end=Timestamp.from_millis(convert(c.end_ms)),
                text=c.text,
                index=c.index,
                settings=c.settings,
                identifier=c.identifier,
            )
        )
    return _rebuild(cues, sub)


def correct_drift(
    sub: Subtitle,
    anchor_start_ms: int,
    anchor_start_target_ms: int,
    anchor_end_ms: int,
    anchor_end_target_ms: int,
) -> Subtitle:
    """双锚点线性漂移校正。

    给定两个源时间点及其期望目标点，构造线性映射 ``t' = a*t + b`` 并应用到所有 cue。
    典型场景：字幕整体随时间逐渐超前，片头对准、片尾超前 2 秒，用两个锚点即可
    线性消除漂移。

    :param anchor_start_ms: 源时间轴上的第一个锚点（毫秒）
    :param anchor_start_target_ms: 该锚点期望落在的目标时间（毫秒）
    :param anchor_end_ms: 源时间轴上的第二个锚点
    :param anchor_end_target_ms: 第二个锚点的目标时间
    """
    span = anchor_end_ms - anchor_start_ms
    if span == 0:
        raise ValueError("两个锚点的时间必须不同")
    a = (anchor_end_target_ms - anchor_start_target_ms) / span
    b = anchor_start_target_ms - a * anchor_start_ms

    cues: List[Cue] = []
    for c in sub.cues:
        s = max(0, round(a * c.start_ms + b))
        e = max(0, round(a * c.end_ms + b))
        cues.append(
            Cue(
                start=Timestamp.from_millis(s),
                end=Timestamp.from_millis(e),
                text=c.text,
                index=c.index,
                settings=c.settings,
                identifier=c.identifier,
            )
        )
    return _rebuild(cues, sub)
