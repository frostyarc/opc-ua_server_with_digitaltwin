# 개발노트 — 실물 PLC(Q03UDECPU) + pymcprotocol + OPC-UA 브릿지

`05 TotalSys/02 작업/08-27` 폴더. 어제(GX Simulator2 + MX Component) 흐름을 실물 PLC로 이어받은 세션.

## 핵심 아키텍처 결론

어제 개발노트의 "다음 단계" 메모(`실물 PLC 확보 시: pymcprotocol로 직접 TCP 접속`)가 그대로 실현됨.

**실물 PLC는 MX Component/32비트 파이썬이 전혀 필요 없다.** `pymcprotocol`로 내장 이더넷 포트에 raw TCP(MC프로토콜 3E프레임)로 직접 접속 가능. 기본 64비트 파이썬(3.14)에 `pymcprotocol`, `asyncua` 둘 다 이미 설치돼 있어서 환경 구축 자체가 생략됨.

```
Q03UDECPU (내장 이더넷) --MC프로토콜(TCP,3E프레임)--> pymcprotocol --OPC-UA--> 클라이언트
```

## 물리/네트워크 구성

- PC ↔ PLC USB(프로그래밍 포트, GX Works2 직결용) — 파라미터 설정/쓰기 전용
- PC(IPTIME USB3.0 기가비트 이더넷 어댑터) ↔ PLC 내장 이더넷 포트 — **스위치 없는 직결(point-to-point)**, DHCP 서버가 없어서 양쪽 다 고정 IP 필수
  - PC측(IPTIME 어댑터): `192.168.3.10/24`
  - PLC측(내장 이더넷): `192.168.3.39/24`, Open설정 TCP 포트 `5010`

### 고정 IP 설정 (관리자 권한 필요)
```powershell
netsh interface ip set address name="이더넷" static 192.168.3.10 255.255.255.0
```

### GX Works2 "접속대상 지정" — 이더넷 경로로 GX Works2 자체 접속할 때
- PC측 I/F: **Ethernet Board**
- PLC측 I/F: **PLC Module** (자국 직결)
- 다른국 지정 / 네트워크통신경로 / 이종네트워크통신경로: **불필요** — 이 항목들은 CC-Link/MELSECNET 등 중계망을 거쳐 원격국(자기 자신이 아닌 다른 스테이션)에 도달할 때만 쓰는 라우팅 설정. 자국 직결 구조에서는 기본값(미사용)으로 둠.

## 트러블슈팅

### 1. USB 프로그래밍 포트 — Windows 드라이버 미설치
- 증상: USB로 물려도 GX Works2가 PLC 인식 못 함
- 원인: `Get-PnpDevice`로 확인 시 `VID_06D3&PID_1800`(미쓰비시 전기) 장치가 `Status: Error`, `ProblemCode: 28`(드라이버 미설치)
- 해결: GX Works2 설치 폴더 안에 있던 드라이버를 관리자 권한으로 수동 설치
  ```powershell
  pnputil /add-driver "C:\Program Files (x86)\MELSOFT\Easysocket\USBDrivers\ECUsbd.inf" /install
  ```
  설치 후 `FriendlyName: MITSUBISHI Easysocket Driver`, `Status: OK`로 정상화. USB 케이블 재연결 필요할 수 있음.

### 2. MC프로토콜 write 시 에러 `0x0055`
- 증상: `batchread_wordunits`(읽기)는 정상, `batchwrite_wordunits`(쓰기)만 `MCProtocolError: error code 0x0055`
- 원인: "온라인 변경(쓰기)이 금지된 상태에서 RUN 중인 CPU 모듈에 데이터 쓰기를 요청함" — PLC가 RUN 상태일 때 통신을 통한 쓰기가 기본적으로 막혀있음
- 해결: PLC파라미터 → 내장Ethernet포트 설정(또는 관련 네트워크 파라미터)에서 **"RUN 중 쓰기 허용"** 체크 → PLC에 파라미터 재전송(Write) → **전원 재투입(Off→On)**. 리셋 스위치만으로는 반영 안 됨, 전원을 완전히 껐다 켜야 적용됨.

