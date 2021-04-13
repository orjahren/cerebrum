#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2012-2015 University of Oslo, Norway
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
"""Run a generic sync with Active Directory.

This is the default script for running syncs against AD for all instances. The
purpose of the script is to be able to update every instance' Active Directory.
The hope is that we don't need instance specific scripts.

A full sync is gathering all relevant data from both Cerebrum and AD and
comparing it. If there are mismatches between Cerebrum and AD, AD gets updated.
The quick sync does instead just check Cerebrum's change log and blindly sends
the changes to AD. If AD complains, the changes will be processed later on.
"""
from __future__ import print_function

import getopt
import logging
import sys

import adconf
import Cerebrum.logutils
from Cerebrum.Utils import Factory
from Cerebrum.modules.ad2.ADSync import BaseSync

logger = logging.getLogger(__name__)


def usage(exitcode=0):
    print("""Usage: sync.py [OPTIONS] --type TYPE

    %(doc)s

    Sync options:

    --type TYPE     Which sync (adconf.SYNCS[TYPE]) sync to perform.

                    Normally, the sync type is the name of a spread, which
                    makes the entities with the given spread the targets.

    --quick CL_NAME Run a quicksync (i.e. only send the latest Cerebrum changes
                    to AD).  The default is a fullsync (i.e. compare all data
                    in AD and Cerebrum).

                    The CL_NAME is a CLHandler key to use for tracking changes
                    that has already been processed.  Each quicksync needs to
                    use its own key!

    --change-id ID  Run the quicksync only for a given changelog event.

                    The ID(s) must refer to changelog IDs, which are then
                    processed as in the quicksync.  This option can be repeated
                    for multiple IDs.

    -d, --dryrun    Do not write changes back to AD (only log them).

                    Useful when testing.  Note that the sync is still reading
                    data from AD.

    --sync_class CLS
                    Override the sync_class from config.

                    This option can be repeated.  If multiple sync classes are
                    given, a new sync class will be created, with the the given
                    classes as bases.

    --add-subset    Add a name to the subset configuration list.

                    If a subset list is given (as option, or in the config),
                    only the entities and objects with a name in this list will
                    be processed. This is for debugging and testing purposes
                    only.  This option can be repeated.

    --set VALUE=... Override any setting in the config.

                    This is used to be able to set any configuration variable,
                    e.g. 'store_sid' or 'move_objects'. The name and the value
                    of a configuration variable must be separated with '='.

                    This is for now only supported for config that requires
                    strings (or integers).

                    Note that setting config values like this does not have any
                    input control. Use with care.

    AD related options:

    --host HOSTNAME The hostname of the Windows server we communicate with. We
                    normally don't communicate with a domain controller
                    directly, but rather through a Windows server which again
                    communicates with AD.

    --port PORT     The port number on the Windows server. Default: 5986 for
                    encrypted communication, otherwise 5985.

    --unencrypted   If the communication should go unencrypted. This should
                    only be used for testing! We should e.g. not send passwords
                    in plaintext unencrypted.

    Mocking:

    -m, --mock      Use a mock AD server rather than connect to AD.

                    You'll typically want to load a state into the mock object,
                    otherwise the mock ad environment will look empty.

    -n, --store-mock-state <FILE>
                    Store the mock state in a JSON file.

                    This option will typically be used without --mock, in order
                    to fetch actual ad data from an ad server.  The mock state
                    can later be used with the --mock argument.

    -l, --load-mock-state <FILE>
                    Load the mocks state from a JSON file.

                    This state file is typically generated with
                    --store-mock-state.

    Debug options:

    --debug         Print debug information, mostly for developers.

    --dump-cerebrum-data
                    Only dump cerebrum data.

                    Instead of syncing, just dump out how Cerebrum wants
                    the AD side to look like.  The output is meant to be easy
                    to search and compare, so the format is:

                        ad-id;attribute-name;value

                    For example:

                        emplyees;GidNumber;1002
                        bob;GivenName;Bob
                        bob;EmployeeNumber;0123456

                    The output is sorted by entity name and the attribute
                    names.

    Other options:

    --logger-level LEVEL What log level should it start logging. This is
                         handled by Cerebrum's logger. Default: DEBUG.

    --logger-name NAME   The name of the log. Default: ad_sync. Could be
                         specified to separate different syncs, e.g. one for
                         users and one for groups. The behaviour is handled by
                         Cerebrum's logger.

                         Note that the logname must be defined in logging.ini.

    -h, --help      Show this and quit.

    """ % {'doc': __doc__})

    sys.exit(exitcode)


