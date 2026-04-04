"""Test hat functionality"""

import unittest

from buildhat import Hat


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
        """Test getting list of devices"""
        h = Hat(
            device="/dev/ttyAMA4",
            reset_gpio=25,
            boot0_gpio=24,
            debug=False,
        )
        print("h.get()")
        self.assertIsInstance(h.get(), dict)

    def test_serial(self):
        """Test setting serial device"""
        Hat(device="/dev/ttyAMA4", reset_gpio=25)


if __name__ == '__main__':
    unittest.main()
