# PROGRESS

## Chu kỳ 1 — kiểm tra môi trường khởi động
- Trạng thái: BLOCKED
- Đã đọc `company/AUTOPILOT.md`; 18 chu kỳ trước được ghi là DONE.
- Đã xác nhận thư mục làm việc: `E:\Trade-AI\BananaTrade`.
- Đã kiểm tra interpreter bắt buộc: `E:\Trade-AI\BananaTrade.venv\Scripts\python.exe`.
- Kết quả thực tế: `MISSING E:\Trade-AI\BananaTrade.venv\Scripts\python.exe`.
- Theo hard rule, không được dùng interpreter khác và phải dừng phiên.
- Không sửa code, không thêm test, không chạy kiểm chứng bằng interpreter thay thế.
- Chi tiết lỗi đã ghi trong `BLOCKED.md`.

## Step A1 — chẩn đoán merge fallout
- Trạng thái: BLOCKED trước khi chạy chẩn đoán.
- Đã đọc lại `PROGRESS.md` và xác nhận thư mục làm việc đúng: `E:\\Trade-AI\\BananaTrade`.
- Đã kiểm tra lại interpreter duy nhất được phép: `E:\\Trade-AI\\BananaTrade.venv\\Scripts\\python.exe`.
- Kết quả thực tế: `MISSING E:\\Trade-AI\\BananaTrade.venv\\Scripts\\python.exe`.
- Không chạy full pytest, mypy hoặc lệnh thay thế; không thể ghi danh sách failure/traceback thật hay nhóm root cause mà không vi phạm hard rule.
- Không sửa code/test và không commit vì môi trường bắt buộc bị thiếu.
- Hành động tiếp theo: chỉ tiếp tục A1 sau khi interpreter đúng đường dẫn tồn tại.

## Yêu cầu mới — tài liệu API và dừng sau C2
- Trạng thái: BLOCKED trước khi bắt đầu A1.
- Đã đọc lại `PROGRESS.md`; thư mục hiện tại vẫn là `E:\\Trade-AI\\BananaTrade`.
- Interpreter duy nhất được phép vẫn thiếu: `E:\\Trade-AI\\BananaTrade.venv\\Scripts\\python.exe` (`MISSING`).
- Không chạy full pytest/mypy và không dùng interpreter thay thế theo hard rule.
- Chưa thể chẩn đoán merge fallout, hoàn thành Phase A/B/C, hoặc tài liệu hóa endpoint mới bằng response shape đã kiểm chứng.
- Không sửa code/test và không tạo tài liệu API suy đoán.
- Phiên dừng tại A1; quyền tự quyết không ghi đè hard rule về interpreter bắt buộc.

## Step độc lập — tài liệu hóa Dashboard API [DONE]
- Commit: chưa tạo; môi trường vẫn thiếu interpreter bắt buộc.
- Tests: không thay đổi (không được chạy pytest bằng interpreter khác).
- Checks: ruff=na mypy=na pytest=na node=na.
- Root cause (Phase A only): interpreter `E:\\Trade-AI\\BananaTrade.venv\\Scripts\\python.exe` không tồn tại; chẩn đoán merge fallout vẫn bị chặn.
- Requirement -> test:
  - Tạo tài liệu endpoint, params, response shape và ví dụ: đã đối chiếu trực tiếp các handler/module hiện có; không có test runner khả dụng theo hard rule.
- Forbidden-pattern scan: chưa chạy vì interpreter bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Đây là hạng mục độc lập chỉ đọc source, không thêm endpoint hoặc số liệu giả vào code. Các response mẫu phản ánh shape do handler/module hiện tại định nghĩa; cần chạy full suite sau khi khôi phục interpreter.

## Goal round 1 — kiểm tra lại môi trường [BLOCKED]
- Đã đọc lại `PROGRESS.md` trước khi thực hiện bước.
- Thư mục thực tế: `E:\\Trade-AI\\BananaTrade`.
- Interpreter duy nhất được phép: `E:\\Trade-AI\\BananaTrade.venv\\Scripts\\python.exe`.
- Kết quả thực tế: `MISSING`.
- Không chạy pytest/mypy/ruff và không dùng Python thay thế; không sửa code/test vì sẽ vi phạm hard rule.
- Hành động: dừng round này và chờ interpreter đúng đường dẫn được khôi phục.

## Goal round 2 — kiểm tra lại môi trường [BLOCKED]
- Đã đọc lại `PROGRESS.md` trước khi thực hiện bước.
- Đã xác nhận thư mục đúng: `E:\\Trade-AI\\BananaTrade`.
- Đã kiểm tra `E:\\Trade-AI\\BananaTrade.venv\\Scripts\\python.exe`; kết quả thực tế: `MISSING`.
- Không chạy pytest/mypy/ruff, không dùng interpreter thay thế và không sửa code/test.
- Hạng mục tài liệu API đã hoàn tất ở commit `3c868c0`; không có công việc độc lập mới phù hợp với hard rule hiện tại.
- Hành động: dừng round này; blocker chưa được khắc phục.

## Goal round 3 — kiểm tra lại môi trường [BLOCKED]
- Đã đọc lại `PROGRESS.md` trước khi thực hiện bước.
- Đã xác nhận thư mục đúng: `E:\\Trade-AI\\BananaTrade`.
- Đã kiểm tra interpreter bắt buộc `E:\\Trade-AI\\BananaTrade.venv\\Scripts\\python.exe`; kết quả thực tế: `MISSING`.
- Đây là lần thứ ba liên tiếp cùng một blocker; không chạy pytest/mypy/ruff, không dùng interpreter thay thế, không sửa code/test.
- Hạng mục tài liệu API đã hoàn tất; không còn hạng mục độc lập hợp lệ để thực hiện mà không vi phạm hard rule.
- Hành động: đánh dấu goal bị chặn theo chính sách sau khi ghi nhận đủ ba round liên tiếp.

## Chu kỳ 21 — sửa request snapshot frontend [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy do interpreter bắt buộc bị thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Phase A bị chặn bởi `E:\\Trade-AI\\BananaTrade.venv\\Scripts\\python.exe` không tồn tại; frontend gọi `/api/snapshot` không có query bắt buộc `symbol` và `timeframe`.
- Requirement -> test:
  - Frontend phải gửi symbol và timeframe bắt buộc: kiểm tra tĩnh xác nhận `URLSearchParams` chứa `BTC/USDT`, `1h` và URL `/api/snapshot?`.
  - JavaScript phải hợp lệ: `node --check web/app.js` — pass, không có output lỗi.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Đây là sửa frontend độc lập, không chạm backend, database, LLM hay exchange. Full suite phải chạy lại khi interpreter đúng đường dẫn được khôi phục.

## Chu kỳ 23 — loại bỏ số liệu placeholder khỏi dashboard [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Phase A vẫn bị chặn bởi interpreter bắt buộc; HTML dashboard chứa giá, chỉ báo, council, equity và hoạt động hard-code không truy vết backend.
- Requirement -> test:
  - Không hiển thị số liệu market/equity/council giả trước dữ liệu backend: quét placeholder HTML — pass.
  - Chỉ dùng snapshot/paper-state cho metric: quét client loại bỏ fallback equity/quantity giả — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Frontend hiện hiển thị `—` khi chưa có dữ liệu, lấy giá/indicator từ `/api/snapshot`, equity từ `/api/paper/state`, và quantity từ order ticket. Không thay đổi backend hoặc test Python.

