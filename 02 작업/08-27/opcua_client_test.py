import asyncio
from asyncua import Client

async def main():
    async with Client(url="opc.tcp://127.0.0.1:4845/plc/server/") as client:
        idx = await client.get_namespace_index("urn:plc:opcua:namespace")
        plc_obj = await client.nodes.objects.get_child([f"{idx}:PLC"])
        d100_var = await plc_obj.get_child([f"{idx}:D100"])

        for _ in range(5):
            value = await d100_var.read_value()
            print("D100 =", value)
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
