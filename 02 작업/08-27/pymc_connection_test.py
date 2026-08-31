import pymcprotocol

PLC_IP = "192.168.3.39"   # GX Works2 이더넷포트 파라미터에서 설정한 PLC IP로 변경
PLC_PORT = 5010            # Open 설정에서 지정한 포트
PLC_DEVICE1 = "D100"
PLC_DEVICE2 = "M10"

pymc = pymcprotocol.Type3E()
pymc.connect(PLC_IP, PLC_PORT)
print("연결 성공")

values = pymc.batchread_wordunits(headdevice=PLC_DEVICE1, readsize=1)
print(f"{PLC_DEVICE1} = {values[0]}")

pymc.batchwrite_wordunits(headdevice=PLC_DEVICE1, values=[1234])
print(f"{PLC_DEVICE1}에 1234 씀")

pymc.batchwrite_bitunits(headdevice=PLC_DEVICE2, values=[1])
print(f"{PLC_DEVICE2} ON")

values = pymc.batchread_wordunits(headdevice=PLC_DEVICE1, readsize=1)
print(f"{PLC_DEVICE1} = {values[0]} (쓰기 확인)")

pymc.close()
