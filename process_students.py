#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003, 2004 University of Oslo, Norway
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

import hotshot, hotshot.stats
proffile  = 'hotshot.prof'
import getopt
import datetime
import sys
import os
import pickle
import traceback
import mx
from time import localtime, strftime, time

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory, SimilarSizeWriter
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd import errors
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uit import AutoStud
from Cerebrum.modules.no.uit import DiskQuota
from Cerebrum.modules.no.uit import PrinterQuotas
from Cerebrum.modules.templates.letters import TemplateHandler
#UIT:
from Cerebrum.modules.no.uit import Email



db = Factory.get('Database')()
db.cl_init(change_program='process_students')
const = Factory.get('Constants')(db)
all_passwords = {}
derived_person_affiliations = {}
person_student_affiliations = {}
has_quota = {}
processed_students = {}
processed_accounts = {}
keep_account_home = {}
paid_paper_money = {}
account_id2fnr = {}

posix_user_obj = PosixUser.PosixUser(db)
account_obj = Factory.get('Account')(db)
person_obj = Factory.get('Person')(db)
group_obj = Factory.get('Group')(db)
disk_quota_obj = DiskQuota.DiskQuota(db)

debug = 0
max_errors = 50          # Max number of errors to accept in person-callback
posix_spreads = [int(const.Spread(_s)) for _s in cereconf.POSIX_SPREAD_CODES]

# global Command-line alterable variables.  Defined here to make
# pychecker happy
skip_lpr = True       # Must explicitly tell that we want lpr
create_users = move_users = dryrun = update_accounts = False
with_quarantines = False
remove_groupmembers = False
ou_perspective = None
workdir = None
only_dump_to = None
paper_money_file = None         # Default: don't check for paid paper money
student_info_file = None
studconfig_file = None
studieprogs_file = None
emne_info_file = None
fast_test = False

# Other globals (to make pychecker happy)
autostud = logger = accounts = persons = None
default_creator_id = default_expire_date = default_shell = None




