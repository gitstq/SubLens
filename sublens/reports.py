"""审计报告渲染器：text / json / sarif。

SARIF 2.1.0 输出使 SubLens 可直接接入 GitHub Code Scanning 等 CI 体系。
"""

from __future__ import annotations

import json
from typing import Dict, List

from .audit import AuditReport

__all__ = ["render"]

_SEVERITY_TO_SARIF = {"error": "error", "warning": "warning", "info": "note"}
_SEVERITY_TO_RANK = {"error": 9.0, "warning": 5.0, "info": 2.0}


def _render_text(report: AuditReport) -> str:
    lines: List[str] = []
    lines.append(f"SubLens 审计结果：{report.cue_count} 条字幕")
    lines.append(
        f"  errors={report.error_count} warnings={report.warning_count} "
        f"infos={report.info_count} score={report.score}/100"
    )
    lines.append("")
    if not report.findings:
        lines.append("  ✓ 未发现问题")
    for f in report.findings:
        lines.append("  " + str(f))
    lines.append("")
    lines.append("结论：" + ("PASS" if report.passed else "FAIL"))
    return "\n".join(lines) + "\n"


def _render_json(report: AuditReport) -> str:
    doc = {
        "tool": "SubLens",
        "cue_count": report.cue_count,
        "summary": {
            "errors": report.error_count,
            "warnings": report.warning_count,
            "infos": report.info_count,
            "score": report.score,
            "passed": report.passed,
        },
        "findings": [
            {
                "rule_id": f.rule_id,
                "severity": f.severity,
                "cue_index": f.cue_index,
                "message": f.message,
            }
            for f in report.findings
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def _rule_descriptor(rule_id: str, severity: str, message: str) -> Dict[str, object]:
    return {
        "id": rule_id,
        "name": rule_id,
        "shortDescription": {"text": f"{rule_id} 字幕质量规则"},
        "fullDescription": {"text": message},
        "defaultConfiguration": {"level": _SEVERITY_TO_SARIF[severity]},
        "properties": {"tags": ["subtitle", "quality"]},
    }


def _render_sarif(report: AuditReport) -> str:
    # 汇总所有出现过的规则，生成 rule 表与结果
    rules_meta: Dict[str, Dict[str, object]] = {}
    results: List[Dict[str, object]] = []
    for f in report.findings:
        rules_meta.setdefault(
            f.rule_id, _rule_descriptor(f.rule_id, f.severity, f.message)
        )
        result: Dict[str, object] = {
            "ruleId": f.rule_id,
            "level": _SEVERITY_TO_SARIF[f.severity],
            "message": {"text": f.message},
            "properties": {"security-severity": str(_SEVERITY_TO_RANK[f.severity])},
        }
        if f.cue_index is not None:
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": "subtitle"},
                        "region": {"startLine": f.cue_index},
                    }
                }
            ]
        results.append(result)

    doc = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "SubLens",
                        "version": "1.0.0",
                        "informationUri": "https://github.com/gitstq/SubLens",
                        "rules": list(rules_meta.values()),
                    }
                },
                "results": results,
                "properties": {
                    "sublens": {
                        "score": report.score,
                        "passed": report.passed,
                        "cue_count": report.cue_count,
                    }
                },
            }
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def render(report: AuditReport, fmt: str = "text") -> str:
    """按 ``fmt``（``text``/``json``/``sarif``）渲染审计报告。"""
    fmt = fmt.lower()
    if fmt == "text":
        return _render_text(report)
    if fmt == "json":
        return _render_json(report)
    if fmt == "sarif":
        return _render_sarif(report)
    raise ValueError(f"不支持的报告格式: {fmt!r}")
