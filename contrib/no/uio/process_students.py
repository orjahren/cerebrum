#!/usr/bin/env python2.2
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

import getopt
import sys
import os
import pickle
import traceback
from time import localtime, strftime, time

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd import errors
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.modules.templates.letters import TemplateHandler

db = Factory.get('Database')()
db.cl_init(change_program='process_students')
const = Factory.get('Constants')(db)
all_passwords = {}
derived_person_affiliations = {}
has_quota = {}
processed_students = {}
keep_account_home = {}
paid_paper_money = {}
account_id2fnr = {}

debug = 0
max_errors = 50          # Max number of errors to accept in person-callback

def bootstrap():
    global default_creator_id, default_expire_date, default_shell
    for t in ('PRINT_PRINTER', 'PRINT_BARCODE', 'AUTOADMIN_LOG_DIR',
              'TEMPLATE_DIR', 'PRINT_LATEX_CMD', 'PRINT_DVIPS_CMD',
              'PRINT_LPR_CMD'):
        if not getattr(cereconf, t):
            logger.warn("%s not set, check your cereconf file" % t)
    account = Factory.get('Account')(db)
    account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
    default_creator_id = account.entity_id
    default_expire_date = None
    default_shell = const.posix_shell_bash

def create_user(fnr, profile):
    # dryruning this method is unfortunately a bit tricky
    assert not dryrun
    logger.info2("CREATE")
    person = Factory.get('Person')(db)
    try:
        person.find_by_external_id(const.externalid_fodselsnr, fnr, const.system_fs)
    except Errors.NotFoundError:
        logger.warn("OUCH! person %s not found" % fnr)
        return None
    posix_user = PosixUser.PosixUser(db)
    full_name = person.get_name(const.system_cached, const.name_full)
    first_name, last_name = full_name.split(" ", 1)
    uname = posix_user.suggest_unames(const.account_namespace,
                                      first_name, last_name)[0]
    account = Factory.get('Account')(db)
    account.populate(uname,
                     const.entity_person,
                     person.entity_id,
                     None,
                     default_creator_id, default_expire_date)
    password = account.make_passwd(uname)
    account.set_password(password)
    tmp = account.write_db()
    # Temporary hack until all students should have imap spread
    account.add_spread(const.spread_uio_imap)
    logger.debug("new Account, write_db=%s" % tmp)
    all_passwords[int(account.entity_id)] = [password, profile.get_brev()]
    update_account(profile, fnr, [account.entity_id])
    return account.entity_id

