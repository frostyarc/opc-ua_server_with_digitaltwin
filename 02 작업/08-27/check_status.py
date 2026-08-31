import asyncio
from asyncua import Client

async def main():
    async with Client(url="opc.tcp://127.0.0.1:4846/dronefactory/server/") as client:
        idx = await client.get_namespace_index("urn:dronefactory:opcua:namespace")
        plc_obj = await client.nodes.objects.get_child([f"{idx}:PLC"])

        for name in ["Order_Accept", "Under_Start", "Under_Busy", "Arm_Busy", "Pro_Finish"]:
            node = await plc_obj.get_child([f"{idx}:{name}"])
            value = await node.read_value()
            print(f"{name} = {value}")

if __name__ == "__main__":
    asyncio.run(main())