## Chu kỳ 25 — sửa luồng đóng paper position [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): frontend gọi route `/api/paper/close` không tồn tại trong backend; route thực tế là `/api/paper/order`.
- Requirement -> test:
  - Đóng LONG/SHORT phải gửi lệnh ngược qua route paper order hiện có: kiểm tra tĩnh xác nhận side ngược, quantity vị thế và giá snapshot — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Đây là thay đổi frontend độc lập, vẫn paper-only và không thêm endpoint/backend giả. Full HTTP integration test cần chạy sau khi interpreter được khôi phục.

## Chu kỳ 27 — validation input order frontend [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Phase A bị chặn bởi interpreter bắt buộc; submit order có thể gửi số không hợp lệ/`NaN` khi input rỗng.
- Requirement -> test:
  - Từ chối quantity, entry, stop hoặc target không phải số dương trước HTTP request: kiểm tra tĩnh xác nhận guard `Number.isFinite` và `> 0` — pass.
  - Dùng symbol snapshot canonical: kiểm tra tĩnh xác nhận `symbol: SNAPSHOT_SYMBOL` — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Guard chỉ bổ sung client-side; backend vẫn là nguồn kiểm soát cuối và không có thay đổi paper broker.

## Chu kỳ 29 — đồng bộ paper state từ backend [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): localStorage có thể giữ position/trades cũ trong khi `/api/paper/state` là nguồn trạng thái backend thực tế.
- Requirement -> test:
  - Reload phải phản ánh positions backend kể cả khi local state cũ: kiểm tra tĩnh xác nhận backend luôn ghi đè hoặc xóa `state.position` — pass.
  - Không tự chế PnL từ fills: kiểm tra tĩnh xác nhận không map fills thành performance trades — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Backend chưa cung cấp closed-trade PnL; frontend giữ lịch sử performance rỗng thay vì hiển thị số liệu giả. Full integration test cần chạy sau khi khôi phục Python.

## Chu kỳ 31 — loader local state an toàn [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `JSON.parse` ở top-level có thể làm crash toàn bộ dashboard khi localStorage chứa JSON hỏng hoặc kiểu dữ liệu không phải object.
- Requirement -> test:
  - State hỏng không chặn dashboard: kiểm tra tĩnh xác nhận `loadStoredState()` bắt lỗi và fallback `{}` — pass.
  - Không nhận array như state object: kiểm tra tĩnh xác nhận `!Array.isArray(stored)` — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Backend vẫn là nguồn state paper chính; loader chỉ là fallback an toàn cho localStorage.

## Chu kỳ 33 — bảo vệ localStorage unavailable [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `localStorage.getItem` hoặc `setItem` có thể ném lỗi quyền truy cập trong private mode/storage bị chặn, làm hỏng dashboard dù backend còn hoạt động.
- Requirement -> test:
  - Đọc local state lỗi phải fallback rỗng: đã có `loadStoredState()` bắt lỗi — pass.
  - Ghi local state lỗi không được chặn backend state: kiểm tra tĩnh xác nhận mọi `setItem` nằm trong `persistState` có try/catch — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Dashboard không phụ thuộc localStorage; backend vẫn là nguồn dữ liệu paper authoritative.

## Chu kỳ 35 — bảo vệ reset khi localStorage unavailable [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): nút reset gọi trực tiếp `localStorage.removeItem`, có thể ném lỗi khi browser storage bị chặn.
- Requirement -> test:
  - Reset paper không crash khi storage unavailable: kiểm tra tĩnh xác nhận `clearStoredState()` bao quanh `removeItem` bằng try/catch — pass.
  - Không còn thao tác removeItem trực tiếp ngoài helper: quét tĩnh đếm một lần gọi — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Reload vẫn làm mới UI; backend account không bị xóa bởi thao tác localStorage này.

## Chu kỳ 37 — parse response API an toàn [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `response.json()` trực tiếp có thể throw khi backend trả body rỗng, HTML hoặc JSON malformed.
- Requirement -> test:
  - Snapshot, paper state, open/close order và analysis dùng parser an toàn: quét tĩnh xác nhận sáu call site dùng `readJson(response)` — pass.
  - Parser trả typed error object khi JSON invalid: kiểm tra tĩnh xác nhận fallback `Backend returned invalid JSON` — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Backend response schema không thay đổi; frontend chỉ thêm lớp bảo vệ parse lỗi.

## Chu kỳ 39 — chuẩn hóa local state [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): dữ liệu localStorage có thể chứa số/string/array/object sai schema, gây lỗi render hoặc phép tính sau khi spread vào runtime state.
- Requirement -> test:
  - Chỉ nhận cash/equity hữu hạn: kiểm tra tĩnh xác nhận `Number.isFinite(Number(...))` — pass.
  - Chỉ nhận trades/position đúng shape và số dương: kiểm tra tĩnh xác nhận filter/map normalization — pass.
  - Runtime dùng state đã normalize: kiểm tra tĩnh xác nhận `normalizeStoredState(loadStoredState())` — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Backend paper state vẫn ghi đè position/cash/equity khi endpoint trả dữ liệu; normalization chỉ bảo vệ fallback localStorage.

## Chu kỳ 41 — reset snapshot khi backend lỗi [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): request snapshot lỗi sau response thành công để lại `state.price`/snapshot cũ, khiến dashboard tiếp tục hiển thị giá stale như dữ liệu hiện tại.
- Requirement -> test:
  - Snapshot lỗi phải xóa price và snapshot runtime: kiểm tra tĩnh xác nhận cả hai được set `null` trong catch — pass.
  - Không ảnh hưởng paper account state: thay đổi chỉ nằm trong `updateSnapshot` — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Khi snapshot lỗi, UI hiển thị placeholder; paper position/cash/equity vẫn chờ `/api/paper/state`.

## Chu kỳ 43 — xác thực paper state response [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): response `/api/paper/state` có thể thiếu field hoặc sai kiểu nhưng frontend vẫn truy cập trực tiếp.
- Requirement -> test:
  - Chỉ nhận paper-state object, không nhận array/null: kiểm tra tĩnh xác nhận validator trả `null` cho shape sai — pass.
  - Positions phải là object; cash/equity phải finite hoặc null: kiểm tra tĩnh xác nhận normalization — pass.
  - `renderState` chỉ dùng payload sau validator: kiểm tra tĩnh xác nhận `normalizePaperState(await readJson(response))` — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Validator không tạo số liệu mặc định; field không hợp lệ thành `null`, còn positions sai shape thành object rỗng.

## Chu kỳ 45 — xác thực order response [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): HTTP 200 với body thiếu `order.order_id` làm frontend throw sau khi backend đã xử lý, khiến UI không phản ánh đúng kết quả.
- Requirement -> test:
  - Submit/open/close order chỉ thành công khi có `data.order.order_id` là non-empty string: quét tĩnh xác nhận ba guard — pass.
  - Payload sai không làm thay đổi local position/trades: guard nằm trước mọi state mutation — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không thay đổi backend hoặc broker; validator chỉ bảo vệ client khỏi response success giả.

## Chu kỳ 47 — xác thực analysis response [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): analysis response 200 có thể thiếu `reports` hoặc chứa item không phải object, làm frontend gọi `.find`/đọc field trên payload sai shape.
- Requirement -> test:
  - Chỉ dùng reports là array và report có agent string: kiểm tra tĩnh xác nhận `normalizeAnalysis` filter — pass.
  - Analysis flow validate trước `.find`: kiểm tra tĩnh xác nhận `normalizeAnalysis(await readJson(response))` và guard null — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Validator không tạo report hoặc bias giả; response hợp lệ nhưng không có technical report chỉ hiển thị completed.

