"""Motor device handling functionality"""

import threading
import time
from collections import deque
from concurrent.futures import Future
from enum import Enum
from threading import Condition

from .devices import Device
from .exc import MotorError


class PassiveMotor(Device):
    """Passive Motor device

    :param port: Port of device
    :param kwargs: Forwarded to :class:`Device` (e.g. ``hat_instance=``)
    :raises DeviceError: Occurs if there is no passive motor attached to port
    """

    def __init__(self, port, **kwargs):
        super().__init__(port, **kwargs)
        self._default_speed = 20
        self._currentspeed  = 0
        self.plimit(0.7)

    def set_default_speed(self, default_speed):
        """Set default speed (-100 to 100)."""
        if not (-100 <= default_speed <= 100):
            raise MotorError("Invalid Speed")
        self._default_speed = default_speed

    def start(self, speed=None):
        """Start motor at *speed* (-100 to 100)."""
        if self._currentspeed == speed:
            return
        if speed is None:
            speed = self._default_speed
        else:
            if not (-100 <= speed <= 100):
                raise MotorError("Invalid Speed")
        self._currentspeed = speed
        self._write(f"port {self.port} ; pwm ; set {speed / 100}\r")

    def stop(self):
        """Stop motor."""
        self._write(f"port {self.port} ; off\r")
        self._currentspeed = 0

    def plimit(self, plimit):
        """Power limit (0–1)."""
        if not (0 <= plimit <= 1):
            raise MotorError("plimit should be 0 to 1")
        self._write(f"port {self.port} ; port_plimit {plimit}\r")

    def bias(self, bias):
        """Removed in 0.6.0."""
        raise MotorError("Bias no longer available")


class MotorRunmode(Enum):
    """Current mode motor is in"""
    NONE    = 0
    FREE    = 1
    DEGREES = 2
    SECONDS = 3


