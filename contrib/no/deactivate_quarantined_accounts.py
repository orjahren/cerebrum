#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011, 2012, 2014 University of Oslo, Norway
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

"""Deactivate accounts with a given quarantine.

The criterias for deactivating accounts:

- The account must have an ACTIVE quarantine of the given type.

- The quarantine must have had a `start_date` from before the given number of
  days.

- If the account belongs to a person, it can not have any person affiliation.
  The script could be specified to ignore certain affiliations from this
  criteria.

- The account can't already be deleted.

Note that this script depends by default on `Account.deactivate()` for removal
of spreads, home directory etc. depending on what the institution needs. The
`deactivate` method must be implemented in the institution specific account
mixin - normally `Cerebrum/modules/no/$INST/Account.py` - before this script
would work.

The script also supports *deleting* (nuking) accounts instead of just
deactivating them. You should be absolutely sure before you run it with nuking,
as this deletes *all* the details around the user accounts, even its change log.

Note: If a quarantine has been temporarily disabled, it would not be found by
this script. This would make it possible to let accounts live for a prolonged
period. This is a problem which should be solved in other ways, and not by this
script.

"""

import sys
import getopt
import re

import time
import mx.DateTime as dt

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import BofhdRequests

logger = Factory.get_logger("cronjob")
database = Factory.get("Database")()
database.cl_init(change_program="deactivate-qua")
constants = Factory.get("Constants")(database)
# we could probably generalise and use entity here, but for now we
# need only look at accounts
account = Factory.get("Account")(database)
person = Factory.get("Person")(database)
today = dt.today()

account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
operator_id = account.entity_id
account.clear()

def fetch_all_relevant_accounts(qua_type, since, ignore_affs,
                                system_accounts):
    """Fetch all accounts that matches the criterias for deactivation.

    :param QuarantineCode qua_type:
        The quarantine that the accounts must have to be targeted.

    :param int since:
        The number of days a quarantine must have been active for the account to
        be targeted.

    :type ignore_affs: set, list or tuple
    :param ignore_affs:
        A given list of `PersonAffiliationCode`. If given, we will ignore them,
        and process the persons' accounts as if they didn't have an affiliation,
        and could therefore be targeted for deactivation.

    :param bool system_accounts:
        If True, accounts owned by groups are also included in the resulting
        target list.

    :rtype: set
    :returns: The `entity_id` for all the accounts that match the criterias.

    """
    max_date = dt.now() - since
    logger.debug("Search quarantines older than %s days, i.e. before %s", since,
                 max_date.strftime('%Y-%m-%d'))
    targets = set(row['entity_id'] for row in
                      account.list_entity_quarantines(
                            entity_types=constants.entity_account,
                            quarantine_types=qua_type, only_active=True)
                      if row['start_date'] <= max_date)
    logger.debug("Found %d quarantine targets", len(targets))
    if len(targets) == 0:
        return targets

    # Ignore those with person affiliations:
    persons = set(r['person_id'] for r in
                  person.list_affiliations(include_deleted=False)
                  if r['affiliation'] not in ignore_affs)
    logger.debug2("Found %d persons with affiliations", len(persons))
    accounts_to_ignore = set(r['account_id'] for r in
                             account.search(owner_type=constants.entity_person)
                             if r['owner_id'] in persons)
    targets.difference_update(accounts_to_ignore)
    logger.debug2("Removed targets with person-affs (%d). Result: %d",
                  len(accounts_to_ignore), len(targets))

    # Ignore accounts owned by groups:
    if not system_accounts:
        targets.difference_update(r['account_id'] for r in
                                  account.search(
                                      owner_type=constants.entity_group))
        logger.debug2("Removed system accounts. Result: %d", len(targets))
    return targets

def process_account(account, delete=False, bofhdreq=False):
    """Deactivate the given account.

    :param Cerebrum.Account: The account that should get deactivated.

    :param bool delete:
        If True, the account will be totally deleted instead of just
        deactivated.

    :param bool bofhdreq:
        If True, the account will be given to BofhdRequest for further
        processing. It will then not be deactivated by this script.

    :rtype: bool
    :returns: If the account really got deactivated/deleted.

    """
    if account.is_deleted():
        logger.debug2("Account %s already deleted", account.account_name)
        return False
    logger.info('Deactivating account: %s (%s)', account.account_name,
                account.entity_id)
    if delete:
        logger.info("Terminating account: %s", account.account_name)
        account.terminate()
    elif bofhdreq:
        logger.debug("Send to BofhdRequest: %s", account.account_name)
        br = BofhdRequests(database, constants)
        try:
            reqid = br.add_request(operator_id, when=br.now,
                                   op_code=constants.bofh_delete_user,
                                   entity_id=account.entity_id,
                                   destination_id=None)
            logger.debug("BofhdRequest-Id: %s", reqid)
        except Errors.CerebrumError, e:
            # A CerebrumError is thrown if there exists some move_user for the
            # same user...
            logger.warn("Couldn't delete %s: %s", account.account_name, e)
            return False
    else:
        account.deactivate()
    return True

