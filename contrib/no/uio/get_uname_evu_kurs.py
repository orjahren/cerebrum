#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
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
Usage: get_kurs_evu_kurs <evukurskode> <tidskode>

Gir en oversikt over brukernavnene til de som er registrert p� evu
kurset og en oversikt over hvem som ikke har brukernavn.
"""

import cerebrum_path
import cereconf

from Cerebrum import database
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.no.uio.access_FS import FS

import sys
import time





def fetch_primary_uname(row, person, account, constants):

    birth_date = str(row['fodselsdato']).zfill(6)
    no_ssn = birth_date + str(row['personnr']).zfill(5)
    sources = map(lambda x: getattr( constants, x ),
                  cereconf.SYSTEM_LOOKUP_ORDER)
    sources.append(None)

    # Jupp, we try extra hard to get a username
    for source in sources:
        try:
            person.clear()
            person.find_by_external_id(constants.externalid_fodselsnr,
                                       no_ssn,
                                       source_system = source)
            account_id = person.get_primary_account()
            if not account_id:
                return "No account"
            # fi

            account.clear()
            account.find(account_id)
            return account.get_account_name()
        except (Errors.NotFoundError, Errors.TooManyRowsError):
            pass
        # yrt
    # od

    return "No uname found"
# end fetch_primary_uname



def main():
    db_fs = database.connect(user = "ureg2000", service = "FSPROD.uio.no",
                             DB_driver = cereconf.DB_DRIVER_ORACLE)
    fs = FS(db_fs)
    db_cerebrum = Factory.get("Database")()
    person = Factory.get("Person")(db_cerebrum)
    account = Factory.get("Account")(db_cerebrum)
    constants = Factory.get("Constants")(db_cerebrum)
    
    evukode = sys.argv[1]
    tidskode = sys.argv[2]
    for row in fs.evu.list_kurs_deltakere(evukode, tidskode):
        uname = fetch_primary_uname(row, person, account, constants)
        
        print "%06d %05d %-20s%-30s --> %-10s" % (row['fodselsdato'],
                                                  row['personnr'],
                                                  row['etternavn'],
                                                  row['fornavn'],
                                                  uname)
    # od
# end main





if __name__ == '__main__':
    main()
# fi

