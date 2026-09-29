# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Đình Khang
- **MSSV:** 2A202602584
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/ilkhangnd/K4-L3-DAY13-NguyenDinhKhang-2A202602584-Monitoring-LLMOps.git
- **Commit SHA cuối:** f241de83010e71f1795570a344223f621fd0b5a5 
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602584`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10a-production-v2.png`, `evidence/10b-trace-v2-production.png`, `evidence/10c-production-rollback-v1.png`, `evidence/10d-trace-v1-after-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | FAILED — 100/102 records thiếu required fields; 100/102 thiếu enrichment; 0 correlation IDs; PII leaks: 0; estimated 30/100 | PASSED — 0 records thiếu required fields/enrichment; 114 correlation IDs; 0 PII leaks; 100/100 | CP0 chưa có structured logging và enrichment; sau CP1 đã có correlation ID, context và PII scrubber. |
| `validate_dashboard.py` | PASSED — 6/6 panel hợp lệ | PASSED — 6/6 panel hợp lệ | Dashboard contract luôn hợp lệ; dashboard runtime đã có dữ liệu thực tế ở đủ sáu panel. |
| `pytest` | PASSED — 22 passed (1.79s) | PASSED — 26 passed | Bổ sung test cho CP1, child observations và dashboard runtime. |
| Số traces hợp lệ | Chưa xác nhận | 67 root traces trong evidence trace list | Vượt yêu cầu tối thiểu 10 traces trong project Langfuse cá nhân. |
| Số PII leak | 0 | 0 | PII scrubber che email, điện thoại Việt Nam, CCCD và số thẻ trước khi ghi log. |
| Latency P95 / TTFT P95 | Chưa đo | Runtime bình thường: P95 1,075 ms / TTFT P95 55 ms; CP3: P95 2,659 ms | CP3 cho thấy latency tăng do retrieval chậm, trong khi TTFT vẫn gần baseline. |
| Retrieval success rate | Chưa đo | 100.0% | Incident CP3 là chậm retrieval, không phải retrieval fail; `tool_success=true`. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware dùng `x-request-id` nếu client gửi; nếu không thì sinh `req-<8-hex>`. ID được bind vào log context, trả lại qua response header và truyền vào trace metadata.
- **Các metadata được ghi vào structured log:** `ts`, `level`, `event`, `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`, latency, TTFT, token, cost, quality và retrieval status.
- **Cách bảo đảm PII được scrub trước khi ghi:** PII scrubber chạy trước JSON/file renderer; che email, số điện thoại Việt Nam, CCCD và số thẻ.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100; không phát hiện PII leak.


## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Trace nằm trong project Langfuse `day13-k4-l3a-2A202602584`; trace list có trên 10 root traces do workload cá nhân tạo.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` có hai child observations là `retrieve-context` và `generate-answer`.
- **Cách nối trace với log:** Dùng trường `correlation_id` giống nhau trong structured log và trace metadata.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** v1 — `baseline`, `production`.
- **Version/label candidate:** v2 — `candidate`.
- **Trace ID của mỗi version:** v2 production: `b8d13ce5ffb2d97f3a85d3ee31bb1943`; v1 sau rollback: `3721c30ec63ff7d3da33336d74ffa7b7`.
- **Cách promote và rollback `production`:** Promote `production` sang v2, chạy workload tạo trace v2; sau đó gán lại `production` cho v1 và chạy workload tạo trace v1.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Latency/TTFT, traffic, error rate/retrieval success, cost, input-output tokens và quality proxy; time range 60 phút, có đơn vị và threshold/SLO line.
- **SLO và lý do chọn:** Latency P95 ≤ 3,000 ms; error rate ≤ 2%; retrieval success ≥ 90%; quality mean ≥ 0.75.
- **Cách tính error budget:** Availability target 99.5% tương ứng error budget 0.5%; trong 28 ngày là 201.6 phút downtime/error budget.
- **Ba alert và runbook tương ứng:** `latency_slo_breach`, `elevated_request_failures`, `degraded_retrieval_success`; mỗi alert có severity, owner, Slack channel và runbook trong `docs/alerts.md`.
- **Source, config và tests liên quan:** [middleware](../app/middleware.py), [logging config](../app/logging_config.py), [agent tracing](../app/agent.py), [SLO](../config/slo.yaml), [alert rules](../config/alert_rules.yaml), [runbook alerts](../docs/alerts.md), [tests](../tests/).

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`.
- **Khoảng thời gian điều tra:** 2026-09-29 16:39:52–16:39:54 ICT.
- **Triệu chứng từ metrics:** Dashboard ghi nhận latency P95 = 2,659 ms và P99 = 2,668 ms, tăng rõ rệt so với baseline; error rate vẫn 0%.
- **Log line và correlation ID liên quan:** `req-55487b8a`; event `response_sent` có `latency_ms=2668`, `ttft_ms=54`, `tool_success=true`.
- **Trace ID và span gây ảnh hưởng:** Trace `e1dd9e3ca5deb26aff3183c5f6c4d5b4`; `retrieve-context` mất 2.51s, trong khi `generate-answer` chỉ 158ms.
- **Root cause:** Độ trễ được inject vào bước retrieval.
- **Fix action:** Kiểm tra dependency/vector store, thêm timeout và retry có giới hạn cho retrieval.
- **Preventive measure:** Theo dõi retrieval latency riêng, alert theo P95 và dùng fallback/circuit breaker khi retrieval chậm.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Tạo correlation ID tại middleware để mọi event trong cùng request có định danh chung, giúp điều tra từ dashboard sang log rồi trace không bị đứt đoạn.
- **Một lỗi/blocker đã gặp:** Python 3.14 không tương thích dependency `pydantic-core` của lab.
- **Cách tìm nguyên nhân và xử lý:** Kiểm tra lỗi khi cài dependency, sau đó tạo virtual environment bằng Python 3.13 và ghi lại yêu cầu phiên bản trong hướng dẫn setup.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics phát hiện P95 tăng; log khoanh vùng request bằng `correlation_id`; trace cùng ID xác định span `retrieve-context` là phần chậm.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt labels cho phép chạy, promote và rollback an toàn; trace ghi token/cost để theo dõi chi phí; SLO và alerts biến chỉ số runtime thành hành động vận hành.
- **Điều quan trọng nhất đã học:** Quan sát đầy đủ Metrics → Logs → Traces làm giảm đáng kể thời gian xác định nguyên nhân incident.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Dashboard hiện đọc JSONL phù hợp lab cục bộ; production nên dùng log/metric backend tập trung, retention và alert delivery thực tế.

## 9. Checklist trước khi nộp

- [X] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [X] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
