#!/usr/bin/python3
#
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2019-2021 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

"""ndl - a tool for measuring memory access latency observed by a network card."""

import sys
import logging
from pathlib import Path

try:
    import argcomplete
except ImportError:
    # We can live without argcomplete, we only lose tab completions.
    argcomplete = None

from pepclibs.helperlibs import Logging, ArgParse, Trivial
from pepclibs.helperlibs.Exceptions import Error
from wultlibs import Deploy, ToolsCommon, NdlRunner, NetIface
from wultlibs.helperlibs import ReportID, Human
from wultlibs.rawresultlibs import WORawResult
from wultlibs.htmlreport import NdlReport

VERSION = "1.3.13"
OWN_NAME = "ndl"

LOG = logging.getLogger()
Logging.setup_logger(prefix=OWN_NAME)

def get_axes_default(name):
    """Returns the default CSV column names for X- or Y-axes, as well as histograms."""

    names = getattr(NdlReport, f"DEFAULT_{name.upper()}")
    # The result is used for argparse, which does not accept '%' symbols.
    return names.replace("%", "%%")

def build_arguments_parser():
    """Build and return the arguments parser object."""

    text = "ndl - a tool for measuring memory access latency observed by a network card."
    parser = ArgParse.SSHOptsAwareArgsParser(description=text, prog=OWN_NAME, ver=VERSION)

    text = "Force coloring of the text output."
    parser.add_argument("--force-color", action="store_true", help=text)
    subparsers = parser.add_subparsers(title="commands", metavar="")
    subparsers.required = True

    #
    # Create parsers for the "deploy" command.
    #
    Deploy.add_deploy_cmdline_args(subparsers, OWN_NAME, Deploy.deploy_command, drivers=True,
                                   helpers=["ndlrunner"], argcomplete=argcomplete)

    #
    # Create parsers for the "scan" command.
    #
    text = "Scan for device id."
    descr = """Scan for compatible device."""
    subpars = subparsers.add_parser("scan", help=text, description=descr)
    subpars.set_defaults(func=ToolsCommon.scan_command)

    ArgParse.add_ssh_options(subpars)

    #
    # Create parsers for the "start" command.
    #
    text = "Start the measurements."
    descr = """Start measuring and recording the latency data."""
    subpars = subparsers.add_parser("start", help=text, description=descr)
    subpars.set_defaults(func=start_command)

    ArgParse.add_ssh_options(subpars)

    subpars.add_argument("-c", "--datapoints", default=1000000, metavar="COUNT", dest="dpcnt",
                         help=ToolsCommon.DATAPOINTS_DESCR)
    subpars.add_argument("--time-limit", dest="tlimit", metavar="LIMIT",
                         help=ToolsCommon.TIME_LIMIT_DESCR)

    arg = subpars.add_argument("-o", "--outdir", type=Path, help=ToolsCommon.START_OUTDIR_DESCR)
    if argcomplete:
        arg.completer = argcomplete.completers.DirectoriesCompleter()

    text = ToolsCommon.get_start_reportid_descr(ReportID.get_charset_descr())
    subpars.add_argument("--reportid", help=text)

    text = f"""The launch distance in microseconds. This tool works by scheduling a delayed network
               packet, then sleeping and waiting for the packet to be sent. This step is referred to
               as a "measurement cycle" and it is usually repeated many times. The launch distance
               defines how far in the future the delayed network packets are scheduled. By
               default this tool randomly selects launch distance in range of [5000, 50000]
               microseconds (same as '--ldist 5000,50000'). Specify a comma-separated range or a
               single value if you want launch distance to be precisely that value all the time. The
               default unit is microseconds, but you can use the following specifiers as well:
               {Human.DURATION_NS_SPECS_DESCR}. For example, '--ldist 500us,100ms' would be a
               [500,100000] microseconds range.  Note, too low values may cause failures or prevent
               the SUT from reaching deep C-states. The optimal value is system-specific."""
    subpars.add_argument("-l", "--ldist", default="5000,50000", help=text)

    subpars.add_argument("--rfilt", action=ArgParse.OrderedArg, help=ToolsCommon.RFILT_START_DESCR)
    subpars.add_argument("--rsel", action=ArgParse.OrderedArg, help=ToolsCommon.RSEL_DESCR)
    text = f"""{ToolsCommon.KEEP_FILTERED_DESCR} Here is an example. Suppose you want to collect
               100000 datapoints where RTD is greater than 50 microseconds. In this case, you can
               use these options: -c 100000 --rfilt="RTD > 50". The result will contain 100000
               datapoints, all of them will have RTD bigger than 50 microseconds. But what if you do
               not want to simply discard the other datapoints, because they are also interesting?
               Well, add the '--keep-filtered' option. The result will contain, say, 150000
               datapoints, 100000 of which will have RTD value greater than 50."""
    subpars.add_argument("--keep-filtered", action="store_true", help=text)

    text = """Generate an HTML report for collected results (same as calling 'report' command with
              default arguments)."""
    subpars.add_argument("--report", action="store_true", help=text)

    text = """The network interface backed by the NIC to use for latency measurements. Today only
              Intel I210 and I211 NICs are supported. Please, specify NIC's network interface name
              (e.g., eth0)."""
    subpars.add_argument("ifname", help=text)

    #
    # Create parsers for the "report" command.
    #
    text = "Create an HTML report."
    descr = """Create an HTML report for one or multiple test results."""
    subpars = subparsers.add_parser("report", help=text, description=descr)
    subpars.set_defaults(func=report_command)

    subpars.add_argument("-o", "--outdir", type=Path,
                         help=ToolsCommon.get_report_outdir_descr(OWN_NAME))
    subpars.add_argument("--rfilt", action=ArgParse.OrderedArg, help=ToolsCommon.RFILT_DESCR)
    subpars.add_argument("--rsel", action=ArgParse.OrderedArg, help=ToolsCommon.RSEL_DESCR)
    subpars.add_argument("--even-up-dp-count", action="store_true", dest="even_dpcnt",
                         help=ToolsCommon.EVEN_UP_DP_DESCR)
    subpars.add_argument("-x", "--xaxes", help=ToolsCommon.XAXES_DESCR % get_axes_default('xaxes'))
    subpars.add_argument("-y", "--yaxes", help=ToolsCommon.YAXES_DESCR % get_axes_default('yaxes'))
    subpars.add_argument("--hist", help=ToolsCommon.HIST_DESCR % get_axes_default('hist'))
    subpars.add_argument("--chist", help=ToolsCommon.CHIST_DESCR % get_axes_default('chist'))
    subpars.add_argument("--reportids", help=ToolsCommon.REPORTIDS_DESCR)
    subpars.add_argument("--title-descr", help=ToolsCommon.TITLE_DESCR)
    subpars.add_argument("--relocatable", action="store_true", help=ToolsCommon.RELOCATABLE_DESCR)
    subpars.add_argument("--list-columns", action="store_true", help=ToolsCommon.LIST_COLUMNS_DESCR)

    text = f"""One or multiple {OWN_NAME} test result paths."""
    subpars.add_argument("respaths", nargs="+", type=Path, help=text)

    #
    # Create parsers for the "filter" command.
    #
    text = "Filter datapoints out of a test result."
    subpars = subparsers.add_parser("filter", help=text, description=ToolsCommon.FILT_DESCR)
    subpars.set_defaults(func=ToolsCommon.filter_command)

    subpars.add_argument("--rfilt", action=ArgParse.OrderedArg, help=ToolsCommon.RFILT_DESCR)
    subpars.add_argument("--rsel", action=ArgParse.OrderedArg, help=ToolsCommon.RSEL_DESCR)
    subpars.add_argument("--cfilt", action=ArgParse.OrderedArg, help=ToolsCommon.CFILT_DESCR)
    subpars.add_argument("--csel", action=ArgParse.OrderedArg, help=ToolsCommon.CSEL_DESCR)
    subpars.add_argument("--human-readable", action="store_true",
                         help=ToolsCommon.FILTER_HUMAN_DESCR)
    subpars.add_argument("-o", "--outdir", type=Path, help=ToolsCommon.FILTER_OUTDIR_DESCR)
    subpars.add_argument("--list-columns", action="store_true", help=ToolsCommon.LIST_COLUMNS_DESCR)
    subpars.add_argument("--reportid", help=ToolsCommon.FILTER_REPORTID_DESCR)

    text = f"The {OWN_NAME} test result path to filter."
    subpars.add_argument("respath", type=Path, help=text)

    #
    # Create parsers for the "calc" command.
    #
    text = f"Calculate summary functions for a {OWN_NAME} test result."
    descr = f"""Calculates various summary functions for a {OWN_NAME} test result (e.g., the median
                value for one of the CSV columns)."""
    subpars = subparsers.add_parser("calc", help=text, description=descr)
    subpars.set_defaults(func=ToolsCommon.calc_command)

    subpars.add_argument("--rfilt", action=ArgParse.OrderedArg, help=ToolsCommon.RFILT_DESCR)
    subpars.add_argument("--rsel", action=ArgParse.OrderedArg, help=ToolsCommon.RSEL_DESCR)
    subpars.add_argument("--cfilt", action=ArgParse.OrderedArg, help=ToolsCommon.CFILT_DESCR)
    subpars.add_argument("--csel", action=ArgParse.OrderedArg, help=ToolsCommon.CSEL_DESCR)
    subpars.add_argument("-f", "--funcs", help=ToolsCommon.FUNCS_DESCR)
    subpars.add_argument("--list-funcs", action="store_true", help=ToolsCommon.LIST_FUNCS_DESCR)

    text = f"""The {OWN_NAME} test result path to calculate summary functions for."""
    subpars.add_argument("respath", type=Path, help=text)

    if argcomplete:
        argcomplete.autocomplete(parser)

    return parser

