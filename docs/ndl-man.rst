===
ndl
===

:Date:   Manual

.. contents::
   :depth: 3
..

NAME
====

ndl

SYNOPSIS
========

**ndl** [-h] [-q] [-d] [--version] [--force-color] ...

DESCRIPTION
===========

ndl - a tool for measuring memory access latency observed by a network
card.

OPTIONS
=======

**-h**
   Show this help message and exit.

**-q**
   Be quiet.

**-d**
   Print debugging information.

**--version**
   Print version and exit.

**--force-color**
   Force coloring of the text output.

COMMANDS
========

**ndl** *deploy*
   Compile and deploy ndl helpers and drivers.

**ndl** *scan*
   Scan for device id.

**ndl** *start*
   Start the measurements.

**ndl** *report*
   Create an HTML report.

**ndl** *filter*
   Filter datapoints out of a test result.

**ndl** *calc*
   Calculate summary functions for a ndl test result.

COMMAND *'ndl* deploy'
======================

usage: ndl deploy [-h] [-q] [-d] [--kernel-src KSRC] [-H HOSTNAME] [-U
USERNAME] [-K PRIVKEY] [-T TIMEOUT]

Compile and deploy ndl helpers and drivers to the SUT (System Under
Test), which can be either local or a remote host, depending on the '-H'
option.The drivers are searched for in the following directories (and in
the following order) on the local host: ./drivers/idle,
$NDL_DATA_PATH/drivers/idle (if 'NDL_DATA_PATH' environment variable is
defined), $HOME/.local/share/wult/drivers/idle,
/usr/local/share/wult/drivers/idle, /usr/share/wult/drivers/idle.The ndl
tool also depends on the following helpers: ndlrunner. These helpers
will be compiled on the SUT and deployed to the SUT. The sources of the
helpers are searched for in the following paths (and in the following
order) on the local host: ./helpers, $NDL_DATA_PATH/helpers (if
'NDL_DATA_PATH' environment variable is defined),
$HOME/.local/share/wult/helpers, /usr/local/share/wult/helpers,
/usr/share/wult/helpers. By default, helpers are deployed to the path
defined by the NDL_HELPERSPATH environment variable. If the variable is
not defined, helpers are deployed to '$HOME/.local/bin', where '$HOME'
is the home directory of user 'USERNAME' on host 'HOST' (see '--host'
and '--username' options).

OPTIONS *'ndl* deploy'
======================

**-h**
   Show this help message and exit.

**-q**
   Be quiet.

**-d**
   Print debugging information.

**--kernel-src** *KSRC*
   Path to the Linux kernel sources to build the drivers against. The
   default is host, this is the path on the remote host (HOSTNAME).

**-H** *HOSTNAME*, **--host** *HOSTNAME*
   Name of the host to run the command on.

**-U** *USERNAME*, **--username** *USERNAME*
   Name of the user to use for logging into the remote host over SSH.
   The default user name is 'root'.

**-K** *PRIVKEY*, **--priv-key** *PRIVKEY*
   Path to the private SSH key that should be used for logging into the
   remote host. By default the key is automatically found from standard
   paths like

**-T** *TIMEOUT*, **--timeout** *TIMEOUT*
   SSH connect timeout in seconds, default is 8.

COMMAND *'ndl* scan'
====================

usage: ndl scan [-h] [-q] [-d] [-H HOSTNAME] [-U USERNAME] [-K PRIVKEY]
[-T TIMEOUT]

Scan for compatible device.

OPTIONS *'ndl* scan'
====================

**-h**
   Show this help message and exit.

**-q**
   Be quiet.

**-d**
   Print debugging information.

**-H** *HOSTNAME*, **--host** *HOSTNAME*
   Name of the host to run the command on.

**-U** *USERNAME*, **--username** *USERNAME*
   Name of the user to use for logging into the remote host over SSH.
   The default user name is 'root'.

**-K** *PRIVKEY*, **--priv-key** *PRIVKEY*
   Path to the private SSH key that should be used for logging into the
   remote host. By default the key is automatically found from standard
   paths like

**-T** *TIMEOUT*, **--timeout** *TIMEOUT*
   SSH connect timeout in seconds, default is 8.

COMMAND *'ndl* start'
=====================

usage: ndl start [-h] [-q] [-d] [-H HOSTNAME] [-U USERNAME] [-K PRIVKEY]
[-T TIMEOUT] [-c COUNT] [--time-limit LIMIT] [-o OUTDIR] [--reportid
REPORTID] [-l LDIST] [--rfilt RFILT] [--rsel RSEL] [--keep-filtered]
[--report] ifname

