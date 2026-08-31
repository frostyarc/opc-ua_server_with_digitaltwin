import win32com.client

# "ActUtlType.ActMLUtlType"는 미쓰비시가 지은 이름(ProgID) - 우리가 못 바꿈.
# MX Component가 윈도우에 등록해놓은 COM 객체를 빌려오는 것.
act = win32com.client.Dispatch("ActUtlType.ActMLUtlType")

# 이 번호 자체엔 접속 정보가 없음. ActComm.exe(통신설정 유틸리티)에
# "1번"으로 저장해둔 설정(GX Simulator2, CPU 타입 등)을 찾아 쓰라는 지시일 뿐.
act.ActLogicalStationNumber = 1

# Open()이 실제 접속 시도. ret은 그냥 변수 이름(반환값을 담는 상자).
# 0이면 성공, 그 외엔 매뉴얼에 정의된 에러코드.
ret = act.Open()
if hex(ret & 0xFFFFFFFF)=="0x0":
    print("통신 성공!")

# ReadDeviceBlock(디바이스이름, 개수, 그릇)
# - "D100": 어디서부터 읽을지
# - 1: D100부터 몇 개 연속으로 읽을지
# - [0]: 원래(VB) 세상에선 값을 채워 돌려받는 그릇이지만,
#        파이썬 win32com에선 내용물은 버려지고 길이(개수)만 의미 있음.
# 결과가 (에러코드, 읽은값들) 튜플로 따로 나오는 게 win32com 특이사항.
Rret, values = act.ReadDeviceBlock("D100", 1, [0])
if Rret == 0:
    print(f'읽기 성공! D100: {values}')

Wret = act.WriteDeviceBlock("D100",1,[777])
if Wret == 0:
    print(f'쓰기 성공! D100: {values}')

# 실행 명령어
# py -3.13-32 -u "C:\Users\kingp\OneDrive\Desktop\Python\05 TotalSys\00 Practice\01 test.py"