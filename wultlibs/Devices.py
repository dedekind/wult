# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2019-2021 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

"""
This module provides an abstraction for a device that can be used as a source of delayed events
(e.g., the I210 network card). This module basically provides 2 methods - 'WultDevice()' and
'scan_devices()'. The former is a factory method that figures out what wult device object to return
(wult device class API is defined by '_WultDeviceBase'. The latter scans the target host for
compatible wult devices.
"""

import contextlib
import logging
from pathlib import Path
from pepclibs.helperlibs import FSHelpers, Dmesg
from pepclibs.helperlibs.Exceptions import Error, ErrorNotFound, ErrorNotSupported
from wultlibs import NetIface, LsPCI

# All the possible wult device driver names.
DRVNAMES = set()

# All supported device types.
DEVTYPES = ("i210", "tdt", "hrtimer")

_LOG = logging.getLogger()

class _WultDeviceBase:
    """
    This is the base class for wult delayed event devices. It has 2 purposes.
       * Implement common functionality.
       * Define the API that subclasses (particular device types) have to implement.
    """

    # Name of wult driver that handles this device.
    drvname = None

    def bind(self, drvname): # pylint: disable=no-self-use, unused-argument
        """Bind the device to the 'drvname' driver."""

    def unbind(self): # pylint: disable=no-self-use
        """
        Unbind the device from its driver if it is bound to any driver. Returns name of the
        driver the was unbinded from (or 'None' if it was not).
        """
        return None

    def get_new_dmesg(self):
        """
        Return new dmesg messages as a single string, if available."""

        if not self.dmesg_obj:
            return ""
        new_msgs = self.dmesg_obj.get_new_messages(join=True)
        if new_msgs:
            return f"New kernel messages{self._pman.hostmsg}:\n{new_msgs}"
        return ""

    def __init__(self, devid, cpunum, pman, dmesg=None):
        """
        The class constructor. The arguments are as follows.
          * devid - device ID. What the "ID" is depends on the device type.
          * pman - the host process manager object defining the host to operate on.
          * cpunum - the measured CPU number.
          * dmesg - 'True' to enable 'dmesg' output checks (default), 'False' to disable them.
        """

        if not devid:
            raise Error("device ID was not provided")

        if dmesg is None:
            dmesg = True

        self._devid = devid
        self._cpunum = cpunum
        self._pman = pman
        self.dmesg_obj = None

        if dmesg:
            self.dmesg_obj = Dmesg.Dmesg(pman=self._pman)
            self.dmesg_obj.run(capture=True)

        # Device information dictionary. Every subclass is expected to provide the following keys.
        # * name - device name (string). Should be short (1-2 words), preferably human-readable.
        #          Should not be capitalized, unless it is necessary (e.g., in case of an acronym).
        # * devid - canonical device ID (string). Does not have to be the same as the 'devid'
        #           argument. Instead, it should be the best type of ID the device can be found on
        #           the system. E.g., in case of PCI devices it would be the PCI address.
        # * descr - device description. May contain multiple sentences. Every sentence should start
        #           with a capital letter and end with a dot.
        #
        # Each subclass is free to add more information to this dictionary.
        self.info = {"name" : None, "devid" : None, "descr" : None}

    def close(self):
        """Uninitialize the device."""
        if getattr(self, "_pman", None):
            self._pman = None
        if getattr(self, "dmesg_obj", None):
            self.dmesg_obj.close()
            self.dmesg_obj = None

    def __enter__(self):
        """Enter the run-time context."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context."""
        self.close()

    def __init_subclass__(cls, **_):
        """Populate the device driver names collection ('DRVNAMES')."""
        if cls.drvname:
            DRVNAMES.add(cls.drvname)