Start measuring and recording the latency data.

**ifname**
   The network interface backed by the NIC to use for latency
   measurements. Today only Intel I210 and I211 NICs are supported.
   Please, specify NIC's network interface name (e.g., eth0).

OPTIONS *'ndl* start'
=====================

**-h**
   Show this help message and exit.

**-q**
   Be quiet.

**-d**
   Print debugging information.

**-H** *HOSTNAME*, **--host** *HOSTNAME*
   Name of the host to run the command on.

**-U** *USERNAME*, **--username** *USERNAME*
   Name of the user to use for logging into the remote host over SSH.
   The default user name is 'root'.

**-K** *PRIVKEY*, **--priv-key** *PRIVKEY*
   Path to the private SSH key that should be used for logging into the
   remote host. By default the key is automatically found from standard
   paths like

**-T** *TIMEOUT*, **--timeout** *TIMEOUT*
   SSH connect timeout in seconds, default is 8.

**-c** *COUNT*, **--datapoints** *COUNT*
   How many datapoints should the test result include, default is
   1000000. Note, unless the '--start-over' option is used, the
   pre-existing datapoints are taken into account. For example, if the
   test result already has 6000 datapoints and '-c 10000' is used, the
   tool will collect 4000 datapoints and exit. Warning: collecting too
   many datapoints may result in a very large test result file, which
   will be difficult to process later, because that would require a lot
   of memory.

**--time-limit** *LIMIT*
   The measurement time limit, i.e., for how long the SUT should be
   measured. The default unit is minutes, but you can use the following
   handy specifiers as well: {'d': 'days', 'h': 'hours', 'm': 'minutes',
   's': 'seconds'}. For example

seconds. Value '0' means "no time limit", and this is the default. If
this option is used along with the '--datapoints' option, then
measurements will stop as when either the time limit is reached, or the
required amount of datapoints is collected.

**-o** *OUTDIR*, **--outdir** *OUTDIR*
   Path to the directory to store the results at.

**--reportid** *REPORTID*
   Any string which may serve as an identifier of this run. By default
   report ID is the current date, prefixed with the remote host name in
   case the '-H' option was used: [hostname-]YYYYMMDD. For example,
   "20150323" is a report ID for a run made on March 23, 2015. The
   allowed characters are: ACSII alphanumeric, '-', '.', ',', '_', and
   '~'.

**-l** *LDIST*, **--ldist** *LDIST*
   The launch distance in microseconds. This tool works by scheduling a
   delayed network packet, then sleeping and waiting for the packet to
   be sent. This step is referred to as a "measurement cycle" and it is
   usually repeated many times. The launch distance defines how far in
   the future the delayed network packets are scheduled. By default this
   tool randomly selects launch distance in range of [5000, 50000]
   microseconds (same as '--ldist 5000,50000'). Specify a comma-
   separated range or a single value if you want launch distance to be
   precisely that value all the time. The default unit is microseconds,
   but you can use the following specifiers as well: {'ms':
   'milliseconds', 'us': 'microseconds',

[500,100000] microseconds range. Note, too low values may cause failures
or prevent the SUT from reaching deep C-states. The optimal value is
system- specific.

**--rfilt** *RFILT*
   The row filter: remove all the rows satisfying the filter expression.
   Here is an example of an expression: '(WakeLatency < 10000) \| (PC6%
   < 1)'. This row filter expression will remove all rows with
   'WakeLatency' smaller than 10000 nanoseconds or package C6 residency
   smaller than 1%. You can use any column names in the expression.

**--rsel** *RSEL*
   The row selector: remove all rows except for those satisfying the
   selector expression. In other words, the selector is just an inverse
   filter: '--rsel expr' is the same as '--rfilt "not (expr)"'.

**--keep-filtered**
   If the '--rfilt' / '--rsel' options are used, then the datapoints not
   matching the selector or matching the filter are discarded. This is
   the default behavior which can be changed with this option. If
   '--keep-filtered' has been specified, then all datapoints are saved
   in result. Here is an example. Suppose you want to collect 100000
   datapoints where RTD is greater than 50 microseconds. In this case,
   you can use these options: -c 100000 --rfilt="RTD > 50". The result
   will contain 100000 datapoints, all of them will have RTD bigger than
   50 microseconds. But what if you do not want to simply discard the
   other datapoints, because they are also interesting? Well, add the
   '--keep- filtered' option. The result will contain, say, 150000
   datapoints, 100000 of which will have RTD value greater than 50.

**--report**
   Generate an HTML report for collected results (same as calling
   'report' command with default arguments).

COMMAND *'ndl* report'
======================