def usage(exitcode=0):
    print """Usage: deactivate_quarantined_accounts.py -q quarantine_type -s #days [-d]

Deactivate all accounts where given quarantine has been set for at least #days.

Accounts will NOT be deactivated by default if their persons are registered with
affiliations, or if the account is a system account, i.e. owned by a group and
not a person.

%s

    -q, --quarantines QUAR  Quarantine types, to find out the exact names run
                            the following command: "jbofh> quarantine list". If
                            muliple values are to be provided those should be
                            comma separated with no spaces in between. If not
                            provided it defaults to the "generell" quarantine.

    -s, --since DAYS        Number of days since quarantine started. Default: 30

    -l, --limit LIMIT       Limit the number of deactivations by the script.
                            This is to prevent too much changes in the system,
                            as archiving could take time. Defaults to no limit.

        --bofhdrequest      If specified, instead of deactivating the account
                            directly, it is handed over to BofhdRequest for
                            further processing. This is needed e.g. when we need
                            to archive the home directory before the account
                            gets deactivated.

    -a, --affiliations AFFS List of person affiliation types that will be
                            ignored, and handled as if the person did not have
                            an affiliation. Affiliations specified here will
                            make the person's accounts getting deactivated.
                            Manual affiliation are typically added here. Could
                            be comma separated.

                            Note: Affiliation status types are not supported.

        --include-system-accounts If set, system accounts with the quarantine
                            will also de deactivated.

    -d, --dryrun            Do not commit changes to the database

        --terminate         *Delete* the account instead of just deactivating
                            it. Warning: This deletes *everything* about the
                            accounts with active quarantines, even their logs.
                            This can not be undone, so use with care!

    -h, --help              show this and quit.
    """ % __doc__
    sys.exit(exitcode)

def main():
    options, junk = getopt.getopt(sys.argv[1:],
                                  "q:s:dhl:a:",
                                  ("quarantines=",
                                   "dryrun",
                                   "affiliations=",
                                   "help",
                                   "limit=",
                                   "bofhdrequest",
                                   "include-system-accounts",
                                   "terminate",
                                   "since=",))
    dryrun = False
    limit = None
    # default quarantine type
    quarantines = [int(constants.quarantine_generell)]
    # number of days since the quarantines have started
    since = 30
    delete = bofhdreq = False
    system_accounts = False
    affiliations = set()

    for option, value in options:
        if option in ("-q", "--quarantines"):
            quarantines = []
            target = re.sub("\,$", "", value)
            for i in target.split(","):
                quarantines.append(int(constants.Quarantine(i)))
        elif option in ("-d", "--dryrun"):
            dryrun = True
        elif option in ("-s", "--since"):
            since = int(value)
        elif option in ("-l", "--limit"):
            limit = int(value)
        elif option in ("--bofhdrequest",):
            logger.debug('Set to use BofhdRequest for deactivation')
            bofhdreq = True
        elif option in ("--include-system-accounts",):
            system_accounts = True
        elif option in ("--terminate",):
            logger.debug('Set to delete accounts and not just deactivating!')
            delete = True
        elif option in ('-a', '--affiliations'):
            for af in value.split(','):
                aff = constants.PersonAffiliation(af)
                try:
                    int(aff)
                except Errors.NotFoundError:
                    print "Unknown affiliation: %s" % af
                    sys.exit(2)
                affiliations.add(aff)
        elif option in ("-h", "--help"):
            usage()
        else:
            print "Unknown argument: %s" % option
            usage(1)

    logger.info("Start deactivation, quar=%s, since=%s, terminate=%s, "
                "bofhdreq=%s, limit=%s",
                [str(co.human2constant(q)) for q in quarantines], since,
                delete, bofhdreq, limit)
    logger.debug("Ignoring those with person-affilations: %s",
                 ', '.join(str(a) for a in affiliations))
    logger.info("Fetching relevant accounts")
    rel_accounts = fetch_all_relevant_accounts(quarantines, since,
                                               ignore_affs=affiliations,
                                               system_accounts=system_accounts)
    logger.info("Got %s accounts to process", len(rel_accounts))

    i = 0
    for a in rel_accounts:
        if limit and i >= limit:
            logger.debug("Limit of deactivations reached (%d), stopping", limit)
            break
        account.clear()
        try:
            account.find(int(a))
        except Errors.NotFoundError:
            logger.warn("Could not find account_id %s, skipping", a)
            continue
        try:
            if process_account(account, delete=delete, bofhdreq=bofhdreq):
                i += 1
        except Exception:
            logger.exception("Failed deactivating account: %s (%s)" %
                             (account.account_name, account.entity_id))

    if dryrun:
        database.rollback()
        logger.info("rolled back all changes")
    else:
        database.commit()
        logger.info("changes commited")
    logger.info("Done deactivate_quarantined_accounts")

if __name__ == '__main__':
    main()
