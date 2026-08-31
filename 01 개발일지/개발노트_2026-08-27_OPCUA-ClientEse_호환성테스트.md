# 개발노트 — OPC UA Client Ese 호환성 검증 (KEPServerEX6 전용 여부 확인 + Subscribe 버그 + 인증서 트러블슈팅)

`OPC-UA-ClientEse`(학원 실습용 .NET 클라이언트, 소스 없이 exe만 배포됨)가 KEPServerEX6 외의 서버에도 붙는지 검증한 세션. 결론부터: **범용 클라이언트가 맞고, 자체 구축한 Python(asyncua) 서버와 연결도 성공**했지만 그 과정에서 클라이언트 자체 버그 하나와 인증서 관련 함정 하나를 발견/해결함.

## 1. Client Ese가 KEPServerEX6 전용인지 확인

exe 바이너리 문자열을 직접 추출해서 분석(`.cs` 소스 없음, exe/dll/config만 존재):
- `OPCFoundation.UA.ClientSDK.dll` 기반의 OPC Foundation 공식 SDK 클라이언트. `kepware`/`kepserver` 하드코딩 전혀 없음
- UI 문자열: `ServerUriTB`(URI 직접입력), `ConnectBT`/`DisconnectBT`, `BrowseNodesTV` — 전형적인 범용 SampleClient 구조
- **결론**: KEPServerEX6만 됐던 건 그것만 테스트해봤기 때문. 스펙 준수 서버라면 뭐든 접속 가능

## 2. Subscribe 시 크래시 — `Convert.ToInt32` 버그 (Client 쪽 버그, 서버 문제 아님)

드론팩토리용 OpenPLC 서버(`opc.tcp://127.0.0.1:4840/openplc/opcua`)의 Boolean 태그(`Under_Start` 등)를 Client Ese에서 Monitor(Subscribe) 걸면 "입력 문자열의 형식이 잘못되었습니다" 크래시.

**스택트레이스**:
```
System.Number.StringToNumber → System.Number.ParseInt32 → System.Convert.ToInt32(String value)
  ← OPC_UA_Client_Ese.EseClient.monitoredItem_Notification(MonitoredItem, MonitoredItemNotificationEventArgs)
```

- 서버 쪽은 문제없음(확인됨): 같은 서버·같은 Boolean 태그(`BUSY`, `FINISH`)를 `plc_worker.py`(Python `asyncua`, `create_subscription`+`subscribe_data_change`)로 구독하면 정상 수신됨 → 서버 인코딩은 spec 준수, 크래시는 클라이언트 쪽 문제라는 것까지는 확실
- 최초 가설(**기각됨**): "Boolean 노드를 Monitor/Subscribe하면 값을 `Convert.ToInt32`로 강제 변환하려다 무조건 크래시 난다"고 추정했으나, §3의 `ese_test_server.py`(`Busy`, Boolean, 3초마다 자동 토글)를 Client Ese에서 실제로 Monitor Start 걸어본 결과 **크래시 없이 정상 모니터링됨**. Boolean 타입 자체는 원인이 아니었음
- **결론(현재까지)**: 크래시는 "Boolean이라서"가 아니라 **OpenPLC Runtime 서버 특유의 뭔가**(정확한 트리거는 미특정) 때문으로 보임. 순수 `asyncua` 기본 서버 구현과 OpenPLC의 내장 OPC-UA 구현 사이에 뭔가 차이가 있다는 것까지는 좁혀졌지만, 정확히 어떤 필드/조건이 원인인지는 아직 모름
- **대응**: 결론이 안 났으므로 여전히 보수적으로, OpenPLC 서버 대상 Monitor/Subscribe는 피하고 Read 위주로 쓰는 걸 권장 (asyncua 기반 자체 서버는 이번 테스트로 Boolean 구독 안전성 확인됨)

## 3. 자체 asyncua 서버 구축 → Client Ese 연결 (`03 Server/04 ese_test_server.py`)

`opc.tcp://0.0.0.0:4841/freeopcua/server/`에 `PLC` 오브젝트 하위로 `Temperature`(Double), `Busy`(Boolean, 3초마다 자동 토글), `Count`(Int32, 3초마다 +1), `Message`(String) 노출.

