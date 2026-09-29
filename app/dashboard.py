from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any


LOG_PATH = Path("data/logs.jsonl")
WINDOW_MINUTES = 60


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percentile / 100) * len(ordered) + 0.5) - 1))
    return float(ordered[index])


def _series(start: datetime, values: dict[datetime, float | list[float]]) -> list[dict[str, Any]]:
    points = []
    for offset in range(WINDOW_MINUTES):
        bucket = start + timedelta(minutes=offset)
        value = values.get(bucket, 0.0)
        points.append(
            {
                "time": bucket.strftime("%H:%M"),
                "value": round(mean(value), 4) if isinstance(value, list) and value else round(float(value), 4),
            }
        )
    return points


def build_dashboard_data(
    path: Path = LOG_PATH, now: datetime | None = None
) -> dict[str, Any]:
    """Aggregate the six dashboard panels from the structured application logs."""
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    start = now.replace(second=0, microsecond=0) - timedelta(minutes=WINDOW_MINUTES - 1)
    records: list[dict[str, Any]] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            timestamp = _timestamp(record.get("ts"))
            if timestamp is not None and timestamp >= start:
                record["_timestamp"] = timestamp
                records.append(record)

    responses = [record for record in records if record.get("event") == "response_sent"]
    requests = [record for record in records if record.get("event") == "request_received"]
    failures = [record for record in records if record.get("event") == "request_failed"]

    def numeric(items: list[dict[str, Any]], key: str) -> list[float]:
        return [float(item[key]) for item in items if isinstance(item.get(key), (int, float))]

    latency = numeric(responses, "latency_ms")
    ttft = numeric(responses, "ttft_ms")
    costs = numeric(responses, "cost_usd")
    quality = numeric(responses, "quality_score")
    tokens_in = numeric(responses, "tokens_in")
    tokens_out = numeric(responses, "tokens_out")

    response_latency: dict[datetime, list[float]] = defaultdict(list)
    response_ttft: dict[datetime, list[float]] = defaultdict(list)
    traffic: Counter[datetime] = Counter()
    errors: Counter[datetime] = Counter()
    minute_cost: Counter[datetime] = Counter()
    minute_input: Counter[datetime] = Counter()
    minute_output: Counter[datetime] = Counter()
    minute_quality: dict[datetime, list[float]] = defaultdict(list)

    for record in records:
        bucket = record["_timestamp"].replace(second=0, microsecond=0)
        if record.get("event") == "request_received":
            traffic[bucket] += 1
        elif record.get("event") == "request_failed":
            errors[bucket] += 1
        elif record.get("event") == "response_sent":
            if isinstance(record.get("latency_ms"), (int, float)):
                response_latency[bucket].append(float(record["latency_ms"]))
            if isinstance(record.get("ttft_ms"), (int, float)):
                response_ttft[bucket].append(float(record["ttft_ms"]))
            if isinstance(record.get("cost_usd"), (int, float)):
                minute_cost[bucket] += float(record["cost_usd"])
            if isinstance(record.get("tokens_in"), (int, float)):
                minute_input[bucket] += float(record["tokens_in"])
            if isinstance(record.get("tokens_out"), (int, float)):
                minute_output[bucket] += float(record["tokens_out"])
            if isinstance(record.get("quality_score"), (int, float)):
                minute_quality[bucket].append(float(record["quality_score"]))

    error_rate = (len(failures) / len(requests) * 100) if requests else 0.0
    retrieval_outcomes = [record["tool_success"] for record in records if isinstance(record.get("tool_success"), bool)]
    retrieval_success = (sum(retrieval_outcomes) / len(retrieval_outcomes) * 100) if retrieval_outcomes else 0.0
    breakdown = Counter(
        str(record.get("error_type", "unknown")) for record in failures
    )

    error_rate_by_minute = {
        bucket: (errors[bucket] / count * 100) if count else 0.0
        for bucket, count in traffic.items()
    }
    return {
        "generated_at": now.isoformat(),
        "window_minutes": WINDOW_MINUTES,
        "records": len(records),
        "latency": {
            "p50": round(_percentile(latency, 50), 1),
            "p95": round(_percentile(latency, 95), 1),
            "p99": round(_percentile(latency, 99), 1),
            "ttft_p95": round(_percentile(ttft, 95), 1),
            "threshold": 3000,
            "series": _series(start, response_latency),
            "ttft_series": _series(start, response_ttft),
        },
        "traffic": {
            "count": len(requests),
            "rate_per_minute": round(len(requests) / WINDOW_MINUTES, 2),
            "threshold": 1,
            "series": _series(start, traffic),
        },
        "errors": {
            "error_rate_pct": round(error_rate, 2),
            "retrieval_success_rate_pct": round(retrieval_success, 2),
            "threshold": 2,
            "breakdown": dict(breakdown),
            "series": _series(start, error_rate_by_minute),
        },
        "cost": {
            "total": round(sum(costs), 6),
            "threshold": 2.5,
            "series": _series(start, minute_cost),
        },
        "tokens": {
            "input_total": int(sum(tokens_in)),
            "output_total": int(sum(tokens_out)),
            "threshold": 50000,
            "input_series": _series(start, minute_input),
            "output_series": _series(start, minute_output),
        },
        "quality": {
            "mean": round(mean(quality), 3) if quality else 0.0,
            "threshold": 0.75,
            "series": _series(start, minute_quality),
        },
    }


