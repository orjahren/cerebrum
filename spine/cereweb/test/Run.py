#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

# $Id: Run.py 3981 2004-11-02 09:42:37Z runefro $

import unittest

modules = [
    'AccountDAOTest',
    'ConstantsDAOTest',
    'DiskDAOTest',
    'EntityDAOTest',
    'GroupDAOTest',
    'HistoryDAOTest',
    'HostDAOTest',
    'PersonDAOTest',
    'AuthTest',
    'SearchTest',
    'OuDAOTest',
]

# When this module is executed from the command-line, run all its tests
if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromNames(modules)
    unittest.TextTestRunner(verbosity=1).run(suite)
