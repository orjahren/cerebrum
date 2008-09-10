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

import getopt
import sys
import time
import os
import re
import cyruslib

import cerebrum_path
import cereconf

from Cerebrum import Errors
from Cerebrum.modules import Email
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum import Constants
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.errors import CerebrumError
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uio import AutoStud
from Cerebrum.modules.no.uio.AutoStud.Util import AutostudError
from Cerebrum.extlib import logging

db = Factory.get('Database')()
db.cl_init(change_program='process_bofhd_r')
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)
logger = Factory.get_logger("cronjob")

# Hosts to connect to, set to None in a production environment:
debug_hostlist = None
SUDO_CMD = "/usr/bin/sudo"
ldapconn = None
imapconn = None
imaphost = None

# TODO: now that we support multiple homedirs, we need to which one an
# operation is valid for.  This information should be stored in
# state_data, but for e-mail commands this column is already used for
# something else.  The proper solution is to change the databasetable
# and/or letting state_data be pickled.
default_spread = const.spread_uio_nis_user

def email_delivery_stopped(user):
    global ldapconn
    # Delayed import so that the script can be run on machines without
    # the ldap module
    import ldap, ldap.filter, ldap.ldapobject
    if ldapconn is None:
        ldapconn = ldap.ldapobject.ReconnectLDAPObject("ldap://ldap.uio.no/")
        ldapconn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        ldapconn.set_option(ldap.OPT_DEREF, ldap.DEREF_NEVER)
    try:
        res = ldapconn.search_s("ou=mail,dc=uio,dc=no",
                                ldap.SCOPE_ONELEVEL,
                                ("(&(target=%s)(mailPause=TRUE))" %
                                 ldap.filter.escape_filter_chars(user)),
                                ["1.1"])
    except ldap.LDAPError, e:
        logger.error("LDAP search failed: %s", e)
        return False

    return len(res) == 1

def get_email_hardquota(user_id):
    eq = Email.EmailQuota(db)
    try:
        eq.find_by_target_entity(user_id)
    except Errors.NotFoundError:
        return 0	# unlimited/no quota
    return eq.email_quota_hard


def get_imaphost(user_id):
    """
    user_id is entity id of account to look up. Return hostname of
    IMAP server, or None if user's mail is stored in a different
    system.
    """
    em = Email.EmailTarget(db)
    em.find_by_target_entity(user_id)
    server = Email.EmailServer(db)
    server.find(em.get_server_id())
    if server.email_server_type == const.email_server_type_cyrus:
        return server.name
    return None

def get_home(acc, spread=None):
    if not spread:
        spread = default_spread
    return acc.get_homepath(spread)

def add_forward(user_id, addr):
    ef = Email.EmailForward(db)
    ef.find_by_target_entity(user_id)
    # clean up input a little
    if addr.startswith('\\'):
        addr = addr[1:]
    addr = addr.strip()

    if addr.startswith('|') or addr.startswith('"|'):
        logger.warn("forward to pipe ignored: %s", addr)
        return
    elif not addr.count('@'):
        acc = Factory.get('Account')(db)
        try:
            acc.find_by_name(addr)
        except Errors.NotFoundError:
            logger.warn("forward to unknown username: %s", addr)
            return
        addr = acc.get_primary_mailaddress()
    for r in ef.get_forward():
        if r['forward_to'] == addr:
            return
    ef.add_forward(addr)
    ef.write_db()

def connect_cyrus(host=None, user_id=None):
    global imapconn, imaphost
    if host is None:
        assert user_id is not None
        try:
            host = get_imaphost(user_id)
        except:
            raise CerebrumError("connect_cyrus: unknown user " +
                                "(user id = %d)" % user_id)
        if host is None:
            raise CerebrumError("connect_cyrus: not an IMAP user " +
                                "(user id = %d)" % user_id)
    if imapconn is not None:
        if not imaphost == host:
            imapconn.logout()
            imapconn = None
    if imapconn is None:
        imapconn = cyruslib.CYRUS(host = host)
        # TODO: _read_password should moved into Utils or something
        pw = db._read_password(cereconf.CYRUS_HOST, cereconf.CYRUS_ADMIN)
        if imapconn.login(cereconf.CYRUS_ADMIN, pw) is None:
            raise CerebrumError("Connection to IMAP server %s failed" % host)
        imaphost = host
    return imapconn