usage: ndl report [-h] [-q] [-d] [-o OUTDIR] [--rfilt RFILT] [--rsel
RSEL] [--even-up-dp-count] [-x XAXES] [-y YAXES] [--hist HIST] [--chist
CHIST] [--reportids REPORTIDS] [--title-descr TITLE_DESCR]
[--relocatable] [--list-columns] respaths [respaths ...]

Create an HTML report for one or multiple test results.

**respaths**
   One or multiple ndl test result paths.

OPTIONS *'ndl* report'
======================

**-h**
   Show this help message and exit.

**-q**
   Be quiet.

**-d**
   Print debugging information.

**-o** *OUTDIR*, **--outdir** *OUTDIR*
   Path to the directory to store the report at. By default the report
   is stored in the 'ndl-report-<reportid>' sub-directory of the test
   result directory. If there are multiple test results, the report is
   stored in the current directory. The '<reportid>' is report ID of ndl
   test result.

**--rfilt** *RFILT*
   The row filter: remove all the rows satisfying the filter expression.
   Here is an example of an expression: '(WakeLatency < 10000) \| (PC6%
   < 1)'. This row filter expression will remove all rows with
   'WakeLatency' smaller than 10000 nanoseconds or package C6 residency
   smaller than 1%. The detailed row filter expression syntax can be
   found in the documentation for the 'eval()' function of Python
   'pandas' module. You can use column names in the expression, or the
   special word 'index' for the row number. Value '0' is the header,
   value '1' is the first row, and so on. For example, expression 'index
   >= 10' will get rid of all data rows except for the first 10 ones.

**--rsel** *RSEL*
   The row selector: remove all rows except for those satisfying the
   selector expression. In other words, the selector is just an inverse
   filter: '--rsel expr' is the same as '--rfilt "not (expr)"'.

**--even-up-dp-count**
   Even up datapoints count before generating the report. This option is
   useful when generating a report for many test results (a diff). If
   the test results contain different count of datapoints (rows count in
   the CSV file), the resulting histograms may look a little bit
   misleading. This option evens up datapoints count in the test
   results. It just finds the test result with the minimum count of
   datapoints and ignores the extra datapoints in the other test
   results.

**-x** *XAXES*, **--xaxes** *XAXES*
   A comma-separated list of CSV column names (or python style regular
   expressions matching the names) to use on X-axes of the scatter
   plot(s), default is 'LDist'. Use '--list-columns' to get the list of
   the available column names. Use value 'none' to disable scatter
   plots.

**-y** *YAXES*, **--yaxes** *YAXES*
   A comma-separated list of CSV column names (or python style regular
   expressions matching the names) to use on the Y-axes for the scatter
   plot(s). If multiple CSV column names are specified for the X- or
   Y-axes, then the report will include multiple scatter plots for all
   the X- and Y-axes combinations. The default is 'RTD'. Use
   '--list-columns' to get the list of the available column names. se
   value 'none' to disable scatter plots.

**--hist** *HIST*
   A comma-separated list of CSV column names (or python style regular
   expressions matching the names) to add a histogram for, default is
   'RTD'. Use

**--chist** *CHIST*
   A comma-separated list of CSV column names (or python style regular
   expressions matching the names) to add a cumulative distribution for,
   default is 'RTD'. Use '--list-columns' to get the list of the
   available column names. Use value 'none' to disable cumulative
   histograms.

**--reportids** *REPORTIDS*
   Every input raw result comes with a report ID. This report ID is
   basically a short name for the test result, and it used in the HTML
   report to refer to the test result. However, sometimes it is helpful
   to temporarily override the report IDs just for the HTML report, and
   this is what the '--reportids' option does. Please, specify a
   comma-separated list of report IDs for every input raw test result.
   The first report ID will be used for the first raw rest result, the
   second report ID will be used for the second raw test result, and so
   on. Please, refer to the '--reportid' option description in the
   'start' command for more information about the report ID.

**--title-descr** *TITLE_DESCR*
   The report title description - any text describing this report as
   whole, or path to a file containing the overall report description.
   For example, if the report compares platform A and platform B, the
   description could be something like 'platform A vs B comparison'.
   This text will be included into the very beginning of the resulting
   HTML report.

**--relocatable**
   Generate a report which contains a copy of the raw test results. With
   this option, viewers of the report will be able to browse raw logs
   and statistics files which are copied across with the raw test
   results.

**--list-columns**
   Print the list of the available column names and exit.

COMMAND *'ndl* filter'
======================

usage: ndl filter [-h] [-q] [-d] [--rfilt RFILT] [--rsel RSEL] [--cfilt
CFILT] [--csel CSEL] [--human-readable] [-o OUTDIR] [--list-columns]
[--reportid REPORTID] respath