def update_account(profile, fnr, account_ids, account_info={}):
    """Update the account by checking that group, disk and
    affiliations are correct.  For existing accounts, account_info
    should be filled with affiliation info """

    # dryruning this method is unfortunately a bit tricky
    assert not dryrun
    
    group = Factory.get('Group')(db)

    as_posix = False
    for spread in profile.get_spreads():  # TBD: Is this check sufficient?
        if str(spread).startswith('NIS'):
            as_posix = True
    if as_posix:
        user = PosixUser.PosixUser(db)
    else:
        user = Factory.get('Account')(db)
    person = Factory.get('Person')(db)

    for account_id in account_ids:
        logger.info2(" UPDATE:%s" % account_id)
        changes = []
        if as_posix:
            try:
                user.clear()
                user.find(account_id)
            except Errors.NotFoundError:
                uid = user.get_free_uid()
                gid = profile.get_dfg()
                shell = default_shell
                user.populate(uid, gid, None, shell, 
                              parent=account_id, expire_date=default_expire_date)
            old_gid = user.gid_id
            user.gid = profile.get_dfg()
            if user.gid_id != old_gid:
                changes.append("dfg %s->%s" % (user.gid_id, old_gid))
        else:
            user.clear()
            user.find(account_id)  # If it don't exist, it is a bug

        if user.expire_date:
            user.expire_date = default_expire_date

        # Set/change homedir
        user_spreads = [int(s) for s in profile.get_spreads()]
        for disk_spread in profile.get_disk_spreads():
            if not disk_spread in user_spreads:
                # The disk-spread in disk-defs was not one of the users spread
                continue 
            try:
                current_disk_id = user.get_home(disk_spread)['disk_id']
            except Errors.NotFoundError:
                current_disk_id = None
            if keep_account_home[fnr] and (move_users or current_disk_id is None):
                try:
                    new_disk = profile.get_disk(current_disk_id)
                except ValueError, msg:
                    raise
                if current_disk_id != new_disk:
                    profile.notify_used_disk(old=current_disk_id, new=new_disk)
                    changes.append("disk %s->%s" % (
                        autostud.disks.get(current_disk_id, ['None'])[0],
                        autostud.disks.get(new_disk, ['None'])[0]))
                    if current_disk_id is None:
                        logger.debug("Set home: %s" % new_disk)
                        user.set_home(disk_spread, disk_id = new_disk,
                                      status=const.home_status_not_created)
                    else:
                        br = BofhdRequests(db, const)
                        # TBD: Is it correct to set requestee_id=None?
                        try:
                            br.add_request(None, br.batch_time,
                                           const.bofh_move_user, account_id,
                                           new_disk, state_data=int(disk_spread))
                        except errors.CerebrumError, e:
                            # Conflicting request or similiar
                            logger.warn(e)

        tmp = user.write_db()
        logger.debug("write_db=%s" % tmp)

        # Populate groups
        already_member = {}
        for r in group.list_groups_with_entity(account_id):
            if r['operation'] == const.group_memberop_union:
                already_member[int(r['group_id'])] = True
        for g in profile.get_grupper():
            if not already_member.has_key(g):
                group.clear()
                group.find(g)
                group.add_member(account_id, const.entity_account,
                                 const.group_memberop_union)
                changes.append("g_add: %s" % group.group_name)
            else:
                del already_member[g]
        if remove_groupmembers:
            for g in already_member.keys():
                if autostud.pc.group_defs.get(g, {}).get('auto', None) == 'auto':
                    group.clear()
                    group.find(g)
                    group.remove_member(account_id, const.group_memberop_union)

        # Check quarantines
        if user.get_entity_quarantine(type=const.quarantine_autostud):
            changes.append("removed quarantine_autostud")
            user.delete_entity_quarantine(const.quarantine_autostud)

        # Populate affiliations
        # Speedup: Try to determine if object is changed without populating
        changed = False
        paffs = derived_person_affiliations.get(int(user.owner_id), [])
        for ou_id in profile.get_stedkoder():
            try:
                idx = paffs.index((const.system_fs_derived, ou_id, const.affiliation_student,
                                   const.affiliation_status_student_aktiv))
                del paffs[idx]
            except ValueError:
                changed = True
                pass
        if paffs:
            changed = True
        person.clear()
        person.find(user.owner_id)
        if changed:
            for ou_id in profile.get_stedkoder():
                person.populate_affiliation(const.system_fs_derived, ou_id, const.affiliation_student,
                                            const.affiliation_status_student_aktiv)
            tmp = person.write_db()
            logger.debug2("alter person affiliations, write_db=%s" % tmp)
        for ou_id in profile.get_stedkoder():
            has = False
            for has_ou, has_aff in account_info.get(account_id, []):
                if has_ou == ou_id and has_aff == const.affiliation_student:
                    has = True
            if not has:
                user.set_account_type(ou_id, const.affiliation_student)
        # Populate spreads
        has_acount_spreads = [int(x['spread']) for x in user.get_spread()]
        has_person_spreads = [int(x['spread']) for x in person.get_spread()]
        for spread in profile.get_spreads():
            if spread.entity_type == const.entity_account:
                if not int(spread) in has_acount_spreads:
                    user.add_spread(spread)
                    changes.append("Add spread: %s" % str(spread))
            elif spread.entity_type == const.entity_person:
                if not int(spread) in has_person_spreads:
                    person.add_spread(spread)
        if changes:
            logger.debug("Changes [%s]: %s" % (user.account_name, ", ".join(changes)))
        # TODO: update default e-mail address