### 트러블슈팅

**① `Server did not return the certificate used to create the secure channel.`**
- 증상: 서버는 Python `asyncua` 클라이언트로는 정상 연결·Subscribe 다 되는데, Client Ese에서만 연결 자체가 이 오류로 거부됨
- 원인: 서버에 인증서를 전혀 로드하지 않은 상태라 `GetEndpoints` 응답의 `ServerCertificate` 필드가 완전히 빈 값(0바이트)이었음. **Client Ese는 `SecurityMode=None`이어도 서버가 인증서를 아예 안 주면 이 오류를 던지는 버그성 동작**임을 실측으로 확인
- 잘못 짚었던 가설: "보안 엔드포인트가 같이 광고돼서 그런가" → `server.set_security_policy([ua.SecurityPolicyType.NoSecurity])`로 제한했는데도 재현됨. "엔드포인트 캐시가 클라이언트 어딘가 남아있나" → `%APPDATA%`, `%ProgramData%`에 OPC Foundation 캐시 폴더 자체가 없어서 기각. 실제 원인은 **살아있는 서버 프로세스에 직접 GetEndpoints를 쏴서 `ServerCertificate` 바이트 길이를 확인**하는 방식으로 확정(0바이트 → 문제 있음)
- 해결:
  ```python
  from pathlib import Path
  from asyncua.crypto.cert_gen import setup_self_signed_certificate
  from cryptography.x509.oid import ExtendedKeyUsageOID

  cert_dir = Path(__file__).parent / "certs"
  cert_dir.mkdir(exist_ok=True)
  await setup_self_signed_certificate(
      key_file=cert_dir / "server_key.pem",
      cert_file=cert_dir / "server_cert.der",
      app_uri="urn:freeopcua:python:server",
      host_name="localhost",
      cert_use=[ExtendedKeyUsageOID.SERVER_AUTH],
      subject_attrs={"countryName": "KR", "stateOrProvinceName": "Seoul",
                      "localityName": "Seoul", "organizationName": "TestServer",
                      "commonName": "ese_test_server"},
  )
  await server.load_certificate(str(cert_dir / "server_cert.der"))
  await server.load_private_key(str(cert_dir / "server_key.pem"))
  server.set_security_policy([ua.SecurityPolicyType.NoSecurity])  # 보안 정책은 그대로 None 유지
  ```
  `SecurityPolicy`는 여전히 `None`이지만, 인증서가 로드돼 있으면 asyncua가 `GetEndpoints` 응답에 그 인증서를 실어서 보냄(0→1256바이트) — 실제 암호화 채널을 쓰는 게 아니라 클라이언트의 "서버 인증서 존재 여부" 체크만 통과시켜준 것. 이걸로 **연결 성공**

**② `load_certificate`/`load_private_key`가 코루틴인데 `await` 누락**
- 증상: `RuntimeWarning: coroutine was never awaited`만 뜨고 예외 없이 조용히 넘어감 → 인증서가 실제로는 로드 안 된 채로 서버가 떠서 원인 파악에 혼선
- 해결: `await` 추가

**③ 포트 충돌 (`WinError 10048`, 각 소켓 주소는 하나만 사용할 수 있음)**
- 증상: 스크립트를 다른 경로(`05 TotalSys/02 작업/08-27/`)로 복사해서 재실행할 때마다 발생
- 원인: VS Code ▶ 버튼으로 재실행할 때마다 새 터미널이 뜨는데, 이전 터미널의 프로세스가 안 죽고 같은 포트를 계속 물고 있음
- 진단/정리 절차:
  ```powershell
  netstat -ano | findstr :4841          # 또는 Get-NetTCPConnection -LocalPort 4841 -State Listen
  Get-Process -Id <PID>                  # 무슨 프로세스인지 확인
  Stop-Process -Id <PID> -Force          # 종료
  ```
  Git Bash에서 `python script.py &` 실행 시 `$!`로 나오는 PID는 MSYS 자체 PID 변환 때문에 실제 Windows PID와 다를 수 있어서 `taskkill`이 안 먹는 경우가 있었음 — 이럴 땐 `netstat -ano`로 실제 리스닝 PID를 다시 찾아서 죽여야 함
