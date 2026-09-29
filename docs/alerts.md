# Alert và runbook

Mỗi alert dưới đây dựa trên triệu chứng người dùng hoặc SLO, không phụ thuộc tên implementation nội bộ.

## Alert 1: latency SLO breach

- **Severity:** warning
- **Duration:** 10 phút liên tục
- **Kênh thông báo:** Slack `#day13-llmops-alerts`
- **SLI/SLO liên quan:** P95 latency của `response_sent` phải không quá 3,000 ms.
- **Điều kiện:** `latency_p95_ms > 3000` trong 10 phút.
- **Ảnh hưởng tới người dùng:** người dùng thấy phản hồi chậm, dù request có thể vẫn thành công.
- **Ba bước kiểm tra đầu tiên:**
  1. Xem panel Latency để xác nhận P95/P99 và TTFT P95 cùng tăng trong cùng time range.
  2. Lọc `data/logs.jsonl` lấy `correlation_id` chậm và mở trace cùng ID trên Langfuse.
  3. So sánh thời gian child observation `retrieve-context` và `generate-answer` để khoanh vùng bước chậm.
- **Mitigation tạm thời:** giảm concurrency hoặc tắt traffic không thiết yếu; nếu retrieval là bottleneck, dùng fallback answer đã được phê duyệt.
- **Owner:** `llmops-oncall`

## Alert 2: elevated request failures

- **Severity:** critical
- **Duration:** 5 phút liên tục
- **Kênh thông báo:** Slack `#day13-llmops-alerts`
- **SLI/SLO liên quan:** error rate phải không quá 2%.
- **Điều kiện:** `error_rate_pct > 2` trong 5 phút.
- **Ảnh hưởng tới người dùng:** request thất bại hoặc không nhận được câu trả lời.
- **Ba bước kiểm tra đầu tiên:**
  1. Xem panel Errors để xác định error type và tỷ lệ lỗi.
  2. Tìm các log `request_failed`, ghi lại `correlation_id` và `error_type`.
  3. Mở trace cùng correlation ID để kiểm tra retrieval hay generation kết thúc lỗi.
- **Mitigation tạm thời:** tắt incident/fault injection nếu đang bật; giảm traffic vào feature lỗi và chuyển sang thông báo retry an toàn.
- **Owner:** `llmops-oncall`

## Alert 3: degraded retrieval success

- **Severity:** warning
- **Duration:** 10 phút liên tục
- **Kênh thông báo:** Slack `#day13-llmops-alerts`
- **SLI/SLO liên quan:** retrieval success rate phải ít nhất 90%.
- **Điều kiện:** `retrieval_success_rate_pct < 90` trong 10 phút.
- **Ảnh hưởng tới người dùng:** câu trả lời có thể thiếu context hoặc request thất bại trước khi tạo câu trả lời.
- **Ba bước kiểm tra đầu tiên:**
  1. Xem retrieval success rate và error breakdown trên panel Errors.
  2. Lọc log có `tool_name=retrieval` và `tool_success=false` để lấy correlation ID.
  3. Kiểm tra child observation `retrieve-context` của trace tương ứng và lỗi/span duration.
- **Mitigation tạm thời:** tắt route retrieval lỗi hoặc dùng fallback answer; không retry vô hạn khi upstream đang timeout.
- **Owner:** `llmops-oncall`