def get_existing_accounts():
    """Return a mapping of <fnr>:{account_id}[(ou_id, affiliation)]
    for all students, and a mapping <fnr>:<account_id|None>
    (account_id is used when the account is a reservation) for all
    others that owns an account"""
    
    if fast_test:
        return {}, {}
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)
    for p in person.list_affiliations(source_system=const.system_fs_derived,
                                      affiliation=const.affiliation_student,
                                      fetchall=False):
        derived_person_affiliations.setdefault(int(p['person_id']), []).append(
            (int(p['source_system']), int(p['ou_id']), int(p['affiliation']), int(p['status'])))
    logger.info("Finding student accounts...")
    pid2fnr = {}
    for p in person.list_external_ids(source_system=const.system_fs,
                                      id_type=const.externalid_fodselsnr):
        pid2fnr[int(p['person_id'])] = p['external_id']
    for p in person.list_external_ids(id_type=const.externalid_fodselsnr):
        if not pid2fnr.has_key(int(p['person_id'])):
            pid2fnr[int(p['person_id'])] = p['external_id']

    # Find all student accounts.  A student account is an account that
    # has only account_types with affiliation=student.  We're
    # currently only interested in active accounts, thus we filter on
    # expired (which also includes filtering on deleted)

    # TBD: skal vi implementere en cereconf.STUDENT_DISKS som benyttes
    # istedet dersom den er != None?

    students = {}
    for a in account.list_accounts_by_type(
        affiliation=const.affiliation_student, filter_expired=True,
        fetchall=False):
        if not pid2fnr.has_key(int(a['person_id'])):
            continue
        student_data = students.setdefault(pid2fnr[int(a['person_id'])], {})
        student_data.setdefault(int(a['account_id']), []).append(
            [ int(a['ou_id']), int(a['affiliation']) ])
    for person_id in students.keys():
        for account_id in students[person_id].keys():
            do_del = False
            for aff_data in students[person_id][account_id]:
                if aff_data[1] != const.affiliation_student:
                    do_del = True
            if do_del:
                del(students[person_id][account_id])

    others = {}
    # We only register the reserved account if the user doesn't
    # have another active account
    for a in account.list_reserved_users(fetchall=False):
        fnr = pid2fnr.get(int(a['owner_id']), None)
        if (fnr is not None) and (not students.has_key(fnr)):
            others[fnr] = int(a['account_id'])

    # If the user has no student or reserved account, we check for
    # other active accounts

    for a in account.list(filter_expired=True, fetchall=False):
        # Also populate account_id -> fnr mapping
        account_id2fnr[int(a['account_id'])] = pid2fnr.get(
            int(a['owner_id'] or 0), None)
        fnr = pid2fnr.get(int(a['owner_id']), None)
        if (fnr is not None) and (not students.has_key(fnr) and
                                  not others.has_key(fnr)):
            others[fnr] = None
    logger.info(" found %i + %i entires" % (len(students), len(others)))
    return students, others