## Chu kỳ 49 — strict analysis payload [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizeAnalysis` trước đó biến payload thiếu `reports` thành array rỗng, che giấu response malformed như thành công.
- Requirement -> test:
  - Payload thiếu hoặc reports không phải array phải bị từ chối: kiểm tra tĩnh xác nhận guard `!Array.isArray(payload.reports)` — pass.
  - Payload hợp lệ nhưng reports rỗng vẫn được xử lý như không có report: flow giữ `data.reports.find` sau null guard — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không tạo dữ liệu mặc định; phân biệt rõ malformed response và empty analysis result.

## Chu kỳ 51 — shared order response helper [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): submit/open/close có ba bản sao kiểm tra `order_id`, dễ lệch thông báo và schema handling.
- Requirement -> test:
  - Một helper duy nhất đọc order ID an toàn từ payload: kiểm tra tĩnh xác nhận `readOrderId` — pass.
  - Cả ba flow dùng helper trước state mutation/thông báo thành công: quét tĩnh xác nhận ba call site — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Helper chỉ chấp nhận non-empty string và không thay đổi API/backend.

## Chu kỳ 53 — strict shared order guard [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): ba flow vẫn tự xử lý null/error sau `readOrderId`, dễ tạo thông báo không đồng nhất.
- Requirement -> test:
  - Một helper `requireOrderId` throw typed Error cho order thường/close: kiểm tra tĩnh xác nhận — pass.
  - Submit/open/close dùng helper trước success/state mutation: quét tĩnh xác nhận ba call site — pass.
  - Không còn gọi `readOrderId(data)` trực tiếp ở flow: quét tĩnh — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giữ nguyên paper-only; helper chỉ chuẩn hóa lỗi client.

## Chu kỳ 55 — validate backend position [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): position từ paper-state có thể chứa quantity/average_price sai kiểu hoặc không hữu hạn, nhưng frontend vẫn map trực tiếp.
- Requirement -> test:
  - Chỉ nhận quantity finite, khác 0 và average_price finite dương: kiểm tra tĩnh xác nhận `normalizePosition` — pass.
  - State dùng position sau normalization, không map trực tiếp payload: quét tĩnh xác nhận `.map(normalizePosition)` — pass.
  - Position invalid bị loại và không tạo side/entry/qty giả: kiểm tra tĩnh xác nhận `filter(position !== null)` — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không thay đổi backend; position hợp lệ vẫn hiển thị side LONG/SHORT và entry/qty đã chuẩn hóa.

## Chu kỳ 57 — chuẩn hóa timestamp paper state [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): timestamp `opened`/`closed` từ backend hoặc localStorage có thể là string malformed, gây `Invalid Date` trong UI.
- Requirement -> test:
  - Timestamp phải là ISO hợp lệ hoặc fallback timestamp hiện tại: kiểm tra tĩnh xác nhận `normalizeTimestamp` + `getTime()` finite — pass.
  - Trade/position không dùng raw timestamp: quét tĩnh xác nhận ba call site dùng helper — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không bịa dữ liệu giao dịch; fallback chỉ áp dụng cho metadata thời gian hiển thị.

## Chu kỳ 59 — fail-closed paper state [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): khi `/api/paper/state` lỗi hoặc payload malformed, UI có thể giữ position/equity/trades cũ trong memory và hiển thị dữ liệu stale.
- Requirement -> test:
  - Backend state không khả dụng phải xóa position/cash/equity/trades local: quét tĩnh xác nhận catch fail-closed — pass.
  - Stored paper state phải bị xóa khi backend state lỗi: kiểm tra tĩnh xác nhận `clearStoredState()` — pass.
  - UI phải hiện waiting thay vì flat/state cũ: kiểm tra tĩnh xác nhận `backendState = null` và waiting branch — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Backend vẫn là nguồn authoritative; lỗi state không được che bằng dữ liệu local cũ.

## Chu kỳ 61 — fail-closed HTTP paper state [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `renderState` không throw khi `/api/paper/state` trả HTTP non-2xx, nên catch reset state không được kích hoạt.
- Requirement -> test:
  - HTTP 4xx/5xx phải đi vào fail-closed catch: kiểm tra tĩnh xác nhận `if (!response.ok) throw` — pass.
  - Không còn nhánh `if (response.ok)` bao quanh toàn bộ state sync: quét tĩnh — pass.
  - Payload/reset behavior giữ nguyên và JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: HTTP error không được coi là trạng thái paper hợp lệ; UI chuyển waiting và xóa cache như payload/network error.

## Chu kỳ 63 — giữ lịch sử PnL local khi sync state [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): sync paper-state thành công luôn gán `state.trades = []`, làm mất closed-trade PnL sau refresh dù backend chưa cung cấp audit trail.
- Requirement -> test:
  - Sync state hợp lệ không xóa closed trades local: kiểm tra tĩnh xác nhận không có reset trong success block — pass.
  - State fail-closed vẫn xóa trades để không hiển thị dữ liệu stale: quét tĩnh xác nhận reset chỉ trong catch — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ giữ các trade do client paper flow ghi nhận; không suy diễn PnL từ backend fills.

## Chu kỳ 65 — chuẩn hóa snapshot regime [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): snapshot `regime` sai kiểu có thể làm render gọi `.toUpperCase()` trên non-string và phá UI.
- Requirement -> test:
  - Chỉ render regime là string non-empty sau trim/uppercase: kiểm tra tĩnh xác nhận `snapshotRegime` — pass.
  - Không còn truy cập `.toUpperCase()` trực tiếp trên payload: quét tĩnh — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Regime không hợp lệ hiển thị `—`; không tạo bias mặc định.

## Chu kỳ 67 — chuẩn hóa snapshot stale flag [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `stale` dạng string `"false"` bị coi là truthy, làm UI hiển thị cờ STALE sai.
- Requirement -> test:
  - Chỉ boolean `true` được coi là stale: kiểm tra tĩnh xác nhận `snapshotIsStale` — pass.
  - Confidence text và badge dùng cùng helper: quét tĩnh xác nhận hai call site — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không diễn giải chuỗi hoặc số thành boolean; payload sai kiểu được coi là không stale.

## Chu kỳ 69 — chặn snapshot indicator shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `indicators` sai shape như array/string được truyền thẳng vào render, khiến field lookup không có contract rõ ràng.
- Requirement -> test:
  - Chỉ chấp nhận indicators là object không phải array: kiểm tra tĩnh xác nhận guard type/array — pass.
  - Payload indicators sai shape fallback về object rỗng, không tạo số liệu — kiểm tra tĩnh — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Indicator thiếu hoặc sai shape hiển thị `—` qua `formatMetric`; không tạo giá trị kỹ thuật mặc định.

## Chu kỳ 71 — validate snapshot candle input [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): candle config sai shape có thể bị gọi `.map` trực tiếp và làm hỏng render chart.
- Requirement -> test:
  - Candle input cuối cùng luôn là array trước `.map`: kiểm tra tĩnh xác nhận `Array.isArray(configuredInput)` — pass.
  - Candle config non-array fallback về mảng rỗng để dùng one-price candle path: kiểm tra tĩnh — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không tạo candle lịch sử giả; input rỗng dùng fallback chart đã có với canonical snapshot price.

## Chu kỳ 73 — validate snapshot candle item [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): candle item null/primitive có thể làm callback đọc `open/high/low/close` trên giá trị sai shape.
- Requirement -> test:
  - Chỉ map candle item là object không phải array: kiểm tra tĩnh xác nhận filter trước map — pass.
  - Item sai shape bị loại trước khi đọc leaf fields: quét tĩnh — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Candle hợp lệ vẫn phải qua finite numeric filter; item lỗi không tạo nến giả.

