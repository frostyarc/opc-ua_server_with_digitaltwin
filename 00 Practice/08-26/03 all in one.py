import win32com.client
import asyncio
from asyncua import Server

act = win32com.client.Dispatch("ActUtlType.ActMLUtlType")
act.ActLogicalStationNumber = 1
act.open()

async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4844/study/server/")
    idx = await server.register_namespace("urn:study:opcua")

    plc_obj = await server.nodes.objects.add_object(idx, "PLC")
    d100_var = await plc_obj.add_variable(idx, "D100", 0)

    async with server:
       
        while True:
            Rret, values = act.ReadDeviceBlock("D100", 1, [0])
            await d100_var.write_value(values[0])
            print(f'D100의 값은 {values} 입니다.')

            await asyncio.sleep(1)


asyncio.run(main())

# 실행 명령어
# py -3.13-32 -u "C:\Users\kingp\OneDrive\Desktop\Python\05 TotalSys\00 Practice\03 all in one.py"