class _PCIDevice(_WultDeviceBase):
    """This class represents a PCI device that can be used for as a source of delayed events."""

    # Subclasses can define this dictionary to limit list of supported PCI devices.
    supported_devices = {}

    def _get_driver(self):
        """
        Find out whether the PCI device is bound to any driver. If it is not, returns the
        '(None, None)' tuple. Otherwise returns a tuple of:
         * driver name
         * driver sysfs path
        """

        drvpath = Path(f"{self._devpath}/driver")
        if not FSHelpers.exists(drvpath, pman=self._pman):
            return (None, None)

        drvpath = FSHelpers.abspath(drvpath, pman=self._pman)
        drvname = Path(drvpath).name
        return (drvname, drvpath)

    def get_driver_name(self):
        """
        Returns name of the driver the PCI device is bound to, or 'None' in case it is not bound to
        any driver.
        """

        return self._get_driver()[0]

    def bind(self, drvname):
        """Bind the PCI device to driver 'drvname'."""

        _LOG.debug("binding device '%s' to driver '%s'%s",
                   self._pci_info["pciaddr"], drvname, self._pman.hostmsg)

        failmsg = f"failed to bind device '{self._pci_info['pciaddr']}' to driver '{drvname}'" \
                  f"{self._pman.hostmsg}"

        drvpath = Path(f"/sys/bus/pci/drivers/{drvname}")
        if not FSHelpers.exists(drvpath, pman=self._pman):
            raise Error(f"{failmsg}':\npath '{drvpath}' does not exist{self._pman.hostmsg}")

        cur_drvname = self.get_driver_name()
        if cur_drvname == drvname:
            _LOG.debug("device '%s' is already bound to driver '%s'%s",
                       self._pci_info["pciaddr"], drvname, self._pman.hostmsg)
            return

        if cur_drvname:
            raise Error(f"{failmsg}:\nit is already bound to driver '{cur_drvname}'")

        # At this point we do not know if the driver supports this PCI ID. So start with the
        # assumption that it does not, in which case writing to the 'new_id' file should do both:
        # * make the driver aware of the PCI ID
        # * bind the device
        path = f"{drvpath}/new_id"
        val = f"{self._pci_info['vendorid']} {self._pci_info['devid']}"
        bound = True

        try:
            with self._pman.open(path, "wt") as fobj:
                _LOG.debug("writing '%s' to file '%s'", val, path)
                fobj.write(val)
        except Error as err:
            bound = False

        if not bound:
            # Probably the driver already knows about this PCI ID. Use the 'bind' file in this case.
            path = f"{drvpath}/bind"
            val = self._pci_info["pciaddr"]
            with self._pman.open(path, "wt") as fobj:
                _LOG.debug("writing '%s' to file '%s'", val, path)
                try:
                    fobj.write(val)
                except Error as err:
                    raise Error(f"{failmsg}:\n{err}\n{self.get_new_dmesg()}") from err

        # Verify that the device is bound to the driver.
        if not self._get_driver()[1]:
            raise Error(f"{failmsg}\n{self.get_new_dmesg()}")

        _LOG.debug("binded device '%s' to driver '%s'%s\n%s", self._pci_info["pciaddr"], drvname,
                   self._pman.hostmsg, self.get_new_dmesg())

    def unbind(self):
        """
        Unbind the PCI device from its driver if it is bound to any driver. Returns name of the
        driver the was unbinded from (or 'None' if it was not).
        """

        drvname, drvpath = self._get_driver()

        if not drvname:
            _LOG.debug("device '%s' is not bound to any driver%s",
                       self._pci_info["pciaddr"], self._pman.hostmsg)
            return drvname

        _LOG.debug("unbinding device '%s' from driver '%s'%s",
                   self._pci_info["pciaddr"], drvname, self._pman.hostmsg)

        failmsg = f"failed to unbind PCI device '{self._pci_info['pciaddr']}' from driver " \
                  f"'{drvname}'{self._pman.hostmsg}"

        with self._pman.open(drvpath / "unbind", "wt") as fobj:
            _LOG.debug("writing '%s' to '%s'", self._pci_info["pciaddr"], drvpath / "unbind")
            try:
                fobj.write(self._pci_info["pciaddr"])
            except Error as err:
                raise Error(f"{failmsg}:\n{err}\n{self.get_new_dmesg()}") from err

        if self._get_driver()[1]:
            raise Error(f"{failmsg}:\npath '{drvpath}' still exists\n{self.get_new_dmesg()}")

        _LOG.debug("unbinded device '%s' from driver '%s'%s\n%s", self._pci_info["pciaddr"],
                   drvname, self._pman.hostmsg, self.get_new_dmesg())

        return drvname

    def __init__(self, devid, cpunum, pman, dmesg=None):
        """The class constructor. The arguments are the same as in '_WultDeviceBase.__init__()'."""

        super().__init__(devid, cpunum, pman, dmesg=dmesg)

        self._pci_info = None
        self._devpath = None

        path = Path(f"/sys/bus/pci/devices/{self._devid}")
        if not FSHelpers.exists(path, pman=pman):
            raise ErrorNotFound(f"cannot find device '{self._devid}'{self._pman.hostmsg}:\n"
                                f"path {path} does not exist")

        self._devpath = FSHelpers.abspath(path, pman=self._pman)
        self._pci_info = LsPCI.LsPCI(pman).get_info(Path(self._devpath).name)

        if self.supported_devices and self._pci_info["devid"] not in self.supported_devices:
            supported = ["%s - %s" % (key, val) for key, val in self.supported_devices.items()]
            supported = "\n * ".join(supported)
            raise ErrorNotSupported(f"PCI device '{self._pci_info['pciaddr']}' (PCI ID "
                                    f"{self._pci_info['devid']}) is not supported by wult driver "
                                    f"{self.drvname}.\nHere is the list of supported PCI IDs:\n* "
                                    f"{supported}")

        self.info["name"] = "Intel I210"
        self.info["devid"] = self._pci_info["pciaddr"]
        if self.supported_devices:
            self.info["descr"] = self.supported_devices[self._pci_info["devid"]]
        else:
            self.info["name"] = self._pci_info["name"]
            self.info["descr"] = self.info['name'].capitalize()

        self.info["descr"] += f". PCI address {self._pci_info['pciaddr']}, Vendor ID " \
                              f"{self._pci_info['vendorid']}, Device ID {self._pci_info['devid']}."
        self.info["aspm_enabled"] = self._pci_info["aspm_enabled"]

