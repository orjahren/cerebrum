# -*- coding: iso-8859-1 -*-
# Copyright 2002, 2003 University of Oslo, Norway
#

"""The PasswordHistory module is used to keep track of previous
passwords for an Entity.  This allows one to prevent Entities from
setting their password to an old password.
"""

import cereconf
import md5
import base64
from Cerebrum.DatabaseAccessor import DatabaseAccessor

class PasswordHistory(DatabaseAccessor):
    """PasswordHistory does not enfoce that Entity is an Account as
    other things also may have passwords"""

    def encode_for_history(self, account, password):
        m = md5.md5("%s%s" % (account.account_name, password))
        return base64.encodestring(m.digest())[:22]

    def add_history(self, account, password, _csum=None):
        """Add an entry to the password history."""
        if _csum is not None:
            csum = _csum
        else:
            csum = encode_for_history(account, password)
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=password_history]
          (entity_id, md5base64) VALUES (:e_id, :md5)""",
                     {'e_id': account.entity_id, 'md5': csum})

    def del_history(self, entity_id):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=password_history]
        WHERE entity_id=:e_id""", {'e_id': entity_id})

    def get_history(self, entity_id):
        return self.query("""
        SELECT md5base64, set_at
        FROM [:table schema=cerebrum name=password_history] WHERE entity_id=:e_id""",
                          {'e_id': entity_id})   

