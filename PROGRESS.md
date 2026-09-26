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
