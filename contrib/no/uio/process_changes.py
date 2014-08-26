#!/usr/bin/env python
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

# This script should be run regularly.  It processes the changelog,
# and performs a number of tasks:
#
# - when a user has been created: create users homedir
# - when a guest user's home has been archived: make a new home directory

# TBD: If this script is only going to be used for creating users, it
# should probably be renamed.  There are already other scrits, like
# nt/notes sync that process the changelog themselves.  We need to
# determine wheter it is a good idea to have multiple small scripts
# doing this, or if there is an advantage into merging all of them
# into a bigger script, perhaps with some plugin-like structure for
# subscribing to certain event types.

import os
import sys
import getopt
import pickle

import cerebrum_path
import cereconf
from Cerebrum.extlib import logging
from Cerebrum.modules import CLHandler
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.Entity import EntityQuarantine
from Cerebrum.modules import PosixGroup
from Cerebrum.modules.bofhd.utils import BofhdRequests

logger = Factory.get_logger("cronjob")
db = Factory.get('Database')()
db.cl_init(change_program="process_changes")
cl_const = Factory.get('CLConstants')(db)
const = Factory.get('Constants')(db)
posix_user = Factory.get('PosixUser')(db)
posix_group = PosixGroup.PosixGroup(db)
host = Factory.get('Host')(db)
disk = Factory.get('Disk')(db)
debug_hostlist = None

SUDO_CMD = "sudo"
SSH_CEREBELLUM = ["/local/bin/ssh", "cerebrum@cerebellum"]


class EvtHandler(object):
    """Abstract parent class for event handlers.  Currently it only
    defines the default evt_key to use.

    Subclasses should implement get_triggers and one or more notify
    methods.

    Note: Users should be careful about having multiple classes
    listening for the same event with the same evt_key.  If so, all
    classes must confirm the event before it is removed.  TBD: should
    we even allow it?
    """

    evt_key = 'uio_ch'

    def get_triggers(self):
        """This method returns a list of strings representing the
        events in the changelog that we want callbacks for.  The
        string should be the name of a constant in CLConstants, and
        the corresponding callback method should be named
        notify_<string>
        """
        raise NotImplementedError

    def notify_example(self, evt, params):
        """Callbackmethod called when an event of type
        CLConstants.example is found in the changelog.  evt is a
        db_row from the changelog.  params is a depickled
        change_params.  The method should return True uppon success."""

        raise NotImplementedError

class MakeUser(EvtHandler):
    # TODO: change if we decide to allow different homedirs for same user
    home_spread = const.spread_uio_nis_user   

    def get_triggers(self):
        return ("account_home_added", "homedir_update")

    def notify_account_home_added(self, evt, params):
        if params.get('spread', 0) == int(self.home_spread):
            logger.debug("Creating entity_id=%s" % (evt.fields.subject_entity))
            try:
                if self._make_user(evt['subject_entity']):
                    status = const.home_status_on_disk
                else:
                    status = const.home_status_create_failed
            except Errors.NotFoundError:
                return True # A reserved user or similar that don't get a homedir
            # posix_user was set by get_make_user_data
            home = posix_user.get_home(self.home_spread)
            posix_user.set_homedir(current_id=home['homedir_id'],
                                   status=status)
            db.commit()
        return True

    def notify_homedir_update(self, evt, params):
        acc = Factory.get("Account")(db)
        try:
            x, accid, x, x, status = acc.get_homedir(params['homedir_id'])
        except Errors.NotFoundError:
            # Ancient changelog entry?  Skip it.
            logger.debug("Skipping deleted homedir %d for account %d",
                         params['homedir_id'], evt['subject_entity'])
            return True
        if accid != evt['subject_entity']:
            logger.error("Homedir %d doesn't belong to account %d",
                         params['homedir_id'], evt['subject_entity'])
            return True
        acc.find(accid)
        guest_trait = acc.get_trait(const.trait_uio_guest_owner)
        if (guest_trait and status == const.home_status_archived and
            not acc.is_expired()):
            logger.debug("Creating fresh home directory for guest %d" % accid)
            if not self._make_user(evt['subject_entity']):
                return False
            logger.debug("Successfully created home %d" % params['homedir_id'])
            acc.set_homedir(current_id=params['homedir_id'],
                            status=const.home_status_on_disk)
            db.commit()
        return True

    def _get_make_user_data(self, entity_id):
        posix_user.clear()
        posix_user.find(entity_id)
        posix_group.clear()
        posix_group.find(posix_user.gid_id)
        disk.clear()
        home = posix_user.get_home(self.home_spread)
        homedir = posix_user.get_posix_home(self.home_spread)
        disk.find(home['disk_id'])
        host.clear()
        host.find(disk.host_id)

        return {'uname': posix_user.account_name,
                'home': posix_user.get_posix_home(self.home_spread),
                'uid': str(posix_user.posix_uid),
                'gid': str(posix_group.posix_gid),
                'gecos': posix_user.get_gecos(),
                'host': host.name,
                'home': home,
                'homedir': homedir}

    def _make_user(self, entity_id):
        try:
            info = self._get_make_user_data(entity_id)
        except Errors.NotFoundError:
            logger.warn("NotFound error for entity_id %s" % entity_id, exc_info=1)
            raise
        if int(info['home']['status']) == const.home_status_on_disk:
            logger.warn("User already on disk? %s" % entity_id)
            return
        if info['homedir'] is None:
            logger.warn("No home for %s" % entity_id)
            return

        args = [SUDO_CMD, cereconf.CREATE_USER_SCRIPT,
               # info['host'],  # the mkhome script figures out the host
               info['uname'], info['homedir'], info['uid'], info['gid'],
               '"' + info['gecos'] + '"']

        to_exec = " ".join(args)
        cmd = SSH_CEREBELLUM + [to_exec,]
        #cmd = cmd[1:]  # DEBUG

        logger.debug("Doing: %s" % str(cmd))
        if debug_hostlist is None or info['host'] in debug_hostlist:
            errnum = os.spawnv(os.P_WAIT, cmd[0], cmd)
        else:
            errnum = 0
        if not errnum:
            return 1
        logger.error("%s returned %i" % (cmd, errnum))
        return 0

