"""Test motors"""

import time
import unittest

from buildhat import Hat, Motor
from buildhat.devices import Device
from buildhat.exc import DeviceError, MotorError

def deregister_all():
    """Shut down all HATs and wipe the Device registry.

    Leaves the process in a clean state so the next test can open ports
    from scratch. Does NOT re-open the HAT — the next Motor() or Hat()
    call will do that automatically.
    """
    for bhat in list(Device._registry.values()):
        try:
            bhat.shutdown()
        except Exception:
            pass
    Device._registry.clear()
    Device._default_key = None
    Device._used.clear()

class TestMotor(unittest.TestCase):
    """Test motors"""

    THRESHOLD_DISTANCE = 15

    @classmethod
    def setUpClass(cls):
        """Open the HAT once for the whole class."""
        Hat()   # default /dev/serial0 — registers and becomes default

    def tearDown(self):
        """Release all ports after every test so the next one starts clean.

        We do NOT shut down the HAT between tests (that would take ~10 s to
        re-init each time). We only clear the port-in-use table so Motor('A')
        can be constructed again.  Any Motor local variables the test held
        are already out of scope by the time tearDown runs, so __del__ will
        have fired and cleared _used — but CPython's GC timing isn't
        guaranteed, so we clear explicitly.
        """
        Device._used.clear()

    @classmethod
    def tearDownClass(cls):
        """Full shutdown after all motor tests complete."""
        deregister_all()

    def test_rotations(self):
        """Test motor rotating"""
        m = Motor('A')
        pos1 = m.get_position()
        m.run_for_rotations(2)
        pos2 = m.get_position()
        rotated = (pos2 - pos1) / 360
        self.assertLess(abs(rotated - 2), 0.5)

    def test_nonblocking(self):
        """Test motor nonblocking mode"""
        m = Motor('A')
        m.set_default_speed(10)
        last = 0
        for delay in [1, 0]:
            for _ in range(3):
                m.run_to_position(90, blocking=False)
                time.sleep(delay)
                m.run_to_position(90, blocking=False)
                time.sleep(delay)
                m.run_to_position(90, blocking=False)
                time.sleep(delay)
                m.run_to_position(last, blocking=False)
                time.sleep(delay)
                # Wait for a bit, before reading last position
                time.sleep(7)
                pos1 = m.get_aposition()
                diff = abs((last - pos1 + 180) % 360 - 180)
                self.assertLess(diff, self.THRESHOLD_DISTANCE)

    def test_nonblocking_multiple(self):
        """Test motor nonblocking mode"""
        m1 = Motor('A')
        m1.set_default_speed(10)
        m2 = Motor('B')
        m2.set_default_speed(10)
        last = 0
        for delay in [1, 0]:
            for _ in range(3):
                m1.run_to_position(90, blocking=False)
                m2.run_to_position(90, blocking=False)
                time.sleep(delay)
                m1.run_to_position(90, blocking=False)
                m2.run_to_position(90, blocking=False)
                time.sleep(delay)
                m1.run_to_position(90, blocking=False)
                m2.run_to_position(90, blocking=False)
                time.sleep(delay)
                m1.run_to_position(last, blocking=False)
                m2.run_to_position(last, blocking=False)
                time.sleep(delay)
                # Wait for a bit, before reading last position
                time.sleep(7)
                pos1 = m1.get_aposition()
                diff = abs((last - pos1 + 180) % 360 - 180)
                self.assertLess(diff, self.THRESHOLD_DISTANCE)
                pos2 = m2.get_aposition()
                diff = abs((last - pos2 + 180) % 360 - 180)
                self.assertLess(diff, self.THRESHOLD_DISTANCE)

    def test_nonblocking_mixed(self):
        """Test motor nonblocking mode mixed with blocking mode"""
        m = Motor('A')
        m.run_for_seconds(5, blocking=False)
        m.run_for_degrees(360)
        m.run_for_seconds(5, blocking=False)
        m.run_to_position(180)
        m.run_for_seconds(5, blocking=False)
        m.run_for_seconds(5)
        m.run_for_seconds(5, blocking=False)
        m.start()
        m.run_for_seconds(5, blocking=False)
        m.stop()

    def test_position(self):
        """Test motor goes to desired position"""
        m = Motor('A')
        m.run_to_position(0)
        pos1 = m.get_aposition()
        diff = abs((0 - pos1 + 180) % 360 - 180)
        self.assertLess(diff, self.THRESHOLD_DISTANCE)

        m.run_to_position(180)
        pos1 = m.get_aposition()
        diff = abs((180 - pos1 + 180) % 360 - 180)
        self.assertLess(diff, self.THRESHOLD_DISTANCE)

    def test_time(self):
        """Test motor runs for correct duration"""
        m = Motor('A')
        t1 = time.time()
        m.run_for_seconds(5)
        t2 = time.time()
        self.assertEqual(int(t2 - t1), 5)

    def test_speed(self):
        """Test setting motor speed"""
        m = Motor('A')
        m.set_default_speed(50)
        self.assertRaises(MotorError, m.set_default_speed, -101)
        self.assertRaises(MotorError, m.set_default_speed, 101)

    def test_plimit(self):
        """Test altering power limit of motor"""
        m = Motor('A')
        m.plimit(0.5)
        self.assertRaises(MotorError, m.plimit, -1)
        self.assertRaises(MotorError, m.plimit, 2)

    def test_pwm(self):
        """Test PWMing motor"""
        m = Motor('A')
        m.pwm(0.3)
        time.sleep(0.5)
        m.pwm(0)
        self.assertRaises(MotorError, m.pwm, -2)
        self.assertRaises(MotorError, m.pwm, 2)

    def test_callback(self):
        """Test setting callback"""
        m = Motor('A')

        def handle_motor(speed, pos, apos):
            handle_motor.evt += 1
        handle_motor.evt = 0
        m.when_rotated = handle_motor
        m.run_for_seconds(1)
        self.assertGreater(handle_motor.evt, 0)

    def test_callback_interval(self):
        """Test setting callback and interval"""
        m = Motor('A')
        m.interval = 10

        def handle_motor(speed, pos, apos):
            handle_motor.evt += 1
        handle_motor.evt = 0
        m.when_rotated = handle_motor
        m.run_for_seconds(5)
        self.assertGreater(handle_motor.evt, 0.8 * ((1 / ((m.interval) * 1e-3)) * 5))

    def test_none_callback(self):
        """Test setting empty callback"""
        m = Motor('A')
        m.when_rotated = None
        m.start()
        time.sleep(0.5)
        m.stop()

    def test_duplicate_port(self):
        """Test using same port for motor"""
        m1 = Motor('A')  # noqa: F841
        self.assertRaises(DeviceError, Motor, 'A')

    def test_del(self):
        """Test deleting motor"""
        m1 = Motor('A')
        del m1
        Motor('A')

    def test_continuous_start(self):
        """Test starting motor for 5mins"""
        t = time.time() + (60 * 5)
        m = Motor('A')
        toggle = 0
        while time.time() < t:
            m.start(toggle)
            toggle ^= 1

    def test_continuous_degrees(self):
        """Test setting degrees for 5mins"""
        t = time.time() + (60 * 5)
        m = Motor('A')
        toggle = 0
        while time.time() < t:
            m.run_for_degrees(toggle)
            toggle ^= 1

    def test_continuous_position(self):
        """Test setting position of motor for 5mins"""
        t = time.time() + (60 * 5)
        m = Motor('A')
        toggle = 0
        while time.time() < t:
            m.run_to_position(toggle)
            toggle ^= 1

    def test_continuous_feedback(self):
        """Test feedback of motor for 30mins"""
        Hat(debug=True)
        t = time.time() + (60 * 30)
        m = Motor('A')
        m.start(40)
        while time.time() < t:
            _ = (m.get_speed(), m.get_position(), m.get_aposition())

    def test_interval(self):
        """Test motor interval"""
        m = Motor('A')
        m.interval = 10
        count = 1000
        expected_dur = count * m.interval * 1e-3
        start = time.time()
        for _ in range(count):
            m.get_position()
        end = time.time()
        diff = abs((end - start) - expected_dur)
        self.assertLess(diff, expected_dur * 0.1)

    def test_dual_interval(self):
        """Test dual motor interval"""
        m1 = Motor('A')
        m2 = Motor('B')
        for interval in [20, 10]:
            m1.interval = interval
            m2.interval = interval
            count = 1000
            expected_dur = count * m1.interval * 1e-3
            start = time.time()
            for _ in range(count):
                m1.get_position()
                m2.get_position()
            end = time.time()
            diff = abs((end - start) - expected_dur)
            self.assertLess(diff, expected_dur * 0.1)


if __name__ == '__main__':
    unittest.main()
