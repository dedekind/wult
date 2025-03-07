# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2019-2021 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

"""
This module provides API for dealing with Linux function trace buffer.
"""

import logging
from pepclibs.helperlibs import FSHelpers
from pepclibs.helperlibs.Exceptions import Error, ErrorNotSupported, ErrorTimeOut
from wultlibs.helperlibs import ProcHelpers

_LOG = logging.getLogger()

class FTraceLine():
    """
    This class represents an ftrace buffer line. When an instance is created, the trace buffer line
    is split and the following attributes become available.
      * procname - process name.
      * pid - process PID.
      * cpunum - logical CPU number.
      * flags - trace flags.
      * timestamp - the trace timestamp.
      * func - name of the kernel function where the trace happened.
      * msg - the trace buffer message (comes after all the standard prefixes inlcuding process
      *       name, PID, etc)
      * line - full trace buffer line (includs all the standard prefixes)
    """

    def __init__(self, line):
        """Create a class instance for trace buffer line 'line'."""

        self.line = line.strip()
        self.procname = None
        self.pid = None
        self.cpunum = None
        self.flags = None
        self.timestamp = None
        self.func = None
        self.msg = None

        split = self.line.split(maxsplit=5)
        if len(split) == 6:
            procinfo, self.cpunum, self.flags, self.timestamp, self.func, self.msg = split
            self.procname, self.pid = procinfo.split("-")

class FTrace:
    """This class represents the Linux function trace buffer."""

    def _clear(self):
        """Clear the function trace buffer."""

        _LOG.debug("clearing the trace buffer")
        with self._pman.open(self.ftpath, "w+") as fobj:
            fobj.write("0")

    def getlines(self):
        """
        Yield trace buffer lines one-by-one. Wait for a trace line for maximum 'timeout' seconds.
        """

        while True:
            stdout, stderr, exitcode = self._reader.wait(timeout=self.timeout, lines=[32, None],
                                                         join=False)

            if not stdout and not stderr and exitcode is None:
                raise ErrorTimeOut(f"no data in trace buffer for {self._reader.timeout} seconds"
                                   f"{self._pman.hostmsg}")


            # The process has terminated or printed something to standard error.
            if exitcode is not None or stderr:
                msg = self._reader.cmd_failed_msg(stdout, stderr, exitcode)
                raise Error(f"the function trace reader process has exited unexpectedly:\n{msg}")

            for line in stdout:
                if line.startswith("#"):
                    continue
                self.raw_line = line.strip()
                yield FTraceLine(line)

    def __init__(self, pman, timeout=30):
        """
        Class constructor. The arguments are as follows.
          * pman - the process manager object object that defines the host to operate on.
          * timeout - longest time in seconds to wait for data in the trace buffer.
        """

        self._reader = None
        self._pman = pman
        self.timeout = timeout
        self.raw_line = None

        mntpoint = FSHelpers.mount_debugfs(pman=pman)
        self.ftpath = mntpoint.joinpath("tracing/trace")
        self.ftpipe_path = mntpoint.joinpath("tracing/trace_pipe")

        for path in (self.ftpath, self.ftpipe_path):
            if not FSHelpers.isfile(path, pman=pman):
                raise ErrorNotSupported(f"linux kernel function trace file was not found at "
                                        f"'{path}'{pman.hostmsg}")

        cmd = f"cat {self.ftpipe_path}"
        name = "stale wult function trace reader process"
        ProcHelpers.kill_processes(cmd, log=True, name=name, pman=self._pman)
        self._clear()
        self._reader = self._pman.run_async(cmd)

    def close(self):
        """Stop following the function trace buffer."""

        if getattr(self, "_pman", None):
            pman = self._pman
            self._pman = None
        else:
            return

        if getattr(self, "_reader", None) and getattr(self._reader, "pid", None):
            _LOG.debug("killing the function trace reader process PID %d%s",
                       self._reader.pid, pman.hostmsg)
            ProcHelpers.kill_pids(self._reader.pid, kill_children=True, must_die=False, pman=pman)
            self._reader = None

    def __enter__(self):
        """Enter the run-time context."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context."""
        self.close()
