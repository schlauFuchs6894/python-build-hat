"""Test hat functionality"""

import unittest

from buildhat import Hat
import logging

class TestHat(unittest.TestCase):
    """Test hat functions"""



    def test_vin(self):
        """Test voltage measure function"""
        h = Hat(
            device="/dev/ttyAMA4",
            reset_gpio=25,
            boot0_gpio=24,
            debug=False,
        )
        vin = h.get_vin()
        self.assertGreaterEqual(vin, 7.2)
        self.assertLessEqual(vin, 8.5)
 
    def test_get(self):
        # Read HAT 2
        """Test getting list of devices"""
        rstH1 = OutputDevice(4, active_high=True, initial_value=True)
        print("Reset high")
        rstH1.off()
 
        h2 = Hat(
            device="/dev/ttyAMA4",
            reset_gpio=25,
            boot0_gpio=24,
            debug=False,
        )
        logging.basicConfig(level=logging.INFO)
        print("h.get()")
        logging.info("HAT 2:")
        logging.info(h2.get())
        self.assertIsInstance(h2.get(), dict)
        
        # Read HAT 1
        rstH2 = OutputDevice(25, active_high=True, initial_value=True)
        print("Reset high")
        rstH2.off()

        h1 = Hat(
            device="/dev/ttyAMA0",
            reset_gpio=4,
            boot0_gpio=22,
            debug=False,
        )    
        logging.info("HAT 1:")
        logging.info(h1.get())
        self.assertIsInstance(h1.get(), dict)

    def test_serial(self):
        """Test setting serial device"""
        Hat(device="/dev/ttyAMA4", reset_gpio=25)


if __name__ == '__main__':
    unittest.main()