def parse_arguments():
    """Parse input arguments."""

    parser = build_arguments_parser()

    args = parser.parse_args()
    args.toolname = OWN_NAME
    args.minkver = "5.1-rc1"
    args.devtypes = ("i210",)

    return args

def start_command(args):
    """Implements the 'start' command."""

    pman = ToolsCommon.get_pman(args)

    if not args.reportid and pman.is_remote:
        prefix = pman.hostname
    else:
        prefix = None
    args.reportid = ReportID.format_reportid(prefix=prefix, reportid=args.reportid,
                                             strftime=f"{OWN_NAME}-%Y%m%d")

    if not args.outdir:
        args.outdir = Path(f"./{args.reportid}")
    if args.tlimit:
        args.tlimit = Human.parse_duration(args.tlimit, default_unit="m", name="time limit")

    args.ldist = ToolsCommon.parse_ldist(args.ldist)

    # Figure out the helper path.
    helpers_path = Deploy.get_helpers_deploy_path(pman, OWN_NAME)
    ndlrunner_bin = helpers_path / "ndlrunner"

    if Deploy.is_deploy_needed(pman, OWN_NAME, helpers=["ndlrunner"]):
        msg = f"'{OWN_NAME}' helpers and/or drivers are not up-to-date{pman.hostmsg}, " \
              f"please run: {OWN_NAME} deploy"
        if pman.is_remote:
            msg += f" -H {pman.hostname}"
        LOG.warning(msg)

    if not Trivial.is_int(args.dpcnt) or int(args.dpcnt) <= 0:
        raise Error(f"bad datapoints count '{args.dpcnt}', should be a positive integer")
    args.dpcnt = int(args.dpcnt)

    with WORawResult.NdlWORawResult(args.reportid, args.outdir, VERSION) as res:
        ToolsCommon.setup_stdout_logging(OWN_NAME, res.logs_path)
        ToolsCommon.set_filters(args, res)

        with NetIface.NetIface(args.ifname, pman=pman) as netif:
            info = netif.get_pci_info()
            if info.get("aspm_enabled"):
                LOG.notice("PCI ASPM is enabled for the NIC '%s', and this typically increases "
                           "the measured latency.", args.ifname)

            with NdlRunner.NdlRunner(pman, netif, res, ndlrunner_bin, ldist=args.ldist) as runner:
                runner.prepare()
                runner.run(dpcnt=args.dpcnt, tlimit=args.tlimit)

    if not args.report:
        return

    rsts = ToolsCommon.open_raw_results([args.outdir], args.toolname)
    rep = NdlReport.NdlReport(rsts, args.outdir, title_descr=args.reportid)
    rep.relocatable = False
    rep.generate()

