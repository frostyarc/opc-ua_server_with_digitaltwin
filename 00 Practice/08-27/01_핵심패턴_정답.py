"""
01_핵심패턴_연습.py 정답. 먼저 직접 풀어본 다음에만 열어보세요.
"""

# 문제 1
readings = [False, False, True, True, True, False, True, True]

prev = False

for value in readings:
    if value and not prev:
        print("엣지 감지!")
    prev = value


# 문제 2
orders_pending = [101, 102, 103]
orders_in_flight = []

next_order = orders_pending.pop(0)
orders_in_flight.append(next_order)

print(next_order, orders_pending, orders_in_flight)


# 문제 3
STAGE_UNDER, STAGE_ARM = 0, 1
stage_orders = [101, None]

stage_orders[STAGE_ARM] = stage_orders[STAGE_UNDER]
stage_orders[STAGE_UNDER] = None

print(stage_orders)