class AccountUtil(object):
    """Collection of methods that operate on a single account to make
    it conform to a profile """

    def create_user(fnr, profile):
        # dryruning this method is unfortunately a bit tricky
        assert not dryrun
        today = datetime.datetime.now()
        logger.info2("CREATE")
        person = Factory.get('Person')(db)
        logger.info("Trying to create user for person with fnr=%s" % fnr)

        try:
            person.find_by_external_id(const.externalid_fodselsnr, fnr,
                                       const.system_fs)
        except Errors.NotFoundError:
            logger.warn("OUCH! person %s not found" % fnr)
            return None

        try:
            first_name = person.get_name(const.system_cached, const.name_first)
        except Errors.NotFoundError:
            # This can happen if the person has no first name and no
            # authoritative system has set an explicit name_first variant.
            first_name = ""
        if not persons[fnr].get_affiliations():
            logger.error("The person %s has no student affiliations" % fnr)
            return None
        try:
            last_name = person.get_name(const.system_cached, const.name_last)
        except Errors.NotFoundError:
            # See above.  In such a case, name_last won't be set either,
            # but name_full will exist.
            last_name = person.get_name(const.system_cached, const.name_full)
            assert last_name.count(' ') == 0

        account = Factory.get('Account')(db)
        
        #UIT changed this call to match our own username builder.
        uname = account.suggest_unames(fnr, first_name, last_name)
        account.populate(uname,
                         const.entity_person,
                         person.entity_id,
                         None,
                         default_creator_id, default_expire_date)
        
        ## UIT: We no longer use fnr as initial password!
        #password = fnr
        password = account.make_passwd(uname)
        account.set_password(password)
        tmp = account.write_db()
        logger.debug("new Account, write_db=%s" % tmp)
        # Need to set initial quarantine for students only (no quarantine for "fagpersoner").
        # setting todays date at start date.
        check_aff=persons[fnr].get_affiliations()
        for aff in persons[fnr].get_affiliations():
            if aff == const.affiliation_student:
                # This persons has a student affiliation. set quarantine on the account. (we do not set quarantine for employees or "fagpersoner" accounts)
                quarantine_date = "%s" % today.date()
                logger.debug("quarantine date =%s" % quarantine_date)
                account.add_entity_quarantine(const.quarantine_tilbud,default_creator_id,start=quarantine_date)
        #sys.exit(1) # <- for debuging purposes. remove this once quarantene settings on new accounts has been verified.
        logger.debug("new Account, write_db=%s" % tmp)
        all_passwords[int(account.entity_id)] = [password, profile.get_brev()]
        as_posix = False
        for spread in profile.get_spreads():
            if int(spread) in posix_spreads:
                as_posix = True
        accounts[int(account.entity_id)] = ExistingAccount(fnr,mx.DateTime.today())
        AccountUtil.update_account(account.entity_id, fnr, profile, as_posix)
        return account.entity_id
    create_user=staticmethod(create_user)


    
    def _update_email(account_obj):
        # The UIT way of handling student email
        student_email = "%s@student.uit.no" % (account_obj.account_name)
        current_email = ""
        try:
            current_email = account_obj.get_primary_mailaddress()
            
        except Errors.NotFoundError:
            # no current mail try to retreive from ad-mail table
            pass

        logger.debug("UIT _update_email: student_email='%s', current='%s'" % (student_email,current_email))

        # need to figure out if this a student or "fagperson"
        only_tilknyttet = 0
        account_types = account_obj.get_account_types(filter_expired=False)
        for acc_aff in account_types:
            if ((const.affiliation_student == acc_aff['affiliation']) or (const.affiliation_ansatt == acc_aff['affiliation'])):
                only_tilknyttet = 1

        if only_tilknyttet == 0 and current_email =="":
            student_email = "%s@mailbox.uit.no" % (account_obj.account_name)
            logger.debug("account:%s only has a tilknyttet affiliation, use %s@mailbox.uit.no" % (account_obj.account_name,account_obj.account_name))

            
        if (current_email != student_email):
            # update email!
            em = Email.email_address(db)
            try:
                # We need an additional check here. If the student already has an employee account
                # with an employee primary email address, this script must NOT update the primary
                # email address (only add an additional email address).
                # if person_affiliation_soure.affiliation == ansatt && person_affiliation_source.delete_date == NULL
                #   do not update primary email
                # else:
                #   update_primary_email
                person_id = account_obj.owner_id
                my_person = Factory.get('Person')(db)
                my_person.clear()
                my_person.find(person_id)
                affiliations = my_person.get_affiliations()
                update_primary_email=True
                #print "PERSON ID->%s,affiliations=%s" % (person_id,affiliations)
                for i in affiliations:
                    #print "AFF-> %s" % i
                    #print "affiliation=>>%s, delete_date=%s" % (i.affiliation,i.deleted_date)
                    if(((i.affiliation==const.affiliation_ansatt) and (i.deleted_date==None))or ((i.affiliation==const.affiliation_tilknyttet) and (i.deleted_date==None) and (i.source_system==const.system_x))):
                        update_primary_email=False
                        #print "has employee affiliation. do not update primary email"
                        #print "affiliation=%s,create_date=%s,delete_date=%s" % (i.affiliation,i.create_date,i.deleted_date)
                if update_primary_email==False:
                    logger.debug("adding student email")
                    em.process_mail(account_obj.entity_id,"no_primary_update",student_email)
                else:
                    logger.debug("has no employee affiliation. update primary email")
                    em.process_mail(account_obj.entity_id,"defaultmail",student_email)

                logger.debug("UIT: process mailaddr update!")
            except Exception:
                logger.debug("EMAIL UPDATE FAILED: account_id=%s , email=%s" % (account_obj.entity_id,student_email))
                sys.exit(2)
        else:
            #current email = student_email :=> we need to do nothing. all is ok....
            pass
        
        # end update_mail()
    _update_email=staticmethod(_update_email)

        
        
        
        
        
    
    
    
    def _populate_account_affiliations(account_id, fnr):
        """Assert that the account has the same student affiliations as
        the person.  Will not remove the last student account affiliation
        even if the person has no such affiliation"""

        changes = []
        remove_idx = 1     # Do not remove last account affiliation
        tilknyttet_remove_idx = 1
        account_ous = [ou for aff, ou in accounts[account_id].get_affiliations()
                       if aff == const.affiliation_student]

        tilknyttet_account_ous = [ou for aff, ou in accounts[account_id].get_affiliations()
                       if aff == const.affiliation_tilknyttet]

        for aff, ou, status in persons[fnr].get_affiliations():
            if not ou in account_ous and aff == const.affiliation_student:
                changes.append(('set_ac_type', (ou, const.affiliation_student)))
            else:
                if ((len(account_ous)>0) and (aff == const.affiliation_student)):
                    account_ous.remove(ou)
                    # The account has at least one valid affiliation, so
                    # we can delete everything left in account_ous.
                    remove_idx = 0

            if not ou in tilknyttet_account_ous and aff == const.affiliation_tilknyttet:
                changes.append(('set_ac_type', (ou, const.affiliation_tilknyttet)))
            else:
                if ((len(tilknyttet_account_ous)>0) and (aff==const.affiliation_tilknyttet)):
                    tilknyttet_account_ous.remove(ou)
                    # The account has at least one valid affiliation, so
                    # we can delete everything left in account_ous.
                    tilknyttet_remove_idx = 0


        for ou in account_ous[remove_idx:]:
            changes.append(('del_ac_type', (ou, const.affiliation_student)))

        for ou in tilknyttet_account_ous[tilknyttet_remove_idx:]:
            changes.append(('del_ac_type', (ou, const.affiliation_tilknyttet)))


        return changes
    _populate_account_affiliations=staticmethod(_populate_account_affiliations)
    
    def _handle_user_changes(changes, account_id, as_posix):
        if as_posix:
            user = posix_user_obj
        else:
            user = account_obj
        user.clear()
        if changes[0][0] == 'dfg' and accounts[account_id].get_gid() is None:
            uid = user.get_free_uid()
            shell = default_shell
            account_obj.clear()
            account_obj.find(account_id)
            user.populate(uid, changes[0][1], None, shell, 
                          parent=account_obj, expire_date=default_expire_date)
            user.write_db()
            logger.debug("Used dfg2: "+str(changes[0][1]))
            accounts[account_id].append_group(changes[0][1])
            del(changes[0])
        else:
            user.find(account_id)
            
        for c_id, dta in changes:
            if c_id == 'dfg':
                user.gid_id = dta
                logger.debug("Used dfg: "+str(dta))
                accounts[account_id].append_group(dta)
            elif c_id == 'expire':
                logger.debug("Updated expire:" + str(dta))
                user.expire_date = dta
            elif c_id == 'disk':
                current_disk_id, disk_spread, new_disk = dta
                if current_disk_id is None:
                    logger.debug("Set home: %s" % new_disk)
                    #homedir_id = user.set_home_dir(
                    #    disk_id=new_disk, status=const.home_status_not_created)
                    #user.set_home(disk_spread, homedir_id)
                    #accounts[account_id].set_home(disk_spread, new_disk, homedir_id)
                    user.set_home_dir(disk_spread)
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
            elif c_id == 'remove_autostud_quarantine':
                user.delete_entity_quarantine(dta)
            elif c_id == 'add_spread':
                user.add_spread(dta)
            elif c_id == 'add_person_spread':
                if (not hasattr(person_obj, 'entity_id') or
                    person_obj.entity_id != user.owner_id):
                    person_obj.clear()
                    person_obj.find(user.owner_id)
                person_obj.add_spread(dta)
            elif c_id == 'set_ac_type':
                user.set_account_type(dta[0], dta[1])
            elif c_id == 'del_ac_type':
                user.del_account_type(dta[0], dta[1])
            elif c_id == 'add_quarantine':
                start_at = strftime('%Y-%m-%d', localtime(dta[1] + time()))
                user.add_entity_quarantine(
                    dta[0], default_creator_id, 'automatic', start_at)
            elif c_id == 'disk_kvote':
                disk_id, homedir_id, quota, spread = dta
                if homedir_id is None:    # homedir was added in this run
                    homedir_id = accounts[account_id].get_home(spread)[1]
                disk_quota_obj.set_quota(homedir_id, quota=int(quota))
            else:
                raise ValueError, "Unknown change: %s" % c_id
        tmp = user.write_db()
        logger.debug("write_db=%s" % tmp)
    _handle_user_changes=staticmethod(_handle_user_changes)

    def _update_group_memberships(account_id, profile):
        global fisk
        fisk = account_id
        changes = []       # Changes is only used for debug output
        already_member = {}
        today = str(datetime.date.today())
        try:
            if(accounts[account_id].get_expire_date().date < today):
                expired=1
                logger.debug("account %s is expired" % account_id)
            else:
                expired=0
        except AttributeError, m:
            # we are working on a yet-to-be account. no account object has been
            # created. set expire to 0;
            expired =0
            
        for group_id in accounts[account_id].get_groups():
            already_member[group_id] = True
        logger.debug("%i already in %s" % (account_id, repr(already_member)))
        for g in profile.get_grupper():
            if((not already_member.has_key(g)) and(not expired)):
                group_obj.clear()
                group_obj.find(g)
                group_obj.add_member(account_id, const.entity_account,
                                 const.group_memberop_union)
                changes.append(("g_add", group_obj.group_name))
            else:
                if(not expired):
                    del already_member[g]
        if remove_groupmembers:
            for g in already_member.keys():
                if autostud.pc.group_defs.get(g, {}).get('auto', None) == 'auto':
                    if accounts[account_id].get_gid() == g:
                        logger.warn("Can't remove %i from its dfg %i" % (
                            account_id, g))
                    group_obj.clear()
                    group_obj.find(g)
                    group_obj.remove_member(account_id, const.group_memberop_union)
                    changes.append(('g_rem', group_obj.group_name))
        return changes
    _update_group_memberships=staticmethod(_update_group_memberships)

    def update_account(account_id, fnr, profile, as_posix):
        # First fill 'changes' with all needed modifications.  We will
        # only lookup databaseobjects if changes is non-empty.
        logger.info2(" UPDATE:%s" % account_id)
        processed_accounts[account_id] = True
        changes = []
        ac = accounts[account_id]
        if as_posix:
            gid = profile.get_dfg()
            # we no longer want to change the default-group
            if (ac.get_gid() is None): # or ac['gid'] != gid):
                changes.append(('dfg', gid))

        ## MAY BE WRONG! What if another sourcesys has set another date (further out)?
        #if ac.get_expire_date() != default_expire_date:
        #    changes.append(('expire', default_expire_date))
        ## new update expire method
        current_expire = mx.DateTime.DateFrom(ac.get_expire_date())
        new_expire = mx.DateTime.DateFrom(default_expire_date)
        today = mx.DateTime.today()
        if ((new_expire > today) and (new_expire > current_expire)):
            # If account is expired in cerebrum => update expire
            # or if our expire is further out than current expire => update
            changes.append(('expire', default_expire_date))

        # Set/change homedir
        user_spreads = [int(s) for s in profile.get_spreads()]

        # quarantine scope='student_disk' should affect all users with
        # home on a student-disk, or that doesn't have a home at all
        may_be_quarantined = False
        if not ac.has_homes():
            may_be_quarantined = True
        for s in autostud.disk_tool.get_known_spreads():
            disk_id, homedir_id = ac.get_home(s)
            if (disk_id and
                autostud.disk_tool.get_diskdef_by_diskid(disk_id)):
                may_be_quarantined = True

        current_disk_id = None
        for disk_spread in profile.get_disk_spreads():
            if not disk_spread in user_spreads:
                # The disk-spread in disk-defs was not one of the users spread
                continue 
            current_disk_id, notused = ac.get_home(disk_spread)
            if keep_account_home[fnr] and (move_users or current_disk_id is None):
                try:
                    new_disk = profile.get_disk(disk_spread, current_disk_id)
                except AutoStud.ProfileHandler.NoAvailableDisk:
                    raise
                if current_disk_id != new_disk:
                    autostud.disk_tool.notify_used_disk(old=current_disk_id, new=new_disk)
                    changes.append(('disk', (current_disk_id, disk_spread, new_disk)))
                    current_disk_id = new_disk
                    ac.set_home(disk_spread, new_disk, ac.get_home(disk_spread)[1])

        if autostud.disk_tool.using_disk_kvote:
            for spread in accounts[account_id].get_home_spreads():
                disk_id, homedir_id = accounts[account_id].get_home(spread)
                if not autostud.disk_tool.get_diskdef_by_diskid(disk_id):
                    # Setter kun kvote p� student-disker
                    continue
                quota = profile.get_disk_kvote(disk_id)
                if (ac.get_disk_kvote(homedir_id) != quota):
                    changes.append(('disk_kvote', (disk_id, homedir_id, quota, spread)))
                    ac.set_disk_kvote(homedir_id, quota)

        # TBD: Is it OK to ignore date on existing quarantines when
        # determining if it should be added?
        tmp = []
        for q in profile.get_quarantines():
            if q['scope'] == 'student_disk' and not may_be_quarantined:
                continue
            tmp.append(int(q['quarantine']))
            if with_quarantines and not int(q['quarantine']) in ac.get_quarantines():
                changes.append(('add_quarantine', (q['quarantine'], q['start_at'])))

        # Remove auto quarantines
        for q in (const.quarantine_auto_inaktiv,
                  const.quarantine_auto_emailonly):
            if (int(q) in ac.get_quarantines() and
                int(q) not in tmp):
                changes.append(("remove_autostud_quarantine", q))

        # Populate spreads
        has_acount_spreads = ac.get_spreads()
        has_person_spreads = persons[fnr].get_spreads()
        for spread in profile.get_spreads():
            if spread.entity_type == const.entity_account:
                if not int(spread) in has_acount_spreads:
                    changes.append(('add_spread', spread))
            elif spread.entity_type == const.entity_person:
                if not int(spread) in has_person_spreads:
                    changes.append(('add_person_spread', spread))
                    has_person_spreads.append(int(spread))

        changes.extend(AccountUtil._populate_account_affiliations(account_id, fnr))
        # We have now collected all changes that would need fetching of
        # the user object.
        if changes:
            AccountUtil._handle_user_changes(changes, account_id, as_posix)


        # uit:Need to check for email updates here
        my_user = account_obj
        my_user.clear()
        my_user.find(account_id)
        #print "my_user.name:%s" % my_user.account_name
        AccountUtil._update_email(my_user)
        
        changes.extend(AccountUtil._update_group_memberships(account_id, profile))

        

        if changes:
            logger.debug("Changes [%i/%s]: %s" % (
                account_id, fnr, repr(changes)))
    update_account = staticmethod(update_account)