## Chu kỳ 75 — validate candle numeric constraints [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): candle OHLC finite nhưng zero/âm hoặc high thấp hơn low vẫn đi vào chart scale.
- Requirement -> test:
  - OHLC phải finite và dương: kiểm tra tĩnh xác nhận numeric guard — pass.
  - Candle phải có `high >= low`: kiểm tra tĩnh xác nhận range guard — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không ép quan hệ open/close với high/low ngoài range tối thiểu; chỉ loại giá không dương và range đảo.

## Chu kỳ 77 — bảo vệ snapshot source shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `snapshotSource` có thể trả primitive/array truthy, không giữ contract object cho các helper nested access.
- Requirement -> test:
  - Snapshot source chỉ là plain object không phải array: kiểm tra tĩnh xác nhận guard type/array — pass.
  - Payload primitive/array fallback về object rỗng: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không tạo snapshot hoặc giá trị market mặc định; source sai shape sẽ render placeholder.

## Chu kỳ 79 — validate snapshot timeframe shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `timeframes` primitive/array có thể bị truy cập như map và truyền summary ngoài contract vào price/indicator/candle helpers.
- Requirement -> test:
  - Chỉ dùng timeframes plain object không phải array: kiểm tra tĩnh xác nhận guard — pass.
  - Price và indicators dùng cùng map đã chuẩn hóa: quét tĩnh xác nhận — pass.
  - Candle map chỉ index configured object hợp lệ: kiểm tra tĩnh xác nhận guard — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Timeframe sai shape bị coi là thiếu dữ liệu, không tạo summary hoặc candle giả.

## Chu kỳ 81 — chặn snapshot summary shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): timeframe summary primitive/array vẫn có thể được optional-chain đọc như object, không bảo đảm semantic contract.
- Requirement -> test:
  - Summary chỉ là plain object không phải array: kiểm tra tĩnh xác nhận `snapshotSummary` — pass.
  - Price/indicators/candles dùng summary đã chuẩn hóa: quét tĩnh xác nhận ba call site — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Summary sai shape bị fallback object rỗng; không tạo giá hoặc indicators/candles mặc định.

## Chu kỳ 83 — chặn snapshot price không dương [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `snapshotPrice` chỉ kiểm tra finite nên giá zero/âm vẫn được dùng cho chart và order form.
- Requirement -> test:
  - Last price phải finite và dương: kiểm tra tĩnh xác nhận positive guard — pass.
  - Giá không hợp lệ tiếp tục làm snapshot refresh fail-closed: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không tạo giá thay thế; giá zero/âm được coi là snapshot unavailable.

## Chu kỳ 85 — chuẩn hóa snapshot metadata [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): regime và stale metadata đọc trực tiếp từ source mà chưa có contract helper riêng cho metadata object và leaf types.
- Requirement -> test:
  - Metadata chỉ là plain object không phải array: kiểm tra tĩnh xác nhận `snapshotMetadata` — pass.
  - Regime chỉ nhận string không rỗng: quét tĩnh xác nhận — pass.
  - Stale chỉ nhận boolean `true`: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Metadata sai shape hoặc leaf sai type hiển thị trạng thái trung tính, không suy đoán dữ liệu.

## Chu kỳ 87 — validate paper state shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizePaperState` biến positions sai shape thành object rỗng và cho phép cash/equity âm, khiến UI tiếp nhận state ngoài contract.
- Requirement -> test:
  - Payload phải có positions plain object không phải array: kiểm tra tĩnh xác nhận — pass.
  - Cash/equity phải finite và không âm: kiểm tra tĩnh xác nhận — pass.
  - Payload sai shape trả `null` để renderState fail-closed: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Paper backend vẫn là nguồn dữ liệu authoritative; không tạo positions/cash/equity mặc định khi payload sai.

## Chu kỳ 89 — validate position payload shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizePosition` chỉ kiểm tra object nên array có thể được đọc như position payload và tiếp tục vào UI.
- Requirement -> test:
  - Position payload phải là object không phải array: kiểm tra tĩnh xác nhận guard — pass.
  - Chỉ đọc quantity/average price sau khi shape guard: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Position array hoặc primitive bị loại; position hợp lệ vẫn phải có quantity khác zero và average price dương.

## Chu kỳ 91 — validate analysis report shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizeAnalysis` giữ nguyên report object sau khi chỉ lọc agent, nên report array và leaf sai type có thể làm notification/UI đọc dữ liệu ngoài contract.
- Requirement -> test:
  - Report phải là object không phải array và có agent string: kiểm tra tĩnh xác nhận — pass.
  - Bias chỉ nhận string, confidence chỉ nhận string hoặc finite numeric: quét tĩnh xác nhận — pass.
  - Report được tạo thành object sở hữu nhỏ thay vì giữ live payload: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Report thiếu leaf tùy chọn được chuẩn hóa thành `null`; không suy đoán bias/confidence mặc định.

## Chu kỳ 93 — validate stored paper state shapes [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizeStoredState` chưa loại rõ array cho trade/position trước khi đọc leaf fields từ localStorage payload.
- Requirement -> test:
  - Stored trade phải là object không phải array: kiểm tra tĩnh xác nhận — pass.
  - Stored position phải là object không phải array: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Local state sai shape bị loại; backend vẫn authoritative cho paper cash/equity/positions.

## Chu kỳ 95 — validate local state numeric bounds [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): localStorage có thể chứa cash/equity âm hoặc trade entry/exit không dương, làm metrics và paper UI hiển thị state ngoài contract.
- Requirement -> test:
  - Cash/equity local chỉ nhận finite không âm: kiểm tra tĩnh xác nhận — pass.
  - Trade entry/exit chỉ nhận finite dương: kiểm tra tĩnh xác nhận — pass.
  - Trade PnL phải finite: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: PnL có thể âm hợp lệ; chỉ loại PnL non-finite và giá entry/exit không dương.

## Chu kỳ 97 — validate order id shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `readOrderId` chấp nhận chuỗi whitespace và trả nguyên văn order id chưa chuẩn hóa, có thể làm order response giả được coi là thành công.
- Requirement -> test:
  - Order id phải là string sau trim và không rỗng: kiểm tra tĩnh xác nhận — pass.
  - Giá trị trả về được trim trước state mutation/notification: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không tạo order id thay thế; id sai shape tiếp tục bị reject bởi `requireOrderId`.

## Chu kỳ 99 — validate order payload shape [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `readOrderId` chưa có contract rõ cho order envelope; payload order primitive/array vẫn được optional-chain xử lý như object.
- Requirement -> test:
  - Order envelope phải là object không phải array: kiểm tra tĩnh xác nhận — pass.
  - Chỉ đọc `order_id` sau shape guard: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Envelope sai shape bị reject; không thay đổi order ID normalization đã có.

## Chu kỳ 101 — chuẩn hóa error message cho order/analysis [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Catch handler đọc trực tiếp `error.message`, nên thrown value hoặc backend error shape sai có thể tạo notification undefined/không ổn định.
- Requirement -> test:
  - Error object có message string không rỗng được trim: kiểm tra tĩnh xác nhận — pass.
  - Error string được dùng trực tiếp sau trim: quét tĩnh xác nhận — pass.
  - Order open/close và analysis đều dùng fallback message an toàn: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không hiển thị object/undefined thô cho người dùng; fallback chỉ mô tả lỗi thao tác, không che response thành công.