class Motor(Device):
    """Motor device

    :param port: Port of device
    :param kwargs: Forwarded to :class:`Device` (e.g. ``hat_instance=``)
    :raises DeviceError: Occurs if there is no motor attached to port
    """

    def __init__(self, port, **kwargs):
        super().__init__(port, **kwargs)
        self.default_speed = 20
        self._currentspeed = 0
        if self._typeid in {38}:
            self.mode([(1, 0), (2, 0)])
            self._combi  = "1 0 2 0"
            self._noapos = True
        else:
            self.mode([(1, 0), (2, 0), (3, 0)])
            self._combi  = "1 0 2 0 3 0"
            self._noapos = False
        self.plimit(0.7)
        self.pwmparams(0.65, 0.01)
        self._rpm     = False
        self._release = True
        self._bqueue  = deque(maxlen=5)
        self._cvqueue = Condition()
        self.when_rotated = None
        self._oldpos  = None
        self._runmode = MotorRunmode.NONE

    def set_speed_unit_rpm(self, rpm=False):
        """Use RPM instead of percent for speed units."""
        self._rpm = rpm

    def set_default_speed(self, default_speed):
        """Set default speed (-100 to 100)."""
        if not (-100 <= default_speed <= 100):
            raise MotorError("Invalid Speed")
        self.default_speed = default_speed

    def run_for_rotations(self, rotations, speed=None, blocking=True):
        """Run motor for N rotations."""
        self._runmode = MotorRunmode.DEGREES
        spd = self.default_speed if speed is None else speed
        if not (-100 <= spd <= 100):
            raise MotorError("Invalid Speed")
        self.run_for_degrees(int(rotations * 360), spd, blocking)

    def _run_for_degrees(self, degrees, speed):
        self._runmode = MotorRunmode.DEGREES
        mul = 1
        if speed < 0:
            speed, mul = abs(speed), -1
        pos    = self.get_position()
        newpos = ((degrees * mul) + pos) / 360.0
        self._run_positional_ramp(pos / 360.0, newpos, speed)
        self._runmode = MotorRunmode.NONE

    def _run_to_position(self, degrees, speed, direction):
        self._runmode = MotorRunmode.DEGREES
        data  = self.get()
        pos   = data[1]
        apos  = pos if self._noapos else data[2]
        diff  = (degrees - apos + 180) % 360 - 180
        newpos = (pos + diff) / 360
        v1 = (degrees - apos) % 360
        v2 = (apos  - degrees) % 360
        mul = -1 if diff > 0 else 1
        diff = sorted([diff, mul * (v2 if abs(diff) == v1 else v1)])
        if direction == "shortest":
            pass
        elif direction == "clockwise":
            newpos = (pos + diff[1]) / 360
        elif direction == "anticlockwise":
            newpos = (pos + diff[0]) / 360
        else:
            raise MotorError("Invalid direction, should be: shortest, clockwise or anticlockwise")
        self._run_positional_ramp(pos / 360.0, newpos, speed)
        self._runmode = MotorRunmode.NONE

    def _run_positional_ramp(self, pos, newpos, speed):
        if self._rpm:
            speed = self._speed_process(speed)
        else:
            speed *= 0.05
        dur = abs((newpos - pos) / speed)
        cmd = (f"port {self.port}; select 0 ; selrate {self._interval}; "
               f"pid {self.port} 0 1 s4 0.0027777778 0 5 0 .1 3 0.01; "
               f"set ramp {pos} {newpos} {dur} 0\r")
        ftr = Future()
        self._hat.rampftr[self.port].append(ftr)
        self._write(cmd)
        ftr.result()
        if self._release:
            time.sleep(0.2)
            self.coast()

    def run_for_degrees(self, degrees, speed=None, blocking=True):
        """Run motor for N degrees."""
        self._runmode = MotorRunmode.DEGREES
        spd = self.default_speed if speed is None else speed
        if not (-100 <= spd <= 100):
            raise MotorError("Invalid Speed")
        if not blocking:
            self._queue((self._run_for_degrees, (degrees, spd)))
        else:
            self._wait_for_nonblocking()
            self._run_for_degrees(degrees, spd)

    def run_to_position(self, degrees, speed=None, blocking=True, direction="shortest"):
        """Run motor to absolute position (-180 to 180 degrees)."""
        self._runmode = MotorRunmode.DEGREES
        spd = self.default_speed if speed is None else speed
        if not (0 <= spd <= 100):
            raise MotorError("Invalid Speed")
        if degrees < -180 or degrees > 180:
            raise MotorError("Invalid angle")
        if not blocking:
            self._queue((self._run_to_position, (degrees, spd, direction)))
        else:
            self._wait_for_nonblocking()
            self._run_to_position(degrees, spd, direction)

    def _run_for_seconds(self, seconds, speed):
        speed = self._speed_process(speed)
        self._runmode = MotorRunmode.SECONDS
        if self._rpm:
            pid = f"pid_diff {self.port} 0 5 s2 0.0027777778 1 0 2.5 0 .4 0.01; "
        else:
            pid = f"pid {self.port} 0 0 s1 1 0 0.003 0.01 0 100 0.01;"
        cmd = (f"port {self.port} ; select 0 ; selrate {self._interval}; "
               f"{pid}"
               f"set pulse {speed} 0.0 {seconds} 0\r")
        ftr = Future()
        self._hat.pulseftr[self.port].append(ftr)
        self._write(cmd)
        ftr.result()
        if self._release:
            self.coast()
        self._runmode = MotorRunmode.NONE

    def run_for_seconds(self, seconds, speed=None, blocking=True):
        """Run motor for N seconds."""
        self._runmode = MotorRunmode.SECONDS
        spd = self.default_speed if speed is None else speed
        if not (-100 <= spd <= 100):
            raise MotorError("Invalid Speed")
        if not blocking:
            self._queue((self._run_for_seconds, (seconds, spd)))
        else:
            self._wait_for_nonblocking()
            self._run_for_seconds(seconds, spd)

    def start(self, speed=None):
        """Start motor continuously."""
        self._wait_for_nonblocking()
        if self._runmode == MotorRunmode.FREE:
            if self._currentspeed == speed:
                return
        elif self._runmode != MotorRunmode.NONE:
            return
        spd = self.default_speed if speed is None else speed
        if not (-100 <= spd <= 100):
            raise MotorError("Invalid Speed")
        spd = self._speed_process(spd)
        if self._runmode == MotorRunmode.NONE:
            if self._rpm:
                pid = f"pid_diff {self.port} 0 5 s2 0.0027777778 1 0 2.5 0 .4 0.01; "
            else:
                pid = f"pid {self.port} 0 0 s1 1 0 0.003 0.01 0 100 0.01; "
            cmd = (f"port {self.port} ; select 0 ; selrate {self._interval}; "
                   f"{pid}set {spd}\r")
        else:
            cmd = f"port {self.port} ; set {spd}\r"
        self._runmode      = MotorRunmode.FREE
        self._currentspeed = spd
        self._write(cmd)

    def stop(self):
        """Stop motor."""
        self._wait_for_nonblocking()
        self._runmode      = MotorRunmode.NONE
        self._currentspeed = 0
        self.coast()

    def get_position(self):
        """Position relative to preset (degrees, may be negative).

        :rtype: int
        """
        return self.get()[1]

    def get_aposition(self):
        """Absolute position (-180 to 180 degrees).

        :rtype: int
        :raises MotorError: Motor has no absolute position sensor.
        """
        if self._noapos:
            raise MotorError("No absolute position with this motor")
        return self.get()[2]

    def get_speed(self):
        """:rtype: int"""
        return self.get()[0]

    @property
    def when_rotated(self):
        """Callback invoked when the motor rotates."""
        return self._when_rotated

    def _intermediate(self, data):
        if self._noapos:
            speed, pos = data
            apos = None
        else:
            speed, pos, apos = data
        if self._oldpos is None:
            self._oldpos = pos
            return
        if abs(pos - self._oldpos) >= 1:
            if self._when_rotated is not None:
                self._when_rotated(speed, pos, apos)
            self._oldpos = pos

    @when_rotated.setter
    def when_rotated(self, value):
        self._when_rotated = value
        self.callback(self._intermediate)

    def plimit(self, plimit):
        """Power limit (0–1)."""
        if not (0 <= plimit <= 1):
            raise MotorError("plimit should be 0 to 1")
        self._write(f"port {self.port} ; port_plimit {plimit}\r")

    def bias(self, bias):
        """Removed in 0.6.0."""
        raise MotorError("Bias no longer available")

    def pwmparams(self, pwmthresh, minpwm):
        """PWM thresholds."""
        if not (0 <= pwmthresh <= 1):
            raise MotorError("pwmthresh should be 0 to 1")
        if not (0 <= minpwm <= 1):
            raise MotorError("minpwm should be 0 to 1")
        self._write(f"port {self.port} ; pwmparams {pwmthresh} {minpwm}\r")

    def pwm(self, pwmv):
        """Direct PWM drive (-1 to 1)."""
        if not (-1 <= pwmv <= 1):
            raise MotorError("pwm should be -1 to 1")
        self._write(f"port {self.port} ; pwm ; set {pwmv}\r")

    def coast(self):
        """Coast motor."""
        self._write(f"port {self.port} ; coast\r")

    def float(self):
        """Float motor."""
        self.pwm(0)

    @property
    def release(self):
        """Whether motor is released (hand-turnable) after a run."""
        return self._release

    @release.setter
    def release(self, value):
        if not isinstance(value, bool):
            raise MotorError("Must pass boolean")
        self._release = value

    def _queue(self, cmd):
        self._hat_instance.motorqueue[self.port].put(cmd)

    def _wait_for_nonblocking(self):
        """Block until all queued non-blocking commands finish."""
        self._hat_instance.motorqueue[self.port].join()

    def _speed_process(self, speed):
        return speed / 60 if self._rpm else speed