def make_letters(data_file=None, type=None, range=None):
    if data_file is not None:  # Load info on letters to print from file
        f=open(data_file, 'r')
        tmp_passwords = pickle.load(f)
        f.close()
        for r in [int(x) for x in range.split(",")]:
            tmp = tmp_passwords["%s-%i" % (type, r)]
            tmp.append(r)
            all_passwords[tmp[0]] = tmp[1]
    person = Factory.get('Person')(db)
    account = Factory.get('Account')(db)
    dta = {}
    logger.debug("Making %i letters" % len(all_passwords))
    for account_id in all_passwords.keys():
        try:
            account.clear()
            account.find(account_id)
            person.clear()
            person.find(account.owner_id)  # should be account.owner_id
        except Errors.NotFoundError:
            logger.warn("NotFoundError for account_id=%s" % account_id)
            continue
        tpl = {}
        address = person.get_entity_address(source=const.system_fs,
                                            type=const.address_post)
        if not address:
            logger.warn("Bad address for %s" % account_id)
            continue
        address = address[0]
        alines = address['address_text'].split("\n")+[""]
        fullname = person.get_name(const.system_cached, const.name_full)
        tpl['address_line1'] = fullname
        tpl['address_line2'] = alines[0]
        tpl['address_line3'] = alines[1]
        tpl['zip'] = address['postal_number']
        tpl['city'] = address['city']
        tpl['country'] = address['country']

        tpl['uname'] = account.account_name
        tpl['password'] =  all_passwords[account_id][0]
        tpl['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
        tpl['fullname'] =  fullname
        tmp = person.get_external_id(id_type=const.externalid_fodselsnr,
                                     source_system=const.system_fs)
        tpl['birthno'] =  tmp[0]['external_id']
        tpl['emailadr'] =  "TODO"  # We probably don't need to support this...
        tpl['account_id'] = account_id
        dta[account_id] = tpl

    # Print letters sorted by zip.  Each template type has its own
    # letter number sequence
    keys = dta.keys()
    keys.sort(lambda x,y: cmp(dta[x]['zip'], dta[y]['zip']))
    letter_info = {}
    files = {}
    tpls = {}
    counters = {}
    for account_id in keys:
        if not dta[account_id]['zip'] or dta[account_id]['country']:
            # TODO: Improve this check, which is supposed to skip foreign addresses
            logger.warn("Not sending abroad: %s" % dta[account_id]['uname'])
            continue
        
        password, brev_profil = all_passwords[account_id][:2]
        letter_type = "%s.%s" % (brev_profil['mal'], brev_profil['type'])
        if not files.has_key(letter_type):
            files[letter_type] = file("letter-%i-%s" % (time(), letter_type), "w")
            tpls[letter_type] = TemplateHandler(
                'no_NO/letter', brev_profil['mal'], brev_profil['type'])
            if tpls[letter_type]._hdr is not None:
                files[letter_type].write(tpls[letter_type]._hdr)
            counters[letter_type] = 1
        if data_file is not None:
            dta[account_id]['lopenr'] = all_passwords[account_id][2]
            if not os.path.exists("barcode_%s.eps" % account_id):
                make_barcode(account_id)
        else:
            dta[account_id]['lopenr'] = counters[letter_type]
            letter_info["%s-%i" % (brev_profil['mal'], counters[letter_type])] = \
                                [account_id, [password, brev_profil, counters[letter_type]]]
            # We allways create a barcode file, this is not strictly
            # neccesary
            make_barcode(account_id)
        dta[account_id]['barcode'] = os.path.realpath('barcode_%s.eps' %  account_id)
        files[letter_type].write(tpls[letter_type].apply_template(
            'body', dta[account_id], no_quote=('barcode',)))
        counters[letter_type] += 1
    # Save passwords for created users so that letters may be
    # re-printed at a later time in case of print-jam etc.
    if data_file is None:
        f=open("letters.info", 'w')
        pickle.dump(letter_info, f)
        f.close()
    # Close files and spool jobs
    for letter_type in files.keys():
        if tpls[letter_type]._footer is not None:
            files[letter_type].write(tpls[letter_type]._footer)
        files[letter_type].close()
        try:
            tpls[letter_type].spool_job(files[letter_type].name,
                                        tpls[letter_type]._type, cereconf.PRINT_PRINTER,
                                        skip_lpr=skip_lpr)
            os.unlink(tpls[letter_type].logfile)
        except IOError, msg:
            print msg

def make_barcode(account_id):
    ret = os.system("%s -e EAN -E -n -b %012i > barcode_%s.eps" % (
        cereconf.PRINT_BARCODE, account_id, account_id))
    if ret:
        logger.warn("Bardode returned %s" % ret)

def _filter_person_info(person_info):
    """Makes debugging easier by removing some of the irrelevant
    person-information."""
    ret = {}
    filter = {
        'opptak': ['studieprogramkode', 'studierettstatkode'],
        'privatist_emne': ['emnekode'],
        'privatist_studieprogram': ['studieprogramkode'],
        'fagperson': [],
        'alumni': ['studieprogramkode', 'studierettstatkode'],
        'evu': ['etterutdkurskode'],
        'tilbud': ['studieprogramkode']
        }
    for info_type in person_info.keys():
        if info_type in ('fodselsdato', 'personnr'):
            continue
        for f in filter:
            if info_type == f:
                for dta in person_info[info_type]:
                    ret.setdefault(info_type, []).append(
                        dict([(k, dta[k]) for k in filter[info_type]]))
        if not ret.has_key(info_type):
            ret[info_type] = person_info[info_type]
    return ret

def recalc_quota_callback(person_info):
    fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                              int(person_info['personnr'])))
    logger.set_indent(0)
    logger.debug("Callback for %s" % fnr)
    logger.set_indent(3)
    logger.debug(logger.pformat(_filter_person_info(person_info)))
    pq = PrinterQuotas.PrinterQuotas(db)
    group = Factory.get('Group')(db)

    for account_id in students.get(fnr, {}).keys():
        groups = []
        for r in group.list_groups_with_entity(account_id):
            groups.append(int(r['group_id']))
        try:
            profile = autostud.get_profile(person_info, member_groups=groups)
            quota = profile.get_pquota()
        except AutoStud.ProfileHandler.NoMatchingQuotaSettings, msg:
            logger.warn("Error for %s: %s" %  (fnr, msg))
            logger.set_indent(0)
            return
        except AutoStud.ProfileHandler.NoMatchingProfiles, msg:
            logger.warn("Error for %s: %s" %  (fnr, msg))
            logger.set_indent(0)
            return
        except Errors.NotFoundError, msg:
            logger.warn("Error for %s: %s" %  (fnr, msg))
            logger.set_indent(0)
            return
        logger.debug("Setting %s as pquotas for %s" % (quota, account_id))
        if dryrun:
            continue
        pq.clear()
        try:
            pq.find(account_id)
        except Errors.NotFoundError:
            # The quota update script should be ran just after this script
            if quota['weekly_quota'] == 'UL':
                init_quota = 0
            else:
                init_quota = int(quota['initial_quota']) - int(quota['weekly_quota'])
            pq.populate(account_id, init_quota, 0, 0, 0, 0, 0, 0)
        if quota['weekly_quota'] == 'UL' or profile.get_printer_kvote_fritak():
            pq.has_printerquota = 'F'
        else:
            pq.has_printerquota = 'T'
            pq.weekly_quota = quota['weekly_quota']
            pq.max_quota = quota['max_quota']
            pq.termin_quota = quota['termin_quota']
        if paper_money_file:
            if (not profile.get_printer_betaling_fritak() and
                not paid_paper_money.get(fnr, False)):
                logger.debug("didn't pay, max_quota=0 for %s " % fnr)
                pq.max_quota = 0
                pq.printer_quota = 0
        pq.write_db()
        has_quota[int(account_id)] = True
    logger.set_indent(0)
    # We commit once for each person to avoid locking too many db-rows
    if not dryrun:
        db.commit()