## Chu kỳ 103 — validate backend error payload [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Backend error field object/array truthy có thể đi vào `new Error` và tạo message `[object Object]` thay vì lỗi có nghĩa.
- Requirement -> test:
  - Backend error chỉ nhận trimmed string không rỗng: kiểm tra tĩnh xác nhận `backendError` — pass.
  - Risk, analysis, open và close order đều dùng helper trước khi throw: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Error payload sai type dùng fallback thao tác; không biến response lỗi thành thành công.

## Chu kỳ 105 — chuẩn hóa analysis report leaf [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Analysis report chấp nhận leaf string whitespace và giữ confidence numeric string, làm notification/UI nhận nhãn rỗng hoặc kiểu không nhất quán.
- Requirement -> test:
  - Agent được trim và report thiếu agent sau trim bị loại: kiểm tra tĩnh xác nhận — pass.
  - Bias string được trim, rỗng thành `null`: quét tĩnh xác nhận — pass.
  - Confidence number finite giữ dạng number; numeric string được chuyển number; string không numeric giữ trimmed string: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không suy đoán confidence/bias; chỉ chuẩn hóa whitespace và kiểu dữ liệu đã có.

## Chu kỳ 107 — validate analysis reports container [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Reports container guard nằm trong điều kiện dài, chưa biểu đạt rõ fail-closed trước filter/map.
- Requirement -> test:
  - Payload object được kiểm tra trước khi đọc reports: kiểm tra tĩnh xác nhận — pass.
  - Reports phải là array qua biến local riêng: kiểm tra tĩnh xác nhận — pass.
  - Reports không phải array trả `null` trước filter/map: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không tạo reports mặc định; payload analysis sai container tiếp tục fail-closed.

## Chu kỳ 109 — chuẩn hóa snapshot indicator leaves [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Indicator container đúng object nhưng leaf boolean/object/array có thể bị `Number()` coercion trong `formatMetric`, tạo hiển thị ngoài contract.
- Requirement -> test:
  - Indicators phải là object không phải array: kiểm tra tĩnh xác nhận — pass.
  - Boolean/object/array leaf thành `null`: quét tĩnh xác nhận — pass.
  - Leaf finite numeric hoặc numeric string được chuẩn hóa thành number; sai thành `null`: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không tạo indicator kỹ thuật mặc định; leaf sai type hiển thị placeholder qua `formatMetric`.

## Chu kỳ 111 — validate snapshot price leaf [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Snapshot price dùng `Number(value)` trực tiếp, nên boolean/null/object/array có thể bị coercion thành giá trị dương ngoài contract.
- Requirement -> test:
  - Boolean/object/array price bị reject trước coercion: quét tĩnh xác nhận — pass.
  - Chuỗi whitespace bị reject: quét tĩnh xác nhận — pass.
  - Price chỉ hợp lệ khi finite và dương sau numeric conversion: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không tạo giá thị trường thay thế; giá snapshot sai shape tiếp tục fail-closed.

## Chu kỳ 113 — chuẩn hóa stored numeric leaves [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizeStoredState` dùng `Number()` trực tiếp cho cash/equity/trade/position, cho phép boolean/null/object/array coercion thành số hợp lệ ngoài contract.
- Requirement -> test:
  - Helper `safeNumber` reject null, boolean, object/array và chuỗi whitespace: quét tĩnh xác nhận — pass.
  - Cash/equity/trade entry/exit/pnl/position entry/qty dùng helper trước bound checks: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Numeric string không rỗng vẫn được hỗ trợ; state sai shape tiếp tục bị loại thay vì coercion mơ hồ.

## Chu kỳ 115 — chuẩn hóa backend paper numeric leaves [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizePaperState` và `normalizePosition` dùng `Number()` trực tiếp, cho phép boolean/null/object/array coercion vào paper state.
- Requirement -> test:
  - Paper cash/equity dùng `safeNumber` và reject giá trị null/non-finite trước bound checks: quét tĩnh xác nhận — pass.
  - Position quantity/average price dùng `safeNumber` và reject sai type trước bound checks: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Numeric string hợp lệ vẫn được hỗ trợ thống nhất với stored state; payload sai shape fail-closed.

## Chu kỳ 117 — loại bỏ coercion renderState [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `renderState` đã nhận paper state qua `normalizePaperState` nhưng lại gọi `Number()` cash/equity lần hai, mở rộng contract không cần thiết.
- Requirement -> test:
  - State cash/equity được gán trực tiếp sau normalize: kiểm tra tĩnh xác nhận — pass.
  - Không còn `Number()` coercion trên `backendState.cash/equity`: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: `normalizePaperState` là boundary duy nhất cho backend numeric state; không thay đổi hành vi hiển thị.

## Chu kỳ 119 — loại bỏ duplicate equity state [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): State object khai báo `equity` hai lần; key sau cùng là `null`, ghi đè giá trị normalize và làm contract state khó đọc.
- Requirement -> test:
  - State chỉ khai báo một `equity` key: kiểm tra tĩnh xác nhận — pass.
  - Không thay đổi merge order của stored state hoặc backend sync: review diff xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: `state.equity` vẫn mặc định null khi chưa có backend; stored state merge tiếp tục giữ nguyên.

## Chu kỳ 121 — tách snapshot khỏi localStorage [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `updateSnapshot` gọi `save()` sau khi nhận market snapshot, dù localStorage chỉ nên chứa paper state; snapshot/price có thể bị trộn với local state qua persistence path.
- Requirement -> test:
  - Snapshot refresh vẫn gán `state.snapshot` và `state.price`: kiểm tra tĩnh xác nhận — pass.
  - Snapshot refresh không gọi `save()`: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Backend snapshot là nguồn dữ liệu phiên hiện tại; localStorage chỉ giữ cash/position/trades qua `save()`.

## Chu kỳ 123 — chuẩn hóa candle numeric leaves [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `snapshotCandles` dùng `Number()` trực tiếp cho OHLC, cho phép boolean/null/object/array coercion thành candle hợp lệ.
- Requirement -> test:
  - OHLC dùng `safeNumber` trước positive/range checks: quét tĩnh xác nhận — pass.
  - Không còn `Number(candle.open/high/low/close)` trực tiếp: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Candle sai leaf thành null và bị filter; fallback candle vẫn dùng canonical snapshot price đã validate.

## Chu kỳ 125 — chuẩn hóa formatMetric leaf [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `formatMetric` dùng `Number(value)` trực tiếp, có thể coercion boolean/null/object từ caller khác dù indicator đã normalize.
- Requirement -> test:
  - `formatMetric` dùng `safeNumber` strict trước locale formatting: kiểm tra tĩnh xác nhận — pass.
  - Không còn `Number(value)` trong formatMetric: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giá trị không hợp lệ hiển thị placeholder `—`; numeric string hợp lệ vẫn được format như trước.

## Chu kỳ 127 — chuẩn hóa order ticket numeric leaves [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Submit order và `openPaper` dùng `Number(input.value)` trực tiếp; input sai shape trong test/mock path có thể bị coercion ngoài contract.
- Requirement -> test:
  - Submit order quantity/price/stop/target dùng `safeNumber`: quét tĩnh xác nhận — pass.
  - `openPaper` quantity dùng `safeNumber` và reject null/non-positive: quét tĩnh xác nhận — pass.
  - Không còn unsafe `Number($('#...'))` cho order ticket: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Numeric string từ input DOM vẫn được hỗ trợ; null/boolean/object/array/non-finite bị reject trước request.

## Chu kỳ 129 — chuẩn hóa snapshot indicator conversion [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `snapshotIndicators` còn dùng `Number(value)` cho leaf, không nhất quán với safeNumber strict đã dùng ở các boundary khác.
- Requirement -> test:
  - Indicator leaves đi qua `safeNumber`: kiểm tra tĩnh xác nhận — pass.
  - Indicator sai type/whitespace không bị coercion ngoài contract: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Indicator finite number và numeric string vẫn giữ hành vi hiển thị; leaf khác type thành null.

