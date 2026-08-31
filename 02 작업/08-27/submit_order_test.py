import asyncio
from asyncua import Client, ua

ORDER_IDS = [1, 2, 3]

async def main():
    async with Client(url="opc.tcp://127.0.0.1:4846/dronefactory/server/") as client:
        idx = await client.get_namespace_index("urn:dronefactory:opcua:namespace")
        plc_obj = await client.nodes.objects.get_child([f"{idx}:PLC"])

        for order_id in ORDER_IDS:
            args = [
                ua.Variant(order_id, ua.VariantType.Int64),
                ua.Variant(1, ua.VariantType.Int64),  # quantity
            ]
            result = await plc_obj.call_method(f"{idx}:SubmitOrder", *args)
            print(f"주문 {order_id} 제출 결과:", result)

if __name__ == "__main__":
    asyncio.run(main())
