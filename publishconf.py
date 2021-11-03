# -*- coding: utf-8 -*- #
# vim: ts=4 sw=4 tw=100 et ai si

# This file is only used if you use `make publish` or
# explicitly specify it as your config file.

import os
import sys
sys.path.append(os.curdir)
from pelicanconf import *

SITEURL = "https://intel.github.io/wult"

MENUITEMS = (
    ("How it works", "/wult/pages/how-it-works.html"),
    ("Install", "/wult/pages/install-guide.html"),
    ("Use", "/wult/pages/user-guide.html"),
    ("Ndl", "/wult/pages/ndl.html"),
)
