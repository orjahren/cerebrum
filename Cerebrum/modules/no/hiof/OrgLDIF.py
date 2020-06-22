# -*- coding: utf-8 -*-
#
# Copyright 2007-2020 University of Oslo, Norway
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
from __future__ import unicode_literals

import logging
import os
import pickle

from Cerebrum.modules.OrgLDIF import OrgLDIF
from Cerebrum.modules.LDIFutils import ldapconf
from Cerebrum.Utils import make_timer

logger = logging.getLogger(__name__)


# TODO: HiofLdifMixin

class hiofLDIFMixin(OrgLDIF):  # noqa: N801

    def init_person_addresses(self):
        # No snail mail addresses for persons.
        self.addr_info = {}

    def init_person_groups(self):
        """Populate dicts with a person's group information."""
        timer = make_timer(logger, 'Processing person groups...')
        self.person2group = pickle.load(file(
            os.path.join(ldapconf(None, 'dump_dir'), "personid2group.pickle")))
        timer("...person groups done.")

    def init_person_dump(self, use_mail_module):
        """Supplement the list of things to run before printing the
        list of people."""
        super(hiofLDIFMixin, self).init_person_dump(use_mail_module)
        self.init_person_groups()

    def make_person_entry(self, row, person_id):
        """ Extend person entry. """
        dn, entry, alias_info = super(hiofLDIFMixin,
                                      self).make_person_entry(row, person_id)
        if not dn:
            return dn, entry, alias_info

        # Add group memberships
        if person_id in self.person2group:
            entry['hiofMemberOf'] = self.person2group[person_id]
            entry['objectClass'].extend(('hiofMembership', ))

        return dn, entry, alias_info