def dependency_pending(dep_id):
    if not dep_id:
        return False
    br = BofhdRequests(db, const)
    for dr in br.get_requests(request_id=dep_id):
        logger.debug("waiting for request %d" % dep_id)
        return True
    return False

def process_email_requests():
    acc = Factory.get('Account')(db)
    br = BofhdRequests(db, const)
    for r in br.get_requests(operation=const.bofh_email_create):
        logger.debug("Req: email_create %d at %s",
                     r['request_id'], r['run_at'])
        if keep_running() and r['run_at'] < br.now:
            hq = get_email_hardquota(r['entity_id'])
            if (cyrus_create(r['entity_id']) and
                cyrus_set_quota(r['entity_id'], hq)):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_hquota):
        logger.debug("Req: email_hquota %s", r['run_at'])
	if keep_running() and r['run_at'] < br.now:
            hq = get_email_hardquota(r['entity_id'])
            if cyrus_set_quota(r['entity_id'], hq):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_delete):
        logger.debug("Req: email_delete %s", r['run_at'])
	if keep_running() and r['run_at'] < br.now:
	    try:
                acc.clear()
                acc.find(r['entity_id'])
                uname = acc.account_name
            except Errors.NotFoundError:
                logger.error("bofh_email_delete: %d: user not found",
                             r['entity_id'])
                br.delay_request(request_id=r['request_id'])
                db.commit()
                continue
            
            # The database contains the new host, so the id of the server
            # to remove from is passed in state_data.
            server = Email.EmailServer(db)
            try:
                server.find(r['state_data'])
            except Errors.NotFoundError:
                logger.error("bofh_email_delete: %d: target server not found",
                             r['state_data'])
                br.delay_request(request_id=r['request_id'])
                db.commit()
                continue
            if cyrus_delete(server.name, uname):
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_move):
        logger.debug("Req: email_move %s %d", r['run_at'], int(r['state_data']))
	if keep_running() and r['run_at'] < br.now:
            # state_data is a request-id which must complete first,
            # typically an email_create request.
            logger.debug("email_move %d, state is %r" % \
                         (r['entity_id'], r['state_data']))
            if dependency_pending(r['state_data']):
                br.delay_request(r['request_id'])
                continue 
	    try:
                acc.clear()
                acc.find(r['entity_id'])
            except Errors.NotFoundError:
                logger.error("email_move: user %d not found", r['entity_id'])
                continue
            et = Email.EmailTarget(db)
            et.find_by_target_entity(r['entity_id'])
            old_server = r['destination_id']
            new_server = et.get_server_id()
            if old_server == new_server:
                logger.error("trying to move %s from and to the same server!",
                             acc.account_name)
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue
            if not email_delivery_stopped(acc.account_name):
                logger.debug("E-mail delivery not stopped for %s",
                             acc.account_name)
                db.rollback()
                br.delay_request(r['request_id'])
                db.commit()
                continue
            if move_email(r['entity_id'], r['requestee_id'],
                          old_server, new_server):
                br.delete_request(request_id=r['request_id'])
                es = Email.EmailServer(db)
                es.find(old_server)
                if es.email_server_type == const.email_server_type_nfsmbox:
                    br.add_request(r['requestee_id'], r['run_at'],
                                   const.bofh_email_convert,
                                   r['entity_id'], old_server)
                elif es.email_server_type == const.email_server_type_cyrus:
                    br.add_request(r['requestee_id'], r['run_at'],
                                   const.bofh_email_delete,
                                   r['entity_id'], None,
                                   state_data=old_server)
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()

    for r in br.get_requests(operation=const.bofh_email_convert):
        logger.debug("Req: email_convert %s", r['run_at'])
	if keep_running() and r['run_at'] < br.now:
            user_id = r['entity_id']
            try:
                acc.clear()
                acc.find(user_id)
            except Errors.NotFoundErrors:
                logger.error("bofh_email_convert: %d not found" % user_id)
                continue
            try:
                posix = PosixUser.PosixUser(db)
                posix.find(user_id)
            except Errors.NotFoundErrors:
                logger.debug("bofh_email_convert: %s: " % acc.account_name +
                             "not a PosixUser, skipping e-mail conversion")
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue

            try:
                posix_group = PosixGroup.PosixGroup(db)
                posix_group.find(posix.gid_id)
            except Errors.NotFoundErrors:
                logger.debug("bofh_email_convert: %s: " % acc.account_name +
                             "missing primary fg, skipping")
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue

            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'convertmail',
                   acc.account_name, get_home(acc),
                   posix.posix_uid, posix_group.posix_gid]
            cmd = ["%s" % x for x in cmd]
            unsafe = False
            for word in cmd:
                if not re.match("^[A-Za-z0-9./_-]*$", word):
                    unsafe = True
            if unsafe:
                logger.error("possible unsafe invocation to popen: %s", cmd)
                continue

            try:
                fd = os.popen(" ".join(cmd))
            except:
                logger.error("bofh_email_convert: %s: " % acc.account_name +
                             "running %s failed" % cmd)
                continue
            success = True
            try:
                subsep = '\034'
                for line in fd.readlines():
                    if line.endswith('\n'):
                        line = line[:-1]
                    logger.debug("email_convert: %s", repr(line))
                    if line.startswith("forward: "):
                        for addr in [t.split(subsep)
                                     for t in line.split(": ")][1]:
                            add_forward(user_id, addr)
                    elif line.startswith("forward+local: "):
                        add_forward(user_id, acc.get_primary_mailaddress())
                        for addr in [t.split(subsep)
                                     for t in line.split(": ")][1]:
                            add_forward(user_id, addr)
                    elif line.startswith("tripnote: "):
                        msg = "\n".join([t.split(subsep)
                                         for t in line.split(": ")][1])
                        vac = Email.EmailVacation(db)
                        vac.find_by_target_entity(user_id)
                        # if there's a message imported from ~/tripnote
                        # already, get rid of it -- this message will
                        # be the same or fresher.
                        start = db.Date(1970, 1, 1)
                        for v in vac.get_vacation():
                            if v['start_date'] == start:
                                vac.delete_vacation(start)
                        vac.add_vacation(start, msg, enable='T')
                    else:
                        logger.error("%s: convertmail reported: %s\n",
                                     acc.account_name, line)
            except Exception, e:
                    db.rollback()
                    # TODO better diagnostics
                    success = False
                    logger.error("%s: convertmail failed: %s (%s)",
                                 acc.account_name, repr(e), e)
            if success:
                br.delete_request(request_id=r['request_id'])
            else:
                db.rollback()
                br.delay_request(r['request_id'])
            db.commit()
        