Filter datapoints out of a test result by removing CSV rows and columns
according to specified criteria. The criteria is specified using the row
and column filter and selector options ('--rsel', '--cfilt', etc). The
options may be specified multiple times.

**respath**
   The ndl test result path to filter.

OPTIONS *'ndl* filter'
======================

**-h**
   Show this help message and exit.

**-q**
   Be quiet.

**-d**
   Print debugging information.

**--rfilt** *RFILT*
   The row filter: remove all the rows satisfying the filter expression.
   Here is an example of an expression: '(WakeLatency < 10000) \| (PC6%
   < 1)'. This row filter expression will remove all rows with
   'WakeLatency' smaller than 10000 nanoseconds or package C6 residency
   smaller than 1%. The detailed row filter expression syntax can be
   found in the documentation for the 'eval()' function of Python
   'pandas' module. You can use column names in the expression, or the
   special word 'index' for the row number. Value '0' is the header,
   value '1' is the first row, and so on. For example, expression 'index
   >= 10' will get rid of all data rows except for the first 10 ones.

**--rsel** *RSEL*
   The row selector: remove all rows except for those satisfying the
   selector expression. In other words, the selector is just an inverse
   filter: '--rsel expr' is the same as '--rfilt "not (expr)"'.

**--cfilt** *CFILT*
   The columns filter: remove all column specified in the filter. The
   columns filter is just a comma-separated list of the CSV file column
   names or python style regular expressions matching the names. For
   example expression

columns' to get the list of the available column names.

**--csel** *CSEL*
   The columns selector: remove all column except for those specified in
   the selector. The syntax is the same as for '--cfilt'.

**--human-readable**
   By default the result 'filter' command print the result as a CSV file
   to the standard output. This option can be used to dump the result in
   a more human- readable form.

**-o** *OUTDIR*, **--outdir** *OUTDIR*
   By default the resulting CSV lines are printed to the standard
   output. But this option can be used to specify the output directly to
   store the result at. This will create a filtered version of the input
   test result.

**--list-columns**
   Print the list of the available column names and exit.

**--reportid** *REPORTID*
   Report ID of the filtered version of the result (can only be used
   with '-- outdir').

COMMAND *'ndl* calc'
====================

usage: ndl calc [-h] [-q] [-d] [--rfilt RFILT] [--rsel RSEL] [--cfilt
CFILT] [--csel CSEL] [-f FUNCS] [--list-funcs] respath

Calculates various summary functions for a ndl test result (e.g., the
median value for one of the CSV columns).

**respath**
   The ndl test result path to calculate summary functions for.

OPTIONS *'ndl* calc'
====================

**-h**
   Show this help message and exit.

**-q**
   Be quiet.

**-d**
   Print debugging information.

**--rfilt** *RFILT*
   The row filter: remove all the rows satisfying the filter expression.
   Here is an example of an expression: '(WakeLatency < 10000) \| (PC6%
   < 1)'. This row filter expression will remove all rows with
   'WakeLatency' smaller than 10000 nanoseconds or package C6 residency
   smaller than 1%. The detailed row filter expression syntax can be
   found in the documentation for the 'eval()' function of Python
   'pandas' module. You can use column names in the expression, or the
   special word 'index' for the row number. Value '0' is the header,
   value '1' is the first row, and so on. For example, expression 'index
   >= 10' will get rid of all data rows except for the first 10 ones.

**--rsel** *RSEL*
   The row selector: remove all rows except for those satisfying the
   selector expression. In other words, the selector is just an inverse
   filter: '--rsel expr' is the same as '--rfilt "not (expr)"'.

**--cfilt** *CFILT*
   The columns filter: remove all column specified in the filter. The
   columns filter is just a comma-separated list of the CSV file column
   names or python style regular expressions matching the names. For
   example expression

columns' to get the list of the available column names.

**--csel** *CSEL*
   The columns selector: remove all column except for those specified in
   the selector. The syntax is the same as for '--cfilt'.

**-f** *FUNCS*, **--funcs** *FUNCS*
   Comma-separated list of summary functions to calculate. By default
   all generally interesting functions are calculated (each column name
   is associated with a list of functions that make sense for this
   column). Use '--list-funcs' to get the list of supported functions.

**--list-funcs**
   Print the list of the available summary functions.

AUTHORS
=======

**ndl** was written by Artem Bityutskiy <dedekind1@gmail.com>.

DISTRIBUTION
============

The latest version of ndl may be downloaded from
` <https://github.com/intel/ndl>`__