### 3. `batchwrite_bitunits`의 `values` 인자 타입 실수
- 증상: `pymc.batchwrite_bitunits(headdevice="M100", values=1)` → `TypeError: object of type 'int' has no len()`
- 원인: 라이브러리 내부에서 `write_size = len(values)`로 길이를 재는 구조라 `values`는 반드시 리스트여야 함
- 해결: `values=[1]`

### 4. 동시 접속 충돌 — 백그라운드 프로세스가 연결 점유
- 증상: 브릿지(`plc_opcua_bridge_real.py`)를 백그라운드로 띄운 채 다른 테스트 스크립트를 실행하면, TCP 연결(`connect()`)은 성공하는데 첫 `batchread_wordunits`에서 `TimeoutError`
- 원인: PLC 내장 이더넷 포트의 Open설정은 동시접속 슬롯이 제한적. 브릿지 프로세스가 이미 세션을 점유하고 있어서, 두 번째 클라이언트는 TCP 핸드셰이크까지는 되지만 PLC가 응답을 안 줌
- 해결: 테스트 전 기존 파이썬 프로세스가 살아있는지 확인 후 종료
  ```powershell
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select-Object ProcessId, CommandLine
  Stop-Process -Id <PID> -Force
  ```

## pymcprotocol API 레퍼런스

```python
import pymcprotocol

pymc = pymcprotocol.Type3E()
pymc.connect(PLC_IP, PLC_PORT)

# 워드 디바이스 (D, W, R) — 숫자값
values = pymc.batchread_wordunits(headdevice="D100", readsize=1)
pymc.batchwrite_wordunits(headdevice="D100", values=[1234])

# 비트 디바이스 (M, X, Y, L) — ON/OFF, values는 반드시 0 또는 1로 된 리스트
values = pymc.batchread_bitunits(headdevice="M100", readsize=1)
pymc.batchwrite_bitunits(headdevice="M100", values=[1])

pymc.close()
```

MX Component(`ActUtlType`) 대비 훨씬 단순함 — 논리국번호/ActComm.exe 설정 불필요, IP+포트만 있으면 바로 접속.

## 파일 구조 (오전 세션, D100 단방향 미러링)

- `pymc_connection_test.py` — 실물 PLC 직접 접속 테스트. D100(워드) read/write, M100(비트) write 검증
- `plc_opcua_bridge_real.py` — 어제 `plc_opcua_bridge.py`(MX Component판)를 pymcprotocol 기반으로 교체. D100을 1초마다 읽어 OPC-UA 태그(`opc.tcp://0.0.0.0:4845/plc/server/`)로 미러링. 핸드셰이크 로직 없음, PLC→OPC-UA 단방향만 (어제와 동일하게 의도적으로 스코프 제한)
- `opcua_client_test.py` — 검증용 클라이언트 (D100 미러링 확인용, 이후 드론 팩토리용으로 재작성됨)

---

## 드론 팩토리 핸드셰이크 (오후 세션, `real_plc_server.py`)

래더 완성 후, `02 OPC-UA Project/04 Drone Factory/solution.py`(OpenPLC 시뮬레이터 기준, 어제 이전 세션 산출물)의 핸드셰이크 구조를 실물 PLC로 이식.

### 노드 매핑

| OPC-UA 노드 | PLC 디바이스 | 방향 |
|---|---|---|
| `Order_Accept` | M10 | CPS → PLC (씀) — 하부 공급 트리거 |
| `Under_Start` | M100 | PLC → CPS (읽기 전용) |
| `Under_Busy` | M111 | PLC → CPS |
| `Arm_Busy` | M121 | PLC → CPS |
| `Upper_Busy` | M131 | PLC → CPS |
| `Propeller_Busy` | M141 | PLC → CPS |
| `Pro_Finish` | M142 | PLC → CPS — 전체 라인 최종완료 |