def cyrus_create(user_id):
    try:
        uname = get_username(user_id)
    except Errors.NotFoundError:
        logger.error("cyrus_create: %d not found", user_id)
        return False
    assert uname is not None
    try:
        cyradm = connect_cyrus(user_id = user_id)
    except CerebrumError, e:
        logger.error("cyrus_create: " + str(e))
        return False
    for sub in ("", ".spam", ".Sent", ".Drafts", ".Trash"):
        res, list = cyradm.m.list ('user.', pattern='%s%s' % (uname, sub))
        if res == 'OK' and list[0]:
            continue
        res = cyradm.m.create('user.%s%s' % (uname, sub))
        if res[0] <> 'OK':
            logger.error("IMAP create user.%s%s failed: %s",
                         uname, sub, res[1])
            return False
    # we don't care to check if the next command runs OK.
    # almost all IMAP clients ignore the file, anyway ...
    cyrus_subscribe(uname, imaphost)
    return True

def cyrus_delete(host, uname):
    logger.debug("will delete %s from %s", uname, host)
    try:
        cyradm = connect_cyrus(host=host)
    except CerebrumError, e:
        logger.error("bofh_email_delete: %s: %s" % (host, e))
        return False
    res, list = cyradm.m.list("user.", pattern=uname)
    if res <> 'OK' or list[0] == None:
        # TBD: is this an error we need to keep around?
        db.rollback()
        logger.error("bofh_email_delete: %s: no mailboxes", uname)
        return False
    folders = ["user.%s" % uname]
    res, list = cyradm.m.list("user.%s." % uname)
    if res == 'OK' and list[0]:
        for line in list:
            m = re.match(r'^\(.*?\) ".*?" "(.*)"$', line)
            folders += [ m.group(1) ]
    # Make sure the subfolders are deleted first by reversing
    # the sorted list.
    folders.sort()
    folders.reverse()
    allok = True
    for folder in folders:
        logger.debug("deleting %s ... ", folder)
        cyradm.m.setacl(folder, cereconf.CYRUS_ADMIN, 'c')
        res = cyradm.m.delete(folder)
        if res[0] <> 'OK':
            logger.error("IMAP delete %s failed: %s", folder, res[1])
            return False
    cyrus_subscribe(uname, host, action="delete")
    return True