def process_students_callback(person_info):
    global max_errors
    try:
        process_student(person_info)
    except:
        max_errors -= 1
        if max_errors < 0:
            raise
        trace = "".join(traceback.format_exception(
            sys.exc_type, sys.exc_value, sys.exc_traceback))
        logger.error("Unexpected error: %s" % trace)
        db.rollback()


def process_student(person_info):
    fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                              int(person_info['personnr'])))
    logger.set_indent(0)
    logger.debug("Callback for %s" % fnr)
    alternative_account_id = other_account_owners.get(fnr, -1)
    logger.set_indent(3)
    logger.debug(logger.pformat(_filter_person_info(person_info)))
    try:
        profile = autostud.get_profile(person_info)
    except AutoStud.ProfileHandler.NoMatchingProfiles, msg:
        logger.warn("Error for %s: %s" %  (fnr, msg))
        logger.set_indent(0)
        return
    except Errors.NotFoundError, msg:
        logger.warn("Error for %s: %s" %  (fnr, msg))
        logger.set_indent(0)
        return
    
    processed_students[fnr] = 1
    keep_account_home[fnr] = profile.get_build()['home']
    if fast_test:
        logger.debug(profile.debug_dump())
        # logger.debug("Disk: %s" % profile.get_disk())
        logger.set_indent(0)
        return
    try:
        # Note that we don't pass current_disk to get_disks() here.
        # Thus this value may differ from the one used during an
        # update
        try:
            dfg = profile.get_dfg()       # dfg is only mandatory for PosixGroups
        except ValueError:
            dfg = "<no_dfg>"
        if keep_account_home[fnr]:
            # This will throw an exception if <build home="true">, and
            # we can't get a disk.  This is what we want
            disk = []
            spreads = [int(s) for s in profile.get_spreads()]
            for s in profile.get_disk_spreads():
                if s in spreads:
                    disk.append((profile.get_disk(s), s))
            if not disk:
                raise ValueError, "No disk matches profiles"
        else:
            disk = "<no_home>"
        logger.debug("disk=%s, dfg=%s, fg=%s sko=%s" % \
                     (str(disk), dfg,
                      profile.get_grupper(),
                      profile.get_stedkoder()))
        if dryrun:
            logger.set_indent(0)
            return
        if (create_users and not students.has_key(fnr) and
            profile.get_build()['action']):
            if alternative_account_id is None:
                logger.debug("Has active non-student account, skipping")
                return
            elif alternative_account_id != -1:  # has a reserved account
                logger.debug("using reserved: %i" % alternative_account_id)
                account_id = alternative_account_id
                update_account(profile, fnr, [account_id],
                               account_info=students.get(fnr, {}))
            else:
                account_id = create_user(fnr, profile)
            if account_id is None:
                logger.set_indent(0)
                return
            students.setdefault(fnr, {})[account_id] = []
        elif update_accounts and students.has_key(fnr):
            update_account(profile, fnr, students[fnr].keys(),
                           account_info=students[fnr])
    except ValueError, msg:  # TODO: Bad disk should throw a spesific class
        logger.error("  Error for %s: %s" % (fnr, msg))
    logger.set_indent(0)
    # We commit once for each person to avoid locking too many db-rows
    if not dryrun:
        db.commit()

