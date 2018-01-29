#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
#
# This file is part of Cerebrum.
#
# Cerebrum is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Cerebrum is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Cerebrum; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
Usage: get_kurs_evu_kurs <evukurskode>

Gir en oversikt over kurs med denne kurskoden og tidsangivelseskoder og
datoer.
"""

import cerebrum_path
import cereconf

from Cerebrum import database
from Cerebrum.modules.no.uio.access_FS import FS

import sys





def main():
    db_fs = database.connect(user = "ureg2000", service = "FSPROD.uio.no",
                             DB_driver = cereconf.DB_DRIVER_ORACLE)
    fs = FS(db_fs)
    print "%-20s%-10s%20s%20s" % ("kurskode", "tidskode", "fra", "til")
    print "-" * 70            
    for code in sys.argv[1:]:
        for row in fs.evu.get_kurs_informasjon(code):
            print "%-20s%-10s%20s%20s" % (row["etterutdkurskode"],
                                          row["kurstidsangivelsekode"],
                                          row["dato_fra"], row["dato_til"])
        # od
    # od
# end main



if __name__ == '__main__':
    main()
# fi