class RecalcQuota(object):
    """Collection of methods to calculate proper quota settings for a
    person"""

    def _recalc_quota_callback(person_info):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                                  int(person_info['personnr'])))
        logger.set_indent(0)
        logger.debug("Callback for %s" % fnr)
        logger.set_indent(3)
        logger.debug(logger.pformat(_filter_person_info(person_info)))
        pq = PrinterQuotas.PrinterQuotas(db)

        for account_id in persons.get(fnr, {}).keys():
            try:
                profile = autostud.get_profile(
                    person_info, member_groups=persons[fnr].get_groups())
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
    _recalc_quota_callback=staticmethod(_recalc_quota_callback)

    def recalc_pq_main():
        raise SystemExit("--recalc-quota is obsolete and will be removed shortly")
        if paper_money_file:
            for p in AutoStud.StudentInfo.GeneralDataParser(paper_money_file, 'betalt'):
                fnr = fodselsnr.personnr_ok("%06d%05d" % (int(p['fodselsdato']),
                                                          int(p['personnr'])))
                paid_paper_money[fnr] = True
        autostud.start_student_callbacks(student_info_file,
                                         RecalcQuota._recalc_quota_callback)
        # Set default_quota for the rest that already has quota
        pq = PrinterQuotas.PrinterQuotas(db)
        dv = autostud.pc.default_values
        for row in pq.list_quotas():
            account_id = int(row['account_id'])
            if row['has_printerquota'] == 'F' or has_quota.get(account_id, False):
                continue
            logger.debug("Default quota for %i" % account_id)
            # TODO: sjekk om det er n�dvendig med oppdatering f�r vi gj�r find.
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
    recalc_pq_main=staticmethod(recalc_pq_main)

