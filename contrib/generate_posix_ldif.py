#!/usr/bin/env python2.2
# -*- coding: iso-8859-1 -*-

# Copyright 2002, 2003, 2004 University of Oslo, Norway
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

"""Usage: [options]

Write user and group information to an LDIF file (if enabled in
cereconf), which can then be loaded into LDAP.

  --user=<outfile>     | -u <outfile>  Write users to a LDIF-file
  --group=<outfile>    | -g <outfile>  Write posix groups to a LDIF-file
  --netgroup=<outfile> | -n <outfile>  Write netgroup map to a LDIF-file
  --posix  Write all of the above, plus optional top object and extra file,
           to a file given in cereconf (unless the above options override).
           Also disable ldapsync first.

With none of the above options, do the same as --posix except only write
the parts that are enabled in cereconf.

  --user_spread=<value>     | -U <value>  (used by all components)
  --group_spread=<value>    | -G <value>  (used by --group component)
  --netgroup_spread=<value> | -N <value>  (used by --netgroup component)

The spread options accept multiple spread-values (<value1>,<value2>,...).
They cannot be used without at least one of the previous options."""

import time, sys, getopt, os

import cerebrum_path
import cereconf  
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum.extlib import logging
from Cerebrum.Utils import Factory, latin1_to_iso646_60, SimilarSizeWriter
from Cerebrum.modules import PosixUser
from Cerebrum.modules import PosixGroup
from Cerebrum.Constants import _SpreadCode
from Cerebrum.QuarantineHandler import QuarantineHandler
from Cerebrum.modules.LDIFutils import *

db = Factory.get('Database')()
co = Factory.get('Constants')(db)

logging.fileConfig(cereconf.LOGGING_CONFIGFILE)
logger = logging.getLogger("cronjob")

entity2uname = {}
disablesync_cn = 'disablesync'


def init_ldap_dump():
    glob_fd.write("\n")
    if getattr(cereconf, 'LDAP_POSIX_DN', None):
        glob_fd.write(container_entry_string('POSIX'))
    add_ldif_file(glob_fd, getattr(cereconf, 'LDAP_POSIX_ADD_LDIF_FILE', None))


def generate_users(spread=None,filename=None):
    posix_user = PosixUser.PosixUser(db)
    disk = Factory.get('Disk')(db)
    spreads = eval_spread_codes(spread or cereconf.LDAP_USER_SPREAD)
    shells = {}
    for sh in posix_user.list_shells():
	shells[int(sh['code'])] = sh['shell']
    disks = {}
    for hd in disk.list(spread=spreads[0]):
	disks[int(hd['disk_id'])] = hd['path']  
    posix_dn = "," + get_tree_dn('USER')
    obj_string = "".join(["objectClass: %s\n" % oc for oc in
                          ('top', 'account', 'posixAccount')])
    if filename:
	f = file(filename,'w')
        f.write("\n")
    else:
	f = glob_fd

    f.write(container_entry_string('USER'))

    #done_users = {}
    # Change to uname2id
    # When all authentication-needing accounts possess an 'md5_crypt'
    # password hash, the below code can be fixed to call
    # list_extended_posix_users() only once.  Until then, we fall back
    # to using 'crypt3_des' hashes.
    #
    # We already favour the stronger 'md5_crypt' hash over any
    # 'crypt3_des', though.
    for auth_method in (co.auth_type_md5_crypt, co.auth_type_crypt3_des):
        prev_userid = 0
        for row in posix_user.list_extended_posix_users(auth_method, spreads, 
						include_quarantines = True):
            (acc_id, shell, gecos, uname) = (
                row['account_id'], row['shell'], row['gecos'],
                row['entity_name'])
            acc_id = int(acc_id)
            if entity2uname.has_key(acc_id):
                continue
            if row['auth_data'] is None:
                if auth_method == co.auth_type_crypt3_des:
                    # Neither md5_crypt nor crypt3_des hash found.
                    passwd = '{crypt}*Invalid'
                else:
                    continue
            else:
                passwd = "{crypt}%s" % row['auth_data']
            shell = shells[int(shell)]
            if row['quarantine_type'] is not None:
                qh = QuarantineHandler(db, (row['quarantine_type'],))
                if qh.should_skip():
                    continue
                if qh.is_locked():
                    passwd = '{crypt}*Locked'
                qshell = qh.get_shell()
                if qshell is not None:
                    shell = qshell
            cn    = row['name'] or gecos or uname
            gecos = latin1_to_iso646_60(gecos or cn)
            if row['disk_id']:
                home = "%s/%s" % (disks[int(row['disk_id'])],uname)
            elif row['home']:
                home = row['home']
	    else:
                continue
            if acc_id <> prev_userid:
                f.write('dn: uid=%s%s\n' % (uname, posix_dn))
                f.write('%scn: %s\n' % (obj_string, iso2utf(cn)))
                f.write('uid: %s\n' % uname)
                f.write('uidNumber: %s\n' % str(row['posix_uid']))
                f.write('gidNumber: %s\n' % str(row['posix_gid']))
                f.write('homeDirectory: %s\n' % home)
                f.write('userPassword: %s\n' % passwd)
                f.write('loginShell: %s\n' % shell)
                f.write('gecos: %s\n' % gecos)
                f.write('\n')
		entity2uname[acc_id] = uname
                prev_userid = acc_id
    if filename:
	f.close()