**M10 리셋 타이밍**: solution.py는 `Arm_Busy` 상승엣지에서 Start를 껐지만(OpenPLC 시뮬레이터 래더 기준), 실물 래더는 **`Under_Busy`(하부busy) 상승엣지**에서 바로 M10을 리셋함 — 하부공급공정이 실제로 시작된 걸 확인하는 즉시 트리거를 내리는 구조. 시뮬레이터와 실물 래더의 설계 차이이니 "solution.py 그대로 이식"이 아니라 실측 확인 후 수정 필요했던 부분.

**M10이 안 켜지는 문제**: 실제로는 버그가 아니라 `orders_pending`이 비어있어서였음(주문을 넣은 적이 없었음). `Get-PnpDevice`류의 인프라 디버깅과 달리, 이런 "논리적으로 조건 불충족" 케이스는 PLC 비트를 직접 읽어(`M111=0, M121=0` 등 걸림돌 없음 확인) 배제법으로 좁혀감.

### 파이프라인 구조 — 스테이지별 주문 추적

단일 `status`(대기/진행중/완료) 방식으론 어느 주문이 어느 공정에 있는지 구분 불가 → `stage_orders = [하부, 암, 상부, 프로펠러]` 배열로 스테이지별 현재 점유 주문을 파이프라인처럼 앞칸→뒷칸 이동시키며 추적. 각 스테이지 busy 상승엣지마다 `stage_orders[다음] = stage_orders[이전]; stage_orders[이전] = None`.

입구 조건(다음 주문을 하부에 투입): `not under_busy and not arm_busy and stage_orders[STAGE_UNDER] is None and orders_pending` — 하부/암 둘 다 비어있어야 다음 유닛 진입 가능한 **단일 파이프(overtaking 불가)** 구조.

### DB 연동 (`drone_factory` 재사용)

`orders` 테이블(기존 solution.py가 쓰던 것 그대로)에 더해 신규 테이블 추가:

```sql
CREATE TABLE order_stage_status (
    order_id INT NOT NULL,
    stage VARCHAR(20) NOT NULL,
    status TINYINT NOT NULL DEFAULT 0,        -- 0=대기, 1=진행중, 2=완료
    completed_count INT NOT NULL DEFAULT 0,   -- 이 스테이지를 완전히 통과한 유닛 수
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (order_id, stage),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);
```

- `web_app.py`(FastAPI, `/order` POST)가 주문 생성 시 `orders` INSERT + 4개 스테이지 `order_stage_status` 초기 행(status=0) INSERT까지 같은 트랜잭션성으로 처리
- `real_plc_server.py`가 유일한 PLC 연결 보유자이자 유일한 상태 변화 관찰자이므로, **완료 판정(DB UPDATE)은 전부 이 프로세스가 담당** — `web_app.py`는 순수 OPC-UA 클라이언트로만 동작 (주문 생성 시 `SubmitOrder(order_id, quantity)` OPC-UA 메서드 호출)

### 수량>1 주문의 진행률(X/N) 표시

요청: 하부/암/상부/프로펠러 각각 "지금까지 몇 번째 유닛까지 통과했는지/전체수량"을 보여주고 싶음. 두 가지 카운팅 방식(① 최근 진입 유닛 번호, ② 통과완료 개수) 중 사용자가 **②(통과완료 개수, 0부터 시작)** 선택 → `completed_count` 컬럼을 기존 `status` 갱신 지점(다음 공정 진입 엣지)에 나란히 `+1`.

**마지막 유닛에서만 주문 전체 완료 처리**: 처음엔 `Pro_Finish` 엣지마다(유닛마다) `orders.finish_date`를 갱신해서, 수량>1 주문에서 첫 유닛 완료 시점에 "주문 완료"로 잘못 표시됨. `order_quantity = {}` 딕셔너리(`SubmitOrder` 호출 시 저장)로 총수량을 기억해뒀다가, `increment_completed()`가 반환하는 최신 카운트가 총수량과 같아질 때(=마지막 유닛)만 `finish_date` 갱신 + `propeller` status=2 처리.

