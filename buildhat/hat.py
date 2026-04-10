"""HAT handling functionality"""

from concurrent.futures import Future

from .devices import Device


class Hat:
    """Enumerate and control a Build HAT.

    **Singleton / backward-compatible**::

        hat = Hat()               # reuses or creates the default instance
        hat = Hat("/dev/serial0") # creates a new HAT, becomes the default
                                  # if none existed yet

    **Explicit instance** (multiple HATs)::

        hat_a = Hat("/dev/ttyAMA0")
        hat_b = Hat("/dev/ttyAMA1")

        old_default = Device.set_default_instance(hat_b._instance)
    """

    SERIAL_DEV        = None
    RESET_GPIO_NUMBER = 4
    BOOT0_GPIO_NUMBER = 22

    def __init__(self, device=SERIAL_DEV,
                 reset_gpio=RESET_GPIO_NUMBER,
                 boot0_gpio=BOOT0_GPIO_NUMBER,
                 debug=False):
        """Initialise the HAT.

        :param device: Path to the serial device, or ``None`` to reuse the
            current default BuildHAT instance.
        :param reset_gpio: Reset GPIO number.
        :param boot0_gpio: Boot0 GPIO number.
        :param debug: Enable debug logging.
        """
        self.led_status = -1
        self._instance  = Device._setup(
            device=device,
            reset_gpio=reset_gpio,
            boot0_gpio=boot0_gpio,
            debug=debug,
        )

    # ------------------------------------------------------------------
    # Singleton helpers
    # ------------------------------------------------------------------

    @staticmethod
    def set_default(hat):
        """Make *hat* the default instance used by all ``Device`` subclasses.

        :param hat: A :class:`Hat` instance to promote, or ``None`` to clear.
        :returns: The previous default as a Hat-like wrapper, or ``None``.
        :rtype: Hat | None
        """
        new_bhat  = hat._instance if hat is not None else None
        prev_bhat = Device.set_default_instance(new_bhat)
        if prev_bhat is None:
            return None
        wrapper            = Hat.__new__(Hat)
        wrapper.led_status = -1
        wrapper._instance  = prev_bhat
        return wrapper

    # ------------------------------------------------------------------
    # Device enumeration
    # ------------------------------------------------------------------

    def get(self):
        """Return a dict describing all four ports.

        :rtype: dict
        """
        devices = {}
        for i in range(4):
            conn = self._instance.connections[i]
            if conn.typeid in Device._device_names:
                name = Device._device_names[conn.typeid][0]
                desc = Device._device_names[conn.typeid][1]
            elif conn.typeid == -1:
                name = Device.DISCONNECTED_DEVICE
                desc = ''
            else:
                name = Device.UNKNOWN_DEVICE
                desc = ''
            devices[chr(ord('A') + i)] = {
                "typeid":      conn.typeid,
                "connected":   conn.connected,
                "name":        name,
                "description": desc,
            }
        return devices

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_logfile(self):
        """Path of the debug log file, or ``None`` if debug is disabled.

        :rtype: str | None
        """
        return self._instance.debug_filename

    def get_vin(self, timeout=5.0):
        """Input voltage on the power jack.

        :param timeout: Seconds to wait for a response (default 5).
        :returns: Voltage in volts.
        :rtype: float
        :raises TimeoutError: HAT did not respond within *timeout* seconds.
        """
        ftr = Future()
        self._instance.vinftr.append(ftr)
        self._instance.write(b"vin\r")
        result = ftr.result(timeout=timeout)
        if result is None:
            raise TimeoutError("get_vin timed out — no response from HAT")
        return result

    # ------------------------------------------------------------------
    # LED control
    # ------------------------------------------------------------------

    def _set_led(self, intmode):
        if isinstance(intmode, int) and -1 <= intmode <= 3:
            self.led_status = intmode
            self._instance.write(f"ledmode {intmode}\r".encode())

    def set_leds(self, color="voltage"):
        """Set the two status LEDs.

        :param color: ``"orange"``, ``"green"``, ``"both"``, ``"off"``, or
            ``"voltage"`` (default).
        """
        mapping = {"orange": 1, "green": 2, "both": 3, "off": 0, "voltage": -1}
        if color in mapping:
            self._set_led(mapping[color])

    def orange_led(self, status=True):
        """Turn the orange LED on or off."""
        if status:
            if self.led_status in (3, 1):
                return
            self._set_led(3 if self.led_status == 2 else 1)
        else:
            if self.led_status in (1, -1):
                self._set_led(0)
            elif self.led_status == 3:
                self._set_led(2)

    def green_led(self, status=True):
        """Turn the green LED on or off."""
        if status:
            if self.led_status in (3, 2):
                return
            self._set_led(3 if self.led_status == 1 else 2)
        else:
            if self.led_status in (2, -1):
                self._set_led(0)
            elif self.led_status == 3:
                self._set_led(1)

    def _close(self):
        self._instance.shutdown()