def validate_config():
    AutoStud.AutoStud(db, logger, debug=debug, cfg_file=studconfig_file,
                      studieprogs_file=studieprogs_file,
                      emne_info_file=emne_info_file)

def process_students():
    global autostud, students, other_account_owners

    logger.info("process_students started")
    students, other_account_owners = get_existing_accounts()
    
    logger.info("got student accounts")
    autostud = AutoStud.AutoStud(db, logger, debug=debug, cfg_file=studconfig_file,
                                 studieprogs_file=studieprogs_file,
                                 emne_info_file=emne_info_file)
    logger.info("config processed")
    if recalc_pq:
        if paper_money_file:
            for p in AutoStud.StudentInfo.GeneralDataParser(paper_money_file, 'betalt'):
                fnr = fodselsnr.personnr_ok("%06d%05d" % (int(p['fodselsdato']),
                                                          int(p['personnr'])))
                paid_paper_money[fnr] = True
        autostud.start_student_callbacks(student_info_file,
                                         recalc_quota_callback)
        # Set default_quota for the rest that already has quota
        pq = PrinterQuotas.PrinterQuotas(db)
        dv = autostud.pc.default_values
        for row in pq.list_quotas():
            account_id = int(row['account_id'])
            if row['has_printerquota'] == 'F' or has_quota.get(account_id, False):
                continue
            logger.debug("Default quota for %i" % account_id)
            pq.clear()
            try:
                pq.find(account_id)
            except Errors.NotFoundError:
                logger.error("not found: %i, recently deleted?" % account_id)
                continue
            pq.weekly_quota = dv['print_uke']
            pq.max_quota = dv['print_max_akk']
            pq.termin_quota = dv['print_max_sem']
            if paper_money_file:
                if not account_id2fnr.has_key(account_id):
                    # probably a deleted user
                    logger.debug("account_id %i not in account_id2fnr, deleted?" % account_id)
                elif not paid_paper_money.get(account_id2fnr[account_id], False):
                    logger.debug("didn't pay, max_quota=0 for %i " % account_id)
                    pq.max_quota = 0
                    pq.printer_quota = 0
            pq.write_db()
        if not dryrun:
            db.commit()
        else:
            db.rollback()
    else:
        autostud.start_student_callbacks(student_info_file,
                                         process_students_callback)
        logger.set_indent(0)
        logger.info("student_info_file processed")
        if not dryrun:
            db.commit()
            logger.info("making letters")
            if only_dump_to is not None:
                f = open(only_dump_to, 'w')
                pickle.dump(all_passwords, f)
                f.close()
            else:
                make_letters()
        else:
            db.rollback()
        process_unprocessed_students()
    logger.info("process_students finished")