def cyrus_set_quota(user_id, hq):
    try:
        uname = get_username(user_id)
    except Errors.NotFoundError:
        logger.error("cyrus_set_quota: %d: user not found", user_id)
        return False
    try:
        cyradm = connect_cyrus(user_id = user_id)
    except CerebrumError, e:
        logger.error("cyrus_set_quota(%s, %d): %s" % (uname, hq, e))
        return False
    res, msg = cyradm.m.setquota("user.%s" % uname, 'STORAGE', hq * 1024)
    logger.debug("cyrus_set_quota(%s, %d): %s" % (uname, hq, repr(res)))
    return res == 'OK'

def cyrus_subscribe(uname, server, action="create"):
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'subscribeimap',
           action, server, uname];
    cmd = ["%s" % x for x in cmd]
    if debug_hostlist is None or old_host in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    else:
        errnum = 0
    if not errnum:
        return True
    logger.error("%s returned %i", cmd, errnum)
    return False

def move_email(user_id, mailto_id, from_host, to_host):
    acc = Factory.get("Account")(db)
    # bofh_move_email requests that are "magically" added by giving a
    # user spread 'spread_uio_imap' will have mailto_id == None.
    mailto = ""
    if mailto_id is not None:
        try:
            acc.find(mailto_id)
        except Errors.NotFoundError:
            logger.error("move_email: operator %d not found" % mailto_id)
            return False
        try:
            mailto = acc.get_primary_mailaddress()
        except Errors.NotFoundError:
            mailto = ""
    try:
        acc.clear()
        acc.find(user_id)
    except Errors.NotFoundError:
        logger.error("move_email: %d not found" % user_id)
        return False

    es_to = Email.EmailServer(db)
    es_to.find(to_host)
    type_to = int(es_to.email_server_type)
    
    es_fr = Email.EmailServer(db)
    es_fr.find(from_host)
    type_fr = int(es_fr.email_server_type)

    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'mvmail',
           acc.account_name, get_home(acc),
           mailto, get_email_hardquota(user_id),
           es_fr.name, str(Email._EmailServerTypeCode(type_fr)),
           es_to.name, str(Email._EmailServerTypeCode(type_to))]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    EXIT_SUCCESS = 0
    EXIT_LOCKED = 101
    EXIT_NOTIMPL = 102
    EXIT_QUOTAEXCEEDED = 103
    EXIT_FAILED = 104
    errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    if errnum == EXIT_QUOTAEXCEEDED:
        # TODO: bump quota, or something else
        pass
    elif errnum == EXIT_SUCCESS:
        pass
    else:
        logger.error('mvmail failed, returned %d' % errnum)
        return False
    if es_fr.email_server_type == const.email_server_type_cyrus:
        return cyrus_delete(es_fr.name, acc.account_name)
    return True

