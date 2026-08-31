import asyncio
from asyncua import Client
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

OPCUA_URL = "opc.tcp://127.0.0.1:4846/dronefactory/server/"
NAMESPACE_URI = "urn:dronefactory:opcua:namespace"

# OPC-UA Start 변수 브라우즈네임 -> (웹 디지털트윈 티칭 프로그램 이름, 종료신호 메서드)
# station_name은 scene.js/teaching.js에 저장된 티칭 프로그램 이름과 정확히 일치해야 함
STATIONS = {
    "Under_Start": {"station_name": "하부공급", "finish_method": "NotifyUnderFinish"},
    "Arm_Start": {"station_name": "암조립", "finish_method": "NotifyArmFinish"},
    "Upper_Start": {"station_name": "상부조립", "finish_method": "NotifyUpperFinish"},
    "Propeller_Start": {"station_name": "프로펠러조립", "finish_method": "NotifyPropellerFinish"},
}
FINISH_METHOD_BY_STATION = {v["station_name"]: v["finish_method"] for v in STATIONS.values()}

app = FastAPI()
browser_clients: set[WebSocket] = set()
plc_ref = {}  # opcua_watcher가 채워두는 {"client", "idx", "station_obj"}


async def broadcast(message: dict):
    dead = set()
    for ws in browser_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    browser_clients.difference_update(dead)


class StationChangeHandler:
    def __init__(self, node_to_station: dict):
        self.node_to_station = node_to_station

    async def datachange_notification(self, node, val, data):
        if not val:
            return
        station_name = self.node_to_station.get(node.nodeid.to_string())
        if station_name:
            await broadcast({"station": station_name, "event": "start"})


async def notify_finish(station_name: str):
    method = FINISH_METHOD_BY_STATION.get(station_name)
    if method is None or not plc_ref:
        return
    idx = plc_ref["idx"]
    await plc_ref["station_obj"].call_method(f"{idx}:{method}")


async def opcua_watcher():
    # opcua_server.py는 PLC 연결까지 마쳐야 포트를 열기 때문에 이 브릿지보다 늦게
    # 준비될 수 있음(또는 나중에 재시작될 수도 있음) - 접속 실패/끊김 시 계속 재시도.
    while True:
        try:
            async with Client(url=OPCUA_URL) as client:
                idx = await client.get_namespace_index(NAMESPACE_URI)
                station_obj = await client.nodes.objects.get_child([f"{idx}:PLC"])
                plc_ref["client"] = client
                plc_ref["idx"] = idx
                plc_ref["station_obj"] = station_obj

                node_to_station = {}
                var_nodes = []
                for browse_name, info in STATIONS.items():
                    var_node = await station_obj.get_child([f"{idx}:{browse_name}"])
                    node_to_station[var_node.nodeid.to_string()] = info["station_name"]
                    var_nodes.append(var_node)

                handler = StationChangeHandler(node_to_station)
                sub = await client.create_subscription(200, handler)
                await sub.subscribe_data_change(var_nodes)

                print("OPC-UA 구독 시작, 브릿지 준비 완료")
                while True:
                    await asyncio.sleep(3600)
        except Exception as e:
            plc_ref.clear()
            print(f"OPC-UA 서버({OPCUA_URL}) 접속 실패/끊김: {e} - 3초 후 재시도")
            await asyncio.sleep(3)


@app.on_event("startup")
async def startup():
    asyncio.create_task(opcua_watcher())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    browser_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("event") == "finish":
                await notify_finish(data.get("station"))
    except WebSocketDisconnect:
        browser_clients.discard(websocket)

# 실행코드1: cd "C:\Users\kingp\OneDrive\Desktop\Programming\01 Python\05 TotalSys\02 작업\08-31"
# 실행코드2: python -m uvicorn bridge_server:app --port 8765
# (opcua_server.py를 먼저 켜둔 상태에서 실행할 것 - 브릿지가 시작할 때 바로 OPC-UA 서버에 접속을 시도함)
#
# 브라우저(scene.js) 쪽 연동 메시지 규격:
#   서버->브라우저: {"station": "하부공급", "event": "start"}   (station: 하부공급/암조립/상부조립/프로펠러조립)
#   브라우저->서버: {"station": "하부공급", "event": "finish"}  (해당 이름의 티칭 프로그램 재생이 끝났을 때 전송)
