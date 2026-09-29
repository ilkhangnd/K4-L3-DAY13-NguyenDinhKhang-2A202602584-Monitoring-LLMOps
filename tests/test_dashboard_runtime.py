from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.dashboard import build_dashboard_data


def test_dashboard_aggregates_all_six_panels_from_logs(tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    now = datetime(2026, 9, 29, 8, 30, tzinfo=timezone.utc)
    records = [
        {"ts": "2026-09-29T08:29:00Z", "event": "request_received"},
        {
            "ts": "2026-09-29T08:29:01Z",
            "event": "response_sent",
            "latency_ms": 400,
            "ttft_ms": 50,
            "cost_usd": 0.002,
            "tokens_in": 20,
            "tokens_out": 80,
            "quality_score": 0.9,
            "tool_success": True,
        },
        {"ts": "2026-09-29T08:29:02Z", "event": "request_failed", "error_type": "RuntimeError", "tool_success": False},
    ]
    log_path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

    dashboard = build_dashboard_data(log_path, now=now)

    assert dashboard["records"] == 3
    assert dashboard["latency"]["p95"] == 400
    assert dashboard["traffic"]["count"] == 1
    assert dashboard["errors"]["error_rate_pct"] == 100
    assert dashboard["errors"]["retrieval_success_rate_pct"] == 50
    assert dashboard["cost"]["total"] == 0.002
    assert dashboard["tokens"]["output_total"] == 80
    assert dashboard["quality"]["mean"] == 0.9