def generate_posixgroup(spread=None,u_spread=None,filename=None):
    posix_group = PosixGroup.PosixGroup(db)
    group = Factory.get('Group')(db)
    spreads = eval_spread_codes(spread or cereconf.LDAP_GROUP_SPREAD)
    u_spreads = eval_spread_codes(u_spread or cereconf.LDAP_USER_SPREAD)
    if filename:
	f = file(filename, 'w')
        f.write("\n")
    else:
	f = glob_fd

    f.write(container_entry_string('GROUP'))

    groups = {}
    dn_str = get_tree_dn('GROUP')
    obj_str = "".join(["objectClass: %s\n" % oc for oc in
                       ('top', 'posixGroup')])
    for row in posix_group.list_all_grp(spreads):
	posix_group.clear()
        posix_group.find(row.group_id)
        gname = posix_group.group_name
        pos_grp = "dn: cn=%s,%s\n" % (gname, dn_str)
        pos_grp += "%s" % obj_str
        pos_grp += "cn: %s\n" % gname
        pos_grp += "gidNumber: %d\n" % posix_group.posix_gid
        if posix_group.description:
            # latin1_to_iso646_60 later
            pos_grp += "description: %s\n" % iso2utf(posix_group.description)
	group.clear()
        group.find(row.group_id)
        # Since get_members only support single user spread, spread is
        # set to [0]
        for id in group.get_members(spread=u_spreads[0], get_entity_name=True):
            uname_id = int(id[0])
            if not entity2uname.has_key(uname_id):
                entity2uname[uname_id] = id[1]
            pos_grp += "memberUid: %s\n" % entity2uname[uname_id]
        f.write(pos_grp)
	f.write("\n")
    if filename:
	f.close()


def generate_netgroup(spread=None,u_spread=None,filename=None):
    global grp_memb
    pos_netgrp = Factory.get('Group')(db)
    if filename:
        f = file(filename, 'w')
        f.write("\n")
    else:
	f = glob_fd

    f.write(container_entry_string('NETGROUP'))

    spreads = eval_spread_codes(spread or cereconf.LDAP_NETGROUP_SPREAD)
    u_spreads = eval_spread_codes(u_spread or cereconf.LDAP_USER_SPREAD)
    dn_str = get_tree_dn('NETGROUP')
    obj_str = "".join(["objectClass: %s\n" % oc for oc in
                       ('top', 'nisNetGroup')])
    for row in pos_netgrp.list_all_grp(spreads):
	grp_memb = {}
        pos_netgrp.clear()
        pos_netgrp.find(row.group_id)
        netgrp_name = pos_netgrp.group_name
        netgrp_str = "dn: cn=%s,%s\n" % (netgrp_name, dn_str)
        netgrp_str += "%s" % obj_str
        netgrp_str += "cn: %s\n" % netgrp_name
        if not entity2uname.has_key(int(row.group_id)):
            entity2uname[int(row.group_id)] = netgrp_name
        if pos_netgrp.description:
            netgrp_str += "description: %s\n" % \
                          latin1_to_iso646_60(pos_netgrp.description)
        f.write(netgrp_str)
        get_netgrp(int(row.group_id), spreads, u_spreads, f)
        f.write("\n")
    if filename:
	f.close()

