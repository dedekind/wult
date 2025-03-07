# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2020-2021 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

"""
This module contains misc. helper functions related to processes (tasks).
"""

import os
import re
import time
import logging
import contextlib
from pepclibs.helperlibs.Exceptions import Error
from pepclibs.helperlibs import LocalProcessManager, Trivial

_LOG = logging.getLogger()

def _is_sigterm(sig: str):
    """Return 'True' if sig' is the 'SIGTERM' signal."""
    return sig == "15" or sig.endswith("TERM")

def _is_sigkill(sig: str):
    """Return 'True' if sig' is the 'SIGKILL' signal."""
    return sig == "15" or sig.endswith("KILL")

def is_root(pman=None):
    """
    If 'pman' is 'None' or a local process manager object, return 'True' if current process' user
    name is 'root' and 'False' if current process' user name is not 'root'.

    If 'pman' is a remote process manager object, returns 'True' if user has 'root' permissions on
    the remote host, otherwise returns 'False'.
    """

    if not pman or not pman.is_remote:
        return Trivial.is_root()

    stdout, _ = pman.run_verify("id -u")
    stdout = stdout.strip()
    if not Trivial.is_int(stdout):
        raise Error("unexpected output from 'id -u' command, expected an integer, got:\n{stdout}")

    return int(stdout) == 0

def kill_pids(pids, sig: str = "SIGTERM", kill_children: bool = False, must_die: bool = False,
              pman=None):
    """
    This function kills or signals processes with PIDs in 'pids' on the host defined by 'procs'. The
    'pids' argument can be a collection of PID numbers ('int' or 'str' types) or a single PID
    number.

    By default the processes are killed (SIGTERM), but you can specify any signal either by name or
    by number.

    The 'children' and 'must_die' arguments must only be used when killing processes (SIGTERM or
    SIGKILL).  The 'children' argument controls whether this function should also try killing the
    children. If the 'must_die' argument is 'True', then this function also verifies that the
    process(es) did actually die, and if any of them did not die, it raises an exception.

    The 'pman' process manager object defines the system to kill processes on (local host by
    default).
    """

    def collect_zombies(pman):
        """In case of a local process we need to 'waitpid()' the children."""

        if not pman.is_remote:
            with contextlib.suppress(OSError):
                os.waitpid(0, os.WNOHANG)

    if not pman:
        pman = LocalProcessManager.LocalProcessManager()

    if not pids:
        return

    if not Trivial.is_iterable(pids):
        pids = (pids, )

    pids = [str(int(pid)) for pid in pids]

    if sig is None:
        sig = "SIGTERM"
    else:
        sig = str(sig)

    killing = _is_sigterm(sig) or _is_sigkill(sig)
    if (kill_children or must_die) and not killing:
        raise Error(f"'children' and 'must_die' arguments cannot be used with '{sig}' signal")

    if kill_children:
        # Find all the children of the process.
        for pid in pids:
            children, _, exitcode = pman.run(f"pgrep -P {pid}", join=False)
            if exitcode != 0:
                break
            pids += [child.strip() for child in children]

    pids_spc = " ".join(pids)
    pids_comma = ",".join(pids)
    _LOG.debug("sending '%s' signal to the following process%s: %s",
               sig, pman.hostmsg, pids_comma)

    try:
        pman.run_verify(f"kill -{sig} -- {pids_spc}")
    except Error as err:
        if not killing:
            raise Error(f"failed to send signal '{sig}' to PIDs '{pids_comma}'{pman.hostmsg}:\n"
                        f"{err}") from err
        # Some error happened on the first attempt. We've seen a couple of situations when this
        # happens.
        # 1. Most often, a PID does not exist anymore, the process exited already (race condition).
        # 2 One of the processes in the list is owned by a different user (e.g., root). Let's call
        #   it process A. We have no permissions to kill process A, but we can kill other processes
        #   in the 'pids' list. But often killing other processes in the 'pids' list will make
        #   process A exit. This is why we do not error out just yet.
        #
        # So the strategy is to do the second signal sending round and often times it happens
        # without errors, and all the processes that we want to kill just go away.
    if not killing:
        return

    # Give the processes up to 4 seconds to die.
    timeout = 4
    start_time = time.time()
    while time.time() - start_time <= timeout:
        collect_zombies(pman)
        _, _, exitcode = pman.run(f"kill -0 -- {pids_spc}")
        if exitcode == 1:
            return
        time.sleep(0.2)

    if _is_sigterm(sig):
        # Something refused to die, try SIGKILL.
        try:
            pman.run_verify(f"kill -9 -- {pids_spc}")
        except Error as err:
            # It is fine if one of the processes exited meanwhile.
            if "No such process" not in str(err):
                raise
        collect_zombies(pman)
        if not must_die:
            return
        # Give the processes up to 4 seconds to die.
        timeout = 4
        start_time = time.time()
        while time.time() - start_time <= timeout:
            collect_zombies(pman)
            _, _, exitcode = pman.run(f"kill -0 -- {pids_spc}")
            if exitcode != 0:
                return
            time.sleep(0.2)

    # Something refused to die, find out what.
    msg, _, = pman.run_verify(f"ps -f {pids_spc}", join=False)
    if len(msg) < 2:
        msg = pids_comma

    raise Error(f"one of the following processes{pman.hostmsg} did not die after 'SIGKILL': {msg}")

def find_processes(regex: str, pman=None):
    """
    Find all processes which match the 'regex' regular expression on the host defined by 'pman'. The
    regular expression is matched against the process executable name + command-line arguments.

    The 'pman' process manager object defines the system to find processes on (local host by
    default).

    Returns a list of tuples containing the PID and the command line.
    """

    if not pman:
        pman = LocalProcessManager.LocalProcessManager()

    cmd = "ps axo pid,args"
    stdout, stderr = pman.run_verify(cmd, join=False)

    if len(stdout) < 2:
        raise Error(f"no processes found at all{pman.hostmsg}\nExecuted this command:\n{cmd}\n"
                    f"stdout:\n{stdout}\nstderr:{stderr}\n")

    procs = []
    for line in stdout[1:]:
        pid, comm = line.strip().split(" ", 1)
        pid = int(pid)
        if pman.hostname == "localhost" and pid == Trivial.get_pid():
            continue
        if re.search(regex, comm):
            procs.append((int(pid), comm))

    return procs

def kill_processes(regex: str, sig: str = "SIGTERM", log: bool = False, name: str = None,
                   pman=None):
    """
    Kill or signal all processes matching the 'regex' regular expression on the host defined by
    'pman'. The regular expression is matched against the process executable name + command-line
    arguments.

    By default the processes are killed (SIGTERM), but you can specify any signal either by name or
    by number.

    If 'log' is 'True', then this function also prints a message which includes the PIDs of the
    processes which are going to be killed.

    The 'name' argument is a human readable name of the processes which are being killed - this name
    will be part of the printed message.

    The 'pman' process manager object defines the system to kill processes on (local host by
    default).

    Returns the list of found and killed processes.
    """

    if not pman:
        pman = LocalProcessManager.LocalProcessManager()

    procs = find_processes(regex, pman=pman)
    if not procs:
        return []

    if not name:
        name = "the following process(es)"

    pids = [pid for pid, _ in procs]
    if log:
        pids_str = ", ".join([str(pid) for pid in pids])
        _LOG.info("Sending '%s' signal to %s%s, PID(s): %s",
                  sig, name, pman.hostmsg, pids_str)

    killing = _is_sigterm(sig) or _is_sigkill(sig)
    kill_pids(pids, sig=sig, kill_children=killing, pman=pman)
    return procs
