#!/usr/bin/env python3
import time
from multiprocessing import Queue
from queue import Empty

from buildhat import Hat, ColorDistanceSensor, Motor

def run_hat2(cmd_q: Queue, evt_q: Queue) -> None:
    print(f"[HAT2] process started, PID={os.getpid()}", flush=True)
    try:
        Hat(
            device="/dev/ttyAMA4",
            reset_gpio=25,
            boot0_gpio=24,
            debug=True,
        )
        print(f"[HAT2] init SensorS and Actors")
        sensor_d = ColorDistanceSensor("D")
        motor_a = Motor("A")
        motor_a.set_default_speed(30)

    except Exception as exc:
        evt_q.put(
            {
                "hat": 2,
                "event": "error",
                "message": f"init failed: {type(exc).__name__}: {exc}",
            }
        )
        return

    evt_q.put({"hat": 2, "event": "ready"})

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
                evt_q.put({"hat": 2, "event": "distance", "value": distance})
            except Exception as exc:
                evt_q.put(
                    {
                        "hat": 2,
                        "event": "error",
                        "message": f"distance read failed: {type(exc).__name__}: {exc}",
                    }
                )

        elif action == "motor_start":
            speed = int(cmd.get("speed", 30))
            try:
                motor_a.start(speed)
                evt_q.put({"hat": 2, "event": "motor_started", "speed": speed})
            except Exception as exc:
                evt_q.put(
                    {
                        "hat": 2,
                        "event": "error",
                        "message": f"motor start failed: {type(exc).__name__}: {exc}",
                    }
                )

        elif action == "motor_stop":
            try:
                motor_a.stop()
                evt_q.put({"hat": 2, "event": "motor_stopped"})
            except Exception as exc:
                evt_q.put(
                    {
                        "hat": 2,
                        "event": "error",
                        "message": f"motor stop failed: {type(exc).__name__}: {exc}",
                    }
                )

        elif action == "shutdown":
            try:
                motor_a.stop()
            except Exception:
                pass
            evt_q.put({"hat": 2, "event": "stopped"})
            running = False

        else:
            evt_q.put(
                {
                    "hat": 2,
                    "event": "error",
                    "message": f"unknown action: {action}",
                }
            )


if __name__ == "__main__":
    raise SystemExit(
        "This module is intended to be started from control_demo.py"
    )