- 예방: 재실행 전 이전 터미널에서 `Ctrl+C`로 먼저 끄거나 터미널 탭을 완전히 닫기

## 4. 확인된 사실 정리

- `0.0.0.0`은 서버 바인딩 주소일 뿐, 클라이언트 접속 주소로는 못 씀 — 같은 PC면 `127.0.0.1`, 다른 PC면 실제 IP/Tailscale IP
- 포트 `4841`은 표준/예약 포트 아님. `01 namespace.py`에 이미 있던 값을 재사용한 것(4840=OpenPLC와 안 겹치게 임의로 고른 숫자)
- Client Ese ↔ KEPServerEX6뿐 아니라 ↔ 순수 Python `asyncua` 서버 연결도 **정상 확인 완료**

## 5. Client Ese의 "Monitoring"이 진짜 Subscribe인지 검증 (Read 폴링 위장 아닌지)

Busy/Count가 화면에서 계속 갱신되는 걸 보고 "이거 진짜 구독 중인 거 맞냐, 그냥 Read 반복 아니냐"는 의문 제기됨. UI 라벨(`Mode: Reporting`, `Deadband`, `Sampling`)만으로는 근거가 약해서, 서버 쪽 프로토콜 로그로 직접 검증.

**방법**: `logging.getLogger("asyncua.server.uaprocessor").setLevel(logging.DEBUG)`로 서버에 로깅 추가 후 재시작, Client Ese에서 재연결.

**첫 시도 실패 — 세션 재사용 문제**: 서버 재시작 직후 클라이언트가 재연결을 시도했는데 `Create session request` 로그가 아예 안 찍히고 바로 `Activate session request`만 찍힘 → `BadSessionIdInvalid`로 거부됨. **클라이언트가 서버 재시작 전의 옛날 세션 ID를 그대로 재사용하려 했던 것** (새로 CreateSession을 안 함). TCP 소켓은 `ESTABLISHED`로 떠 있었지만 그 위에 유효한 OPC-UA 세션은 없어서, 화면에 보이던 값은 사실 재시작 전 마지막으로 받은 값이 멈춰있던 것이었음. **해결**: 클라이언트에서 완전히 Disconnect 후 다시 Connect(세션 재사용 대신 완전히 새로 시작).

**검증 결과 — 진짜 Subscribe 맞음(확인됨)**: 재연결 후 로그에서 정상적인 OPC-UA 구독 시퀀스 확인:
```
create monitored items request
request to subscribe to datachange for node ... attribute 13   # 13 = AttributeId.Value
publish request / publish request with acks []                 # 반복
```
`CreateMonitoredItems`(구독 전용 서비스, attribute=Value)와 `Publish`(구독 알림 수신용 long-polling 서비스)가 확인됨. 단순 Read 폴링이었다면 `ReadRequest`(타입ID 631)가 반복 찍혔어야 하는데 그건 없었음 → **Client Ese의 Monitor 기능은 진짜 CreateSubscription/MonitoredItem/Publish 흐름을 쓰는 정상적인 Subscribe 구현**임을 서버 프로토콜 로그로 확정.

## 다음 단계

- (완료) `Busy` 노드 Monitor Start 실측 → Boolean 구독 자체는 문제없음 확인, 게다가 진짜 Subscribe(Read 폴링 아님)라는 것까지 프로토콜 로그로 확정. **남은 과제**: 크래시가 OpenPLC 서버의 정확히 어떤 특성 때문인지는 여전히 미특정 — 필요하면 OpenPLC 서버 재접속해서 재현되는지, 재현된다면 어떤 노드/타이밍에서인지 다시 좁혀봐야 함
- 학원 컴퓨터에서 이 노트북의 자체 서버로 원격 접속 테스트 (Tailscale 또는 ipTIME 포트포워딩+DDNS 방식, 아직 실측 전)
- 필요시 이 인증서 로드 패턴을 드론팩토리 실물 PLC 서버(`real_plc_server.py`, 포트 4846)에도 적용할지 검토 — 단, 현재는 asyncua 클라이언트로만 접속하고 있어 문제 없었음. Client Ese로 붙일 일이 생기면 동일 패턴 필요