class BuildAccounts(object):
    """Collection of methods for updating/creating student users for
    all persons"""

    def _process_students_callback(person_info):
        global max_errors
        try:
            BuildAccounts._process_student(person_info)
        except:
            max_errors -= 1
            if max_errors < 0:
                raise
            trace = "".join(traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_info()[2]))
            logger.error("Unexpected error: %s" % trace)
            db.rollback()
    _process_students_callback=staticmethod(_process_students_callback)

    def _process_student(person_info):
        fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                                  int(person_info['personnr'])))
        logger.set_indent(0)
        logger.debug("Callback for %s" % fnr)

        logger.set_indent(3)
        pinfo = persons.get(fnr, None)
        if pinfo is None:
            logger.warn("Unknown person %s" % fnr)
            return
        logger.debug(logger.pformat(_filter_person_info(person_info)))
        if not persons.has_key(fnr):
            logger.warn("(person) not found error for %s" % fnr)
            logger.set_indent(0)
            return
        try:
            profile = autostud.get_profile(person_info, member_groups=persons[fnr].get_groups(),
                                           person_affs=persons[fnr].get_affiliations())
            logger.debug(profile.matcher.debug_dump())
        except AutoStud.ProfileHandler.NoMatchingProfiles, msg:
            logger.warn("No matching profile error for %s: %s" %  (fnr, msg))
            logger.set_indent(0)
            return
        except AutoStud.ProfileHandler.NoAvailableDisk, msg:
            # pretend that the account was processed so that
            # list_noncallback_users doesn't include the user(s).
            # While this is only somewhat correct behaviour, the
            # NoAvailableDisk situation should be resolved switftly.
            for account_id in pinfo.get_student_ac():
                processed_accounts[account_id] = True
            raise
        processed_students[fnr] = 1
        keep_account_home[fnr] = profile.get_build()['home']
        if fast_test:
            logger.debug(profile.debug_dump())
            # logger.debug("Disk: %s" % profile.get_disk())
            logger.set_indent(0)
            return
        try:
            _debug_dump_profile_match(profile, fnr)
            if dryrun:
                logger.set_indent(0)
                return
            if (create_users and not pinfo.has_student_ac() and
                profile.get_build()['action']):
                if pinfo.has_other_ac():
                    logger.debug("Has active non-student account, skipping")
                    #print "foo=%s" % pinfo._other_ac
                    BuildAccounts._update_persons_accounts(profile, fnr, [pinfo._other_ac[0]])
                    #BuildAccounts._update_persons_accounts(profile, fnr, [pinfo.get_best_reserved_ac()])
                    return
                elif pinfo.has_reserved_ac():  # has a reserved account
                    logger.debug("using reserved: %s" % pinfo.get_best_reserved_ac())
                    BuildAccounts._update_persons_accounts(
                        profile, fnr, [pinfo.get_best_reserved_ac()])
                else:
                    account_id = AccountUtil.create_user(fnr, profile)
                    if account_id is None:
                        logger.set_indent(0)
                        return
                # students.setdefault(fnr, {})[account_id] = []
            elif update_accounts and pinfo.has_student_ac():
                BuildAccounts._update_persons_accounts(
                    profile, fnr, pinfo.get_student_ac())
        except AutoStud.ProfileHandler.NoAvailableDisk, msg:
            logger.error("  Error for %s: %s" % (fnr, msg))
        logger.set_indent(0)
        # We commit once for each person to avoid locking too many db-rows
        if not dryrun:
            db.commit()
    _process_student=staticmethod(_process_student)
    
    def _update_persons_accounts(profile, fnr, account_ids):
        """Update the account by checking that group, disk and
        affiliations are correct.  For existing accounts, account_info
        should be filled with affiliation info """

        # dryruning this method is unfortunately a bit tricky
        assert not dryrun
        
        as_posix = False
        logger.debug("Spreads from profile=%s, POSIX_SPREADS=%s" %  (profile.get_spreads(),posix_spreads))
        for spread in profile.get_spreads():  # TBD: Is this check sufficient?
            if int(spread) in posix_spreads:
                as_posix = True
        for account_id in account_ids:
            AccountUtil.update_account(account_id, fnr, profile, as_posix)
    _update_persons_accounts=staticmethod(_update_persons_accounts)

    def update_accounts_main():
        autostud.start_student_callbacks(student_info_file,
                                         BuildAccounts._process_students_callback)
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
        BuildAccounts._process_unprocessed_students()
    update_accounts_main=staticmethod(update_accounts_main)

    def _process_unprocessed_students():
        """Unprocessed students didn't match a profile, or didn't get a
        callback at all"""
        # TBD: trenger vi skille p� de?
        logger.info("process_unprocessed_students")

        for fnr, pinfo in persons.items(): 
            if not pinfo.has_student_ac():
                continue
            if not processed_students.has_key(fnr):
                d, p = fodselsnr.del_fnr(fnr)
                BuildAccounts._process_students_callback({
                    'fodselsdato': d,
                    'personnr': p})
    _process_unprocessed_students=staticmethod(_process_unprocessed_students)

