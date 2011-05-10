# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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
Site specific auth.py for UiO

"""

import cereconf
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd import auth
from Cerebrum.modules.bofhd.errors import PermissionDenied
from Cerebrum.modules import Email


class BofhdAuth(auth.BofhdAuth):
    """Defines methods that are used by bofhd to determine wheter
    an operator is allowed to perform a given action.

    This class only contains special cases for UiA.
    """
    # allow account owner to set disclosure traits
    def can_set_person_disclosure_trait(self, operator, person=None, query_run_any=False):
        if query_run_any:
            return True
        # superuser can set traits
        if self.is_superuser(operator):
            return True
        # person can set own traits
        account = Factory.get('Account')(self._db)
        account.find(operator)
        if person.entity_id == account.owner_id:
            return True        
        return False
