"""Functionality for handling Build HAT devices"""

import os
import sys
import weakref
from concurrent.futures import Future

from .exc import DeviceError
from .serinterface import BuildHAT


class Device:
    """Manages BuildHAT instances with both singleton and multi-instance support.

    * The **first** HAT ever initialised becomes the default (singleton).
    * Pass ``hat_instance=`` to bind a device to a specific HAT explicitly.
    * Use :meth:`set_default_instance` / :meth:`get_default_instance` to
      inspect or swap the default at runtime.
    """

    SERIAL_DEV        = None
    RESET_GPIO_NUMBER = 4
    BOOT0_GPIO_NUMBER = 22

    # Registry: resolved_device_path -> BuildHAT
    # None-key holds the "no-device / default" slot used by the singleton path.
    _registry: dict = {}
    _default_key     = None   # key inside _registry that is the current default

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
    # Internal: canonical device path
    # ------------------------------------------------------------------

    # The hardware default when the caller passes device=None.
    _DEFAULT_SERIAL = "/dev/serial0"

    @classmethod
    def _resolve_device(cls, device):
        """Return a stable, canonical key for *device*.

        ``None`` is treated as the hardware default (``/dev/serial0``), so
        ``Hat()`` and ``Hat("/dev/serial0")`` and ``Hat("/dev/ttyAMA0")``
        (when serial0 → ttyAMA0) all map to the **same** registry key and
        therefore reuse the same BuildHAT connection.

        A concrete path is resolved via ``os.path.realpath()`` so symlinks
        collapse to a single key.
        """
        path = device if device is not None else cls._DEFAULT_SERIAL
        try:
            return os.path.realpath(path)
        except (TypeError, ValueError):
            return path

    # ------------------------------------------------------------------
    # Singleton / instance management
    # ------------------------------------------------------------------

    @classmethod
    def _default_instance(cls):
        """Return the current default BuildHAT (may be ``None``)."""
        if cls._default_key is None and not cls._registry:
            return None
        return cls._registry.get(cls._default_key)

    @classmethod
    def set_default_instance(cls, instance):
        """Replace the default (singleton) BuildHAT instance.

        :param instance: A :class:`~buildhat.serinterface.BuildHAT` instance,
            or ``None`` to clear the default.
        :returns: The *previous* default instance (may be ``None``).
        :rtype: BuildHAT | None

        Example::

            old = Device.set_default_instance(hat_b._instance)
            # old is the previous default; pass it back to restore.
        """
        prev = cls._default_instance()

        if instance is None:
            cls._default_key = None
            return prev

        # Find the registry key for this instance (O(n), n ≤ HAT count).
        for key, bhat in cls._registry.items():
            if bhat is instance:
                cls._default_key = key
                return prev

        # Not yet in the registry — add it under a synthetic key.
        key = id(instance)
        cls._registry[key] = instance
        cls._default_key = key
        return prev

    @classmethod
    def get_default_instance(cls):
        """Return the current default BuildHAT instance.

        :rtype: BuildHAT | None
        """
        return cls._default_instance()

    # ------------------------------------------------------------------
    # Internal setup helper
    # ------------------------------------------------------------------

    @staticmethod
    def _create_buildhat(device, reset_gpio, boot0_gpio, debug):
        """Unconditionally construct a new BuildHAT."""
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
        """Resolve (or create) a BuildHAT instance.

        Resolution order
        ~~~~~~~~~~~~~~~~
        1. *hat_instance* supplied → return it directly (no registry lookup).
        2. Resolved device path already in registry → return existing BuildHAT.
        3. Otherwise → create a fresh BuildHAT, register it under the canonical
           path, and apply the promotion rule:

           * No default exists yet → new HAT becomes the default.
           * An **explicit** device path was given (``device is not None``) →
             new HAT *always* becomes the default (last-explicit-init wins).
             This means ``Hat(device="/dev/ttyAMA4")`` in ``setUpClass`` is
             enough to make all subsequent bare ``Motor('A')`` calls route to
             HAT2 without any extra ``set_default_instance()`` call.
           * ``device=None`` (resolved to ``/dev/serial0``) → only promotes
             when there is no default yet, so it never clobbers an explicit one.

           ``None`` is resolved to ``/dev/serial0`` before any lookup, so
           ``Hat()``, ``Hat("/dev/serial0")``, and ``Hat("/dev/ttyAMA0")``
           (when serial0 → ttyAMA0) all share one registry entry.

        :param hat_instance: Pre-constructed BuildHAT to use as-is.
        :returns: Resolved BuildHAT instance.
        :rtype: BuildHAT
        """
        # 1. Explicit instance — bypass registry entirely.
        if hat_instance is not None:
            return hat_instance

        canonical = cls._resolve_device(device)

        # 2. We know this device path — reuse the existing connection.
        if canonical in cls._registry:
            return cls._registry[canonical]

        # 3. Create a new BuildHAT.
        # Always pass the resolved path so serial.Serial() never receives None.
        real_device = canonical  # realpath string, never None
        bhat = cls._create_buildhat(real_device, reset_gpio, boot0_gpio, debug)

        cls._registry[canonical] = bhat

        # Promotion rules:
        #   • No default yet → this HAT becomes the default (first-init wins).
        #   • An explicit device path was given → this HAT always becomes the
        #     default (last-explicit-init wins).  This lets setUpClass / script
        #     code do Hat(device="...") once and have all subsequent bare
        #     Motor('A') / ColorSensor('B') calls land on the right HAT without
        #     any extra set_default_instance() call.
        #   • device was None (resolved to the fallback path) → only promote
        #     when there is no default yet, to avoid clobbering an explicit one.
        explicit = device is not None   # True when caller passed a real path
        if cls._default_key is None or explicit:
            cls._default_key = canonical
        if cls._default_key == canonical:
            weakref.finalize(bhat, bhat.shutdown)

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
        :param device: Serial device path, or ``None`` to use the default HAT.
        :param reset_gpio: Reset GPIO number.
        :param boot0_gpio: Boot0 GPIO number.
        :param debug: Enable debug logging.
        :param hat_instance: Bind to a specific BuildHAT rather than the
            default singleton.
        :raises DeviceError: Invalid/already-used port, or wrong device type.
        """
        if not isinstance(port, str) or len(port) != 1:
            raise DeviceError("Invalid port")
        p = ord(port) - ord('A')
        if not 0 <= p <= 3:
            raise DeviceError("Invalid port")
        if Device._used[p]:
            raise DeviceError("Port already used")

        self.port = p
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
        """Python class name for a numeric device type-id.

        :param typeid: Integer device type.
        :rtype: str
        """
        return Device._device_names.get(typeid, (Device.UNKNOWN_DEVICE,))[0]

    @staticmethod
    def desc_for_id(typeid):
        """Human-readable description for a numeric device type-id.

        :param typeid: Integer device type.
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
        """:rtype: bool"""
        return self._conn.connected

    @property
    def typeid(self):
        """:rtype: int"""
        return self._typeid

    @property
    def typeidcur(self):
        """:rtype: int"""
        return self._conn.typeid

    @property
    def _hat(self):
        return self._hat_instance

    @property
    def name(self):
        """:rtype: str"""
        if not self.connected:
            return Device.DISCONNECTED_DEVICE
        return self._device_names.get(self.typeidcur, (Device.UNKNOWN_DEVICE,))[0]

    @property
    def description(self):
        """:rtype: str"""
        if not self.connected:
            return Device.DISCONNECTED_DEVICE
        if self.typeidcur in self._device_names:
            return self._device_names[self.typeidcur][1]
        return Device.UNKNOWN_DEVICE

    # ------------------------------------------------------------------
    # Device operations (unchanged from original)
    # ------------------------------------------------------------------

    def isconnected(self):
        """Assert device is still present and of the expected type.

        :raises DeviceError: Device gone or swapped.
        """
        if not self.connected:
            raise DeviceError("No device found")
        if self.typeid != self.typeidcur:
            raise DeviceError("Device has changed")

    def reverse(self):
        """Reverse polarity."""
        self._write(f"port {self.port} ; port_plimit 1 ; set -1\r")

    def get(self):
        """Read current sensor value.

        :raises DeviceError: Not in a valid mode.
        """
        self.isconnected()
        if self._simplemode == -1 and self._combimode == -1:
            raise DeviceError("Not in simple or combimode")
        ftr = Future()
        self._hat.portftr[self.port].append(ftr)
        return ftr.result()

    def mode(self, modev):
        """Set combimode (list of tuples) or simple mode (int)."""
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
            self._simplemode      = -1
            self._modestr         = modestr
            self._conn.combimode  = 0
            self._conn.simplemode = -1
        else:
            if self._combimode == -1 and self._simplemode == int(modev):
                return
            if self._combimode != -1:
                self._write(f"port {self.port} ; combi {self._combimode}\r")
            self._write(f"port {self.port}; select\r")
            self._combimode       = -1
            self._simplemode      = int(modev)
            self._write(f"port {self.port} ; select {int(modev)} ; selrate {self._interval}\r")
            self._conn.combimode  = -1
            self._conn.simplemode = int(modev)

    def select(self):
        """Request data from the current mode."""
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
        """Cancel data selection."""
        self._write(f"port {self.port} ; select\r")

    def _write(self, cmd):
        self.isconnected()
        self._hat_instance.write(cmd.encode())

    def _write1(self, data):
        hexstr = ' '.join(f'{h:x}' for h in data)
        self._write(f"port {self.port} ; write1 {hexstr}\r")

    def callback(self, func):
        """Set or clear the data-ready callback."""
        if func is not None:
            self.select()
        else:
            self.deselect()
        self._conn.callit = weakref.WeakMethod(func) if func is not None else None

    @property
    def interval(self):
        """:rtype: int"""
        return self._interval

    @interval.setter
    def interval(self, value):
        if isinstance(value, int) and 0 <= value <= 1_000_000_000:
            self._interval = value
            self._write(f"port {self.port} ; selrate {self._interval}\r")
        else:
            raise DeviceError("Invalid interval")