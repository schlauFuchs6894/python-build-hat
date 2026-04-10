"""Test hat functionality"""

import unittest
import time

from buildhat import Hat
from buildhat.devices import Device
from gpiozero import OutputDevice
import logging

H1_RST_GPIO = 4
H1_BOOT_GPIO = 22
H2_RST_GPIO = 5
H2_BOOT_GPIO = 6

class TestHat(unittest.TestCase):
    """Test hat functions"""

    # ------------------------------------------------------------------
    # Initialise both HATs once for the whole test class.
    # Individual tests must NOT reset GPIOs — put GPIO-toggling tests in
    # their own class (TestHatGPIO below) so they run in isolation.
    # ------------------------------------------------------------------

    @classmethod
    def setUpClass(cls):
        cls.h1 = Hat(
            device="/dev/ttyAMA0",
            reset_gpio=H1_RST_GPIO,
            boot0_gpio=H1_BOOT_GPIO,
            debug=False,
        )
        cls.h2 = Hat(
            device="/dev/ttyAMA4",
            reset_gpio=H2_RST_GPIO,
            boot0_gpio=H2_BOOT_GPIO,
            debug=False,
        )

    @classmethod
    def tearDownClass(cls):
        deregister_all()

    # ------------------------------------------------------------------
    def test_hat2_serial(self):
        """Test setting serial device"""
        Hat( device="/dev/ttyAMA4",
            reset_gpio=H2_RST_GPIO,
            boot0_gpio=H2_BOOT_GPIO,
            debug=False)
        self.assertIs(h._instance, self.h2._instance)

    def test_hat1_serial(self):
        """Registry returns the same instance for the same device path"""
        h = Hat(device="/dev/ttyAM0",
                reset_gpio=H1_RST_GPIO,
                boot0_gpio=H1_BOOT_GPIO)
        self.assertIs(h._instance, self.h1._instance)

    def test_hat2_vin(self):
        """HAT 2 input voltage in expected range"""
        vin = self.h2.get_vin()
        self.assertGreaterEqual(vin, 7.2)
        self.assertLessEqual(vin, 8.5)

    def test_hat1_vin(self):
        """HAT 1 input voltage in expected range"""
        vin = self.h1.get_vin()
        self.assertGreaterEqual(vin, 7.2)
        self.assertLessEqual(vin, 8.5)

    def test_hat2_get(self):
        """HAT 2 get() returns a dict"""
        result = self.h2.get()
        logging.info("HAT 2: %s", result)
        self.assertIsInstance(result, dict)

    def test_hat1_get(self):
        """HAT 1 get() returns a dict"""
        result = self.h1.get()
        logging.info("HAT 1: %s", result)
        self.assertIsInstance(result, dict)



class TestHatGPIO(unittest.TestCase):
    """Tests that physically reset HATs via GPIO — run separately, last."""

    @classmethod
    def tearDownClass(cls):
        deregister_all()

    def test_get_with_gpio_reset(self):
        """Read each HAT after toggling the other's reset line"""
        # Hold HAT1 in reset while we talk to HAT2
        rstH1 = OutputDevice(H1_RST_GPIO, active_high=True, initial_value=True)
        rstH1.off()
        time.sleep(0.01)

        h2 = Hat(device="/dev/ttyAMA4",
                 reset_gpio=H2_RST_GPIO,
                 boot0_gpio=H2_BOOT_GPIO)
        logging.info("HAT 2 (H1 held in reset): %s", h2.get())
        self.assertIsInstance(h2.get(), dict)

        # Release HAT1, hold HAT2 in reset
        rstH1.on()
        rstH2 = OutputDevice(H2_RST_GPIO, active_high=True, initial_value=True)
        rstH2.off()
        time.sleep(0.5)   # wait for HAT1 to boot
        del rstH1

        h1 = Hat(device="/dev/ttyAMA0",
                 reset_gpio=H1_RST_GPIO,
                 boot0_gpio=H1_BOOT_GPIO)
        logging.info("HAT 1 (H2 held in reset): %s", h1.get())
        self.assertIsInstance(h1.get(), dict)

        rstH2.on()
        time.sleep(2.0)   # let HAT2 finish booting before process exits
        del rstH2


def deregister_all():
    """Remove all HATs from the Device registry and clear port tracking.

    Call this after tests complete to leave the process in a clean state,
    e.g. when multiple test modules are run in the same interpreter session.
    """
    for bhat in list(Device._registry.values()):
        try:
            bhat.shutdown()
        except Exception:
            pass
    Device._registry.clear()
    Device._default_key = None
    Device._used.clear()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        unittest.main(exit=False)
    finally:
        deregister_all()