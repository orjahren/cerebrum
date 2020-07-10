#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
OrgLDIF module for generating a sysadm ldif.

TODOs
-----
Unified sysadm lookup/business logic
    System account listings should be defined elsewhere (e.g. a
    Cerebrum.modules.no.uio.account.sysadm.SystemAccountPolicy or a
    Cerebrum.modules.no.uio.account.AccountPolicy)

Non-arbitrary account priority
    We should fix the account priority lookups to avoid 'fallback' to a less
    prioritized account when adding filters (expire_date, spreads).

    The whole account priority bit should probably be separated from
    account_type.

Missing mandatory attrs
    Missing eduPersonPrimaryOrgUnitDN, eduPersonOrgUnitDN.  Not sure how to
    handle:

    1. Dummy OU and set OrgUnit to that?
    2. Refer to OUs at cn=organization,dc=uio,dc=no?  We'd need to somehow
       build the ou-mapping (ou2DN) like OrgLDIF, but without outputting any
       OUs.
    3. These attrs are semi-mandatory, and low availability in higher edu -
       should we just ignore them?
"""
from __future__ import print_function, unicode_literals

import logging

from Cerebrum.Utils import Factory, make_timer
from Cerebrum.modules.Email import EmailTarget
from Cerebrum.modules.no.OrgLDIF import norEduLDIFMixin


logger = logging.getLogger(__name__)


def _get_sysadm_accounts(db):
    """
    Fetch sysadm accounts.

    :param db:
        Cerebrum.database object/db connection
    """
    co = Factory.get('Constants')(db)
    ac = Factory.get('Account')(db)

    # find all tagged sysadm accounts
    trait = co.trait_sysadm_account
    sysadm_filter = set(t['entity_id'] for t in ac.list_traits(code=trait))
    logger.debug('found %d entities with trait=%s',
                 len(sysadm_filter), co.trait_sysadm_account)

    # filter acocunt list by personal accounts with name *-drift
    sysadm_accounts = {
        r['account_id']: r
        for r in ac.search(name='*-drift',
                           owner_type=co.entity_person)
        if r['account_id'] in sysadm_filter
    }
    logger.debug('found %d sysadm (*-drift) accounts', len(sysadm_accounts))

    # identify highest prioritized account/person
    # NOTE: We *really* need to figure out how to use account priority
    #       correctly.  This will pick the highest prioritized *non-expired*
    #       account - which means that the primary account value *will* change
    #       without any user interaction.
    primary_account = {}
    primary_sysadm = {}
    for row in ac.list_accounts_by_type(filter_expired=True,
                                        primary_only=False):
        person_id = row['person_id']
        priority = row['priority']

        # cache primary account (for email)
        if (person_id not in primary_account or
                priority < primary_account[person_id]['priority']):
            primary_account[person_id] = dict(row)

        if row['account_id'] not in sysadm_accounts:
            # non-sysadm account
            continue

        # cache primary sysadm account
        if (person_id not in primary_sysadm or
                priority < primary_sysadm[person_id]['priority']):
            primary_sysadm[person_id] = dict(row)

    logger.info('found %d persons with sysadm accounts', len(primary_sysadm))

    for person_id in primary_sysadm:
        account_id = primary_sysadm[person_id]['account_id']
        account = sysadm_accounts[account_id]

        yield {
            # required by OrgLDIF.list_persons()
            'account_id': account_id,
            'account_name': account['name'],
            'person_id': account['owner_id'],
            'ou_id': primary_sysadm[person_id]['ou_id'],

            # required by SystemAdminOrgLdif.list_persons()
            'primary_account_id': primary_account[person_id]['account_id'],
        }


class SysAdmOrgLdif(norEduLDIFMixin):
    """
    Mixin for exporting system administrator accounts (*-drift).

    This OrgLdif mixin changes primary accounts/filtering to only include
    persons with a sysadm account.
    """

    def list_persons(self):
        """
        List persons decides on which accounts to include.

        We override it with one that returns sysadm users.
        """
        self._account_to_primary = pri = {}
        for account in _get_sysadm_accounts(self.db):
            pri[account['account_id']] = account.pop('primary_account_id')
            yield account

    def init_account_mail(self, use_mail_module):
        if use_mail_module:
            timer = make_timer(logger,
                               "Fetching primary account e-mail addresses...")
            # cache all <uname>@uio.no email addresses
            targets = EmailTarget(self.db).list_email_target_addresses
            mail = {}
            for row in targets(target_type=self.const.email_target_account,
                               domain='uio.no', uname_local=True):
                # Can only return username@uio.no so no need for any checks
                mail[int(row['target_entity_id'])] = "@".join(
                    (row['local_part'], row['domain']))

            # Pick an appropriate email address for each account
            self.account_mail = {}
            for account_id, pri_id in self._account_to_primary.items():
                if pri_id in mail:
                    self.account_mail[account_id] = mail[pri_id]
                else:
                    logger.warning('No email address for account_id=%d, '
                                   'primary_account_id=%d', account_id, pri_id)
            logger.info('found e-mail address for %d accounts',
                        len(self.account_mail))

            timer("...primary account e-mail addresses done.")
        else:
            self.account_mail = None

    @property
    def person_authn_levels(self):
        """Enforces authn level 3 for all users."""
        if not hasattr(self, '_person_authn_levels'):
            d = self._person_authn_levels = {}
            for person_id in self.persons:
                d[person_id] = [('all', '3')]
        return self._person_authn_levels
