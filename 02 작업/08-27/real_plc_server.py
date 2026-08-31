import asyncio
import pymcprotocol
import mysql.connector
from asyncua import Server, ua

PLC_IP = "192.168.3.39"
PLC_PORT = 5010


def get_db():
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="0000",
        database="drone_factory"
    )


def set_stage_status(order_id, stage, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE order_stage_status SET status = %s WHERE order_id = %s AND stage = %s",
        (status, order_id, stage)
    )
    conn.commit()
    cursor.close()
    conn.close()


def increment_completed(order_id, stage):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE order_stage_status SET completed_count = completed_count + 1 WHERE order_id = %s AND stage = %s",
        (order_id, stage)
    )
    conn.commit()
    cursor.execute(
        "SELECT completed_count FROM order_stage_status WHERE order_id = %s AND stage = %s",
        (order_id, stage)
    )
    new_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return new_count

# M10: CPS -> PLC. 하부 공급 트리거. 이 신호를 안 보내면 PLC 자동시퀀스가 안 돎.
M_ORDER_ACCEPT = "M10"
# 이하 전부 PLC -> CPS, 읽기 전용 (쓰면 안 됨)
M_UNDER_START = "M100"
M_UNDER_BUSY = "M111"     # 하부 가동중
M_ARM_BUSY = "M121"       # 암 조립 가동중
M_UPPER_BUSY = "M131"     # 상부 조립 가동중
M_PROP_BUSY = "M141"      # 프로펠러 조립 가동중
M_PRO_FINISH = "M142"     # 프로펠러 조립(전체 라인) 완료

POLL_INTERVAL = 1  # 초

orders_pending = []
orders_in_flight = []
order_quantity = {}  # order_id -> 주문 수량 (마지막 유닛 완료 판정용)

# 파이프라인 각 스테이션에 현재 어떤 주문이 있는지 (하부 -> 암 -> 상부 -> 프로펠러 순서로 넘어감)
STAGE_UNDER, STAGE_ARM, STAGE_UPPER, STAGE_PROP = range(4)


