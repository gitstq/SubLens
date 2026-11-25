"""审计、报告与修复测试。"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sublens import audit, render, repair, parse_srt  # noqa: E402
from sublens.audit import AuditConfig  # noqa: E402

GOOD = """1
00:00:01,000 --> 00:00:04,000
Hello there, this is fine.

2
00:00:05,000 --> 00:00:08,000
Second line here.
"""

BAD = """1
00:00:03,000 --> 00:00:02,000
Negative duration cue

2
00:00:02,500 --> 00:00:03,200
超快速阅读超快速阅读超快速阅读超快速阅读超快速阅读超快速阅读

3
00:00:02,600 --> 00:00:03,000
Overlap and too short

4
00:00:04,000 --> 00:00:05,000
"""


class TestAudit(unittest.TestCase):
    def test_good_passes(self):
        rep = audit(parse_srt(GOOD))
        self.assertTrue(rep.passed)
        self.assertEqual(rep.error_count, 0)
        self.assertGreater(rep.score, 70)

    def test_bad_detects(self):
        rep = audit(parse_srt(BAD))
        self.assertFalse(rep.passed)
        ids = {f.rule_id for f in rep.findings}
        self.assertIn("SUB001", ids)  # 非正时长
        self.assertIn("SUB003", ids)  # 空文本
        self.assertIn("SUB004", ids)  # 过短
        self.assertIn("SUB006", ids)  # 重叠

    def test_config_threshold(self):
        cfg = AuditConfig(min_duration_ms=100)
        rep = audit(parse_srt(BAD), cfg)
        short = [f for f in rep.findings if f.rule_id == "SUB004"]
        self.assertEqual(len(short), 0)

    def test_disabled_rules(self):
        cfg = AuditConfig(enabled={"SUB001"})
        rep = audit(parse_srt(BAD), cfg)
        self.assertTrue(all(f.rule_id == "SUB001" for f in rep.findings))


class TestReports(unittest.TestCase):
    def test_text(self):
        text = render(audit(parse_srt(GOOD)), "text")
        self.assertIn("SubLens", text)
        self.assertIn("PASS", text)

    def test_json(self):
        doc = json.loads(render(audit(parse_srt(BAD)), "json"))
        self.assertIn("summary", doc)
        self.assertFalse(doc["summary"]["passed"])

    def test_sarif(self):
        doc = json.loads(render(audit(parse_srt(BAD)), "sarif"))
        self.assertEqual(doc["version"], "2.1.0")
        self.assertEqual(doc["runs"][0]["tool"]["driver"]["name"], "SubLens")
        self.assertGreater(len(doc["runs"][0]["results"]), 0)


class TestRepair(unittest.TestCase):
    def test_repair_bad(self):
        out, stats = repair(parse_srt(BAD))
        self.assertGreater(stats.total, 0)
        self.assertEqual(stats.removed_empty, 1)
        self.assertEqual(stats.clamped_duration, 1)
        # 修复后不再有 error
        self.assertTrue(audit(out).passed)

    def test_repair_purity(self):
        sub = parse_srt(BAD)
        before = [(c.start_ms, c.end_ms, c.text) for c in sub]
        repair(sub)
        after = [(c.start_ms, c.end_ms, c.text) for c in sub]
        self.assertEqual(before, after)

    def test_renumber(self):
        out, stats = repair(parse_srt(BAD))
        self.assertEqual([c.index for c in out], list(range(1, len(out) + 1)))


if __name__ == "__main__":
    unittest.main()