class ExistingAccount(object):
    def __init__(self, fnr, expire_date):
        self._affs = []
        self._disk_kvote = {}
        self._expire_date =  expire_date
        self._fnr = fnr
        self._gid = None
        self._groups = []
        self._home = {}
        self._quarantines = []
        self._reserved = False
        self._spreads = []

    def append_affiliation(self, affiliation, ou_id):
        self._affs.append((affiliation, ou_id))

    def get_affiliations(self):
        return self._affs

    def has_affiliation(self, aff_cand):
        return aff_cand in [aff for aff, ou in self._affs]

    def get_disk_kvote(self, homedir_id):
        return self._disk_kvote.get(homedir_id, None)

    def set_disk_kvote(self, homedir_id, quota):
        self._disk_kvote[homedir_id] = quota

    def get_expire_date(self):
        return self._expire_date

    def get_fnr(self):
        return self._fnr

    def get_gid(self):
        return self._gid

    def set_gid(self, gid):
        self._gid = gid

    def append_group(self, group_id):
        self._groups.append(group_id)

    def get_groups(self):
        return self._groups

    def get_home(self, spread):
        return self._home.get(spread, (None, None))

    def get_home_spreads(self):
        return self._home.keys()

    def has_homes(self):
        return len(self._home) > 0

    def set_home(self, spread, disk_id, homedir_id):
        self._home[spread] = (disk_id, homedir_id)

    def append_quarantine(self, q):
        self._quarantines.append(q)

    def get_quarantines(self):
        return self._quarantines
    
    def is_reserved(self):
        return self._reserved

    def set_reserved(self, cond):
        self._reserved = cond

    def append_spread(self, spread):
        self._spreads.append(spread)

    def get_spreads(self):
        return self._spreads
 
class ExistingPerson(object):
    def __init__(self):
        self._affs = []
        self._groups = []
        self._other_ac = []
        self._reserved_ac = []
        self._spreads = []
        self._stud_ac = []

    def append_affiliation(self, affiliation, ou_id, status):
        self._affs.append((affiliation, ou_id, status))

    def get_affiliations(self):
        return self._affs

    def append_group(self, group_id):
        self._groups.append(group_id)

    def get_groups(self):
        return self._groups

    def append_other_ac(self, account_id):
        self._other_ac.append(account_id)

    def has_other_ac(self):
        return len(self._other_ac) > 0

    def append_reserved_ac(self, account_id):
        self._reserved_ac.append(account_id)

    def get_best_reserved_ac(self):
        return self._reserved_ac[0]

    def has_reserved_ac(self):
        return len(self._reserved_ac) > 0

    def append_spread(self, spread):
        self._spreads.append(spread)

    def get_spreads(self):
        return self._spreads

    def append_stud_ac(self, account_id):
        self._stud_ac.append(account_id)

    def get_student_ac(self):
        return self._stud_ac

    def has_student_ac(self):
        return len(self._stud_ac) > 0

