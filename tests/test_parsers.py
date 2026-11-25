"""解析器与序列化器测试。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sublens import parse, parse_srt, parse_vtt, write_srt, write_vtt, write_json, detect_format  # noqa: E402
from sublens.parsers import FormatError  # noqa: E402

SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,500
Hello, world!

2
00:00:04,000 --> 00:00:06,000
Line one
Line two
"""

VTT_SAMPLE = """WEBVTT - Sample

STYLE
::cue { color: yellow; }

00:00:01.000 --> 00:00:03.500 align:start
<c.yellow>Hello</c>

intro
00:00:04.000 --> 00:00:06.000
Line one
Line two
"""


class TestParseSrt(unittest.TestCase):
    def test_basic(self):
        sub = parse_srt(SRT_SAMPLE)
        self.assertEqual(len(sub), 2)
        self.assertEqual(sub[0].index, 1)
        self.assertEqual(sub[0].start_ms, 1000)
        self.assertEqual(sub[0].end_ms, 3500)
        self.assertEqual(sub[0].text, "Hello, world!")
        self.assertEqual(sub[1].text, "Line one\nLine two")

    def test_bom_and_crlf(self):
        text = "\ufeff" + SRT_SAMPLE.replace("\n", "\r\n")
        sub = parse_srt(text)
        self.assertEqual(len(sub), 2)
        self.assertEqual(sub[0].start_ms, 1000)

    def test_loose_timestamp(self):
        text = "1\n0:01.5 --> 0:02.250\nHi\n"
        sub = parse_srt(text)
        self.assertEqual(sub[0].start_ms, 1500)
        self.assertEqual(sub[0].end_ms, 2250)

    def test_empty_raises(self):
        with self.assertRaises(FormatError):
            parse_srt("no subtitles here")

    def test_missing_index(self):
        text = "00:00:01,000 --> 00:00:02,000\nHi\n"
        sub = parse_srt(text)
        self.assertIsNone(sub[0].index)
        self.assertEqual(sub[0].text, "Hi")


class TestParseVtt(unittest.TestCase):
    def test_basic(self):
        sub = parse_vtt(VTT_SAMPLE)
        self.assertEqual(len(sub), 2)
        self.assertEqual(sub.source_format, "vtt")
        self.assertIn("STYLE", sub.preamble)
        self.assertEqual(sub[0].start_ms, 1000)
        self.assertEqual(sub[0].settings, "align:start")

    def test_detect(self):
        self.assertEqual(detect_format(VTT_SAMPLE), "vtt")
        self.assertEqual(detect_format(SRT_SAMPLE), "srt")

    def test_auto_parse(self):
        self.assertEqual(parse(VTT_SAMPLE).source_format, "vtt")
        self.assertEqual(parse(SRT_SAMPLE).source_format, "srt")


class TestWriters(unittest.TestCase):
    def test_srt_roundtrip(self):
        sub = parse_srt(SRT_SAMPLE)
        out = write_srt(sub)
        sub2 = parse_srt(out)
        self.assertEqual([(c.start_ms, c.end_ms, c.text) for c in sub],
                         [(c.start_ms, c.end_ms, c.text) for c in sub2])

    def test_vtt_output(self):
        sub = parse_srt(SRT_SAMPLE)
        out = write_vtt(sub)
        self.assertTrue(out.startswith("WEBVTT\n"))
        self.assertIn("00:00:01.000 --> 00:00:03.500", out)

    def test_json_output(self):
        sub = parse_srt(SRT_SAMPLE)
        out = write_json(sub)
        self.assertIn('"cue_count": 2', out)
        self.assertIn("Hello, world!", out)

    def test_deterministic(self):
        sub = parse_srt(SRT_SAMPLE)
        self.assertEqual(write_srt(sub), write_srt(sub))
        self.assertEqual(write_vtt(sub), write_vtt(sub))


if __name__ == "__main__":
    unittest.main()
