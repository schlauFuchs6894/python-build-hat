#!/usr/bin/env python3
import os
from multiprocessing import Queue
from queue import Empty

from buildhat import Hat, ColorDistanceSensor, Motor


def run_hat1(cmd_q: Queue, evt_q: Queue) -> None:
    """
    Worker process for Build HAT 1.
    Sensor on port D, motor on port A.
    """
    print(f"[HAT1] process started, PID={os.getpid()}", flush=True)
    Hat(
        device="/dev/ttyAMA0",
        reset_gpio=4,
        boot0_gpio=22,
        debug=False,
    )

    sensor_d = ColorDistanceSensor("D")
    motor_a = Motor("A")
    motor_a.set_default_speed(30)

    evt_q.put({"hat": 1, "event": "ready"})

    running = True
    while running:
        try:
            cmd = cmd_q.get(timeout=0.1)
        except Empty:
            continue

        action = cmd.get("action")

        if action == "read_distance":
            try:
                distance = sensor_d.get_distance()
                evt_q.put(
                    {
                        "hat": 1,
                        "event": "distance",
                        "value": distance,
                    }
                )
            except Exception as exc:
                evt_q.put(
                    {
                        "hat": 1,
                        "event": "error",
                        "message": f"distance read failed: {exc}",
                    }
                )

        elif action == "motor_start":
            speed = int(cmd.get("speed", 30))
            try:
                motor_a.start(speed)
                evt_q.put(
                    {
                        "hat": 1,
                        "event": "motor_started",
                        "speed": speed,
                    }
                )
            except Exception as exc:
                evt_q.put(
                    {
                        "hat": 1,
                        "event": "error",
                        "message": f"motor start failed: {exc}",
                    }
                )

        elif action == "motor_stop":
            try:
                motor_a.stop()
                evt_q.put({"hat": 1, "event": "motor_stopped"})
            except Exception as exc:
                evt_q.put(
                    {
                        "hat": 1,
                        "event": "error",
                        "message": f"motor stop failed: {exc}",
                    }
                )

        elif action == "shutdown":
            try:
                motor_a.stop()
            except Exception:
                pass
            evt_q.put({"hat": 1, "event": "stopped"})
            running = False

        else:
            evt_q.put(
                {
                    "hat": 1,
                    "event": "error",
                    "message": f"unknown action: {action}",
                }
            )


if __name__ == "__main__":
    raise SystemExit(
        "This module is intended to be started from control_demo.py"
    )