def dump_cerebrum_data(sync):
    """ Format and print data collected from Cerebrum. """
    atrnames = sorted(sync.config['attributes'])
    for entname in sorted(sync.entities):
        ent = sync.entities[entname]
        print(';'.join((ent.ad_id, u'OU', ent.ou)).encode('utf-8'))
        for atrname in atrnames:
            print(';'.join((
                ent.ad_id,
                atrname,
                unicode(ent.attributes.get(atrname, '<Not Set>')),
            )).encode('utf-8'))


def dump_mem_usage():
    """ Print memory usage. """
    for line in open('/proc/self/status', 'r'):
        if 'VmPeak' in line:
            _, size, unit = line.split()
            size = int(size)
            if size > 1024:
                if unit == 'kB':
                    size = size / 1024
                    unit = 'MB'
            print("Memory peak:", str(size), str(unit))


def main():
    # Legacy autoconf -- checks sys.argv directly for log args
    # TODO: Replace getopt with argparse
    Cerebrum.logutils.autoconf('ad_sync', None)

    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "hdmn:l:",
                                   ["help",
                                    "dryrun",
                                    "mock",
                                    "store-mock-state=",
                                    "load-mock-state=",
                                    "debug",
                                    "quick=",
                                    "change-ids=",
                                    "set=",
                                    "unencrypted",
                                    "dump-cerebrum-data",
                                    "dump-diff",
                                    "subset=",
                                    "type=",
                                    "sync_class=",
                                    "host=",
                                    "port="])
    except getopt.GetoptError as e:
        print(e)
        usage(1)

    sync_type = None
    sync_classes = []
    # If we should do the quicksync instead of fullsync:
    quicksync = False
    change_ids = []
    debug = dump_cerebrum_data = False
    store_mock_state = load_mock_state = None

    # The configuration for the sync
    configuration = dict()

    for opt, val in opts:
        # General options
        if opt in ('-h', '--help'):
            usage()
        elif opt in ('-d', '--dryrun'):
            configuration["dryrun"] = True
        elif opt in ('-m', '--mock'):
            configuration["mock"] = True
        elif opt in ('-n', '--store-mock-state'):
            store_mock_state = val
        elif opt in ('-l', '--load-mock-state'):
            load_mock_state = val
        elif opt == '--unencrypted':
            configuration['encrypted'] = False
        elif opt == '--sync_class':
            sync_classes.append(val)
        elif opt == '--type':
            if val not in adconf.SYNCS:
                print("Sync type '%s' not found in config" % val)
                print("Defined sync types:")
                for typ in adconf.SYNCS:
                    print('  %s' % typ)
                sys.exit(2)
            sync_type = configuration['sync_type'] = val
        elif opt == '--host':
            configuration['server'] = val
        elif opt == '--port':
            configuration['port'] = int(val)
        elif opt == '--add-subset':
            configuration.setdefault('subset', []).append(val)
        elif opt == '--set':
            key, value = val.split('=', 1)
            configuration[key] = value
        elif opt == '--change-ids':
            change_ids.append(int(val))
        elif opt == '--quick':
            quicksync = val
        elif opt == '--debug':
            debug = True
        elif opt == '--dump-cerebrum-data':
            dump_cerebrum_data = True
        else:
            print("Unknown option: %s" % opt)
            usage(1)

    if not sync_type:
        print("Need to specify what sync type to perform")
        usage(1)

    # Make use of config file settings, if not set otherwise by arguments
    for key, value in adconf.SYNCS[sync_type].items():
        if key not in configuration:
            configuration[key] = value

    logger.info('start')

    sync_class = BaseSync.get_class(classes=sync_classes, sync_type=sync_type)
    logger.debug("Using sync classes: %s" % ', '.join(repr(c) for c in
                                                      type.mro(sync_class)))

    db = Factory.get('Database')(client_encoding='UTF-8')
    db.cl_init(change_program="ad_sync")
    sync = sync_class(db=db, logger=logger.getChild('sync'))
    sync.configure(configuration)

    # If debugging instead of syncing:
    if dump_cerebrum_data:
        # TODO: How to avoid fetching the get-dc call at init? Maybe it
        # shouldn't be started somewhere else?
        sync.fetch_cerebrum_data()
        sync.calculate_ad_values()
        sync.server.close()
        dump_cerebrum_data(sync)
        return

    try:
        if load_mock_state:
            sync.server._load_state(load_mock_state)

        if change_ids:
            sync.quicksync(change_ids=change_ids)
        elif quicksync:
            sync.quicksync(quicksync)
        else:
            sync.fullsync()

        if store_mock_state:
            sync.server._store_state(store_mock_state)
    finally:
        try:
            sync.server.close()
        except Exception:
            # It's probably already closed
            pass

    if debug:
        dump_mem_usage()

    logger.info('done')


if __name__ == '__main__':
    main()
