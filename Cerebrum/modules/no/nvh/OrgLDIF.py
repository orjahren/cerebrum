#!/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright 2012 University of Oslo, Norway
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

from Cerebrum.modules.no.OrgLDIF import *

class NVHOrgLDIFMixin(OrgLDIF):
    def test_omit_ou(self):
        # Not using Stedkode, so all OUs are available (there is no need to
        # look for special spreads).
        return False

    # Fetch mail addresses from entity_contact_info of accounts, not persons.
    person_contact_mail = False
