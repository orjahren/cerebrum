#!/usr/bin/python

# Lag oversikt over brukere med angitte spread(s) bygget i l�pet av
# siste d�gn.

import sys
import getopt
import time
import pickle
import os

import cerebrum_path
from Cerebrum.Utils import Factory
from Cerebrum import Entity
from Cerebrum import OU
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum import Account
from Cerebrum import Constants

def usage(exitcode=0):
    print """Usage: report_new_users.py [-s spread1 | -f fnrfile]"""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 's:f:', ['help'])
    except getopt.GetoptError:
        usage(1)

    db = Factory.get("Database")()
    const = Factory.get("Constants")(db)

    for opt, val in opts:
        if opt == '--help':
            usage()
        elif opt == '-s':
            dump_new_users(db, const, spread=val)
        elif opt == '-f':
            dump_new_users(db, const, fnr_file=val)

def dump_new_users(db, const, spread=None, fnr_file=None, start_date=None):
    entity = Entity.Entity(db)
    if start_date is None:
        start_date = yesterday(db)
    if spread is not None:
        scode = int(getattr(const, spread))
        rows = entity.list_all_with_spread(scode)
    elif fnr_file is not None:
        account = Account.Account(db)
        person = Person.Person(db)
        rows = []
        f = open(fnr_file)
        for fnr in f.readlines():
            fnr = fnr.rstrip()
            person.clear()
            try:
                person.find_by_external_id(const.externalid_fodselsnr, fnr)
            except Errors.NotFoundError:
                print "no users for %s" % fnr
                continue
            for r in account.list_accounts_by_owner_id(person.entity_id):
                rows.append({'entity_id': r['account_id']})
        
    for r in rows:
        try:
            account = _get_account(db, r['entity_id'])
        except Errors.NotFoundError:
            # Feil entity_type?  B�r ikke kunne skje, da hver enkelt
            # spread er begrenset til en enkelt entity_type.
            continue
        atypes = account.get_account_types()
        if account.create_date < start_date:
            # Hopp over accounts som er eldre enn angitt start-dato.
            continue

        # Finn en (tilfeldig) av stedkodene brukeren har
        # tilknytning til.
        try:
            sko = _get_ou(db, atypes[0].ou_id)
            stedkode = "%02d%02d%02d" % (sko.fakultet, sko.institutt,
                                         sko.avdeling)
        except:
            stedkode = ''

        # Finn brukerens nyeste passord, i klartekst.
        pwd_rows = [row for row in
                    db.get_log_events(0, (const.account_password,))
                    if row.dest_entity == account.entity_id]
        try:
            pwd = pickle.loads(pwd_rows[-1].change_params)['password']
        except:
            pwd = ''

        # Finn personen som eier brukeren, og dermed dennes for- og
        # etternavn.
        person = _get_person(db, account.owner_id)

        # Finn en (tilfeldig) affiliation, og tilsvarende -status,
        # for brukeren.
        aff = affstatus = ''
        try:
            aff = Constants._PersonAffiliationCode(int(atypes[0].affiliation))
            for x in person.get_affiliations():
                if x.affiliation == aff and x.ou_id == atypes[0].ou_id:
                    affstatus = Constants._PersonAffStatusCode(
                        int(aff), int(x.status))
                    break
        except:
            pass

        # Finn brukerens eiers for- og etternavn (fra FS)
        fname = lname = ''
        try:
            fname = person.get_name(const.system_fs,
                                    const.name_first)
            lname = person.get_name(const.system_fs,
                                    const.name_last)
        except:
            pass
        sys.stdout.write("%(brukernavn)s:%(pwd)s:%(sko)s:%(fname)s:%(lname)s:%(aff)s:%(affstatus)s\n" %
                 {'brukernavn': account.account_name,
                  'pwd': pwd,
                  'sko': stedkode,
                  'fname': fname,
                  'lname': lname,
                  'aff': aff,
                  'affstatus': affstatus
                  })


def _get_ou(db, e_id):
    ou = Factory.get("OU")(db)
    ou.find(e_id)
    return ou

def _get_person(db, e_id):
    person = Person.Person(db)
    person.find(e_id)
    return person

def _get_account(db, e_id):
    account = Account.Account(db)
    account.find(e_id)
    return account

def yesterday(db):
    now = time.time()
    return db.DateFromTicks(now - 60*60*24)


if __name__ == '__main__':
    main()