class Quarantine2Request(EvtHandler):
    """When a quarantine has been added/updated/deleted, we register a
    bofh_quarantine_refresh bofhd_request on the apropriate
    start_date, end_date and disable_until dates.
    """
    
    def __init__(self):
        self.br = BofhdRequests(db, const)
        self.eq = EntityQuarantine(db)

    def get_triggers(self):
        return ("quarantine_add", "quarantine_mod", "quarantine_del")

    def _get_quarantine(self, entity_id, q_type):
        self.eq.clear()
        try:
            self.eq.find(entity_id)
        except Errors.NotFoundError:
            return None
        qdata = self.eq.get_entity_quarantine(q_type)
        if not qdata:
            return None
        return qdata[0]

    def notify_quarantine_add(self, evt, params):
        # Register a bofh_quarantine_refresh on start, end and
        # disable_date
        qdata = self._get_quarantine(evt['subject_entity'], params['q_type'])
        if not qdata:
            return True
        for when in ('start_date', 'end_date', 'disable_until'):
            if qdata[when] is not None:
                self.br.add_request(None, qdata[when] ,
                                    const.bofh_quarantine_refresh,
                                    evt['subject_entity'], None,
                                    state_data=int(params['q_type']))
            db.commit()
        return True
    
    def notify_quarantine_mod(self, evt, params):
        # Currently only disable_until is affected by quarantine_mod.
        qdata = self._get_quarantine(evt['subject_entity'], params['q_type'])
        if not qdata:
            return True
        if qdata['disable_until']:
            self.br.add_request(None, qdata['disable_until'],
                                const.bofh_quarantine_refresh,
                                evt['subject_entity'], None,
                                state_data=int(params['q_type']))
            
        self.br.add_request(None, self.br.now, const.bofh_quarantine_refresh,
                            evt['subject_entity'], None,
                            state_data=int(params['q_type']))
        db.commit()
        return True
    
    def notify_quarantine_del(self, evt, params):
        # Remove existing requests for this entity_id/quarantine_type
        # combination as they are no longer needed
        for row in self.br.get_requests(entity_id=evt['subject_entity'],
                                        operation=int(const.bofh_quarantine_refresh)):
            if int(row['state_data']) == int(params['q_type']):
                self.br.delete_request(request_id=row['request_id'])
        self.br.add_request(None, self.br.now, const.bofh_quarantine_refresh,
                            evt['subject_entity'], None,
                            state_data=int(params['q_type']))
        db.commit()
        return True

def process_changelog(evt_key, classes):
    """Process the entries from changelog identifying previous events
    by evt_key, and using events and callback methods in classes
    """
    
    evt_id2call_back = {}
    for c in classes:
        for t in c.get_triggers():
            evt_id2call_back.setdefault(int(getattr(cl_const, t)), []).append(
                getattr(c, "notify_%s" % t))
        
    ei = CLHandler.CLHandler(Factory.get('Database')())
    for evt in ei.get_events(evt_key, evt_id2call_back.keys()):
        ok = []
        for call_back in evt_id2call_back[int(evt.fields.change_type_id)]:
            if evt['change_params']:
                params = pickle.loads(evt['change_params'])
            else:
                params = {}
            logger.debug2("Callback %i -> %s" % (evt['change_id'], call_back))
            ok.append(call_back(evt, params))
        # Only confirm if all call_backs returned true
        if not filter(lambda t: t == False, ok):
            ei.confirm_event(evt)
    ei.commit_confirmations()

def process_changes():
    classes = (MakeUser(), Quarantine2Request())
    keys = dict([(c.evt_key, None) for c in classes]).keys()
    for k in keys:
        process_changelog(k, filter(lambda c: c.evt_key == k, classes))

def usage(exitcode=0):
    print """process_changes.py [options]
    -h | --help
    -i | --insert account_name
    -p | --process-changes
    --debug-hosts <comma-serparated list> limit rsh targets to hosts in host_info"""
    sys.exit(exitcode)

def main():
    global debug_hostlist
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hi:p',
                                   ['help', 'insert=', 'process-changes',
                                    'debug-hosts='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)
    for opt, val in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-i', '--insert'):
            insert_account_in_cl(val)
        elif opt in ('-p', '--process-changes'):
            process_changes()
        elif opt == '--debug-hosts':
            debug_hostlist = val.split(",")
            print debug_hostlist
if __name__ == '__main__':
    main()

# arch-tag: e4f70b5b-763e-485c-9f2e-6d49ccbe320c
