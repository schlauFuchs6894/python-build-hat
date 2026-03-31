#!/usr/bin/env python3
import time
from multiprocessing import Process, Queue, set_start_method
from queue import Empty

from hat1_demo import run_hat1
from hat2_demo import run_hat2


def wait_for_event(evt_q: Queue, hat_id: int, expected: str, timeout: float = 10.0):
    deadline = time.time() + timeout
    buffer = []

    while time.time() < deadline:
        remaining = max(0.0, deadline - time.time())
        try:
            evt = evt_q.get(timeout=min(0.2, remaining))
        except Empty:
            continue

        if evt.get("hat") == hat_id and evt.get("event") == expected:
            for item in buffer:
                evt_q.put(item)
            return evt

        buffer.append(evt)

    for item in buffer:
        evt_q.put(item)

    raise TimeoutError(f"Timeout waiting for hat {hat_id} event '{expected}'")


def drain_events(evt_q: Queue, duration: float = 1.0):
    deadline = time.time() + duration
    while time.time() < deadline:
        try:
            evt = evt_q.get(timeout=0.1)
        except Empty:
            continue
        print(f"EVENT: {evt}")


def main():
    set_start_method("spawn", force=True)

    hat1_cmd_q = Queue()
    hat1_evt_q = Queue()
    hat2_cmd_q = Queue()
    hat2_evt_q = Queue()

    p1 = Process(target=run_hat1, args=(hat1_cmd_q, hat1_evt_q), daemon=True)
    p2 = Process(target=run_hat2, args=(hat2_cmd_q, hat2_evt_q), daemon=True)

    p1.start()
    p2.start()

    try:
        wait_for_event(hat1_evt_q, 1, "ready", timeout=20.0)
        wait_for_event(hat2_evt_q, 2, "ready", timeout=20.0)
        print("Both HAT workers are ready.")

        # 1) Read distance from Hat 1 Sensor D
        hat1_cmd_q.put({"action": "read_distance"})
        evt1 = wait_for_event(hat1_evt_q, 1, "distance", timeout=5.0)
        print(f"Hat 1 Sensor D distance: {evt1['value']}")

        # 2) Read distance from Hat 2 Sensor D
        hat2_cmd_q.put({"action": "read_distance"})
        evt2 = wait_for_event(hat2_evt_q, 2, "distance", timeout=5.0)
        print(f"Hat 2 Sensor D distance: {evt2['value']}")

        # 3) Run Motor 1 on Hat 1 Motor A
        hat1_cmd_q.put({"action": "motor_start", "speed": 30})
        wait_for_event(hat1_evt_q, 1, "motor_started", timeout=5.0)
        print("Hat 1 Motor A started.")

        # 4) Run Motor 2 on Hat 2 Motor A
        hat2_cmd_q.put({"action": "motor_start", "speed": 30})
        wait_for_event(hat2_evt_q, 2, "motor_started", timeout=5.0)
        print("Hat 2 Motor A started.")

        time.sleep(3.0)

        # Stop both motors again
        hat1_cmd_q.put({"action": "motor_stop"})
        hat2_cmd_q.put({"action": "motor_stop"})
        wait_for_event(hat1_evt_q, 1, "motor_stopped", timeout=5.0)
        wait_for_event(hat2_evt_q, 2, "motor_stopped", timeout=5.0)
        print("Both motors stopped.")

    finally:
        hat1_cmd_q.put({"action": "shutdown"})
        hat2_cmd_q.put({"action": "shutdown"})

        try:
            wait_for_event(hat1_evt_q, 1, "stopped", timeout=5.0)
        except Exception:
            pass

        try:
            wait_for_event(hat2_evt_q, 2, "stopped", timeout=5.0)
        except Exception:
            pass

        p1.join(timeout=2.0)
        p2.join(timeout=2.0)


if __name__ == "__main__":
    main()