def render_dashboard() -> str:
    data = json.dumps(build_dashboard_data()).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LLMOps runtime dashboard</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#07111f;color:#e6edf7;font-family:ui-sans-serif,system-ui,-apple-system,sans-serif}}
main{{max-width:1380px;margin:auto;padding:32px 24px 48px}} header{{display:flex;justify-content:space-between;gap:20px;align-items:start;margin-bottom:24px}}
h1{{font-size:27px;margin:0 0 6px}} h2{{font-size:16px;margin:0}} p{{margin:4px 0;color:#aab8ca;font-size:13px}} .badges{{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end}} .badge{{border:1px solid #2b405c;border-radius:999px;padding:6px 10px;color:#bcd0e8;font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}} .panel{{background:#0d1a2c;border:1px solid #203653;border-radius:14px;padding:18px;min-height:265px}} .metrics{{display:flex;flex-wrap:wrap;gap:16px;margin:16px 0 10px}} .metric{{min-width:92px}} .metric b{{display:block;font-size:22px;color:#fff}} .metric span{{font-size:12px;color:#aab8ca}}
.chart{{width:100%;height:112px;display:block;margin-top:6px}} .legend{{display:flex;gap:14px;color:#b6c9df;font-size:12px;margin-top:2px}} .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}} .ok{{color:#72e0ae}} .warn{{color:#ffc56d}} .empty{{height:112px;display:grid;place-items:center;color:#8799ae;border:1px dashed #2d425f;border-radius:8px;margin-top:12px;font-size:13px}}
.foot{{font-size:12px;color:#8fa4be;margin-top:22px}} @media(max-width:760px){{main{{padding:20px 14px}}header{{display:block}}.badges{{justify-content:start;margin-top:14px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<header><div><h1>LLMOps runtime dashboard</h1><p>Six panels sourced from <code>data/logs.jsonl</code></p></div><div class="badges"><span class="badge">Time range: last 60 minutes</span><span class="badge">Refresh: 30 seconds</span><span class="badge" id="records"></span></div></header>
<section class="grid">
<article class="panel"><h2>1. Latency percentiles and TTFT</h2><p>Unit: ms · SLO line: P95 ≤ 3,000 ms</p><div class="metrics" id="latency-metrics"></div><svg class="chart" id="latency-chart" aria-label="Latency chart"></svg><div class="legend"><span><i class="dot" style="background:#59b6ff"></i>Latency avg/min</span><span><i class="dot" style="background:#d38cff"></i>TTFT avg/min</span></div></article>
<article class="panel"><h2>2. Request traffic</h2><p>Unit: requests/min · Threshold: ≥ 1 request/min</p><div class="metrics" id="traffic-metrics"></div><svg class="chart" id="traffic-chart" aria-label="Traffic chart"></svg></article>
<article class="panel"><h2>3. Error rate and retrieval success</h2><p>Unit: % · Error threshold: ≤ 2%</p><div class="metrics" id="errors-metrics"></div><svg class="chart" id="errors-chart" aria-label="Error-rate chart"></svg><p id="error-breakdown"></p></article>
<article class="panel"><h2>4. Cost over time</h2><p>Unit: USD · Window guardrail: ≤ $2.50</p><div class="metrics" id="cost-metrics"></div><svg class="chart" id="cost-chart" aria-label="Cost chart"></svg></article>
<article class="panel"><h2>5. Input and output tokens</h2><p>Unit: tokens · Window guardrail: ≤ 50,000</p><div class="metrics" id="tokens-metrics"></div><svg class="chart" id="tokens-chart" aria-label="Token chart"></svg><div class="legend"><span><i class="dot" style="background:#48d5b0"></i>Input</span><span><i class="dot" style="background:#ffb86b"></i>Output</span></div></article>
<article class="panel"><h2>6. Quality proxy</h2><p>Unit: score (0–1) · SLO line: mean ≥ 0.75</p><div class="metrics" id="quality-metrics"></div><svg class="chart" id="quality-chart" aria-label="Quality chart"></svg></article>
</section><p class="foot">Aggregations follow <code>config/dashboard.yaml</code>. This dashboard refreshes every 30 seconds.</p>
</main><script>const D={data};
const n=(x,d=0)=>Number(x||0).toLocaleString(undefined,{{maximumFractionDigits:d,minimumFractionDigits:d}}); const metric=(label,value,unit='')=>`<div class="metric"><b>${{value}}</b><span>${{label}}${{unit?' · '+unit:''}}</span></div>`;
function lines(id, datasets, threshold, higherIsGood=false){{const svg=document.getElementById(id), w=600,h=112,p=6, all=datasets.flatMap(d=>d.points.map(x=>x.value)); if(!all.some(Boolean)){{svg.outerHTML='<div class="empty">No data in the selected 60-minute window</div>';return}} const max=Math.max(...all,threshold||0,1), min=h-2*p, scale=v=>min-(v/max)*(h-2*p), path=pts=>pts.map((x,i)=>`${{i?'L':'M'}}${{p+i*(w-2*p)/Math.max(pts.length-1,1)}} ${{scale(x.value)}}`).join(' '); let out=`<line x1="${{p}}" y1="${{min}}" x2="${{w-p}}" y2="${{min}}" stroke="#314762"/>`; if(threshold!==null){{const y=scale(threshold);out+=`<line x1="${{p}}" y1="${{y}}" x2="${{w-p}}" y2="${{y}}" stroke="#ffcc66" stroke-dasharray="4 4"/><text x="${{w-p}}" y="${{Math.max(10,y-4)}}" text-anchor="end" fill="#ffcc66" font-size="10">threshold</text>`}} datasets.forEach(d=>out+=`<path d="${{path(d.points)}}" fill="none" stroke="${{d.color}}" stroke-width="2"/>`); svg.setAttribute('viewBox',`0 0 ${{w}} ${{h}}`);svg.innerHTML=out;}}
document.getElementById('records').textContent=`${{D.records}} log records`; const L=D.latency,T=D.traffic,E=D.errors,C=D.cost,K=D.tokens,Q=D.quality;
document.getElementById('latency-metrics').innerHTML=metric('P50',n(L.p50,0),'ms')+metric('P95',n(L.p95,0),'ms')+metric('P99',n(L.p99,0),'ms')+metric('TTFT P95',n(L.ttft_p95,0),'ms'); lines('latency-chart',[{{points:L.series,color:'#59b6ff'}},{{points:L.ttft_series,color:'#d38cff'}}],L.threshold);
document.getElementById('traffic-metrics').innerHTML=metric('Requests',n(T.count,0))+metric('Rate',n(T.rate_per_minute,2),'req/min'); lines('traffic-chart',[{{points:T.series,color:'#48d5b0'}}],T.threshold);
document.getElementById('errors-metrics').innerHTML=metric('Error rate',n(E.error_rate_pct,2),'%')+metric('Retrieval success',n(E.retrieval_success_rate_pct,1),'%'); lines('errors-chart',[{{points:E.series,color:'#ff7b7b'}}],E.threshold); document.getElementById('error-breakdown').textContent='Breakdown: '+(Object.keys(E.breakdown).length?Object.entries(E.breakdown).map(([k,v])=>`${{k}} (${{v}})`).join(', '):'No request failures');
document.getElementById('cost-metrics').innerHTML=metric('Total cost','$'+n(C.total,4),'USD'); lines('cost-chart',[{{points:C.series,color:'#ffb86b'}}],C.threshold);
document.getElementById('tokens-metrics').innerHTML=metric('Input',n(K.input_total,0),'tokens')+metric('Output',n(K.output_total,0),'tokens'); lines('tokens-chart',[{{points:K.input_series,color:'#48d5b0'}},{{points:K.output_series,color:'#ffb86b'}}],K.threshold);
document.getElementById('quality-metrics').innerHTML=metric('Mean quality',n(Q.mean,3),'score'); lines('quality-chart',[{{points:Q.series,color:'#d38cff'}}],Q.threshold,true); setTimeout(()=>location.reload(),30000);</script></body></html>"""