def process_unprocessed_students():
    """Unprocessed students didn't match a profile, or didn't get a
    callback at all"""
    # TBD: trenger vi skille p� de?
    
    user = Factory.get('Account')(db)
    for fnr in students.keys(): 
        if not processed_students.has_key(fnr):
            logger.debug("%s has student accounts, but has not been processed" % fnr)
        if not keep_account_home.get(fnr, False):
            # List accounts that the student has, and that lies on a
            # student-disk
            accounts = []
            for account_id in students[fnr].keys():
                user.clear()
                user.find(account_id)
                disk_ids = []
                for disk_spread in autostud.pc.disk_spreads.keys():
                    try:
                        tmp=user.get_home(disk_spread)['disk_id']
                        if autostud.student_disk.has_key(tmp):
                            disk_ids.append((int(tmp), int(disk_spread)))
                    except (Errors.NotFoundError, TypeError):
                        pass
                accounts.append("%s:%s" % (user.account_name,
                                           str(disk_ids)))
            logger.debug("%s didn't set keep_account_home: %s" % (fnr, str(accounts)))

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dcus:C:S:e:p:',
                                   ['debug', 'create-users', 'update-accounts',
                                    'student-info-file=', 'only-dump-results=',
                                    'studconfig-file=', 'fast-test', 'with-lpr',
                                    'workdir=', 'type=', 'reprint=',
                                    'emne-info-file=', 'move-users',
                                    'recalc-pq', 'studie-progs-file=',
                                    'paper-file=',
                                    'remove-groupmembers'
                                    'dryrun', 'validate'])
    except getopt.GetoptError:
        usage()
    global debug, fast_test, create_users, update_accounts, logger, skip_lpr
    global student_info_file, studconfig_file, only_dump_to, studieprogs_file, \
           recalc_pq, dryrun, emne_info_file, move_users, remove_groupmembers, \
           workdir, paper_money_file

    skip_lpr = True       # Must explicitly tell that we want lpr
    update_accounts = create_users = recalc_pq = dryrun = move_users = False
    remove_groupmembers = validate = False
    fast_test = False
    workdir = None
    range = None
    only_dump_to = None
    paper_money_file = None         # Default: don't check for paid paper money
    to_stdout = False
    log_level = AutoStud.Util.ProgressReporter.DEBUG
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            debug += 1
            log_level += 1
            to_stdout = True
        elif opt in ('-c', '--create-users'):
            create_users = True
        elif opt in ('-u', '--update-accounts'):
            update_accounts = True
        elif opt in ('-s', '--student-info-file'):
            student_info_file = val
        elif opt in ('-e', '--emne-info-file'):
            emne_info_file = val
        elif opt in ('-p', '--paper-file'):
            paper_money_file = val
        elif opt in ('-S', '--studie-progs-file'):
            studieprogs_file = val
        elif opt in ('--recalc-pq',):
            recalc_pq = True
        elif opt in ('--remove-groupmembers',):
            remove_groupmembers = True
        elif opt in ('--move-users',):
            move_users = True
        elif opt in ('-C', '--studconfig-file'):
            studconfig_file = val
        elif opt in ('--fast-test',):  # Internal debug use ONLY!
            fast_test = True
        elif opt in ('--only-dump-results',):
            only_dump_to = val
        elif opt in ('--dryrun',):
            dryrun = True
        elif opt in ('--validate',):
            validate = True
            to_stdout = True
            workdir = '.'
            log_level = AutoStud.Util.ProgressReporter.INFO
        elif opt in ('--with-lpr',):
            skip_lpr = False
        elif opt in ('--workdir',):
            workdir = val
        elif opt in ('--type',):
            type = val
        elif opt in ('--reprint',):
            range = val
            to_stdout = True
        else:
            usage()

    if (not update_accounts and not create_users and not validate and
          range is None):
        if not recalc_pq:
            usage()
    else:
        if recalc_pq:
            raise ValueError, "recalc-pq cannot be combined with other operations"
    if workdir is None:
        workdir = "%s/ps-%s.%i" % (cereconf.AUTOADMIN_LOG_DIR,
                                   strftime("%Y-%m-%d", localtime()),
                                   os.getpid())
        os.mkdir(workdir)
    os.chdir(workdir)
    logger = AutoStud.Util.ProgressReporter("%s/run.log.%i"
                                            % (workdir, os.getpid()),
                                            stdout=to_stdout,
                                            loglevel=log_level)
    bootstrap()
    if validate:
        validate_config()
        sys.exit(0)
    if range is not None:
        make_letters("letters.info", type=type, range=val)
    else:
        process_students()
    
