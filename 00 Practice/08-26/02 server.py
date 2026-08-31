import asyncio
from asyncua import Server

async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4844/study/server/")
    idx = await server.register_namespace("urn:study:opcua")

    plc_obj = await server.nodes.objects.add_object(idx, "PLC")
    d100_var = await plc_obj.add_variable(idx, "D100", 0)

    async with server:
        while True:
            await asyncio.sleep(1)

asyncio.run(main())