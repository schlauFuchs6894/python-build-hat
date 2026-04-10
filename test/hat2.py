"""Test hat functionality"""

import unittest
import time

from buildhat import Hat
from gpiozero import OutputDevice
import logging

H1_RST_GPIO = 4
H1_BOOT_GPIO = 22
H2_RST_GPIO = 5
H2_BOOT_GPIO = 6

class TestHat(unittest.TestCase):
    """Test hat functions"""

    def test_hat2_serial(self):
        """Test setting serial device"""
        Hat( device="/dev/ttyAMA4",
            reset_gpio=H2_RST_GPIO,
            boot0_gpio=H2_BOOT_GPIO,
            debug=False
        )

    def test_hat1_serial(self):
        """Test setting serial device"""
        Hat(
            device="/dev/ttyAMA0",
            reset_gpio=H1_RST_GPIO,
            boot0_gpio=H1_BOOT_GPIO,
           debug=False
        )    

    def test_hat2_vin(self):
        """Test voltage measure function"""
        h2 = Hat(
            device="/dev/ttyAMA4",
            reset_gpio=H2_RST_GPIO,
            boot0_gpio=H2_BOOT_GPIO,
            debug=False,
        )
        vin = h2.get_vin()
        self.assertGreaterEqual(vin, 7.2)
        self.assertLessEqual(vin, 8.5)

    def test_hat1_vin(self):
        """Test voltage measure function"""
        h1 = Hat(
            device="/dev/ttyAMA0",
            reset_gpio=H1_RST_GPIO,
            boot0_gpio=H1_BOOT_GPIO,
           debug=False
        )    
        vin = h1.get_vin()
        self.assertGreaterEqual(vin, 7.2)
        self.assertLessEqual(vin, 8.5) 

    def test_get(self):
        # Read HAT 2
        """Test getting list of devices"""
        rstH1 = OutputDevice(H1_RST_GPIO, active_high=True, initial_value=True)
        print("H1 Reset high")
        rstH1.off()
        time.sleep(0.01)

        h2 = Hat(
            device="/dev/ttyAMA4",
            reset_gpio=H2_RST_GPIO,
            boot0_gpio=H2_BOOT_GPIO,
            debug=False
        )
        logging.basicConfig(level=logging.INFO)
        print("h2.get()")
        logging.info("HAT 2:")
        logging.info(h2.get())
        self.assertIsInstance(h2.get(), dict)

        # Read HAT 1
        rstH1.on()
        rstH2 = OutputDevice(H2_RST_GPIO, active_high=True, initial_value=True)
        rstH2.off()
        print("H2 Reset high")
        time.sleep(0.5)  # wait for HAT to boot after reset
        del rstH1
        h1 = Hat(
            device="/dev/ttyAMA0",
            reset_gpio=H1_RST_GPIO,
            boot0_gpio=H1_BOOT_GPIO,
           debug=False
        )    
        logging.info("HAT 1:")
        logging.info(h1.get())
        rstH2.on()
        time.sleep(2)  # wait for HAT to boot after reset
        del rstH2
        self.assertIsInstance(h1.get(), dict)


if __name__ == '__main__':
    unittest.main()
