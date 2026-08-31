# 개발노트 — GX Works2 + MX Component + 파이썬 OPC-UA 브릿지

`05 TotalSys` 폴더. GX Works2(시뮬레이터) ↔ 파이썬 ↔ OPC-UA 연동 프로젝트.

## 핵심 아키텍처 결론

**GX Simulator2(GX Works2 내장 시뮬레이터)는 외부에서 raw 이더넷 소켓(MC프로토콜 3E프레임 등)으로 직접 접속이 안 된다.** `pymcprotocol` 같은 라이브러리는 실물 PLC 하드웨어(진짜 이더넷 포트가 있는)에서만 쓸 수 있고, 시뮬레이터는 **MX Component(미쓰비시 공식 유료 COM/ActiveX 라이브러리)를 통해서만** 접속 가능하다. (netstat으로 포트 자체가 안 열려있는 것 실측 확인함)

→ 실물 PLC 확보 시: `pymcprotocol`로 직접 TCP 접속 (더 간단, 이미 설치돼 있음)
→ 시뮬레이터로 연습 시: MX Component + `pywin32` COM 경로 필수

## 환경 설정 (재현 방법)

MX Component의 ActiveX 컨트롤(`ActUtlType`)은 **32비트 전용**이라, 별도의 32비트 파이썬이 필요함.

```powershell
# 32비트 Python 3.13 설치
winget install Python.Python.3.13 --architecture x86

# py 런처로 확인
py -0p    # -> -V:3.13-32 항목 확인

# 32비트 환경에 패키지 설치 (cryptography는 49+ 버전부터 win32 wheel 없음 → 48.0.1 고정)
py -3.13-32 -m pip install pywin32
py -3.13-32 -m pip install asyncua "cryptography==48.0.1"
```

실행은 항상 `py -3.13-32 -u "파일경로"` (평범한 `python`은 64비트 3.14라 COM 접속 실패함).

VS Code에서 재생 버튼 쓰려면 `Ctrl+Shift+P` → "Python: Select Interpreter" → 32-bit 3.13 선택 (단, 이 창/폴더 한정으로만 적용됨 — 다른 프로젝트는 원래대로 64비트 유지).

## MX Component API 레퍼런스 (ActUtlType.ActMLUtlType)

출처: `C:\MELSEC\Act\Samples\VBScript\`(공식 설치 샘플) + 공식 Programming Manual V4 PDF.

```python
import win32com.client

act = win32com.client.Dispatch("ActUtlType.ActMLUtlType")
act.ActLogicalStationNumber = 1   # ActComm.exe(통신설정 유틸리티)에서 만든 논리국번호와 일치해야 함
ret = act.Open()                  # 0 = 성공

ret, values = act.ReadDeviceBlock("D100", 1, [0])   # (에러코드, 값튜플) 반환 — 3번째 인자 내용은 버려지고 길이만 씀
ret = act.WriteDeviceBlock("D100", 1, [1234])       # 에러코드만 반환, 3번째 인자 값이 실제로 쓰임

act.Close()
```

**win32com 특이사항**: `ReadDeviceBlock`처럼 원래 VB에서 배열을 채워 돌려주는 [out] 매개변수 방식의 메서드는, 파이썬 win32com에서 넘겨준 리스트를 그대로 안 채우고 `(에러코드, 결과값)` 튜플로 따로 반환한다. `WriteDeviceBlock`처럼 입력 전용 배열은 이 문제 없음.

### 논리국번호(Logical Station Number)란
코드에는 접속 정보(어떤 CPU, 어떤 인터페이스인지)가 전혀 없음 — `ActComm.exe`(통신설정 유틸리티, 경로: `C:\MELSEC\Act\Utl\ActComm.exe`)에 번호별로 저장해둔 설정을 코드에서는 번호로만 참조함. GX Simulator2로 접속하려면 이 유틸리티에서 PC측 인터페이스를 "GX Simulator2"로 설정해야 함.

### 에러코드 확인 방법
공식 매뉴얼(PDF)에서 직접 찾는 게 가장 정확함. `pypdf`로 텍스트 추출 후 에러코드 문자열로 검색:
```python
import pypdf
r = pypdf.PdfReader("매뉴얼경로.pdf")
for i, p in enumerate(r.pages):
    if "F0000002" in (p.extract_text() or ""):
        print(i, ...)
```
확인된 주요 에러코드:
- `0xF0000002`: 논리국번호 설정 읽기 실패 → ActComm.exe에서 설정한 번호랑 코드의 `ActLogicalStationNumber`가 일치하는지 확인

## 파일 구조

- `plc_opcua_bridge.py` — "완성본". D100을 1초마다 읽어서 OPC-UA 태그(`opc.tcp://0.0.0.0:4843/gxworks2/server/`)로 미러링만 함 (핸드셰이크 로직 없음, PLC→OPC-UA 단방향만).
- `opcua_client_test.py` — 그 태그를 읽어보는 테스트용 클라이언트.
- `00 Practice/` — 학습용으로 처음부터 다시 짜본 폴더 (`test.py`: 1~4단계 MX Component 기초, `02 server.py`: OPC-UA 서버 뼈대, `03 all in one.py`: 최종 합본, 연속 폴링 버전).
- `program.gxw` — GX Works2 프로젝트 파일.

## 포트 사용 현황 (충돌 방지용 기록)

- 4840: OpenPLC 기존 서버 (`plc with opcua` 프로젝트)
- 4841: 찬호봇 프로젝트 1차 서버
- 4842: 찬호봇 프로젝트 핸드셰이크 서버
- **4843**: `plc_opcua_bridge.py` (이 프로젝트 완성본)
- **4844**: `00 Practice` 학습용 서버

## 다음 단계 (미착수)

지금은 "PLC 값 쓰면 OPC-UA 태그로 읽어오는 것"까지만 구현된 상태 (사용자가 의도적으로 스코프 제한함). 다음에 확장한다면:
- Start/Qty/Busy/Finish 같은 양방향 핸드셰이크 (찬호봇 프로젝트에서 이미 해본 패턴 재사용 가능)
- 현재는 MX Component 호출(동기/블로킹)을 async 루프 안에 직접 넣고 있음 — 클라이언트가 여러 개이거나 PLC 응답이 느려지면 `run_in_executor`로 블로킹 호출을 분리하는 걸 고려할 것 (지금 스케일에서는 불필요, 의도적으로 단순하게 둔 것).