def start_process_students(recalc_pq=False, update_create=False):
    global autostud, accounts, persons

    logger.info("process_students started")
    autostud = AutoStud.AutoStud(db, logger, debug=debug, cfg_file=studconfig_file,
                                 studieprogs_file=studieprogs_file,
                                 emne_info_file=emne_info_file,
                                 ou_perspective=ou_perspective)
    logger.info("config processed")
    persons, accounts = get_existing_accounts()
    logger.info("got student accounts")
    if recalc_pq:
        RecalcQuota.recalc_pq_main()
    elif update_create:
        BuildAccounts.update_accounts_main()
    logger.info("process_students finished")


def get_semester():
    import time
    t = time.localtime()[0:2]
    this_year = t[0]
    if t[1] <= 6:
        this_sem = 'v�r'
        next_year = this_year
        next_sem = 'h�st'
    else:
        this_sem = 'h�st'
        next_year = this_year + 1
        next_sem = 'v�r'
    return ((str(this_year), this_sem), (str(next_year), next_sem))


def get_default_expire_date():

    this_sem, next_sem = get_semester()
    sem = this_sem[1]
    if (sem=='v�r'):
        month = 9
    else:        
        month = 2
    year = int(next_sem[0])
    day = 16
    expire_date = datetime.date(year,month,day).isoformat()
    return expire_date



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

    default_expire_date = get_default_expire_date()
    default_shell = const.posix_shell_bash