async def plc_worker(pymc, nodes):
    (order_accept_var, under_start_var, under_busy_var,
     arm_busy_var, upper_busy_var, prop_busy_var, pro_finish_var) = nodes

    prev_under_busy = False
    prev_arm_busy = False
    prev_upper_busy = False
    prev_prop_busy = False
    prev_pro_finish = False

    stage_orders = [None, None, None, None]

    while True:
        under_start = bool(pymc.batchread_bitunits(headdevice=M_UNDER_START, readsize=1)[0])
        under_busy = bool(pymc.batchread_bitunits(headdevice=M_UNDER_BUSY, readsize=1)[0])
        arm_busy = bool(pymc.batchread_bitunits(headdevice=M_ARM_BUSY, readsize=1)[0])
        upper_busy = bool(pymc.batchread_bitunits(headdevice=M_UPPER_BUSY, readsize=1)[0])
        prop_busy = bool(pymc.batchread_bitunits(headdevice=M_PROP_BUSY, readsize=1)[0])
        pro_finish = bool(pymc.batchread_bitunits(headdevice=M_PRO_FINISH, readsize=1)[0])

        await under_start_var.write_value(under_start)
        await under_busy_var.write_value(under_busy)
        await arm_busy_var.write_value(arm_busy)
        await upper_busy_var.write_value(upper_busy)
        await prop_busy_var.write_value(prop_busy)
        await pro_finish_var.write_value(pro_finish)

        # 입구 조건: 하부/암 둘 다 안 바쁘고, 하부 스테이션이 비어있을 때만 다음 주문 투입
        if not under_busy and not arm_busy and stage_orders[STAGE_UNDER] is None and orders_pending:
            next_order = orders_pending.pop(0)
            orders_in_flight.append(next_order)
            stage_orders[STAGE_UNDER] = next_order
            pymc.batchwrite_bitunits(headdevice=M_ORDER_ACCEPT, values=[1])
            await order_accept_var.write_value(True)

        # 하부busy 상승엣지 = 하부공급공정이 실제로 시작된 시점 -> 트리거(M10) 내림
        if under_busy and not prev_under_busy:
            pymc.batchwrite_bitunits(headdevice=M_ORDER_ACCEPT, values=[0])
            await order_accept_var.write_value(False)
            set_stage_status(stage_orders[STAGE_UNDER], "lower", 1)

        # 이후 스테이션은 앞 스테이션에서 주문을 순서대로 넘겨받는 파이프라인
        if arm_busy and not prev_arm_busy:
            stage_orders[STAGE_ARM] = stage_orders[STAGE_UNDER]
            stage_orders[STAGE_UNDER] = None
            set_stage_status(stage_orders[STAGE_ARM], "lower", 2)
            increment_completed(stage_orders[STAGE_ARM], "lower")
            set_stage_status(stage_orders[STAGE_ARM], "arm", 1)

        if upper_busy and not prev_upper_busy:
            stage_orders[STAGE_UPPER] = stage_orders[STAGE_ARM]
            stage_orders[STAGE_ARM] = None
            set_stage_status(stage_orders[STAGE_UPPER], "arm", 2)
            increment_completed(stage_orders[STAGE_UPPER], "arm")
            set_stage_status(stage_orders[STAGE_UPPER], "upper", 1)

        if prop_busy and not prev_prop_busy:
            stage_orders[STAGE_PROP] = stage_orders[STAGE_UPPER]
            stage_orders[STAGE_UPPER] = None
            set_stage_status(stage_orders[STAGE_PROP], "upper", 2)
            increment_completed(stage_orders[STAGE_PROP], "upper")
            set_stage_status(stage_orders[STAGE_PROP], "propeller", 1)

        # 프로펠러피니시 상승엣지 = 프로펠러 스테이션에 있던 주문 완료
        if pro_finish and not prev_pro_finish:
            done_order = stage_orders[STAGE_PROP]
            stage_orders[STAGE_PROP] = None
            if done_order is not None:
                if done_order in orders_in_flight:
                    orders_in_flight.remove(done_order)
                completed = increment_completed(done_order, "propeller")
                total = order_quantity.get(done_order, 1)

                if completed >= total:
                    set_stage_status(done_order, "propeller", 2)
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE orders SET finish_date = NOW() WHERE id = %s",
                        (done_order,)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()

        prev_under_busy = under_busy
        prev_arm_busy = arm_busy
        prev_upper_busy = upper_busy
        prev_prop_busy = prop_busy
        prev_pro_finish = pro_finish

        await asyncio.sleep(POLL_INTERVAL)


async def main():
    pymc = pymcprotocol.Type3E()
    pymc.connect(PLC_IP, PLC_PORT)
    print("PLC 연결 성공")

    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4846/dronefactory/server/")
    idx = await server.register_namespace("urn:dronefactory:opcua:namespace")

    plc_obj = await server.nodes.objects.add_object(idx, "PLC")
    order_accept_var = await plc_obj.add_variable(idx, "Order_Accept", False)  # M10
    under_start_var = await plc_obj.add_variable(idx, "Under_Start", False)   # M100
    under_busy_var = await plc_obj.add_variable(idx, "Under_Busy", False)     # M111
    arm_busy_var = await plc_obj.add_variable(idx, "Arm_Busy", False)         # M121
    upper_busy_var = await plc_obj.add_variable(idx, "Upper_Busy", False)     # M131
    prop_busy_var = await plc_obj.add_variable(idx, "Propeller_Busy", False)  # M141
    pro_finish_var = await plc_obj.add_variable(idx, "Pro_Finish", False)     # M142

    async def submit_order(parent, order_id, quantity):
        order_quantity[order_id.Value] = quantity.Value
        for _ in range(quantity.Value):
            orders_pending.append(order_id.Value)
        return [ua.Variant(True, ua.VariantType.Boolean)]

    await plc_obj.add_method(
        idx, "SubmitOrder", submit_order,
        [ua.VariantType.Int64, ua.VariantType.Int64],
        [ua.VariantType.Boolean],
    )

    print("OPC-UA 서버 시작 (포트 4846)")
    async with server:
        await plc_worker(pymc, (
            order_accept_var, under_start_var, under_busy_var,
            arm_busy_var, upper_busy_var, prop_busy_var, pro_finish_var,
        ))


if __name__ == "__main__":
    asyncio.run(main())