def process_mailman_requests():
    acc = Factory.get('Account')(db)
    br = BofhdRequests(db, const)
    for r in br.get_requests(operation=const.bofh_mailman_create):
        logger.debug("Req: mailman_create %d at %s",
                     r['request_id'], r['run_at'])
        if keep_running() and r['run_at'] < br.now:
            try:
                listname = get_address(r['entity_id'])
            except Errors.NotFoundError:
                logger.warn("List address %s deleted!  It probably wasn't "+
                            "needed anyway.", listname)
                br.delete_request(request_id=r['request_id'])
                continue
            try:
                admin = get_address(r['destination_id'])
            except Errors.NotFoundError:
                logger.error("Admin address deleted for %s!  Ask postmaster "+
                             "to create list manually.", listname)
                br.delete_request(request_id=r['request_id'])
                continue
            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c',
                   'mailman', 'newlist', listname, admin ];
            logger.debug(repr(cmd))
            errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
            logger.debug("returned %d", errnum)
            if errnum == 0:
                logger.debug("delete %d", r['request_id'])
                br.delete_request(request_id=r['request_id'])
                db.commit()
            else:
                logger.error("bofh_mailman_create: %s: returned %d" %
                             (listname, errnum))
                br.delay_request(r['request_id'])
    for r in br.get_requests(operation=const.bofh_mailman_add_admin):
        logger.debug("Req: mailman_add_admin %d at %s",
                     r['request_id'], r['run_at'])
        if keep_running() and r['run_at'] < br.now:
            if dependency_pending(r['state_data']):
                br.delay_request(r['request_id'])
                continue 
            listname = get_address(r['entity_id'])
            admin = get_address(r['destination_id'])
            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c',
                   'mailman', 'add_admin', listname, admin ];
            errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
            if errnum == 0:
                br.delete_request(request_id=r['request_id'])
                db.commit()
            else:
                logger.error("bofh_mailman_admin_add: %s: returned %d" %
                             (listname, errnum))
                br.delay_request(r['request_id'])
    for r in br.get_requests(operation=const.bofh_mailman_remove):
        logger.debug("Req: mailman_remove %d at %s",
                     r['request_id'], r['run_at'])
        if keep_running() and r['run_at'] < br.now:
            listname = r['state_data']
            cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c',
                   'mailman', 'rmlist', listname, "dummy" ];
            errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
            if errnum == 0:
                br.delete_request(request_id=r['request_id'])
                db.commit()
            else:
                logger.error("bofh_mailman_remove: %s: returned %d" %
                             (listname, errnum))
                br.delay_request(r['request_id'])

def get_address(address_id):
    ea = Email.EmailAddress(db)
    ea.find(address_id)
    ed = Email.EmailDomain(db)
    ed.find(ea.email_addr_domain_id)
    return "%s@%s" % (ea.email_addr_local_part,
                      ed.rewrite_special_domains(ed.email_domain_name))

def is_ok_batch_time(now):
    times = cereconf.LEGAL_BATCH_MOVE_TIMES.split('-')
    if times[0] > times[1]:   #  Like '20:00-08:00'
        if now > times[0] or now < times[1]:
            return True
    else:                     #  Like '08:00-20:00'
        if now > times[0] and now < times[1]:
            return True
    return False

