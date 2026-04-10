"""Test motors"""

import time
import unittest

from buildhat import Hat, Motor, ColorDistanceSensor, Light 
from buildhat.exc import DeviceError, MotorError

H1_RST_GPIO = 4
H1_BOOT_GPIO = 22
H2_RST_GPIO = 5
H2_BOOT_GPIO = 6

class TestMotor(unittest.TestCase):
    """Test motors"""

    THRESHOLD_DISTANCE = 15
    # init build hat

    def test_dual_hat_dual_interval(self):
        """Test 2 HAT dual motor interval"""
        hat1 = Hat(
            device="/dev/ttyAMA0",
            reset_gpio=H1_RST_GPIO,
            boot0_gpio=H1_BOOT_GPIO,
            debug=False,            
        )
        hat2 = Hat(
            device="/dev/ttyAMA4",
            reset_gpio=H2_RST_GPIO,
            boot0_gpio=H2_BOOT_GPIO,
            debug=False,
        )       

        # HAT 1 - Motor , ColorDistanceSensor
        h1m1 = Motor('A', hat_instance=hat1._instance)
        h1s1 = ColorDistanceSensor('B', hat_instance=hat1._instance)

        # HAT 2 - Light Motor
        h2l1 = Light('A', hat_instance=hat2._instance)
        h2m2 = Motor('B', hat_instance=hat2._instance)

        h2l1.brightness(100)
        h2m2.start()
        time.sleep(0.5)
        color = h1s1.get_color()
        print(f"Color: {color}")
        h1m1.start()
        time.sleep(3)
        color = h1s1.get_color()
        print(f"Color: {color}")
        h2l1.stop()
        h2m2.stop()
        h2l1.brightness(0)
        color = h1s1.get_color()
        print(f"Color: {color}")

if __name__ == '__main__':
    unittest.main()
