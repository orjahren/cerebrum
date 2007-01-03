# -*- coding: iso-8859-1 -*-

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
#

import unittest
from TestBase import *

class AuthTest(SpineObjectTest):
    """A simple test to verify that we can find out what operations
    we have authority to perform."""

    def createObject(self):
        self.tr = self.session.new_transaction()

    def deleteObject(self):
        try:
            self.tr.rollback()
        except:
            pass

    def testAuthOperationSearcher(self):
        searcher = self.tr.get_auth_operation_searcher()
        sr = searcher.search()

    def testJoin(self):
        aos = self.tr.get_auth_operation_searcher()
        aocs = self.tr.get_auth_operation_code_searcher()
        aos.add_join('op', aocs, '')
        return aos.search()

class AuthOperationSetTest(AuthTest):
    def createObject(self):
        super(AuthOperationSetTest, self).createObject()
        try:
            self.op_code_1 = self.tr.get_auth_operation_code_searcher().search()[0]
            self.op_code_2 = self.tr.get_auth_operation_code_searcher().search()[1]
            self.op_code_3 = self.tr.get_auth_operation_code_searcher().search()[2]
        except IndexError, e:
            self.fail('No AuthOpCodes in the database.')
        self.ops = self.tr.get_commands().create_auth_operation_set('test','test')
    
    def testCreate(self):
        assert self.ops.get_id() != 0

    def testGetOperations(self):
        assert len(self.ops.get_operations()) == 0

    def testAddOperations(self):
        assert len(self.ops.get_operations()) == 0
        self.ops.add_operation(self.op_code_1)
        assert len(self.ops.get_operations()) == 1
        self.ops.add_operation(self.op_code_2)
        assert len(self.ops.get_operations()) == 2
        self.ops.add_operation(self.op_code_3)
        assert len(self.ops.get_operations()) == 3

    def testRemoveOperations(self):
        self.ops.add_operation(self.op_code_1)
        self.ops.add_operation(self.op_code_2)
        self.ops.add_operation(self.op_code_3)
        assert len(self.ops.get_operations()) == 3
        self.ops.remove_operation(self.op_code_3)
        assert len(self.ops.get_operations()) == 2
        self.ops.remove_operation(self.op_code_2)
        assert len(self.ops.get_operations()) == 1
        self.ops.remove_operation(self.op_code_1)
        assert len(self.ops.get_operations()) == 0

if __name__ == '__main__':
    unittest.main()
