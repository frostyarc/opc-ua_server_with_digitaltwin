import win32com.client

act = win32com.client.Dispatch("ActUtlType.ActMLUtlType")
act.ActLogicalStationNumber = 1   # ActComm.exe에서 설정한 번호와 동일하게

ret = act.Open()
print("Open 결과:", hex(ret))   # 0이면 성공

if ret == 0:
    ret, values = act.ReadDeviceBlock("D100", 2, [0, 0])
    print("쓰기 전 D100/D101:", ret, values)

    ret = act.WriteDeviceBlock("D100", 2, [1234, 5678])
    print("Write 결과:", ret)

    ret, values = act.ReadDeviceBlock("D100", 2, [0, 0])
    print("쓰기 후 D100/D101:", ret, values)

    act.Close()
