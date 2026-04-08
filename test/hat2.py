"""Test hat functionality"""

import unittest
import time

from buildhat import Hat
from gpiozero import OutputDevice
import logging

class TestHat(unittest.TestCase):
    """Test hat functions"""

    H1_RST_GPIO = 4
    H1_BOOT_GPIO = 22
    H2_RST_GPIO = 5
    H2_BOOT_GPIO = 6

    def test_vin(self):
        """Test voltage measure function"""
        h2 = Hat(
            device="/dev/ttyAMA4",
            reset_gpio=TestHat.H2_RST_GPIO,
            boot0_gpio=TestHat.H2_BOOT_GPIO,
            debug=False,
        )
        vin = h2.get_vin()
        self.assertGreaterEqual(vin, 7.2)
        self.assertLessEqual(vin, 8.5)
 
    def test_get(self):
        # Read HAT 2
        """Test getting list of devices"""
        rstH1 = OutputDevice(TestHat.H1_RST_GPIO, active_high=True, initial_value=True)
        print("H1 Reset high")
        rstH1.off()
        time.sleep(0.01)

        h2 = Hat(
            device="/dev/ttyAMA4",
           reset_gpio=TestHat.H2_RST_GPIO,
            boot0_gpio=TestHat.H2_BOOT_GPIO,
            debug=False,
        )
        logging.basicConfig(level=logging.INFO)
        print("h2.get()")
        logging.info("HAT 2:")
        logging.info(h2.get())
        self.assertIsInstance(h2.get(), dict)

        # Read HAT 1
        rstH1.on()
        rstH2 = OutputDevice(TestHat.H2_RST_GPIO, active_high=True, initial_value=True)
        rstH2.off()
        print("H2 Reset high")
        time.sleep(0.5)  # wait for HAT to boot after reset
        h1 = Hat(
            device="/dev/ttyAMA0",
            reset_gpio=TestHat.H1_RST_GPIO,
            boot0_gpio=TestHat.H1_BOOT_GPIO,
           debug=False,
        )    
        logging.info("HAT 1:")
        logging.info(h1.get())
        rstH2.on()
        time.sleep(0.5)  # wait for HAT to boot after reset
        self.assertIsInstance(h1.get(), dict)

    def test_serial(self):
        """Test setting serial device"""
        Hat(device="/dev/ttyAMA4", reset_gpio=TestHat.H2_RST_GPIO)


if __name__ == '__main__':
    unittest.main()