def get_netgrp(netgrp_id, spreads, u_spreads, f):
    pos_netgrp = Factory.get('Group')(db)
    pos_netgrp.clear()
    pos_netgrp.entity_id = netgrp_id
    for id in pos_netgrp.list_members(u_spreads[0], int(co.entity_account),\
						get_entity_name= True)[0]:
        uname_id,uname = int(id[1]),id[2]
        if ('_' not in uname) and not grp_memb.has_key(uname_id):
            f.write("nisNetgroupTriple: (,%s,)\n" % uname)
            grp_memb[uname_id] = True
    for group in pos_netgrp.list_members(None, int(co.entity_group),
						get_entity_name=True)[0]:
        pos_netgrp.clear()
        pos_netgrp.entity_id = int(group[1])
	if filter(pos_netgrp.has_spread, spreads):
            f.write("memberNisNetgroup: %s\n" % group[2])
        else:
            get_netgrp(int(group[1]), spreads, u_spreads, f)


def eval_spread_codes(spread):
    if isinstance(spread,(str,int)):
        spread = (spread,)
    if isinstance(spread,(list,tuple)):
        return filter(None, map(spread_code, spread))
    return None

def spread_code(spr_str):
    try: return int(spr_str)
    except:
	try: return int(getattr(co, spr_str))
        except: 
	    try: return int(_SpreadCode(spr_str)) 
	    except:
		print >>sys.stderr, "Not valid Spread-Code: %r" % spr_str
		return None


def disable_ldapsync_mode():
    try:
	ldap_servers = cereconf.LDAP_SERVER
	from Cerebrum.modules import LdapCall
    except AttributeError:
	logger.info('No active LDAP-sync severs configured')
    except ImportError: 
	logger.info('LDAP modules missing. Probably python-LDAP')
    else:
	s_list = LdapCall.ldap_connect()
	LdapCall.add_disable_sync(s_list,disablesync_cn)
	LdapCall.end_session(s_list)
	logg_dir = cereconf.LDAP_DUMP_DIR + '/log'
	if os.path.isdir(logg_dir):  
	    rotate_file = '/'.join((logg_dir,'rotate_ldif.tmp'))
	    if not os.path.isfile(rotate_file):
		f = file(rotate_file,'w')
		f.write(time.strftime("%d %b %Y %H:%M:%S", time.localtime())) 
		f.close()


def main():
    short2long_opts = (('u:', 'U:', 'g:', 'G:', 'n:', 'N:'),
                       ('user=', 'user_spread=', 'group=', 'group_spread=',
                        'netgroup=', 'netgroup_spread='))
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "".join(short2long_opts[0]),
                                   ('help', 'posix') + short2long_opts[1])
        opts = dict(opts)
    except getopt.GetoptError:
        usage(1)
    if args or '--help' in opts:
        usage(bool(args))
    # Copy long options into short options
    for short, long in zip(*short2long_opts):
        val = opts.get('--' + long.replace('=',''))
        if val is not None:
            opts['-' + short.replace(':','')] = val

    got_posix  = '--posix' in opts
    got_file   = filter(opts.has_key, ('-u', '-g', '-n'))
    got_spread = filter(opts.has_key, ('-U', '-G', '-N'))
    if got_spread and not (got_posix or got_file):
        usage(1)
    for opt in got_spread:
        opts[opt] = eval_spread_codes(opts[opt].split(','))

    global glob_fd
    glob_fd = None
    if got_posix or not got_file:
        glob_fd = SimilarSizeWriter(cereconf.LDAP_DUMP_DIR + "/" +
                                    cereconf.LDAP_POSIX_FILE)
        glob_fd.set_size_change_limit(10)

    if got_posix or got_file:
        if got_posix:
            disable_ldapsync_mode()
            init_ldap_dump()
        if got_posix or '-u' in opts:
            generate_users(opts.get('-U'), opts.get('-u'))
        if got_posix or '-g' in opts:
            generate_posixgroup(opts.get('-G'), opts.get('-U'), opts.get('-g'))
        if got_posix or '-n' in opts:
            generate_netgroup(opts.get('-N'), opts.get('-U'), opts.get('-n'))
    else:
        config()

    if glob_fd:
        glob_fd.close()

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

def config():
	disable_ldapsync_mode()
        init_ldap_dump()
	if (cereconf.LDAP_USER == 'Enable'):
	    generate_users()
	if (cereconf.LDAP_GROUP == 'Enable'):
	    generate_posixgroup()
	if (cereconf.LDAP_NETGROUP == 'Enable'):
	    generate_netgroup()
	

if __name__ == '__main__':
    	main()

# arch-tag: a8422a23-97b1-4ac9-a1f1-023ff76a4935
