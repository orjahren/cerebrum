#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004-2006 University of Oslo, Norway
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

import os
import sys
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Constants
from sets import Set
from Cerebrum.Errors import NotFoundError
from Cerebrum.spine.SpineLib import Builder
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode

# Needed to make Builder.get_builder_classes() return
# all needed classes for this spine instance.
from Cerebrum.spine.SpineModel import *

from sets import Set

autodesc = 'Managed by UpdateSpineConstants'

def update_spine_auth_codes():
    existing = Set(get_existing())
    db = Factory.get('Database')(user=db_user)
    _ = Constants.Constants(db) # Ugly hack.  See makedb.py

    # Get the methods from spine
    auth_op_codes = Set()
    for cls in Builder.get_builder_classes():
        for method in Builder.get_builder_methods(cls):
            name, data_type, write, args, exceptions = Builder.get_method_signature(method)
            code = "%s.%s" % (cls.__name__, name)
            assert len(code) <= 64, code
            auth_op_codes.add(code)

    new = auth_op_codes - existing
    orphans = existing - auth_op_codes

    # Create the op codes that doesn't already exist.
    for code_str in new:
        code_obj = _AuthRoleOpCode(code_str, autodesc)
        code_obj.insert()
    # Delete the op codes that no longer exist.
    for code_str in orphans:
        code_obj = _AuthRoleOpCode(code_str)
        code_obj.delete()
    db.commit()

def get_existing():
    db = Factory.get('Database')(user=db_user)
    result = db.query("select * from [:table schema=cerebrum name=auth_op_code] where description = :te", {'te': autodesc})
    return [x[1] for x in result]

if __name__ == '__main__':
    db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['table_owner']
    if db_user is None:
        db_user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA['user']
        if db_user is not None:
            print "'table_owner' not set in CEREBRUM_DATABASE_CONNECT_DATA."
            print "Will use regular 'user' (%s) instead." % db_user

    if db_user:
        update_spine_auth_codes()
    else:
        print "System not configured properly.  I didn't do anything."