class MotorPair:
    """Pair of motors driven together.

    :param leftport: Port letter for the left motor.
    :param rightport: Port letter for the right motor.
    :param kwargs: Forwarded to both :class:`Motor` constructors
        (e.g. ``hat_instance=``).
    :raises DeviceError: No motor attached to port.
    """

    def __init__(self, leftport, rightport, **kwargs):
        super().__init__()
        self._leftmotor  = Motor(leftport,  **kwargs)
        self._rightmotor = Motor(rightport, **kwargs)
        self.default_speed = 20
        self._release = True
        self._rpm     = False

    def set_default_speed(self, default_speed):
        self.default_speed = default_speed

    def set_speed_unit_rpm(self, rpm=False):
        self._rpm = rpm
        self._leftmotor.set_speed_unit_rpm(rpm)
        self._rightmotor.set_speed_unit_rpm(rpm)

    def run_for_rotations(self, rotations, speedl=None, speedr=None):
        sl = speedl if speedl is not None else self.default_speed
        sr = speedr if speedr is not None else self.default_speed
        self.run_for_degrees(int(rotations * 360), sl, sr)

    def run_for_degrees(self, degrees, speedl=None, speedr=None):
        sl = speedl if speedl is not None else self.default_speed
        sr = speedr if speedr is not None else self.default_speed
        th1 = threading.Thread(target=self._leftmotor._run_for_degrees,  args=(degrees, sl))
        th2 = threading.Thread(target=self._rightmotor._run_for_degrees, args=(degrees, sr))
        th1.daemon = th2.daemon = True
        th1.start(); th2.start()
        th1.join();  th2.join()

    def run_for_seconds(self, seconds, speedl=None, speedr=None):
        sl = speedl if speedl is not None else self.default_speed
        sr = speedr if speedr is not None else self.default_speed
        th1 = threading.Thread(target=self._leftmotor._run_for_seconds,  args=(seconds, sl))
        th2 = threading.Thread(target=self._rightmotor._run_for_seconds, args=(seconds, sr))
        th1.daemon = th2.daemon = True
        th1.start(); th2.start()
        th1.join();  th2.join()

    def start(self, speedl=None, speedr=None):
        self._leftmotor.start( speedl if speedl is not None else self.default_speed)
        self._rightmotor.start(speedr if speedr is not None else self.default_speed)

    def stop(self):
        self._leftmotor.stop()
        self._rightmotor.stop()

    def run_to_position(self, degreesl, degreesr, speed=None, direction="shortest"):
        spd = speed if speed is not None else self.default_speed
        th1 = threading.Thread(target=self._leftmotor._run_to_position,  args=(degreesl, spd, direction))
        th2 = threading.Thread(target=self._rightmotor._run_to_position, args=(degreesr, spd, direction))
        th1.daemon = th2.daemon = True
        th1.start(); th2.start()
        th1.join();  th2.join()

    @property
    def release(self):
        return self._release

    @release.setter
    def release(self, value):
        if not isinstance(value, bool):
            raise MotorError("Must pass boolean")
        self._release = value
        self._leftmotor.release  = value
        self._rightmotor.release = value