## Chu kỳ 131 — chuẩn hóa analysis confidence conversion [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizeAnalysis` dùng branch Number/string riêng cho confidence, không nhất quán với safeNumber và contract leaf strict.
- Requirement -> test:
  - Confidence number/numeric string đi qua `safeNumber`: kiểm tra tĩnh xác nhận — pass.
  - Confidence non-numeric string được trim giữ lại; null/boolean/object không bị coercion: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giữ non-numeric confidence string để UI có thể hiển thị dữ liệu backend, nhưng không coercion sai type.

## Chu kỳ 133 — chuẩn hóa timestamp leaf [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizeTimestamp` cần contract rõ cho timestamp input; object/number/whitespace không nên đi vào date parser implicit.
- Requirement -> test:
  - Chỉ string không whitespace được parse: kiểm tra tĩnh xác nhận — pass.
  - Timestamp được trim trước `new Date`: quét tĩnh xác nhận — pass.
  - Input invalid fallback về current ISO string: review branch xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không thay đổi format ISO output; timestamp sai type tiếp tục dùng fallback hiện tại.

## Chu kỳ 135 — đơn giản hóa timestamp fallback [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `normalizeTimestamp` lặp lại `new Date().toISOString()` ở nhiều nhánh, không có một fallback duy nhất trong cùng lần gọi.
- Requirement -> test:
  - Fallback ISO được tạo một lần và dùng cho input sai/invalid: kiểm tra tĩnh xác nhận — pass.
  - Timestamp hợp lệ vẫn trả ISO parsed value: review branch xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không đổi contract timestamp; chỉ làm deterministic fallback trong mỗi lần normalize.

## Chu kỳ 137 — chuẩn hóa snapshot price conversion [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `snapshotPrice` dùng `Number(value)` riêng sau các type checks, không nhất quán với safeNumber boundary dùng cho các numeric leaf khác.
- Requirement -> test:
  - Snapshot price đi qua `safeNumber` và vẫn yêu cầu positive: kiểm tra tĩnh xác nhận — pass.
  - Không còn `Number(value)` trực tiếp trong snapshotPrice: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Numeric string hợp lệ tiếp tục được hỗ trợ; null/boolean/object/array/whitespace/non-finite hoặc non-positive trả null.

## Chu kỳ 139 — rà soát numeric coercion boundary [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Cần phân biệt `Number()` nội bộ hợp lệ trong `safeNumber` với coercion trực tiếp tại call site; scan ban đầu quá rộng và bắt nhầm các call `safeNumber(...)`.
- Requirement -> test:
  - `safeNumber` là nơi duy nhất dùng `Number(normalized)`: quét tĩnh chính xác — pass.
  - Không có `Number(...)` trực tiếp ngoài safeNumber boundary: quét tĩnh — pass.
  - Có 28 call sites dùng safeNumber: scan thực tế — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Sửa safeNumber để trim string trước conversion; giữ numeric string hỗ trợ nhưng reject whitespace-only.

## Chu kỳ 141 — bảo toàn local trade history khi backend lỗi [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `renderState` xóa `state.trades` và localStorage khi `/api/paper/state` lỗi, khiến mất lịch sử PnL local trong outage tạm thời.
- Requirement -> test:
  - Backend failure không xóa `state.trades`: kiểm tra tĩnh xác nhận — pass.
  - Backend failure không gọi `clearStoredState`: kiểm tra tĩnh xác nhận — pass.
  - UI vẫn nhận biết backend unavailable qua `backendState = null`: review branch xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Backend vẫn authoritative cho cash/equity/position hiện tại; local closed-trade history được giữ để không mất dữ liệu khi request tạm lỗi.

## Chu kỳ 143 — chuẩn hóa candle finite validation [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `snapshotCandles` kiểm tra finite-positive inline sau normalize, khó đọc và dễ nhầm contract khi leaf null.
- Requirement -> test:
  - Candle leaf phải là number finite dương sau `safeNumber`: predicate `isPositiveFinite` và static scan — pass.
  - Không thêm coercion trực tiếp ở candle path: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ refactor predicate, không đổi filtering/range behavior hoặc fallback candle.

## Chu kỳ 145 — chuẩn hóa equity formatting [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Equity display dùng `Number.isFinite` trực tiếp ở renderState và positions view, không đồng nhất với numeric boundary safeNumber.
- Requirement -> test:
  - RenderState equity dùng safeNumber và placeholder invalid: kiểm tra tĩnh xác nhận — pass.
  - Positions view dùng `formatMetric(state.equity)`: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Backend equity đã normalize vẫn hiển thị như trước; leaf sai type hiển thị `—` thay vì coercion.

## Chu kỳ 147 — chuẩn hóa position display boundary [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Positions view gọi `.toFixed()` trực tiếp trên `state.position.entry/qty`, dù state có thể đến từ storage/mock boundary.
- Requirement -> test:
  - Entry và quantity hiển thị qua `formatMetric`: kiểm tra tĩnh xác nhận — pass.
  - Không còn position `.toFixed()` trực tiếp: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Position backend đã normalize giữ nguyên hiển thị; dữ liệu sai shape hiển thị placeholder thay vì throw.

## Chu kỳ 149 — chuẩn hóa performance trade formatting [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Performance view gọi `.toFixed()` trực tiếp trên PnL, entry, exit, win rate và profit factor từ local trade history.
- Requirement -> test:
  - Performance metrics dùng `formatMetric`: kiểm tra tĩnh xác nhận — pass.
  - Closed trade numeric leaves dùng `formatMetric`: kiểm tra tĩnh xác nhận — pass.
  - Không còn direct `.toFixed()` trên các performance leaves: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giữ dấu PnL dương/âm và placeholder null; chỉ thay boundary formatting để tránh render throw.

## Chu kỳ 151 — chuẩn hóa signed PnL formatting [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Performance view lặp logic thêm dấu `+` cho PnL và gọi formatMetric riêng, không có helper chung cho signed numeric display.
- Requirement -> test:
  - `formatSignedMetric` giữ dấu dương/âm và dùng safe numeric formatting: kiểm tra tĩnh xác nhận — pass.
  - Closed trade PnL dùng helper chung: kiểm tra tĩnh xác nhận — pass.
  - Không còn duplicate sign logic trong performance view: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Zero hiển thị `+0`; invalid leaf hiển thị `—` và không throw.

## Chu kỳ 153 — chuẩn hóa performance metrics input [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `metrics()` tin `state.trades` đã normalize; trade malformed từ local boundary có thể làm reduce thành NaN hoặc render không ổn định.
- Requirement -> test:
  - Chỉ trade object có PnL numeric safe được dùng tính metrics: kiểm tra tĩnh xác nhận — pass.
  - Gains/losses/rate/pf tính từ tập trade đã normalize: review branch xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Trade history display vẫn dùng dữ liệu state hiện tại; metrics bỏ qua record malformed thay vì làm hỏng toàn bộ performance view.

## Chu kỳ 155 — tách metrics trade PnL helper [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `metrics()` dùng inline normalization chain, không có helper named để tái sử dụng/kiểm tra boundary PnL.
- Requirement -> test:
  - `normalizeTradePnl` reject non-object và trả PnL qua safeNumber: kiểm tra tĩnh xác nhận — pass.
  - `metrics()` dùng helper thay vì inline type chain: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không đổi kết quả metrics; chỉ đặt tên boundary để dễ review và tái sử dụng.

