# -*- coding: iso-8859-1 -*-
# Copyright 2009, 2010 University of Oslo, Norway
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

import time

from Cerebrum.modules.no import access_FS

class HINEStudieInfo(access_FS.StudieInfo):
    pass


##     # In time, we'll probably just be retrieving OUs with defined
##     # stedkode_konv, but for now, use the super-class variant that
##     # grabs all OUs
##     def list_ou(self, institusjonsnr=0): # GetAlleOUer
##         """Hent data om stedskoder registrert i FS"""
##         qry = """
##         SELECT DISTINCT
##           institusjonsnr, faknr, instituttnr, gruppenr, stedakronym,
##           stednavn_bokmal, faknr_org_under, instituttnr_org_under,
##           gruppenr_org_under, adrlin1, adrlin2, postnr, adrlin3,
##           stedkortnavn, telefonnr, faxnr, adrlin1_besok, emailadresse,
##           adrlin2_besok, postnr_besok, url, bibsysbeststedkode,
##           stedkode_konv
##         FROM fs.sted
##         WHERE institusjonsnr=%s AND
##           stedkode_konv IS NOT NULL
##         """ % self.institusjonsnr
##         return self.db.query(qry)


class FS(access_FS.FS):

    def __init__(self, db=None, user=None, database=None):
        super(FS, self).__init__(db=db, user=user, database=database)

        t = time.localtime()[0:3]
        self.year = t[0]
        self.mndnr = t[1]
        self.dday = t[2]
        
        # Override with HiNE-spesific classes
        self.info = HINEStudieInfo(self.db)