def process_move_requests():
    br = BofhdRequests(db, const)
    requests = br.get_requests(operation=const.bofh_move_user_now)
    if is_ok_batch_time(time.strftime("%H:%M")):
        process_move_student_requests() # generates bofh_move_user requests
        requests.extend(br.get_requests(operation=const.bofh_move_user))    
    for r in requests:
        if keep_running() and r['run_at'] < br.now:
            logger.debug("Req %d: bofh_move_user %d",
                         r['request_id'], r['entity_id'])
            try:
                account, uname, old_host, old_disk = get_account(
                    r['entity_id'], type='PosixUser', spread=r['state_data'])
                new_host, new_disk  = get_disk(r['destination_id'])
            except Errors.NotFoundError:
                logger.error("move_request: user %i not found" % r['entity_id'])
                continue
            if account.is_expired():
                logger.warn("Account %s is expired, cancelling request" %
                            account.account_name)
                br.delete_request(request_id=r['request_id'])
                db.commit()
                continue
            try:
                operator = get_account(r['requestee_id'])[0].account_name
            except Errors.NotFoundError:
                # The mvuser script requires a valid address here.  We
                # may want to change this later.
                operator = "cerebrum"
            group = get_group(account.gid_id, grtype='PosixGroup')

            spread = ",".join(["%s" % Constants._SpreadCode(int(a['spread']))
                               for a in account.get_spread()]),
            if get_imaphost(r['entity_id']) == None:
                spool = '1'
            else:
                spool = '0'
            if move_user(uname, int(account.posix_uid), int(group.posix_gid),
                         old_host, old_disk, new_host, new_disk, spread,
                         operator, spool):
                logger.debug('user %s moved from %s to %s' %
                             (uname,old_disk,new_disk))
                account.set_home(default_spread, disk_id = r['destination_id'],
                                 status=const.home_status_on_disk)
                account.write_db()
                br.delete_request(request_id=r['request_id'])
            else:
                if new_disk == old_disk:
                    br.delete_request(request_id=r['request_id'])
                else:
                    br.delay_request(r['request_id'], minutes=24*60)
            db.commit()

def process_move_student_requests():
    global fnr2move_student, autostud
    br = BofhdRequests(db, const)
    rows = br.get_requests(operation=const.bofh_move_student)
    if not rows:
        return
    logger.debug("Preparing autostud framework")
    autostud = AutoStud.AutoStud(db, logger, debug=False,
                                 cfg_file=studconfig_file,
                                 studieprogs_file=studieprogs_file,
                                 emne_info_file=emne_info_file,
                                 ou_perspective=ou_perspective)

    # Hent ut personens fødselsnummer + account_id
    fnr2move_student = {}
    account = Factory.get('Account')(db)
    person = Factory.get('Person')(db)
    for r in rows:
        account.clear()
        account.find(r['entity_id'])
        person.clear()
        person.find(account.owner_id)
        fnr = person.get_external_id(id_type=const.externalid_fodselsnr,
                                     source_system=const.system_fs)
        if not fnr:
            logger.warn("Not student fnr for: %i" % account.entity_id)
            br.delete_request(request_id=r['request_id'])
            db.commit()
            continue
        fnr = fnr[0]['external_id']
        if not fnr2move_student.has_key(fnr):
            fnr2move_student[fnr] = []
        fnr2move_student[fnr].append((
            int(account.entity_id), int(r['request_id']),
            int(r['requestee_id'])))
    logger.debug("Starting callbacks to find: %s" % fnr2move_student)
    autostud.start_student_callbacks(
        student_info_file, move_student_callback)

    # Move remaining users to pending disk
    disk = Factory.get('Disk')(db)
    disk.find_by_path(cereconf.AUTOSTUD_PENDING_DISK)
    logger.debug(str(fnr2move_student.values()))
    for tmp_stud in fnr2move_student.values():
        for account_id, request_id, requestee_id in tmp_stud:
            br.delete_request(request_id=request_id)
            br.add_request(requestee_id, br.batch_time,
                           const.bofh_move_user,
                           account_id, disk.entity_id,
                           state_data=int(default_spread))
            db.commit()