def usage():
    print """Usage: process_students.py -d | -c | -u
    -d | --debug: increases debug verbosity
    -c | --create-user : create new users
    -u | --update-accounts : update existing accounts
    -s | --student-info-file file:
    -e | --emne-info-file file:
    -C | --studconfig-file file:
    -S | --studie-progs-file file:
    -p | --paper-file file: check for paid-quota only done if set
    --dryrun: don't do any changes to the database.  This can be used
      to get an idea of what changes a normal run would do.  TODO:
      also dryrun some parts of update/create user.
    --validate: parse the configuration file and report any errors,
      then exit.
    --recalc-pq : recalculate printerquota settings (does not update
      quota).  Cannot be combined with -c/-u
    --only-dump-results file: just dump results with pickle without
      entering make_letters
    --workdir dir:  set workdir for --reprint
    --remove-groupmembers: remove groupmembers if profile says so
    --move-users: move users if profile says so
    --type type: set type (=the mal attribute to <brev> in studconfig.xml) for --reprint
    --reprint range:  Re-print letters in case of paper-jam etc. (comma separated)
    --with-lpr: Spool the file with new user letters to printer

To create new users:
  ./contrib/no/uio/process_students.py -C .../studconfig.xml -S .../studieprogrammer.xml -s .../merged_persons.xml -c

To reprint letters of a given type:
  ./contrib/no/uio/process_students.py --workdir tmp/ps-2003-09-25.1265 --type new_stud_account --reprint 1,2
    """
    sys.exit(0)

if __name__ == '__main__':
    #logger = AutoStud.Util.ProgressReporter(
    #    None, stdout=1, loglevel=AutoStud.Util.ProgressReporter.DEBUG)
    #AutoStud.AutoStud(db, logger, debug=3,
    #                  cfg_file="/home/runefro/usit/cerebrum/uiocerebrum/etc/config/studconfig.xml")

    main()