def get_existing_accounts():
    """Prefetch data about persons and their accounts to avoid
    multiple SQL queries for each callback.  Returns:

    persons = {'fnr': {'affs': [(aff, ou, status)],
                       'stud_ac': [account_id], 'other_ac': [account_id],
                       'reserved_ac': [account_id],
                       'spreads': [spread_id],
                       'groups': [group_id]}}
    accounts = {'account_id': {'owner: fnr, 'reserved': boolean,
                               'gid': group_id, 'quarantines': [quarantine_id],
                               'spreads': [spread_id], 'groups': [group_id],
                               'affs': [(aff, ou)],
                               'expire_date': expire_date,
                               'home': {spread: (disk_id, homedir_id)}}}
    """
    tmp_persons = {}

    logger.info("In get_existing_accounts")
    if fast_test:
        return {}, {}

    logger.info("Listing persons")
    pid2fnr = {}
    for row in person_obj.list_external_ids(id_type=const.externalid_fodselsnr):
        if (row['source_system'] == int(const.system_fs) or
            (not pid2fnr.has_key(int(row['entity_id'])))):
            pid2fnr[int(row['entity_id'])] = row['external_id']
            tmp_persons[row['external_id']] = ExistingPerson()

    for row in person_obj.list_affiliations(
        source_system=const.system_fs,
        affiliation=(const.affiliation_student,const.affiliation_tilknyttet),
        fetchall=False):
        tmp = pid2fnr.get(int(row['person_id']), None)
        if tmp is not None:
            tmp_persons[tmp].append_affiliation(
                int(row['affiliation']), int(row['ou_id']), int(row['status']))

    #
    # Hent ut info om eksisterende og reserverte konti
    #
    logger.info("Listing accounts...")
    tmp_ac = {}
    for row in account_obj.list(filter_expired=False,fetchall=False):
        if not row['owner_id'] or not pid2fnr.has_key(int(row['owner_id'])):
            continue
        tmp_ac[int(row['account_id'])] = ExistingAccount(pid2fnr[int(row['owner_id'])],
                                                           row['expire_date'])
    # PosixGid
    for row in posix_user_obj.list_posix_users():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_gid(int(row['gid']))
    # Reserved users
    for row in account_obj.list_reserved_users(fetchall=False):
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_reserved(True)
    # quarantines
    for row in account_obj.list_entity_quarantines(
        entity_types=const.entity_account):
        tmp = tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_quarantine(int(row['quarantine_type']))
    # Disk kvote
    for row in disk_quota_obj.list_quotas():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_disk_kvote(int(row['homedir_id']), row['quota'])
    # Spreads
    for spread_id in autostud.pc.spread_defs:
        spread = const.Spread(spread_id)
        if spread.entity_type == const.entity_account:
            is_account_spread = True
        elif spread.entity_type == const.entity_person:
            is_account_spread = False
        else:
            logger.warn("Unknown spread type")
            continue
        for row in account_obj.list_all_with_spread(spread_id):
            if is_account_spread:
                tmp = tmp_ac.get(int(row['entity_id']), None)
            else:
                tmp = tmp_persons.get(
                    pid2fnr.get(int(row['entity_id']), None), None)
            if tmp is not None:
                tmp.append_spread(spread_id)
    # Account homes
    for row in account_obj.list_account_home():
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None and row['disk_id']:
            tmp.set_home(int(row['home_spread']), int(row['disk_id']),
                         int(row['homedir_id']))
            
    # Group memberships (TODO: currently only handles union members)
    for group_id in autostud.pc.group_defs.keys():
        group_obj.clear()
        group_obj.find(group_id)
        for row in group_obj.list_members(member_type=const.entity_account)[0]:
            tmp = tmp_ac.get(int(row[1]), None)    # Col 1 is member_id
            if tmp is not None:
                tmp.append_group(group_id)
        for row in group_obj.list_members(member_type=const.entity_person)[0]:
            tmp = tmp_persons.get(int(row[1]), None)    # Col 1 is member_id
            if tmp is not None:
                tmp.append_group(group_id)
    # Affiliations
    for row in account_obj.list_accounts_by_type(
        affiliation=const.affiliation_student, fetchall=False):
        tmp = tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.append_affiliation(int(row['affiliation']), int(row['ou_id']))

    for ac_id, tmp in tmp_ac.items():
        fnr = tmp_ac[ac_id].get_fnr()
        if tmp.is_reserved():
            tmp_persons[fnr].append_reserved_ac(ac_id)
        elif tmp.has_affiliation(int(const.affiliation_student)):
            tmp_persons[fnr].append_stud_ac(ac_id)
        elif tmp_persons[fnr].get_affiliations():
            # get_affiliations() only returns STUDENT affiliations.
            # Accounts on student disks are handled as if they were
            # students if the person has at least one STUDENT
            # affiliation.  The STUDENT affiliation(s) will be added
            # later during this run.
            for s in tmp.get_home_spreads():
                disk_id = tmp.get_home(s)[0]
                if autostud.disk_tool.get_diskdef_by_diskid(disk_id):
                    tmp_persons[fnr].append_stud_ac(ac_id)
                    break
            else:
                tmp_persons[fnr].append_other_ac(ac_id)
        else:
            tmp_persons[fnr].append_other_ac(ac_id)

    logger.info(" found %i persons and %i accounts" % (
        len(tmp_persons), len(tmp_ac)))
    #logger.debug("Persons: \n"+"\n".join([str(y) for y in persons.items()]))
    #logger.debug("Accounts: \n"+"\n".join([str(y) for y in accounts.items()]))
    return tmp_persons, tmp_ac

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
        address = None
        for source, kind in ((const.system_fs, const.address_post),
                             (const.system_fs, const.address_post_private)):
            address = person.get_entity_address(source=source,
                                                    type=kind)
            if address:
                break
        if not address:
            logger.warn("Could not find authoritative address for %s" % account_id)
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

        # First we group letters by 'order_by', default is 'zip'
        brev_profil = all_passwords[account_id][1]
        order_by = 'zip'
        if brev_profil.has_key('order_by'):
            order_by = brev_profil['order_by']
        if not dta.has_key(order_by):
            dta[order_by] = {}
        dta[order_by][account_id] = tpl

    # Do the actual sorting. We end up with one array with account_id's 
    # sorted in groups on sorting criteria.
    sorted_keys = []
    for order in dta.keys():
        keys = dta[order].keys()
        keys.sort(lambda x,y: cmp(dta[order][x][order_by], dta[order][y][order_by]))
        sorted_keys = sorted_keys + keys

    # Each template type has its own letter number sequence
    letter_info = {}
    files = {}
    tpls = {}
    counters = {}
    printers = {}
    for account_id in sorted_keys:
        password, brev_profil = all_passwords[account_id][:2]
        order_by = 'zip'
        if brev_profil.has_key('order_by'):
            order_by = brev_profil['order_by']
        if not dta[order_by][account_id]['zip'] or dta[order_by][account_id]['country']:
            # TODO: Improve this check, which is supposed to skip foreign addresses
            logger.warn("Not sending abroad: %s" % dta[order_by][account_id]['uname'])
            continue
        printer = cereconf.PRINT_PRINTER
        if brev_profil.has_key('printer'):
            printer = brev_profil['printer']
        letter_type = "%s-%s.%s" % (brev_profil['mal'], printer, brev_profil['type'])
        if not files.has_key(letter_type):
            files[letter_type] = file("letter-%i-%s" % (time(), letter_type), "w")
            printers[letter_type] = printer
            tpls[letter_type] = TemplateHandler(
                'no_NO/letter', brev_profil['mal'], brev_profil['type'])
            if tpls[letter_type]._hdr is not None:
                files[letter_type].write(tpls[letter_type]._hdr)
            counters[letter_type] = 1
        if data_file is not None:
            dta[order_by][account_id]['lopenr'] = all_passwords[account_id][2]
            if not os.path.exists("barcode_%s.eps" % account_id):
                make_barcode(account_id)
        else:
            dta[order_by][account_id]['lopenr'] = counters[letter_type]
            letter_info["%s-%i" % (brev_profil['mal'], counters[letter_type])] = \
                                [account_id, [password, brev_profil, counters[letter_type]]]
            # We allways create a barcode file, this is not strictly
            # neccesary
            make_barcode(account_id)
        dta[order_by][account_id]['barcode'] = os.path.realpath('barcode_%s.eps' %  account_id)
        files[letter_type].write(tpls[letter_type].apply_template(
            'body', dta[order_by][account_id], no_quote=('barcode',)))
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
                                        tpls[letter_type]._type,
                                        printers[letter_type],
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
    _filter = {
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
        for f in _filter:
            if info_type == f:
                for dta in person_info[info_type]:
                    ret.setdefault(info_type, []).append(
                        dict([(k, dta[k]) for k in _filter[info_type]]))
        if not ret.has_key(info_type):
            ret[info_type] = person_info[info_type]
    return ret

def _debug_dump_profile_match(profile, fnr):
    # TODO:  H�rer ikke dette hjemme i ProfileHandler?
    # Note that we don't pass current_disk to get_disks() here.
    # Thus this value may differ from the one used during an
    # update
    try:
        dfg = profile.get_dfg()       # dfg is only mandatory for PosixGroups
    except AutoStud.ProfileHandler.NoDefaultGroup:
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
            raise AutoStud.ProfileHandler.NoAvailableDisk(
                "No disk matches profiles")
    else:
        disk = "<no_home>"
    logger.debug("disk=%s, dfg=%s, fg=%s sko=%s" % \
                 (str(disk), dfg,
                  profile.get_grupper(),
                  profile.get_stedkoder()))

def validate_config():
    AutoStud.AutoStud(db, logger, debug=debug, cfg_file=studconfig_file,
                      studieprogs_file=studieprogs_file,
                      emne_info_file=emne_info_file)

def list_noncallback_users(fname):
    """Dump accounts on student-disk that did not get a callback
    resulting in update_account."""

    # TODO: --dryrun currently makes this file useless, since it
    # implies doing no updates, and therefore the file will contain
    # _every_ student.
    if dryrun:
        fname += ".dryrun"

    logger.info("Dumping noncallback users to %s" % fname)
    f = SimilarSizeWriter(fname, 'w')
    f.set_size_change_limit(10)
    on_student_disk = {}
    # TBD: This includes expired accounts, is that what we want?
    for row in account_obj.list_account_home(filter_expired=False):
        if autostud.disk_tool.get_diskdef_by_diskid(int(row['disk_id'])):
            on_student_disk[int(row['account_id'])] = True

    for ac_id in on_student_disk.keys():
        if processed_accounts.has_key(ac_id):
            continue
        f.write("%i\n" % ac_id)
    f.close()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dcus:C:S:e:p:G:',
                                   ['debug', 'create-users', 'update-accounts',
                                    'student-info-file=', 'only-dump-results=',
                                    'studconfig-file=', 'fast-test', 'with-lpr',
                                    'workdir=', 'type=', 'reprint=',
                                    'ou-perspective=',
                                    'emne-info-file=', 'move-users',
                                    'recalc-pq', 'studie-progs-file=',
                                    'paper-file=',
                                    'remove-groupmembers',
                                    'dryrun', 'validate',
                                    'with-quarantines'])
    except getopt.GetoptError, e:
        usage(str(e))
    global debug, fast_test, create_users, update_accounts, logger, skip_lpr
    global student_info_file, studconfig_file, only_dump_to, studieprogs_file, \
           dryrun, emne_info_file, move_users, remove_groupmembers, \
           workdir, paper_money_file, ou_perspective, with_quarantines

    recalc_pq = False
    validate = False
    _range = None
    to_stdout = False
    log_level = AutoStud.Util.ProgressReporter.DEBUG
    non_callback_fname = None
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
        elif opt in ('--with-quarantines',):
            with_quarantines = True
        elif opt in ('--move-users',):
            move_users = True
        elif opt in ('-C', '--studconfig-file'):
            studconfig_file = val
        elif opt in ('-G',):
            non_callback_fname = val
        elif opt in ('--fast-test',):  # Internal debug use ONLY!
            fast_test = True
        elif opt in ('--ou-perspective',):
            ou_perspective = const.OUPerspective(val)
            int(ou_perspective)   # Assert that it is defined
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
            _type = val
        elif opt in ('--reprint',):
            _range = val
            to_stdout = True
        else:
            usage("Unimplemented option: " + opt)

    if recalc_pq and (update_accounts or create_users):
        raise ValueError, "recalc-pq cannot be combined with other operations"

    if workdir is None:
        workdir = "%s/ps-%s.%i" % (cereconf.AUTOADMIN_LOG_DIR,
                                   strftime("%Y-%m-%d", localtime()),
                                   os.getpid())
        os.mkdir(workdir)
    os.chdir(workdir)
    logger = AutoStud.Util.ProgressReporter("%s/process_students.log.%i"
                                            % (workdir, os.getpid()),
                                            stdout=to_stdout,
                                            loglevel=log_level)
    bootstrap()
    if validate:
        validate_config()
        print "The configuration was successfully validated."
        sys.exit(0)
    if _range is not None:
        make_letters("letters.info", type=_type, range=_range)
        return

    if not (recalc_pq or update_accounts or create_users or
            non_callback_fname):
        usage("No action selected")

    start_process_students(recalc_pq=recalc_pq,
                           update_create=(create_users or non_callback_fname))
    if non_callback_fname:
        list_noncallback_users(non_callback_fname)
    