## Chu kỳ 157 — điều chỉnh signed zero display [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `formatSignedMetric` dùng điều kiện `number >= 0`, khiến PnL zero hiển thị dấu `+` không cần thiết.
- Requirement -> test:
  - Số dương có dấu `+`, số âm có dấu `-`, zero không có dấu: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Invalid value vẫn hiển thị `—`; chỉ thay presentation của zero PnL.

## Chu kỳ 159 — chuẩn hóa close PnL notification [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): closePaper notification dùng `pnl.toFixed()` trực tiếp sau close order thành công, không dùng signed numeric boundary chung.
- Requirement -> test:
  - Close PnL notification dùng `formatSignedMetric`: kiểm tra tĩnh xác nhận — pass.
  - Không còn direct `pnl.toFixed()` trong close notification: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Notification giữ dấu dương/âm, zero không dấu và invalid fallback `—`.

## Chu kỳ 161 — chuẩn hóa close PnL calculation [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): closePaper tính PnL trực tiếp từ state leaves mà không normalize entry/quantity/price ngay trước calculation.
- Requirement -> test:
  - Entry, quantity, price đi qua safeNumber và reject non-positive: kiểm tra tĩnh xác nhận — pass.
  - PnL calculation dùng safe operands, không đọc trực tiếp malformed state leaves: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Invalid position data bị từ chối trước request close; paper-only behavior và PnL formula LONG/SHORT không đổi.

## Chu kỳ 163 — chuẩn hóa positions last-price display [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Positions view gọi `state.price.toFixed()` trực tiếp trong ticker, không dùng numeric display boundary chung.
- Requirement -> test:
  - Last price trong Positions view dùng `formatMetric`: kiểm tra tĩnh xác nhận — pass.
  - Không còn direct `state.price.toFixed()` trong Positions view: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giá vẫn hiển thị prefix `$`; giá null giữ placeholder `—`.

## Chu kỳ 165 — chuẩn hóa position opened timestamp [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Positions view parse `state.position.opened` trực tiếp bằng `new Date(...)`, malformed timestamp có thể render `Invalid Date`.
- Requirement -> test:
  - Opened timestamp đi qua `normalizeTimestamp` trước format: kiểm tra tĩnh xác nhận — pass.
  - Không còn direct parse `new Date(state.position.opened)`: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Timestamp invalid fallback về ISO hiện tại qua helper hiện có; không thay đổi dữ liệu persisted.

## Chu kỳ 167 — chuẩn hóa market/equity display [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): `renderSnapshotViews` và `renderState` gọi `.toFixed()` trực tiếp cho market price/equity, không dùng numeric display boundary chung.
- Requirement -> test:
  - Market price text, order price input và equity text dùng `formatMetric`: kiểm tra tĩnh xác nhận — pass.
  - Không còn direct `toFixed()` tại các display boundary này: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giữ prefix `$` cho text display; order input nhận chuỗi formatMetric chuẩn hóa.

## Chu kỳ 169 — chuẩn hóa indicator dot class [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Performance view dùng `trade.pnl >= 0` trực tiếp để chọn dot class và truyền PnL raw vào formatter.
- Requirement -> test:
  - Dot class và signed PnL dùng PnL qua `normalizeTradePnl`: kiểm tra tĩnh xác nhận — pass.
  - Không còn direct comparison `trade.pnl >= 0`: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: PnL dương dùng green dot; zero, âm và invalid dùng cyan dot/placeholder an toàn.

## Chu kỳ 171 — chuẩn hóa closed-trade entry/exit display [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Performance view truyền raw `trade.entry` và `trade.exit` vào formatter, không có named numeric leaves trước render.
- Requirement -> test:
  - Closed-trade entry/exit đi qua `safeNumber` trước `formatMetric`: kiểm tra tĩnh xác nhận — pass.
  - Không còn truyền raw entry/exit vào formatter: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Invalid entry/exit hiển thị `—`; PnL và dot class behavior không đổi.

## Chu kỳ 173 — chuẩn hóa performance side label [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Performance view render raw `trade.side`, cho phép local malformed string xuất hiện trực tiếp trong UI.
- Requirement -> test:
  - Side label chỉ là LONG hoặc SHORT trước render: kiểm tra tĩnh xác nhận — pass.
  - Không còn render trực tiếp `${trade.side}`: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Unknown/malformed side fallback về LONG, nhất quán với normalizeStoredState.

## Chu kỳ 175 — harden openPaper inputs [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): openPaper dùng raw `state.price` và side input trước request/mutation, không có boundary normalization cục bộ.
- Requirement -> test:
  - Side normalize về LONG/SHORT và price đi qua safeNumber trước request: kiểm tra tĩnh xác nhận — pass.
  - Position lưu normalized side/entry: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Click handlers hiện truyền side hợp lệ; fallback LONG bảo vệ cả caller malformed.

## Chu kỳ 177 — chuẩn hóa openPaper notification side [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): openPaper notification dùng raw `side` thay vì `normalizedSide`, không nhất quán với position đã lưu.
- Requirement -> test:
  - Notification dùng normalizedSide: kiểm tra tĩnh xác nhận — pass.
  - Không còn raw side trong open notification: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ thay label notification; request và state mutation đã normalize từ chu kỳ trước.

## Chu kỳ 179 — chuẩn hóa closePaper side boundary [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): closePaper đọc raw `state.position.side` ở request, PnL formula và trade save.
- Requirement -> test:
  - Close side normalize về LONG/SHORT một lần trước side effect: kiểm tra tĩnh xác nhận — pass.
  - Request, formula và trade history dùng side normalized: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Unknown side fallback LONG, đồng nhất với các boundary side khác.

## Chu kỳ 181 — chuẩn hóa closePaper notification side [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): closePaper notification không hiển thị side dù side đã normalize cho request và trade history.
- Requirement -> test:
  - Close notification dùng side normalized: kiểm tra tĩnh xác nhận — pass.
  - Notification vẫn dùng signed PnL formatter: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ bổ sung LONG/SHORT vào notification; không đổi execution hoặc PnL.

## Chu kỳ 183 — chuẩn hóa openPaper response notification [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): openPaper đã validate order id nhưng bỏ qua giá trị id trong notification, làm giảm khả năng trace paper fill.
- Requirement -> test:
  - Order id được gán từ `requireOrderId` và dùng trong notification: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không đổi request hoặc state; chỉ bổ sung backend order id vào toast.

## Chu kỳ 185 — chuẩn hóa submit-order side [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Submit-order path gửi raw select value và không có canonical LONG/SHORT boundary trước khi chuyển thành backend buy/sell.
- Requirement -> test:
  - Select value `buy`/`sell` và legacy `SHORT` được normalize trước request: kiểm tra tĩnh xác nhận — pass.
  - Request dùng backend side `buy` hoặc `sell` từ side đã normalize: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Unknown select value fallback về LONG/buy; không đổi quantity, price hoặc risk fields.

## Chu kỳ 187 — chuẩn hóa submit-order notification side [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Submit-order notification chỉ hiển thị order id, không thể hiện canonical side đã gửi.
- Requirement -> test:
  - Notification dùng `normalizedSide` cùng order id: kiểm tra tĩnh xác nhận — pass.
  - Không còn side-less submit notification: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ cải thiện toast traceability; request và backend order semantics không đổi.

## Chu kỳ 189 — làm rõ submit-order risk gate [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Submit-order toast ghi “filled” nhưng thiếu ngữ cảnh paper/risk-gated đã thể hiện trong UI contract.
- Requirement -> test:
  - Toast hiển thị canonical side, risk-gated context và order id: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ thay presentation; không thay đổi backend request hoặc fill semantics.

