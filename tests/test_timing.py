"""时间轴变换测试。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sublens import parse_srt, shift, scale, retime_fps, correct_drift, resolve_fps  # noqa: E402

SRT = """1
00:00:01,000 --> 00:00:03,000
A

2
00:00:05,000 --> 00:00:07,000
B
"""


class TestTiming(unittest.TestCase):
    def test_shift(self):
        sub = shift(parse_srt(SRT), 2000)
        self.assertEqual(sub[0].start_ms, 3000)
        self.assertEqual(sub[1].end_ms, 9000)
        self.assertEqual(sub[0].text, "A")

    def test_shift_negative_clamps(self):
        sub = shift(parse_srt(SRT), -5000)
        self.assertEqual(sub[0].start_ms, 0)
        self.assertEqual(sub[0].end_ms, 0)

    def test_scale(self):
        sub = scale(parse_srt(SRT), 2.0, origin_ms=0)
        self.assertEqual(sub[0].start_ms, 2000)
        self.assertEqual(sub[0].end_ms, 6000)
        self.assertEqual(sub[1].start_ms, 10000)

    def test_resolve_fps(self):
        self.assertEqual(resolve_fps("23.976"), (24000, 1001))
        self.assertEqual(resolve_fps("24000/1001"), (24000, 1001))
        self.assertEqual(resolve_fps("25"), (25, 1))
        with self.assertRaises(ValueError):
            resolve_fps("0")

    def test_retime_fps_identity(self):
        sub = parse_srt(SRT)
        out = retime_fps(sub, "25", "25")
        self.assertEqual([c.start_ms for c in out], [c.start_ms for c in sub])

    def test_retime_fps_23_976_to_25(self):
        # 23.976 -> 25 为加速，1 分钟处映射到约 57.56s（帧号 1439 -> 25fps）
        text = "1\n00:01:00,000 --> 00:01:01,000\nX\n"
        out = retime_fps(parse_srt(text), "23.976", "25")
        self.assertAlmostEqual(out[0].start_ms, 57560, delta=10)
        self.assertAlmostEqual(out[0].end_ms, 58520, delta=10)

    def test_drift_correction(self):
        # 锚点：源 1000->目标 1000，源 7000->目标 6000（逐渐提前）
        sub = parse_srt(SRT)
        out = correct_drift(sub, 1000, 1000, 7000, 6000)
        self.assertEqual(out[0].start_ms, 1000)
        self.assertEqual(out[1].end_ms, 6000)

    def test_drift_zero_span_raises(self):
        with self.assertRaises(ValueError):
            correct_drift(parse_srt(SRT), 1000, 1000, 1000, 2000)

    def test_purity(self):
        sub = parse_srt(SRT)
        before = [(c.start_ms, c.end_ms) for c in sub]
        shift(sub, 1000)
        after = [(c.start_ms, c.end_ms) for c in sub]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
