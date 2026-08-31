from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from asyncua import Client, ua
import mysql.connector

OPCUA_URL = "opc.tcp://127.0.0.1:4846/dronefactory/server/"
NAMESPACE_URI = "urn:dronefactory:opcua:namespace"


def get_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="0000",
        database="drone_factory"
    )


app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>드론 주문 (실물 PLC)</title>
    </head>
    <body>
        <h1>드론 주문 (실물 PLC)</h1>
        <input type="number" id="qty" value="1" min="1">
        <button onclick="order()">주문</button>
        <p id="result"></p>

        <script>
            async function order() {
                const qty = document.getElementById("qty").value;
                document.getElementById("result").innerText = "접수 중...";

                const res = await fetch(`/order?quantity=${qty}`, { method: "POST" });
                const data = await res.json();

                document.getElementById("result").innerText =
                    `주문 #${data.order_id} 접수됨 - ${data.quantity}대 (${data.status})`;
            }
        </script>
    </body>
    </html>
    """


@app.post("/order")
async def create_order(quantity: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (lower_type, arm_type, upper_type, propeller_type, drone_type, quantity) "
        "VALUES (0, 0, 0, 0, 0, %s)",
        (quantity,)
    )
    conn.commit()
    order_id = cursor.lastrowid

    cursor.executemany(
        "INSERT INTO order_stage_status (order_id, stage, status) VALUES (%s, %s, 0)",
        [(order_id, stage) for stage in ("lower", "arm", "upper", "propeller")]
    )
    conn.commit()
    cursor.close()
    conn.close()

    async with Client(url=OPCUA_URL) as client:
        idx = await client.get_namespace_index(NAMESPACE_URI)
        plc_obj = await client.nodes.objects.get_child([f"{idx}:PLC"])
        await plc_obj.call_method(
            f"{idx}:SubmitOrder",
            ua.Variant(order_id, ua.VariantType.Int64),
            ua.Variant(quantity, ua.VariantType.Int64),
        )

    return {"order_id": order_id, "quantity": quantity, "status": "접수됨"}

# 실행코드1: Cd "C:\Users\kingp\OneDrive\Desktop\Programming\01 Python\05 TotalSys\02 작업\08-27"
# 실행코드2: python -m uvicorn web_app:app