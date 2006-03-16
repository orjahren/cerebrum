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

"""DiskQuotas as specified in uiocerebrum/doc/spec/disk_kvoter.rst"""

from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.modules.CLConstants import _ChangeTypeCode
from Cerebrum import Account
from Cerebrum import Constants

class NotSet(object): pass

class DiskQuotaConstants(Constants.Constants):
    disk_quota_set = _ChangeTypeCode(
        'disk_quota', 'set', 'set disk quota for %(subject)s',
        ('quota=%(int:quota)s',
         'override_quota=%(int:override_quota)s',
         'override_exp=%(string:override_expiration)s',
         'reason=%(string:description)s'))
    disk_quota_clear = _ChangeTypeCode(
        'disk_quota', 'clear', 'clear disk quota for %(subject)s')

class DiskQuota(DatabaseAccessor):
    """Methods for maintaining disk-quotas for accounts.  Typical
    usage would be something like:
    dq = DiskQuota(db)
    # Set initial quota (or update)
    dq.set_quota(account_home.homedir_id, quota=50)
    # Set override for quota
    dq.set_quota(account_home.homedir_id, override_quota=90,
                 override_expiration=mx.DateTime.now(),
                 description='nice guy')
    # Remove override
    dq.clear_override(account_home.homedir_id)
    """

    def __init__(self, database):
        super(DiskQuota, self).__init__(database)
        self.co = Factory.get('Constants')(database)

    def _get_account_id(self, homedir_id):
        ah = Account.Account(self._db)
        row = ah.get_homedir(homedir_id)
        return row['account_id']

    def set_quota(self, homedir_id, quota=NotSet(), override_quota=NotSet(),
                  override_expiration=NotSet(), description=NotSet()):
        """Insert or update disk_quota for homedir_id.  Will only
        affect the columns used as keyword arguments"""
        new_values = { 'homedir_id': int(homedir_id),
                       'quota': quota,
                       'override_quota': override_quota,
                       'override_expiration': override_expiration,
                       'description': description }
        old_values = {}
        try:
            old_values = self.get_quota(homedir_id=homedir_id)
            is_new = False
        except Errors.NotFoundError:
            is_new = True
        for col in new_values.keys():
            if isinstance(new_values[col], NotSet):
                if is_new:
                    new_values[col] = None
                else:
                    del new_values[col]
        if is_new:
            self.execute("""
                INSERT INTO [:table schema=cerebrum name=disk_quota]
                (%s) VALUES (%s)
                """ % (", ".join(new_values.keys()),
                       ", ".join([":%s" % col for col in new_values.keys()])),
                         new_values)
        else:
            for col in new_values.keys():
                if new_values[col] == old_values[col]:
                    del new_values[col]
            if not new_values:
                return
            # homedir_id never changes, so it was removed by the above
            # code, but it is needed in the SQL bind dict.
            new_values['homedir_id'] = int(homedir_id)
            self.execute("""
                UPDATE [:table schema=cerebrum name=disk_quota]
                SET %s
                WHERE homedir_id=:homedir_id
                """ % (", ".join(["%s=:%s" % (col, col)
                                  for col in new_values.keys()])),
                         new_values)
        # We reformat the date into something simpler before pickling.
        # This requires the input date argument to be somewhat
        # DateTime compatible, i.e., support strftime().  The call to
        # Database.execute() will actually convert the date object in
        # new_values to something unusable, but luckily it's still
        # available in the local variable.
        if not isinstance(override_expiration, NotSet):
            new_values['override_expiration'] = override_expiration.\
                                                strftime('%Y-%m-%d')
        self._db.log_change(self._get_account_id(homedir_id),
                            self.co.disk_quota_set, None,
                            change_params=new_values)

    def clear_override(self, homedir_id):
        """Convenience method for clearing override settings"""
        self.set_quota(homedir_id, override_quota=None,
                       override_expiration=None, description=None)

    def clear(self, homedir_id):
        """Remove the disk_quota entry from the table"""
        self.execute("""
        DELETE FROM  [:table schema=cerebrum name=disk_quota]
        WHERE homedir_id=:homedir_id""", {'homedir_id': homedir_id})
        self._db.log_change(self._get_account_id(homedir_id),
                            self.co.disk_quota_clear, None,
                            change_params={'homedir_id': homedir_id})

    def get_quota(self, homedir_id):
        """Return quota information for a given homedir"""
        return self.query_1("""
        SELECT homedir_id, quota, override_quota, override_expiration,
               description
        FROM [:table schema=cerebrum name=disk_quota]
        WHERE homedir_id=:homedir_id""", {'homedir_id': homedir_id})

    def list_quotas(self, spread=None):
        """List quota and homedir information for all users that has
        quota"""
        where = ""
        if spread:
            where = " AND ah.spread=:spread"
            spread = int(spread)
        return self.query("""
        SELECT dq.homedir_id, ah.account_id, hi.home, en.entity_name, di.path,
               dq.quota, dq.override_quota, dq.override_expiration, ah.spread
        FROM [:table schema=cerebrum name=disk_quota] dq,
             [:table schema=cerebrum name=homedir] hi,
             [:table schema=cerebrum name=disk_info] di,
             [:table schema=cerebrum name=account_home] ah,
             [:table schema=cerebrum name=account_info] ai,
             [:table schema=cerebrum name=entity_name] en
        WHERE dq.homedir_id=hi.homedir_id AND
              hi.disk_id=di.disk_id AND
              hi.homedir_id=ah.homedir_id AND
              ah.account_id=en.entity_id AND
              ai.account_id=en.entity_id AND
              en.value_domain=:value_domain AND
              (ai.expire_date IS NULL OR
               ai.expire_date > [:now]) %s""" % where, {
            'value_domain': int(self.co.account_namespace),
            'spread': spread})
    
# arch-tag: 4b6c5df8-8100-4fd3-b679-bc8224f5b0df
