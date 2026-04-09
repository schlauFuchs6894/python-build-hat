"""Functionality for handling Build HAT devices"""

import os
import sys
import weakref
from concurrent.futures import Future

from .exc import DeviceError
from .serinterface import BuildHAT


class Device:
    """Creates instances of BuildHAT; falls back to a module-level singleton
    when no explicit instance is provided.

    Singleton behaviour is unchanged from the original API — the first
    initialised HAT becomes the default.  Call ``Device.set_default_instance``
    to swap the default and get the previous one back.
    """

    SERIAL_DEV = None
    RESET_GPIO_NUMBER = 4
    BOOT0_GPIO_NUMBER = 22

    _default_instance = None   # the singleton / current default
    _used = {0: False, 1: False, 2: False, 3: False}

    _device_names = {
        1:  ("PassiveMotor",        "PassiveMotor"),
        2:  ("PassiveMotor",        "PassiveMotor"),
        8:  ("Light",               "Light"),
        34: ("TiltSensor",          "WeDo 2.0 Tilt Sensor"),
        35: ("MotionSensor",        "MotionSensor"),
        37: ("ColorDistanceSensor", "Color & Distance Sensor"),
        61: ("ColorSensor",         "Color Sensor"),
        62: ("DistanceSensor",      "Distance Sensor"),
        63: ("ForceSensor",         "Force Sensor"),
        64: ("Matrix",              "3x3 Color Light Matrix"),
        38: ("Motor",               "Medium Linear Motor"),
        46: ("Motor",               "Large Motor"),
        47: ("Motor",               "XL Motor"),
        48: ("Motor",               "Medium Angular Motor (Cyan)"),
        49: ("Motor",               "Large Angular Motor (Cyan)"),
        65: ("Motor",               "Small Angular Motor"),
        75: ("Motor",               "Medium Angular Motor (Grey)"),
        76: ("Motor",               "Large Angular Motor (Grey)"),
    }

    UNKNOWN_DEVICE      = "Unknown"
    DISCONNECTED_DEVICE = "Disconnected"

    # ------------------------------------------------------------------
    # Singleton / instance management
    # ------------------------------------------------------------------

    @classmethod
    def set_default_instance(cls, instance):
        """Replace the default (singleton) BuildHAT instance.

        :param instance: A :class:`~buildhat.serinterface.BuildHAT` instance
            (or ``None`` to clear the default).
        :returns: The *previous* default instance (may be ``None``).
        :rtype: BuildHAT | None

        Example::

            hat_a = BuildHAT(...)
            hat_b = BuildHAT(...)
            old = Device.set_default_instance(hat_b)
            # old is hat_a; all subsequent Device() calls without an explicit
            # hat_instance= use hat_b.
        """
        prev = cls._default_instance
        cls._default_instance = instance
        return prev

    @classmethod
    def get_default_instance(cls):
        """Return the current default BuildHAT instance (the singleton).

        :returns: Current default instance, or ``None`` if none has been set.
        :rtype: BuildHAT | None
        """
        return cls._default_instance

    # ------------------------------------------------------------------
    # Internal setup helper
    # ------------------------------------------------------------------

    @staticmethod
    def _create_buildhat(device, reset_gpio, boot0_gpio, debug):
        """Unconditionally create and return a new BuildHAT instance."""
        if (
            os.path.isdir(os.path.join(os.getcwd(), "data/"))
            and os.path.isfile(os.path.join(os.getcwd(), "data", "firmware.bin"))
            and os.path.isfile(os.path.join(os.getcwd(), "data", "signature.bin"))
            and os.path.isfile(os.path.join(os.getcwd(), "data", "version"))
        ):
            data = os.path.join(os.getcwd(), "data/")
        else:
            data = os.path.join(
                os.path.dirname(sys.modules["buildhat"].__file__), "data/"
            )
        firm = os.path.join(data, "firmware.bin")
        sig  = os.path.join(data, "signature.bin")
        ver  = os.path.join(data, "version")
        with open(ver) as vf:
            v = int(vf.read())
        return BuildHAT(
            firmware=firm, signature=sig, version=v,
            device=device, reset_gpio=reset_gpio,
            boot0_gpio=boot0_gpio, debug=debug,
        )

    @classmethod
    def _setup(cls, device=SERIAL_DEV, reset_gpio=RESET_GPIO_NUMBER,
               boot0_gpio=BOOT0_GPIO_NUMBER, debug=False,
               hat_instance=None):
        """Return a BuildHAT instance, creating one only when necessary.

        Resolution order
        ~~~~~~~~~~~~~~~~
        1. ``hat_instance`` was supplied explicitly → use it as-is.
        2. A default instance already exists and ``device`` is ``None``
           → reuse the default (classic singleton behaviour).
        3. Otherwise → create a fresh BuildHAT, register it as the default
           if none exists yet, attach a finaliser, and return it.

        :param hat_instance: An already-constructed BuildHAT to bind to.
        :returns: The resolved BuildHAT instance.
        :rtype: BuildHAT
        """
        # 1. Caller provided an explicit instance — honour it directly.
        if hat_instance is not None:
            return hat_instance

        # 2. Reuse the existing default when no serial device was requested.
        if cls._default_instance is not None and device is None:
            return cls._default_instance

        # 3. Create a new BuildHAT.
        bhat = cls._create_buildhat(device, reset_gpio, boot0_gpio, debug)

        # Register as default if none exists yet (first-initialised wins).
        if cls._default_instance is None:
            cls._default_instance = bhat
            weakref.finalize(cls._default_instance, cls._default_instance.shutdown)

        return bhat

    # ------------------------------------------------------------------
    # Device lifecycle
    # ------------------------------------------------------------------

    def __init__(self, port,
                 device=SERIAL_DEV,
                 reset_gpio=RESET_GPIO_NUMBER,
                 boot0_gpio=BOOT0_GPIO_NUMBER,
                 debug=False,
                 hat_instance=None):
        """Initialise a device on a specific port.

        :param port: Port letter ('A'–'D').
        :param device: Path to the serial device, or ``None`` to reuse the
            default instance.
        :param reset_gpio: Reset GPIO number.
        :param boot0_gpio: Boot0 GPIO number.
        :param debug: Enable debug logging.
        :param hat_instance: Bind this device to a *specific*
            :class:`~buildhat.serinterface.BuildHAT` instance instead of the
            default singleton.  Useful when more than one HAT is present.
        :raises DeviceError: Port string is invalid, already in use, or the
            connected device does not match the expected type.
        """
        if not isinstance(port, str) or len(port) != 1:
            raise DeviceError("Invalid port")
        p = ord(port) - ord('A')
        if not 0 <= p <= 3:
            raise DeviceError("Invalid port")
        if Device._used[p]:
            raise DeviceError("Port already used")

        self.port = p

        # Resolve (or create) the BuildHAT instance for this device.
        self._hat_instance = Device._setup(
            device=device,
            reset_gpio=reset_gpio,
            boot0_gpio=boot0_gpio,
            debug=debug,
            hat_instance=hat_instance,
        )
        if self._hat_instance is None:
            raise DeviceError("Failed to setup Build HAT Device")

        self._simplemode = -1
        self._combimode  = -1
        self._modestr    = ""
        self._typeid     = self._conn.typeid
        self._interval   = 10

        if (
            self._typeid in Device._device_names
            and Device._device_names[self._typeid][0] != type(self).__name__
        ) or self._typeid == -1:
            raise DeviceError(
                f'There is not a {type(self).__name__} connected to port '
                f'{port} (Found {self.name})'
            )

        Device._used[p] = True

    def __del__(self):
        """Release the port when the device object is garbage-collected."""
        if hasattr(self, "port") and Device._used[self.port]:
            Device._used[self.port] = False
            self._conn.callit = None
            self.deselect()
            self.off()

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------

    @staticmethod
    def name_for_id(typeid):
        """Translate a numeric type-id to a Python class name.

        :param typeid: Integer device type.
        :return: Class name string.
        :rtype: str
        """
        return Device._device_names.get(typeid, (Device.UNKNOWN_DEVICE,))[0]

    @staticmethod
    def desc_for_id(typeid):
        """Translate a numeric type-id to a human-readable description.

        :param typeid: Integer device type.
        :return: Description string.
        :rtype: str
        """
        if typeid in Device._device_names:
            return Device._device_names[typeid][1]
        return Device.UNKNOWN_DEVICE

    # ------------------------------------------------------------------
    # Per-instance properties
    # ------------------------------------------------------------------

    @property
    def _conn(self):
        return self._hat_instance.connections[self.port]

    @property
    def connected(self):
        """Whether the device is currently connected.

        :rtype: bool
        """
        return self._conn.connected

    @property
    def typeid(self):
        """Type ID recorded at initialisation time.

        :rtype: int
        """
        return self._typeid

    @property
    def typeidcur(self):
        """Type ID currently reported by the HAT.

        :rtype: int
        """
        return self._conn.typeid

    @property
    def _hat(self):
        """The BuildHAT instance this device is bound to."""
        return self._hat_instance

    @property
    def name(self):
        """Python class name of the device on the port.

        :rtype: str
        """
        if not self.connected:
            return Device.DISCONNECTED_DEVICE
        return self._device_names.get(self.typeidcur, (Device.UNKNOWN_DEVICE,))[0]

    @property
    def description(self):
        """Human-readable description of the device on the port.

        :rtype: str
        """
        if not self.connected:
            return Device.DISCONNECTED_DEVICE
        if self.typeidcur in self._device_names:
            return self._device_names[self.typeidcur][1]
        return Device.UNKNOWN_DEVICE

    # ------------------------------------------------------------------
    # Device operations
    # ------------------------------------------------------------------

    def isconnected(self):
        """Assert that the device is still connected and of the expected type.

        :raises DeviceError: Device is gone or has been swapped for another.
        """
        if not self.connected:
            raise DeviceError("No device found")
        if self.typeid != self.typeidcur:
            raise DeviceError("Device has changed")

    def reverse(self):
        """Reverse polarity."""
        self._write(f"port {self.port} ; port_plimit 1 ; set -1\r")

    def get(self):
        """Read the current sensor value.

        :return: Data list from the device.
        :raises DeviceError: Device is not in a valid mode.
        """
        self.isconnected()
        if self._simplemode == -1 and self._combimode == -1:
            raise DeviceError("Not in simple or combimode")
        ftr = Future()
        self._hat.portftr[self.port].append(ftr)
        return ftr.result()

    def mode(self, modev):
        """Set combimode or simple mode.

        :param modev: List of ``(mode, dataset)`` tuples for a combimode,
            or a single integer for simple mode.
        """
        self.isconnected()
        if isinstance(modev, list):
            modestr = "".join(f"{t[0]} {t[1]} " for t in modev)
            if self._simplemode == -1 and self._combimode == 0 and self._modestr == modestr:
                return
            self._write(f"port {self.port}; select\r")
            self._combimode = 0
            self._write(
                f"port {self.port} ; combi {self._combimode} {modestr} ; "
                f"select {self._combimode} ; selrate {self._interval}\r"
            )
            self._simplemode = -1
            self._modestr    = modestr
            self._conn.combimode = 0
            self._conn.simplemode = -1
        else:
            if self._combimode == -1 and self._simplemode == int(modev):
                return
            if self._combimode != -1:
                self._write(f"port {self.port} ; combi {self._combimode}\r")
            self._write(f"port {self.port}; select\r")
            self._combimode  = -1
            self._simplemode = int(modev)
            self._write(f"port {self.port} ; select {int(modev)} ; selrate {self._interval}\r")
            self._conn.combimode  = -1
            self._conn.simplemode = int(modev)

    def select(self):
        """Request data from the current mode.

        :raises DeviceError: Device is not in a valid mode.
        """
        self.isconnected()
        if self._simplemode != -1:
            idx = self._simplemode
        elif self._combimode != -1:
            idx = self._combimode
        else:
            raise DeviceError("Not in simple or combimode")
        self._write(f"port {self.port} ; select {idx} ; selrate {self._interval}\r")

    def on(self):
        """Turn on the sensor."""
        self._write(f"port {self.port} ; port_plimit 1 ; on\r")

    def off(self):
        """Turn off the sensor."""
        self._write(f"port {self.port} ; off\r")

    def deselect(self):
        """Cancel data selection from the current mode."""
        self._write(f"port {self.port} ; select\r")

    def _write(self, cmd):
        self.isconnected()
        self._hat_instance.write(cmd.encode())

    def _write1(self, data):
        hexstr = ' '.join(f'{h:x}' for h in data)
        self._write(f"port {self.port} ; write1 {hexstr}\r")

    def callback(self, func):
        """Set (or clear) the data-ready callback.

        :param func: Callable invoked with new data, or ``None`` to remove.
        """
        if func is not None:
            self.select()
        else:
            self.deselect()
        self._conn.callit = weakref.WeakMethod(func) if func is not None else None

    @property
    def interval(self):
        """Polling interval in milliseconds (0–1 000 000 000).

        :getter: Returns the current interval.
        :setter: Updates the interval on the HAT.
        :rtype: int
        """
        return self._interval

    @interval.setter
    def interval(self, value):
        if isinstance(value, int) and 0 <= value <= 1_000_000_000:
            self._interval = value
            self._write(f"port {self.port} ; selrate {self._interval}\r")
        else:
            raise DeviceError("Invalid interval")