class _IntelI210(_PCIDevice):
    """
    This class extends the '_PCIDevice' class with 'Intel I210' NIC support.
    """

    drvname = "wult_igb"
    supported_devices = {
        '1533' : 'Intel I210 (copper)',
        '1536' : 'Intel I210 (fiber)',
        '1537' : 'Intel I210 (serdes)',
        '1538' : 'Intel I210 (sgmii)',
        '157b' : 'Intel I210 (copper flashless)',
        '157c' : 'Intel I210 (serdes flashless)',
        '1539' : 'Intel I211 (copper)'}

    def __init__(self, devid, cpunum, pman, dmesg=None, force=False):
        """
        The class constructor. The 'force' argument can be used to initialize I210 device for
        measurements even if its network interface state is "up". Other arguments are the same as in
        '_WultDeviceBase.__init__()'. The 'devid' can be be the PCI address or the network interface
        name.
        """

        netif = None
        try:
            netif = NetIface.NetIface(devid, pman=pman)
        except ErrorNotFound:
            pass

        if netif:
            # Make sure the device is not used for networking, because we are about to unbind it
            # from the driver. This check makes sure users do not lose networking by specifying
            # wrong device by a mistake.
            if not force and netif.getstate() == "up":
                msg = ""
                if devid != netif.ifname:
                    msg = f" (network interface '{netif.ifname}')"

                raise Error(f"refusing to use device '{devid}'{msg}{pman.hostmsg}: "
                            f"it is up and might be used for networking. Please, bring it down "
                            f"if you want to use it for wult measurements.")
            hwaddr = netif.hwaddr
        else:
            hwaddr = devid

        super().__init__(hwaddr, cpunum, pman, dmesg=dmesg)

class _TSCDeadlineTimer(_WultDeviceBase):
    """
    This class represents the TSC deadline timer (TDT). TDT is a LAPIC feature supported by modern
    Intel CPUs. TDT allows to schedule a timer interrupt to happen in the future when TSC reaches
    certain value. Wult can use this as a source of delayed events.
    """

    drvname = "wult_tdt"
    supported_devices = {"tdt" : "TSC deadline timer"}
    alias = "tsc-deadline-timer"

    def __init__(self, devid, cpunum, pman, dmesg=None):
        """The class constructor. The arguments are the same as in '_WultDeviceBase.__init__()'."""

        errmsg = f"device '{devid}' is not supported for CPU {cpunum}{pman.hostmsg}."
        if devid not in self.supported_devices and devid != self.alias:
            raise ErrorNotSupported(f"{errmsg}")

        path = Path(f"/sys/devices/system/clockevents/clockevent{cpunum}/current_device")
        with pman.open(path, "r") as fobj:
            clkname = fobj.read().strip()
            if clkname != "lapic-deadline":
                raise ErrorNotSupported(f"{errmsg}\nCurrent clockevent device is {clkname}, "
                                        f"should be 'lapic-deadline' (see {path})")

        super().__init__(devid, cpunum, pman, dmesg=dmesg)

        self.info["name"] = "tdt"
        self.info["devid"] = devid
        self.info["alias"] = self.alias
        self.info["descr"] = self.supported_devices["tdt"]