def move_student_callback(person_info):
    """We will only move the student if it has a valid fnr from FS,
    and it is not currently on a student disk.

    If the new homedir cannot be determined, user will be moved to a
    pending disk.  process_students moves users from this disk as soon
    as a proper disk can be determined.

    Currently we only operate on the disk whose spread is
    default_spread"""

    fnr = fodselsnr.personnr_ok("%06d%05d" % (int(person_info['fodselsdato']),
                                              int(person_info['personnr'])))
    if not fnr2move_student.has_key(fnr):
        return
    logger.debug("Callback for %s" % fnr)
    account = Factory.get('Account')(db)
    group = Factory.get('Group')(db)
    for account_id, request_id, requestee_id in fnr2move_student.get(fnr, []):
        account.clear()
        account.find(account_id)
        groups = list(int(x["group_id"]) for x in
                      group.search(member_id=account_id,
                                   indirect_members=False))
        try:
            profile = autostud.get_profile(person_info, member_groups=groups)
        except AutostudError, msg:
            logger.debug("Error getting profile, using pending: %s" % msg)
            continue

        # Determine disk
        disks = []
        spreads = [int(s) for s in profile.get_spreads()]
        try:
            for d_spread in profile.get_disk_spreads():
                if d_spread != default_spread:
                    # TBD:  How can all spreads be taken into account?
                    continue
                if d_spread in spreads:
                    try:
                        current_disk_id = account.get_home(d_spread)['disk_id']
                    except Errors.NotFoundError:
                        current_disk_id = None
                    if autostud.student_disk.has_key(int(current_disk_id)):
                        logger.debug("Already on a student disk")
                        raise "NextAccount"
                    try:
                        disks.append(
                            (profile.get_disk(d_spread, current_disk_id),
                             d_spread))
                    except AutostudError, msg:
                        # Will end up on pending (since we only use one spread)
                        logger.debug("Error getting disk: %s" % msg)
                        break
        except "NextAccount":
            pass   # Stupid python don't have labeled breaks
        logger.debug(str((fnr, account_id, disks)))
        if disks:
            del(fnr2move_student[fnr])
            br = BofhdRequests(db, const)
            for disk, spread in disks:
                br.delete_request(request_id=request_id)
                br.add_request(requestee_id, br.batch_time,
                               const.bofh_move_user,
                               account_id, disk, state_data=spread)
                db.commit()

def process_delete_requests():
    br = BofhdRequests(db, const)
    group = Factory.get('Group')(db)
    for r in br.get_requests(operation=const.bofh_delete_user):
        if not keep_running():
            break
        if r['run_at'] > br.now:
            continue
        spread = default_spread
        is_posix = False
        try:
            account, uname, old_host, old_disk = get_account(
                r['entity_id'], spread=spread, type='PosixUser')
            is_posix = True
        except Errors.NotFoundError:
            account, uname, old_host, old_disk = get_account(
                r['entity_id'], spread=spread)
        if account.is_deleted():
            logger.warn("%s is already deleted" % uname)
            br.delete_request(request_id=r['request_id'])
            db.commit()
            continue
        operator = get_account(r['requestee_id'])[0].account_name
        et = Email.EmailTarget(db)
        try:
            et.find_by_target_entity(account.entity_id)
            es = Email.EmailServer(db)
            es.find(et.email_server_id)
            mail_server = es.name
        except Errors.NotFoundError:
            mail_server = ''

        if delete_user(uname, old_host, '%s/%s' % (old_disk, uname), operator,
                       mail_server):
            if is_posix:
                # demote the user first to avoid problems with
                # PosixUsers with names illegal for PosixUsers
                account.delete_posixuser()
                id = account.entity_id
                account = Factory.get('Account')(db)
                account.find(id)
            account.expire_date = br.now
            account.write_db()
            home = account.get_home(spread)
            account.set_home(spread, disk_id=home['disk_id'], home=home['home'],
                             status=const.home_status_archived)
            # Remove references in other tables
            # Note that we preserve the quarantines for deleted users
            # TBD: Should we have an API function for this?
            for s in account.get_spread():
                account.delete_spread(s['spread'])
            for g in group.search(member_id=account.entity_id,
                                  indirect_members=False):
                group.clear()
                group.find(g['group_id'])
                group.remove_member(account.entity_id)
            br.delete_request(request_id=r['request_id'])
            db.commit()
        else:
            db.rollback()
            br.delay_request(r['request_id'], minutes=120)
            db.commit()

def delete_user(uname, old_host, old_home, operator, mail_server):
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'aruser', uname,
           operator, old_home, mail_server]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    if debug_hostlist is None or old_host in debug_hostlist:
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logger.error("%s returned %i" % (cmd, errnum))
    return 0