### Grafana 모니터링 쿼리

```sql
SELECT
    o.id AS 주문번호, o.quantity AS 수량, o.order_date AS 주문시각,
    ROUND(100 * MAX(CASE WHEN s.stage = 'lower' THEN s.completed_count END) / o.quantity) AS 하부,
    ROUND(100 * MAX(CASE WHEN s.stage = 'arm' THEN s.completed_count END) / o.quantity) AS 암,
    ROUND(100 * MAX(CASE WHEN s.stage = 'upper' THEN s.completed_count END) / o.quantity) AS 상부,
    ROUND(100 * MAX(CASE WHEN s.stage = 'propeller' THEN s.completed_count END) / o.quantity) AS 프로펠러,
    o.finish_date AS 완료시각
FROM orders o
JOIN order_stage_status s ON s.order_id = o.id
GROUP BY o.id, o.quantity, o.order_date, o.finish_date
ORDER BY o.order_date DESC
```

`(order_id, stage)`가 PK라 주문당 정확히 4행 — `MAX(CASE WHEN stage=X THEN completed_count END)`로 그 4행을 주문 1행으로 피벗.

**트러블슈팅 — Grafana 스레스홀드 색이 안 바뀜**: 처음엔 `CONCAT(count, '/', quantity)`로 "2/3" 같은 **문자열**을 반환했음 — Grafana 스레스홀드는 숫자 필드에만 적용되므로 무시됨. `ROUND(100 * count / quantity)`로 퍼센트(숫자)를 반환하도록 수정. 추가로 Table 패널의 Cell display mode가 기본값 "Auto"면 숫자여도 색이 안 칠해지므로 "Color background"/"Color text"로 명시 필요.

### 최종 정리 — 모니터링 print 제거

DB+Grafana로 모니터링이 이관되면서 `real_plc_server.py`의 콘솔 print(주문/스테이지 진행 로그)는 전부 제거. 시작 로그(`PLC 연결 성공`, `OPC-UA 서버 시작...`) 2줄만 유지.

## 파일 구조 (오후 세션 최종)

- `real_plc_server.py` — 실물 PLC MC프로토콜 클라이언트 + OPC-UA 서버(포트 4846) + DB(`drone_factory`) 연동. 파이프라인 스테이지 추적, `SubmitOrder` OPC-UA 메서드 노출
- `web_app.py` — FastAPI 웹 주문 폼. DB INSERT 후 `SubmitOrder` OPC-UA 클라이언트 호출만 담당 (PLC 직접 연결 없음)
- `submit_order_test.py` / `check_status.py` — 웹앱 완성 전 임시 테스트용 (SubmitOrder 호출, 5개 신호 상태 조회)

## 포트 사용 현황 (누적)

- 4840: OpenPLC 기존 서버
- 4841: 찬호봇 프로젝트 1차 서버
- 4842: 찬호봇 프로젝트 핸드셰이크 서버
- 4843: `plc_opcua_bridge.py` (GX Simulator2 + MX Component판)
- 4844: `00 Practice` 학습용 서버
- 4845: `plc_opcua_bridge_real.py` (실물 PLC + pymcprotocol판, D100 단방향 미러링)
- **4846**: `real_plc_server.py` (드론 팩토리 실물 PLC 핸드셰이크 + DB + 웹앱)
- PLC측 MC프로토콜 TCP 포트: **5010**

## 다음 단계

- 웹 폼에서 실제로 수량 3+ 주문을 여러 번 넣어 파이프라인 겹침(서로 다른 주문이 동시에 다른 스테이지에 있는 경우) 시나리오 실측 검증
- Grafana 대시보드 완성 (지금은 쿼리/스레스홀드 색상까지만 확인)