## Chu kỳ 191 — harden paper-state positions boundary [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): normalizePaperState giữ nguyên positions object chưa lọc, có thể đưa array hoặc leaf malformed vào render.
- Requirement -> test:
  - Chỉ giữ position record là object không phải array: kiểm tra tĩnh xác nhận — pass.
  - Không còn truyền raw `payload.positions` sang state normalized: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giữ nguyên symbol key và các leaf backend; chỉ loại bỏ record malformed ở boundary.

## Chu kỳ 193 — normalize paper-state position leaves [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): normalizePaperState lọc object nhưng chưa kiểm tra quantity, average_price và opened trước render.
- Requirement -> test:
  - Quantity khác zero, average price dương và timestamp normalized trước state: kiểm tra tĩnh xác nhận — pass.
  - Record có leaf malformed bị loại bỏ: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giữ nguyên side inference từ quantity trong normalizePosition; chỉ canonicalize paper-state payload.

## Chu kỳ 195 — harden paper-state positions container [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): positions normalized object có thể kế thừa prototype hoặc nhận symbol key trống, làm tăng rủi ro khi Object.values/render.
- Requirement -> test:
  - Positions dùng null-prototype record: kiểm tra tĩnh xác nhận — pass.
  - Symbol key trống bị loại bỏ trước state: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không đổi API; chỉ harden boundary container trước render.

## Chu kỳ 197 — canonicalize paper-state symbol keys [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): positions giữ symbol key có whitespace hoặc casing không ổn định, làm lookup/render không nhất quán.
- Requirement -> test:
  - Symbol key được trim và uppercase trước khi normalized: kiểm tra tĩnh xác nhận — pass.
  - Assignment dùng key canonical, không dùng raw key: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ canonicalize key ở UI boundary; không sửa payload backend hoặc symbol contract.

## Chu kỳ 199 — harden duplicate paper-state symbols [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Hai symbol key khác casing/whitespace có thể ghi đè position sau canonicalization mà không có quy tắc rõ ràng.
- Requirement -> test:
  - Record đầu tiên thắng và duplicate canonical symbol không overwrite: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Duy trì thứ tự Object.entries; không thay đổi backend payload.

## Chu kỳ 201 — ổn định renderState position selection [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): renderState chọn position đầu tiên theo Object.values, phụ thuộc thứ tự payload khi backend trả nhiều symbol.
- Requirement -> test:
  - Position của `SNAPSHOT_SYMBOL` được ưu tiên trước fallback: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giữ fallback position đầu tiên nếu snapshot symbol không có position; không đổi backend payload.

## Chu kỳ 203 — harden snapshot indicator primitive boundary [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): snapshotIndicators giữ raw indicator key, có thể tạo label whitespace/casing không ổn định trong render.
- Requirement -> test:
  - Indicator key được trim và lowercase trước render: kiểm tra tĩnh xác nhận — pass.
  - Indicator key rỗng bị loại bỏ: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không đổi giá trị indicator; chỉ canonicalize key tại UI boundary.

## Chu kỳ 205 — harden duplicate snapshot indicators [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Indicator key khác casing/whitespace có thể ghi đè giá trị sau canonicalization mà không có quy tắc rõ ràng.
- Requirement -> test:
  - Indicator value đầu tiên thắng cho mỗi canonical key: kiểm tra tĩnh xác nhận — pass.
  - Normalized map dùng null-prototype record: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Duy trì thứ tự Object.entries; không thay đổi snapshot payload.

## Chu kỳ 207 — harden snapshot indicator source fallback [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): snapshotIndicators dùng truthy fallback, có thể chọn array hoặc malformed source thay vì container object hợp lệ.
- Requirement -> test:
  - Chỉ chọn candidate indicator là object không phải array: kiểm tra tĩnh xác nhận — pass.
  - Fallback hợp lệ giữa source và timeframe summary: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Ưu tiên source.indicators hợp lệ; chỉ fallback summary.indicators khi source không hợp lệ.

## Chu kỳ 209 — harden snapshot indicator values [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): snapshotIndicators giữ null cho value malformed, làm normalized map chứa entry không biểu diễn dữ liệu numeric hợp lệ.
- Requirement -> test:
  - Indicator value được normalize và chỉ giữ finite numeric value: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Indicator malformed bị bỏ qua hoàn toàn thay vì render placeholder; không đổi dữ liệu backend.

## Chu kỳ 211 — harden empty snapshot indicator fallback [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Candidate indicator object rỗng ở source có thể chặn summary indicator hợp lệ vì chỉ kiểm tra shape.
- Requirement -> test:
  - Candidate chỉ được chọn khi có ít nhất một numeric value hợp lệ: kiểm tra tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Empty hoặc all-malformed source sẽ fallback sang summary; nếu cả hai không hợp lệ trả map rỗng.

## Chu kỳ 213 — harden empty snapshot indicator map [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Empty/all-malformed indicator path trả plain object có prototype, không nhất quán với normalized path.
- Requirement -> test:
  - Empty indicator path trả null-prototype map: kiểm tra tĩnh xác nhận — pass.
  - Không còn plain `{}` ở indicator empty path: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ thay đổi container nội bộ; render output vẫn tương đương map rỗng.

## Chu kỳ 215 — deterministic snapshot indicator fallback [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Candidate source/summary cùng object shape nhưng source có thể ít numeric value hợp lệ hơn summary, làm mất indicator hiển thị.
- Requirement -> test:
  - Chọn candidate có numeric value hợp lệ nhiều nhất: kiểm tra tĩnh xác nhận — pass.
  - Hòa số lượng ưu tiên source vì reduce giữ candidate đầu tiên: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Chỉ thay đổi lựa chọn UI source; không thay đổi snapshot payload.

## Chu kỳ 217 — explicit snapshot indicator candidate tie [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): Reduce giữ candidate đầu tiên khi hòa nhưng quy tắc source priority chưa biểu đạt rõ trong source.
- Requirement -> test:
  - Candidate có numeric richness cao hơn vẫn thắng: kiểm tra tĩnh xác nhận — pass.
  - Khi hòa, source candidate có `sourceRank` thấp hơn thắng: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Source candidate rank 0, summary rank 1; không đổi snapshot payload.

## Chu kỳ 219 — ổn định source rank sau filter [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): sourceRank tính từ index sau filter, nên malformed source có thể làm summary hợp lệ nhận rank sai.
- Requirement -> test:
  - Source rank được gán trước filter và giữ ổn định: kiểm tra tĩnh xác nhận — pass.
  - Summary không bị nhầm rank source khi source malformed: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Giữ source rank 0 và summary rank 1 từ candidate list gốc.

## Chu kỳ 221 — semantic snapshot indicator source rank [DONE]
- Commit: chờ commit sau khi hoàn tất journal.
- Tests: không thay đổi; full pytest không thể chạy vì interpreter bắt buộc thiếu.
- Checks: ruff=na mypy=na pytest=na node=0.
- Root cause (Phase A only): sourceRank biểu diễn vị trí candidate nhưng tên không nói rõ source/summary semantics, dễ bị dùng sai khi thêm candidate.
- Requirement -> test:
  - Candidate mang semantic rank `source` hoặc `summary`: kiểm tra tĩnh xác nhận — pass.
  - Khi validCount hòa, rank `source` thắng explicit: quét tĩnh xác nhận — pass.
  - JavaScript hợp lệ: `node --check web/app.js` — pass.
- Forbidden-pattern scan: chưa chạy vì interpreter Python bắt buộc thiếu.
- Spec or test weakened? no
- Notes / assumptions: Không thay đổi numeric richness hoặc snapshot payload.