def move_user(uname, uid, gid, old_host, old_disk, new_host, new_disk, spread,
              operator, spool):
    mailto = operator
    cmd = [SUDO_CMD, cereconf.WRAPPER_CMD, '-c', 'mvuser', uname, uid, gid,
           old_disk, new_disk, spread, mailto, spool]
    cmd = ["%s" % x for x in cmd]
    logger.debug("doing %s" % cmd)
    if debug_hostlist is None or (old_host in debug_hostlist and
                                  new_host in debug_hostlist):
        errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
    else:
        errnum = 0
    if not errnum:
        return 1
    logger.error("%s returned %i" % (cmd, errnum))
    return 0

def get_disk(disk_id):
    disk = Factory.get('Disk')(db)
    disk.clear()
    disk.find(disk_id)
    host = Factory.get('Host')(db)
    host.clear()
    host.find(disk.host_id)
    return host.name, disk.path

def get_account(account_id, type='Account', spread=None):
    if type == 'Account':
        account = Factory.get('Account')(db)
    elif type == 'PosixUser':
        account = PosixUser.PosixUser(db)        
    account.clear()
    account.find(account_id)
    if spread is None:
        spread = default_spread
    home = account.get_home(spread)
    uname = account.account_name
    if home['home'] is None:
        if home['disk_id'] is None:
            return account, uname, None, None
        host, home = get_disk(home['disk_id'])
    else:
        host = None  # TODO:  How should we handle this?
    return account, uname, host, home

def get_username(account_id):
    account = Factory.get('Account')(db)
    account.find(account_id)
    return account.account_name

def get_group(id, grtype="Group"):
    if grtype == "Group":
        group = Factory.get('Group')(db)
    elif grtype == "PosixGroup":
        group = PosixGroup.PosixGroup(db)
    group.clear()
    group.find(id)
    return group

def keep_running():
    # If we've run for more than half an hour, it's time to go on to
    # the next task.  This check is necessary since job_runner is
    # single-threaded, and so this job will block LDAP updates
    # etc. while it is running.
    global max_requests
    max_requests -= 1
    if max_requests < 0:
        return False
    return time.time() - start_time < 15 * 60

def main():
    global start_time, max_requests
    global ou_perspective, emne_info_file, studconfig_file, \
           studieprogs_file, student_info_file
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'dpt:m:',
                                   ['debug', 'process', 'type=', 'max=',
                                    'ou-perspective=',
                                    'emne-info-file=','studconfig-file=',
                                    'studie-progs-file=',
                                    'student-info-file='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    types = []
    max_requests = 999999
    ou_perspective = None
    for opt, val in opts:
        if opt in ('-d', '--debug'):
            print "debug mode has not been implemented"
            sys.exit(1)
        elif opt in ('-t', '--type',):
            types.append(val)
        elif opt in ('-m', '--max',):
            max_requests = int(val)
        elif opt in ('-p', '--process'):
            if not types:
                types = ['delete', 'move', 'email', 'mailman']
            # We set start_time for each type of requests, so that a
            # lot of home directory moves won't stop e-mail requests
            # from being processed in a timely manner.
            for t in types:
                start_time = time.time()
                func = globals()["process_%s_requests" % t]
                apply(func)
        elif opt in ('--ou-perspective',):
            ou_perspective = const.OUPerspective(val)
            int(ou_perspective)   # Assert that it is defined
        elif opt in ('--emne-info-file',):
            emne_info_file = val
        elif opt in ('--studconfig-file',):
            studconfig_file = val
        elif opt in ('--studie-progs-file',):
            studieprogs_file = val
        elif opt in ('--student-info-file',):
            student_info_file = val

def usage(exitcode=0):
    print """Usage: process_bofhd_requests.py
    -d | --debug: turn on debugging
    -p | --process: perform the queued operations
    -t | --type type: performe queued operations of this type.  May be
         repeated, and must be preceeded by -p
    -m | --max val: perform up to this number of requests

    Needed for move_student requests:
    --ou-perspective code_str: set ou_perspective (default: perspective_fs)
    --emne-info-file file:
    --studconfig-file file:
    --studie-progs-file file:
    --student-info-file file:
    """
    sys.exit(exitcode)

if __name__ == '__main__':
    main()

# arch-tag: 2ba33743-c745-4251-b4c8-54cea60e1cb8