def usage(error=None):
    if error:
        print "Error:", error
    print """Usage: process_students.py
    Actions:
      -c | --create-user : create new users
      -u | --update-accounts : update existing accounts
      --reprint range:  Re-print letters in case of paper-jam etc. (comma
        separated)
      --recalc-pq : recalculate printerquota settings (does not update
        quota).  Cannot be combined with -c/-u
      -G file : Dump account_id for users on student disks that did not
       get a callback.

    Input files:
      -s | --student-info-file file:
      -e | --emne-info-file file:
      -C | --studconfig-file file:
      -S | --studie-progs-file file:
      -p | --paper-file file: check for paid-quota only done if set

    Other settings:
      --only-dump-results file: just dump results with pickle without
        entering make_letters
      --workdir dir:  set workdir for --reprint
      --with-lpr: Spool the file with new user letters to printer

    Action limiters/enablers:
      --remove-groupmembers: remove groupmembers if profile says so
      --move-users: move users if profile says so
      --with-quarantines: Enables quarantine settings

    Misc:
      -d | --debug: increases debug verbosity
      --ou-perspective code_str: set ou_perspective (default: perspective_fs)
      --dryrun: don't do any changes to the database.  This can be used
        to get an idea of what changes a normal run would do.  TODO:
        also dryrun some parts of update/create user.
      --validate: parse the configuration file and report any errors,
        then exit.
      --type type: set type (=the mal attribute to <brev> in studconfig.xml)
        for --reprint

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

    if False:
        print "Profilerer..."
        prof = hotshot.Profile(proffile)
        prof.runcall(main)                # profiler hovedprogrammet
        prof.close()
    else:
        main()

# arch-tag: 99817548-9213-4dc3-8d03-002fc6a2f138
