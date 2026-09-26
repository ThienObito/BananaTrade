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