class _LinuxHRTimer(_WultDeviceBase):
    """
    This class represents Linux High Resolution Timers (hrtimers). Hrtimer is basically a Linux
    kernel API for using hardware timers in a platform-independent manner. On a modern Intel CPUs,
    hrtimers typically use TSC deadline timer under the hood, but may also use LAPIC timers. So this
    device may end up using the same hardware as '_TSCDeadlineTimer'. But the '_TSCDeadlineTimer' is
    a bit more precise because it directly acesses the TDT hardware registers and it is not affected
    by Linux hrtimers sybsystem overhead. On the other hand, hrtimers work with both LAPIC and TSC
    deadline timers.
    """

    drvname = "wult_hrtimer"
    supported_devices = {"hrtimer" : "Linux High Resolution Timer"}
    alias = "hrt"

    def __init__(self, devid, cpunum, pman, dmesg=None):
        """The class constructor. The arguments are the same as in '_WultDeviceBase.__init__()'."""

        if devid not in self.supported_devices and devid != self.alias:
            raise ErrorNotSupported(f"device '{devid}' is not supported for CPU "
                                    f"{cpunum}{pman.hostmsg}.")

        super().__init__(devid, cpunum, pman, dmesg=dmesg)

        self.info["name"] = "hrtimer"
        self.info["devid"] = devid
        self.info["alias"] = self.alias
        self.info["descr"] = self.supported_devices["hrtimer"]

def WultDevice(devid, cpunum, pman, dmesg=None, force=False):
    """
    The wult device object factory - creates and returns the correct type of wult device object
    depending on 'devid'. The arguments are the same as in '_WultDeviceBase.__init__()'.
    """

    if devid in _TSCDeadlineTimer.supported_devices or devid in _TSCDeadlineTimer.alias:
        return _TSCDeadlineTimer(devid, cpunum, pman, dmesg=dmesg)

    if devid in _LinuxHRTimer.supported_devices or devid in _LinuxHRTimer.alias:
        return _LinuxHRTimer(devid, cpunum, pman, dmesg=dmesg)

    try:
        return _IntelI210(devid, cpunum, pman, dmesg=dmesg, force=force)
    except ErrorNotSupported as err:
        raise ErrorNotSupported(f"unsupported device '{devid}'{pman.hostmsg}") from err

def scan_devices(pman, devtypes=None):
    """
    Scan the host defined by 'pman' for compatible devices. The 'devtypes' argument can be
    used to limit the scan to only certain type of devices. Supported device types are 'i210' for
    Intel i210 NIC and 'tdt' for TSC deadline timer. Scanning all devices by default.

    Yields tuples of the following elements:
     * devid - device ID of the found compatible device
     * alias - device ID aliases for the device ('None' if there are no aliases). Alias is just
               another device ID for the same device.
     * descr - short device description
    """

    if devtypes is None:
        devtypes = DEVTYPES

    if "tdt" in devtypes:
        for devid in _TSCDeadlineTimer.supported_devices:
            with contextlib.suppress(Error):
                with _TSCDeadlineTimer(devid, 0, pman, dmesg=False) as timerdev:
                    yield timerdev.info["devid"], timerdev.info["alias"], timerdev.info["descr"]

    if "hrtimer" in devtypes:
        for devid in _LinuxHRTimer.supported_devices:
            with contextlib.suppress(Error):
                with _LinuxHRTimer(devid, 0, pman, dmesg=False) as timerdev:
                    yield timerdev.info["devid"], timerdev.info["alias"], timerdev.info["descr"]

    if "i210" in devtypes:
        for pci_info in LsPCI.LsPCI(pman).get_devices():
            pci_id = pci_info["devid"]
            if not _IntelI210.supported_devices.get(pci_id):
                continue

            devid = pci_info['pciaddr']

            # Find out the Linux network interface name for this NIC, if any.
            ifname = None
            with contextlib.suppress(Error):
                with NetIface.NetIface(devid, pman=pman) as netif:
                    ifname = netif.ifname

            descr = _IntelI210.supported_devices.get(pci_id)
            descr += f". PCI address {pci_info['pciaddr']}, Vendor ID {pci_info['vendorid']}, " \
                     f"Device ID {devid}."
            yield devid, ifname, descr