def report_command(args):
    """Implements the 'report' command."""

    # Split the comma-separated lists.
    for name in ("xaxes", "yaxes", "hist", "chist"):
        val = getattr(args, name)
        if val:
            if val == "none":
                setattr(args, name, "")
            else:
                setattr(args, name, Trivial.split_csv_line(val))

    rsts = ToolsCommon.open_raw_results(args.respaths, args.toolname, reportids=args.reportids)

    if args.list_columns:
        ToolsCommon.list_result_columns(rsts)
        return

    for res in rsts:
        ToolsCommon.apply_filters(args, res)

    if args.even_dpcnt:
        ToolsCommon.even_up_dpcnt(rsts)

    if args.outdir is None:
        if len(args.respaths) > 1:
            args.outdir = ReportID.format_reportid(prefix=f"{OWN_NAME}-report",
                                                   reportid=rsts[0].reportid)
        else:
            args.outdir = args.respaths[0]

        args.outdir = Path(args.outdir)
        LOG.info("Generating report into: %s", args.outdir)

    rep = NdlReport.NdlReport(rsts, args.outdir, title_descr=args.title_descr,
                                      xaxes=args.xaxes, yaxes=args.yaxes, hist=args.hist,
                                      chist=args.chist)
    rep.relocatable = args.relocatable
    rep.generate()

def main():
    """Script entry point."""

    try:
        args = parse_arguments()

        if not getattr(args, "func", None):
            LOG.error("please, run '%s -h' for help.", OWN_NAME)
            return -1

        args.func(args)
    except KeyboardInterrupt:
        LOG.info("Interrupted, exiting")
        return -1
    except Error as err:
        LOG.error_out(err)
        return -1

    return 0

# The script entry point.
if __name__ == "__main__":
    sys.exit(main())
