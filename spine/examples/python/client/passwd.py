#!/usr/bin/env python

# Copyright 2004, 2005 University of Oslo, Norway
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
import SpineClient

ior_file = '/tmp/spine.ior'
tmp_dir = os.path.expanduser('~/tmp')
spine = SpineClient.SpineClient(ior_file, idl_path=tmp_dir).connect()

print 'Old password: ',
passwd = sys.stdin.readline().strip()
session = spine.login(os.getlogin(), passwd)
print 'New password: ',
passwd = sys.stdin.readline().strip()
print 'Repeat new password: ',
passwd2 = sys.stdin.readline().strip()

if passwd2 == passwd:
    tr = session.new_transaction()
    tr.get_commands().get_user_by_name(os.getlogin()).set_password(passwd)
