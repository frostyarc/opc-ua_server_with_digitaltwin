import asyncio
import pymcprotocol
from asyncua import Server

PLC_IP = "192.168.3.39"   # GX Works2 이더넷포트 파라미터에서 설정한 PLC IP로 변경
PLC_PORT = 5010
PLC_DEVICE = "D100"
POLL_INTERVAL = 1  # 초

async def main():
    pymc = pymcprotocol.Type3E()
    pymc.connect(PLC_IP, PLC_PORT)
    print("PLC 연결 성공")

    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4845/plc/server/")
    idx = await server.register_namespace("urn:plc:opcua:namespace")

    plc_obj = await server.nodes.objects.add_object(idx, "PLC")
    d100_var = await plc_obj.add_variable(idx, "D100", 0)

    print("OPC-UA 서버 시작 (포트 4845)")
    async with server:
        while True:
            values = pymc.batchread_wordunits(headdevice=PLC_DEVICE, readsize=1)
            await d100_var.write_value(values[0])
            print(f"{PLC_DEVICE} = {values[0]}")
            await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
