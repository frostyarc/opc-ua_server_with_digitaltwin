import asyncio
import win32com.client
from asyncua import Server

PLC_DEVICE = "D100"
POLL_INTERVAL = 1  # 초

async def main():
    act = win32com.client.Dispatch("ActUtlType.ActMLUtlType")
    act.ActLogicalStationNumber = 1
    ret = act.Open()
    if ret != 0:
        print("PLC Open 실패:", hex(ret & 0xFFFFFFFF))
        return
    print("PLC 연결 성공")

    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4843/gxworks2/server/")
    idx = await server.register_namespace("urn:gxworks2:opcua:namespace")

    plc_obj = await server.nodes.objects.add_object(idx, "PLC")
    d100_var = await plc_obj.add_variable(idx, "D100", 0)

    print("OPC-UA 서버 시작 (포트 4843)")
    async with server:
        while True:
            ret, values = act.ReadDeviceBlock(PLC_DEVICE, 1, [0])
            if ret == 0:
                await d100_var.write_value(values[0])
                print(f"{PLC_DEVICE} = {values[0]}")
            await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())

# cd "C:\Users\kingp\OneDrive\Desktop\Programming\01 Python\05 TotalSys\02 작업\08-26"
# py -3.13-32 -u "C:\Users\kingp\OneDrive\Desktop\Programming\01 Python\05 TotalSys\02 작업\08-26\plc_opcua_bridge.py"
