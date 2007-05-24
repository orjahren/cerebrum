# -*- coding: iso-8859-1 -*-

# Copyright 2002-2005 University of Oslo, Norway
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

# Denne fila implementerer er en bofhd extension som i st�rst mulig
# grad fors�ker � etterligne kommandoene i ureg2000 sin bofh klient.
#
# Vesentlige forskjeller:
#  - det finnes ikke lengre fg/ng grupper.  Disse er sl�tt sammen til
#    "group"
#  - det er ikke lenger mulig � lage nye pesoner under bygging av
#    konto, "person create" m� kj�res f�rst

import re
import sys
import time
import os
import email.Generator, email.Message
#import cyruslib
import pickle
from mx import DateTime
try:
    from sets import Set
except ImportError:
    # It's the same module taken from python 2.3, it should
    # work fine in 2.2  
    from Cerebrum.extlib.sets import Set    

import cereconf
from Cerebrum import Cache
from Cerebrum import Database
from Cerebrum import Entity
from Cerebrum import Errors
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.Email import _EmailDomainCategoryCode
from Cerebrum.modules import PasswordChecker
from Cerebrum.modules import PosixGroup
from Cerebrum.modules import PosixUser
from Cerebrum.modules.bofhd.cmd_param import *
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules.bofhd.auth import BofhdAuth, BofhdAuthOpSet, \
     AuthConstants, BofhdAuthOpTarget, BofhdAuthRole
from Cerebrum.modules.no import fodselsnr
from Cerebrum.modules.no.uit import bofhd_uit_help
from Cerebrum.modules.no.uit.access_FS import FS
from Cerebrum.modules.no.uit.DiskQuota import DiskQuota
from Cerebrum.modules.templates.letters import TemplateHandler

from Cerebrum.modules import ChangeLog

# TBD: It would probably be cleaner if our time formats were specified
# in a non-Java-SimpleDateTime-specific way.
def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

def format_time(field):
    fmt = "yyyy-MM-dd HH:mm"            # 16 characters wide
    return ':'.join((field, "date", fmt))

class TimeoutException(Exception):
    pass

class ConnectException(Exception):
    pass

class BofhdExtension(object):
    """All CallableFuncs take user as first arg, and are responsible
    for checking necessary permissions"""

    all_commands = {}
    OU_class = Utils.Factory.get('OU')
    Account_class = Utils.Factory.get('Account')
    Group_class = Utils.Factory.get('Group')
    external_id_mappings = {}

    def __init__(self, server):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        person = Utils.Factory.get('Person')(self.db)
        self.const = person.const
        self.name_codes = {}
        for t in person.list_person_name_codes():
            self.name_codes[int(t['code'])] = t['description']
        self.external_id_mappings['fnr'] = self.const.externalid_fodselsnr
        # TODO: str2const is not guaranteed to be unique (OK for now, though)
        self.num2const = {}
        self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const[str(tmp)] = tmp
        self.ba = BofhdAuth(self.db)
        aos = BofhdAuthOpSet(self.db)
        self.num2op_set_name = {}
        for r in aos.list():
            self.num2op_set_name[int(r['op_set_id'])] = r['name']
        self.change_type2details = {}
        for r in self.db.get_changetypes():
            self.change_type2details[int(r['change_type_id'])] = [
                r['category'], r['type'], r['msg_string']]

        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)
        self.fixup_imaplib()

    def fixup_imaplib(self):
        import imaplib
        def nonblocking_open(self, host=None, port=None):
            import socket
            import select
            import errno
            # Perhaps using **kwargs is cleaner, but this works, too.
            if host is None:
                if not hasattr(self, "host"):
                    self.host = ''
            else:
                self.host = host
            if port is None:
                if not hasattr(self, "port"):
                    self.port = 143
            else:
                self.port = port

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setblocking(False)
            err = self.sock.connect_ex((self.host, self.port))
            # I don't think connect_ex() can ever return success immediately,
            # it has to wait for a roundtrip.
            assert err
            if err <> errno.EINPROGRESS:
                raise ConnectException(errno.errorcode[err])

            ignore, wset, ignore = select.select([], [self.sock], [], 1.0)
            if not wset:
                raise TimeoutException
            err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err == 0:
                self.sock.setblocking(True)
                self.file = self.sock.makefile('rb')
                return
            raise ConnectException(errno.errorcode[err])
        setattr(imaplib.IMAP4, 'open', nonblocking_open)

    def num2str(self, num):
        """Returns the string value of a numerical constant"""
        return str(self.num2const[int(num)])
        
    def str2num(self, string):
        """Returns the numerical value of a string constant"""
        return int(self.str2const[str(string)])

    def get_commands(self, account_id):
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for k in self.all_commands.keys():
            tmp = self.all_commands[k]
            if tmp is not None:
                if tmp.perm_filter:
                    if not getattr(self.ba, tmp.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands

    def get_help_strings(self):
        return (bofhd_uit_help.group_help, bofhd_uit_help.command_help,
                bofhd_uit_help.arg_help)

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()


    #
    # access commands
    #

    # access disk <path>
    all_commands['access_disk'] = Command(
        ('access', 'disk'),
        DiskId(),
        fs=FormatSuggestion("%-16s %-9s %s",
                            ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_disk(self, operator, path):
        disk = self._get_disk(path)[0]
        result = []
        host = Utils.Factory.get('Host')(self.db)
        try:
            host.find(disk.host_id)
            for r in self._list_access("host", host.name, empty_result=[]):
                if r['attr'] == '' or re.search("/%s$" % r['attr'], path):
                    result.append(r)
        except Errors.NotFoundError:
            pass
        result.extend(self._list_access("disk", path, empty_result=[]))
        return result or "None"

    # access group <group>
    all_commands['access_group'] = Command(
        ('access', 'group'),
        GroupName(),
        fs=FormatSuggestion("%-16s %-9s %s", ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_group(self, operator, group):
        return self._list_access("group", group)

    # access host <hostname>
    all_commands['access_host'] = Command(
        ('access', 'host'),
        SimpleString(help_ref="string_host"),
        fs=FormatSuggestion("%-16s %-16s %-9s %s",
                            ("opset", "attr", "type", "name"),
                            hdr="%-16s %-16s %-9s %s" %
                            ("Operation set", "Pattern", "Type", "Name")))
    def access_host(self, operator, host):
        return self._list_access("host", host)

    # access maildom <maildom>
    all_commands['access_maildom'] = Command(
        ('access', 'maildom'),
        SimpleString(help_ref="email_domain"),
        fs=FormatSuggestion("%-16s %-9s %s",
                            ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_maildom(self, operator, maildom):
        return self._list_access("maildom", maildom)

    # access ou <ou>
    all_commands['access_ou'] = Command(
        ('access', 'ou'),
        OU(),
        fs=FormatSuggestion("%-16s %-16s %-9s %s",
                            ("opset", "attr", "type", "name"),
                            hdr="%-16s %-16s %-9s %s" %
                            ("Operation set", "Affiliation", "Type", "Name")))
    def access_ou(self, operator, ou):
        return self._list_access("ou", ou)

    # access user <account>
    all_commands['access_user'] = Command(
        ('access', 'user'),
        AccountName(),
        fs=FormatSuggestion("%-14s %-5s %-20s %-7s %-9s %s",
                            ("opset", "target_type", "target", "attr",
                             "type", "name"),
                            hdr="%-14s %-5s %-20s %-7s %-9s %s" %
                            ("Operation set", "TType", "Target", "Attr",
                             "Type", "Name")))
    def access_user(self, operator, user):
        """This is more tricky than the others, we want to show anyone
        with access, through OU, host or disk.  (not global_XXX,
        though.)

        Note that there is no auth-type 'account', so you can't be
        granted direct access to a specific user."""

        acc = self._get_account(user)
        # Make lists of the disks and hosts associated with the user
        disks = {}
        hosts = {}
        disk = Utils.Factory.get("Disk")(self.db)
        for r in acc.get_homes():
            disk_id = int(r['disk_id'])
            if not disk_id in disks:
                disk.find(disk_id)
                disks[disk_id] = disk.path
                host_id = int(disk.host_id)
                if host_id is not None:
                    basename = disk.path.split("/")[-1]
                    hosts.setdefault(host_id, []).append(basename)
        # Look through disks
        ret = []
        for d in disks.keys():
            for entry in self._list_access("disk", d, empty_result=[]):
                entry['target_type'] = "disk"
                entry['target'] = disks[d]
                ret.append(entry)
        # Look through hosts:
        for h in hosts.keys():
            for candidate in self._list_access("host", h, empty_result=[]):
                candidate['target_type'] = "host"
                candidate['target'] = self._get_host(h).name
                if candidate['attr'] == "":
                    ret.append(candidate)
                    continue
                for dir in hosts[h]:
                    if re.match(candidate['attr'], dir):
                        ret.append(candidate)
                        break
        # TODO: check user's ou(s)
        ret.sort(lambda x,y: (cmp(x['opset'].lower(), y['opset'].lower()) or
                              cmp(x['name'], y['name'])))
        return ret

    # access global_group
    all_commands['access_global_group'] = Command(
        ('access', 'global_group'),
        fs=FormatSuggestion("%-16s %-9s %s", ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_global_group(self, operator):
        return self._list_access("global_group")

    # access global_host
    all_commands['access_global_host'] = Command(
        ('access', 'global_host'),
        fs=FormatSuggestion("%-16s %-9s %s",
                            ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_global_host(self, operator):
        return self._list_access("global_host")
    
    # access global_maildom
    all_commands['access_global_maildom'] = Command(
        ('access', 'global_maildom'),
        fs=FormatSuggestion("%-16s %-9s %s",
                            ("opset", "type", "name"),
                            hdr="%-16s %-9s %s" %
                            ("Operation set", "Type", "Name")))
    def access_global_maildom(self, operator):
        return self._list_access("global_maildom")

    # access global_ou
    all_commands['access_global_ou'] = Command(
        ('access', 'global_ou'),
        fs=FormatSuggestion("%-16s %-16s %-9s %s",
                            ("opset", "attr", "type", "name"),
                            hdr="%-16s %-16s %-9s %s" %
                            ("Operation set", "Affiliation", "Type", "Name")))
    def access_global_ou(self, operator):
        return self._list_access("global_ou")


    def _list_access(self, target_type, target_name=None, decode_attr=str,
                     empty_result="None"):
        target_id, target_type = self._get_access_id(target_type, target_name)
        ret = []
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for r in self._get_auth_op_target(target_id, target_type,
                                          any_attr=True):
            if r['attr'] is None:
                attr = ""
            else:
                attr = decode_attr(r['attr'])
            for r2 in ar.list(op_target_id=r['op_target_id']):
                aos.clear()
                aos.find(r2['op_set_id'])
                ety = self._get_entity(id=r2['entity_id'])
                ret.append({'opset': aos.name,
                            'attr': attr,
                            'type': str(self.const.EntityType(ety.entity_type)),
                            'name': self._get_name_from_object(ety)})
        ret.sort(lambda a,b: (cmp(a['opset'], b['opset']) or
                              cmp(a['name'], b['name'])))
        return ret or empty_result


    # access grant <opset name> <who> <type> <on what> [<attr>]
    all_commands['access_grant'] = Command(
        ('access', 'grant'),
        OpSet(),
        GroupName(repeat=True, help_ref="auth_group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='is_superuser')
    def access_grant(self, operator, opset, group, entity_type, target_name,
                     attr=None):
        return self._manipulate_access(self._grant_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    # access revoke <opset name> <who> <type> <on what> [<attr>]
    all_commands['access_revoke'] = Command(
        ('access', 'revoke'),
        OpSet(),
        GroupName(repeat=True, help_ref="auth_group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='is_superuser')
    def access_revoke(self, operator, opset, group, entity_type, target_name,
                     attr=None):
        return self._manipulate_access(self._revoke_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    def _manipulate_access(self, change_func, operator, opset, group,
                           entity_type, target_name, attr):
        
        """This function does no validation of types itself.  It uses
        _get_access_id() to get a (target_type, entity_id) suitable for
        insertion in auth_op_target.  Additional checking for validity
        is done by _validate_access().

        Those helper functions look for a function matching the
        target_type, and call it.  There should be one
        _get_access_id_XXX and one _validate_access_XXX for each known
        target_type."""
        
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        opset = self._get_opset(opset)
        gr = self._get_group(group)
        target_id, target_type = self._get_access_id(entity_type, target_name)
        self._validate_access(entity_type, opset, attr)
        return change_func(gr.entity_id, opset, target_id, target_type, attr,
                           group, target_name)


    def _get_access_id(self, target_type, target_name):
        func_name = "_get_access_id_%s" % target_type
        if not func_name in dir(self):
            raise CerebrumError, "Unknown id type %s" % target_type
        return self.__getattribute__(func_name)(target_name)

    def _validate_access(self, target_type, opset, attr):
        func_name = "_validate_access_%s" % target_type
        if not func_name in dir(self):
            raise CerebrumError, "Unknown type %s" % target_type
        return self.__getattribute__(func_name)(opset, attr)

    def _get_access_id_disk(self, target_name):
        return self._get_disk(target_name)[1], self.const.auth_target_type_disk
    def _validate_access_disk(self, opset, attr):
        # TODO: check if the opset is relevant for a disk
        if attr is not None:
            raise CerebrumError, "Can't specify attribute for disk access"

    def _get_access_id_group(self, target_name):
        target = self._get_group(target_name)
        return target.entity_id, self.const.auth_target_type_group
    def _validate_access_group(self, opset, attr):
        # TODO: check if the opset is relevant for a group
        if attr is not None:
            raise CerebrumError, "Can't specify attribute for group access"

    def _get_access_id_global_group(self, group):
        if group is not None and group <> "":
            raise CerebrumError, "Cannot set domain for global access"
        return None, self.const.auth_target_type_global_group
    def _validate_access_global_group(self, opset, attr):
        if attr is not None:
            raise CerebrumError, "Can't specify attribute for global group"

    def _get_access_id_host(self, target_name):
        target = self._get_host(target_name)
        return target.entity_id, self.const.auth_target_type_host
    def _validate_access_host(self, opset, attr):
        if attr is not None:
            if attr.count('/'):
                raise CerebrumError, ("The disk pattern should only contain "+
                                      "the last component of the path.")
            try:
                re.compile(attr)
            except re.error, e:
                raise CerebrumError, ("Syntax error in regexp: %s" % e)

    def _get_access_id_global_host(self, target_name):
        if target_name is not None and target_name <> "":
            raise CerebrumError, ("You can't specify a hostname")
        return None, self.const.auth_target_type_global_host
    def _validate_access_global_host(self, opset, attr):
        if attr is not None:
            raise CerebrumError, ("You can't specify a pattern with "
                                  "global_host.")

    def _get_access_id_maildom(self, dom):
        ed = self._get_email_domain(dom)
        return ed.email_domain_id, self.const.auth_target_type_maildomain
    def _validate_access_maildom(self, opset, attr):
        if attr is not None:
            raise CerebrumError, ("No attribute with maildom.")

    def _get_access_id_global_maildom(self, dom):
        if dom is not None and dom <> '':
            raise CerebrumError, "Cannot set domain for global access"
        return None, self.const.auth_target_type_global_maildomain
    def _validate_access_global_maildom(self, opset, attr):
        if attr is not None:
            raise CerebrumError, ("No attribute with global maildom.")

    def _get_access_id_ou(self, ou):
        ou = self._get_ou(stedkode=ou)
        return ou.entity_id, self.const.auth_target_type_ou
    def _validate_access_ou(self, opset, attr):
        if attr is not None:
            try:
                int(self.const.PersonAffiliation(attr))
            except Errors.NotFoundError:
                raise CerebrumError, "Unknown affiliation '%s'" % attr

    def _get_access_id_global_ou(self, ou):
        if ou is not None and ou != '':
            raise CerebrumError, "Cannot set OU for global access"
        return None, self.const.auth_target_type_global_ou
    def _validate_access_global_ou(self, opset, attr):
        try:
            int(self.const.PersonAffiliation(attr))
        except Errors.NotFoundError:
            # This is a policy decision, and should probably be
            # elsewhere.
            raise CerebrumError, "Must specify affiliation for global ou access"

    # access list_opsets
    all_commands['access_list_opsets'] = Command(
        ('access', 'list_opsets'),
        fs=FormatSuggestion("%s", ("opset",),
                            hdr="Operation set"))
    def access_list_opsets(self, operator):
        baos = BofhdAuthOpSet(self.db)
        ret = []
        for r in baos.list():
            ret.append({'opset': r['name']})
        ret.sort(lambda x, y: cmp(x['opset'].lower(), y['opset'].lower()))
        return ret

    # access show_opset <opset name>
    all_commands['access_show_opset'] = Command(
        ('access', 'show_opset'),
        OpSet(),
        fs=FormatSuggestion("%-16s %-16s %s",
                            ("op", "attr", "desc"),
                            hdr="%-16s %-16s %s" %
                            ("Operation", "Attribute", "Description")))
    def access_show_opset(self, operator, opset=None):
        baos = BofhdAuthOpSet(self.db)
        try:
            baos.find_by_name(opset)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown operation set: '%s'" % opset
        ret = []
        for r in baos.list_operations():
            entry = {'op': str(self.const.AuthRoleOp(r['op_code'])),
                     'desc': self.const.AuthRoleOp(r['op_code']).description}
            attrs = []
            for r2 in baos.list_operation_attrs(r['op_id']):
                attrs += [r2['attr']]
            if not attrs:
                attrs = [""]
            for a in attrs:
                entry_with_attr = entry.copy()
                entry_with_attr['attr'] = a
                ret += [entry_with_attr]
        ret.sort(lambda x,y: cmp(x['op'], y['op']) or cmp(x['attr'], y['attr']))
        return ret

    # TODO
    #
    # To be able to manipulate all aspects of bofhd authentication, we
    # need a few more commands:
    #
    #   access create_opset <opset name>
    #   access create_op <opname> <desc>
    #   access delete_op <opname>
    #   access add_to_opset <opset> <op> [<attr>]
    #   access remove_from_opset <opset> <op> [<attr>]
    #
    # The opset could be implicitly deleted after the last op was
    # removed from it.
    #
    # Perhaps we also need "access list entity" to list the
    # permissions entity has.

    def _get_auth_op_target(self, entity_id, target_type, attr=None,
                            any_attr=False, create=False):
        
        """Return auth_op_target(s) associated with (entity_id,
        target_type, attr).  If any_attr is false, return one
        op_target_id or None.  If any_attr is true, return list of
        matching db_row objects.  If create is true, create a new
        op_target if no matching row is found."""
        
        if any_attr:
            op_targets = []
            assert attr is None and create is False
        else:
            op_targets = None

        aot = BofhdAuthOpTarget(self.db)
        for r in aot.list(entity_id=entity_id, target_type=target_type,
                          attr=attr):
            if attr is None and not any_attr and r['attr']:
                continue
            if any_attr:
                op_targets.append(r)
            else:
                # There may be more than one matching op_target, but
                # we don't care which one we use -- we will make sure
                # not to make duplicates ourselves.
                op_targets = int(r['op_target_id'])
        if op_targets or not create:
            return op_targets
        # No op_target found, make a new one.
        aot.populate(entity_id, target_type, attr)
        aot.write_db()
        return aot.op_target_id

    def _grant_auth(self, entity_id, opset, target_id, target_type, attr,
                    entity_name, target_name):
        op_target_id = self._get_auth_op_target(target_id, target_type, attr,
                                                create=True)
        ar = BofhdAuthRole(self.db)
        rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        if len(rows) == 0:
            ar.grant_auth(entity_id, opset.op_set_id, op_target_id)
            return "OK, granted %s %s to %s" % (entity_name, opset.name,
                                                target_name)
        return "%s already has %s access to %s" % (entity_name, opset.name,
                                                   target_name)

    def _revoke_auth(self, entity_id, opset, target_id, target_type, attr,
                     entity_name, target_name):
        op_target_id = self._get_auth_op_target(target_id, target_type, attr)
        if not op_target_id:
            raise CerebrumError, ("No one has matching access to %s" %
                                  target_name)
        ar = BofhdAuthRole(self.db)
        rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        if len(rows) == 0:
            return "%s don't have %s access to %s" % (entity_name, opset.name,
                                                      target_name)
        ar.revoke_auth(entity_id, opset.op_set_id, op_target_id)
        # See if the op_target has any references left, delete it if not.
        rows = ar.list(op_target_id=op_target_id)
        if len(rows) == 0:
            aot = BofhdAuthOpTarget(self.db)
            aot.find(op_target_id)
            aot.delete()
        return "OK, revoked %s for %s from %s" % (opset.name, entity_name,
                                                  target_name)

    #
    # email commands
    #

    # email add_address <address or account> <address>+
    all_commands['email_add_address'] = Command(
        ('email', 'add_address'),
        AccountName(help_ref='account_name'),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_address_add')
    def email_add_address(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        ttype = et.email_target_type
        if ttype not in (self.const.email_target_Mailman,
                         self.const.email_target_forward,
                         self.const.email_target_file,
                         self.const.email_target_multi,
                         self.const.email_target_pipe,
                         self.const.email_target_account):
            raise CerebrumError, ("Can't add e-mail address to target "+
                                  "type %s") % self.num2const[ttype]
        ea = Email.EmailAddress(self.db)
        lp, dom = self._split_email_address(address)
        ed = self._get_email_domain(dom)
        self.ba.can_email_address_add(operator.get_entity_id(),
                                      account=acc, domain=ed)
        ea.clear()
        try:
            ea.find_by_address(address)
            raise CerebrumError, "Address already exists (%s)" % address
        except Errors.NotFoundError:
            pass
        ea.clear()
        ea.populate(lp, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        return "OK, added '%s' as email-address for '%s'" % (address, uname)
    
    # email remove_address <account> <address>+
    all_commands['email_remove_address'] = Command(
        ('email', 'remove_address'),
        AccountName(help_ref='account_name'),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_address_delete')
    def email_remove_address(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        ttype = et.email_target_type
        if ttype not in (self.const.email_target_Mailman,
                         self.const.email_target_account,
                         self.const.email_target_forward,
                         self.const.email_target_pipe,
                         self.const.email_target_multi,
                         self.const.email_target_deleted):
            raise CerebrumError, ("Can't remove e-mail address from target "+
                                  "type %s") % self.num2const[ttype]
        if address.count('@') != 1:
            raise CerebrumError, "Malformed e-mail address (%s)" % address
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_address(address)
        except Errors.NotFoundError:
            raise CerebrumError, "No such e-mail address (%s)" % address
        if ((ttype == int(self.const.email_target_Mailman) and
             self._get_mailman_list(uname) <> self._get_mailman_list(address))
            and ea.get_target_id() <> et.email_target_id):
            raise CerebrumError, ("Address <%s> is not associated with %s" %
                                  (address, uname))
        ed = Email.EmailDomain(self.db)
        ed.find(ea.email_addr_domain_id)
        self.ba.can_email_address_add(operator.get_entity_id(),
                                      account=acc, domain=ed)
        addresses = et.get_addresses()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.email_target_id)
            primary = epat.email_primaddr_id
        except Errors.NotFoundError:
            primary = None

        if primary == ea.email_addr_id:
            if len(addresses) == 1:
                # We're down to the last address, remove the primary
                epat.delete()
            else:
                raise CerebrumError, \
                      "Can't remove primary address <%s>" % address
        ea.delete()
        if len(addresses) > 1:
            # there is at least one address left
            return "OK, removed '%s'" % address
        # clean up and remove the target.
        et.delete()
        return "OK, also deleted e-mail target"

    # email reassign_address <address> <destination>
    all_commands['email_reassign_address'] = Command(
        ('email', 'reassign_address'),
        EmailAddress(help_ref='email_address'),
        AccountName(help_ref='account_name'),
        perm_filter='can_email_address_reassign')
    def email_reassign_address(self, operator, address, dest):
        source_et, source_acc = self.__get_email_target_and_account(address)
        ttype = source_et.email_target_type
        if ttype not in (self.const.email_target_account,
                         self.const.email_target_deleted):
            raise CerebrumError, ("Can't reassign e-mail address from target "+
                                  "type %s") % self.const.EmailTarget(ttype)
        dest_acc = self._get_account(dest)
        if dest_acc.is_deleted():
            raise CerebrumError, ("Can't reassign e-mail address to deleted "+
                                  "account %s") % dest
        dest_et = Email.EmailTarget(self.db)
        try:
            dest_et.find_by_entity(dest_acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError, "Account %s has no e-mail target" % dest
        if dest_et.email_target_type <> self.const.email_target_account:
            raise CerebrumError, ("Can't reassign e-mail address to target "+
                                  "type %s") % self.const.EmailTarget(ttype)
        if source_et.email_target_id == dest_et.email_target_id:
            return "%s is already connected to %s" % (address, dest)
        if (source_acc.owner_type <> dest_acc.owner_type or
            source_acc.owner_id <> dest_acc.owner_id):
            raise CerebrumError, ("Can't reassign e-mail address to a "+
                                  "different person.")
        
        self.ba.can_email_address_reassign(operator.get_entity_id(),
                                           dest_acc)

        source_epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            source_epat.find(source_et.email_target_id)
            source_epat.delete()
        except Errors.NotFoundError:
            pass
        
        ea = Email.EmailAddress(self.db)
        ea.find_by_address(address)
        ea.email_addr_target_id = dest_et.email_target_id
        ea.write_db()
        
        dest_acc.update_email_addresses()
        
        if (len(source_et.get_addresses()) == 0 and
            ttype == self.const.email_target_deleted):
            source_et.delete()
            return "OK, also deleted e-mail target"
        
        source_acc.update_email_addresses()
        return "OK, reassigned %s" % address

    # email forward "on"|"off"|"local" <account>+ [<address>+]
    all_commands['email_forward'] = Command(
        ('email', 'forward'),
        SimpleString(help_ref='email_forward_action'),
        AccountName(help_ref='account_name', repeat=True),
        EmailAddress(help_ref='email_address',
                     repeat=True, optional=True),
        perm_filter='can_email_forward_toggle')
    def email_forward(self, operator, action, uname, addr=None):
        acc = self._get_account(uname)
        self.ba.can_email_forward_toggle(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find_by_entity(acc.entity_id)
        matches = []
        prim = acc.get_primary_mailaddress()

        found = False
        if addr == 'local':
            for a in self.__get_valid_email_addrs(fw):
                if self._forward_exists(fw, a):
                    found = True
                    matches.append(a)
        else:
            for r in fw.get_forward():
                if addr is None or r['forward_to'].find(addr) <> -1:
                    matches.append(r['forward_to'])
        if addr:
            if not matches:
                raise CerebrumError, "No such forward address: %s" % addr
            elif len(matches) > 1 and addr <> 'local':
                raise CerebrumError, "More than one address matches %s" % addr
        elif not matches:
            raise CerebrumError, "No forward addresses for %s" % uname
        if action == 'local':
            action = 'on'
            if not found:
                fw.add_forward(prim)
        for a in matches:
            if action == 'on':
                fw.enable_forward(a)
            elif action == 'off':
                fw.disable_forward(a)
            else:
                raise CerebrumError, ("Unknown action (%s), " +
                                      "choose one of on, off or local") % action
        fw.write_db()
        return 'OK'

    # email add_forward <account>+ <address>+
    # account can also be an e-mail address for pure forwardtargets
    all_commands['email_add_forward'] = Command(
        ('email', 'add_forward'),
        AccountName(help_ref='account_name', repeat=True),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_forward_edit')
    def email_add_forward(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        if uname.count('@') and not acc:
            lp, dom = uname.split('@')
            ed = Email.EmailDomain(self.db)
            ed.find_by_domain(dom)
            self.ba.can_email_forward_edit(operator.get_entity_id(),
                                           domain=ed)
        else:
            self.ba.can_email_forward_edit(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find(et.email_target_id)
        addr = self._check_email_address(address)
        if addr == 'local':
            if acc:
                addr = acc.get_primary_mailaddress()
            else:
                raise CerebrumError, ("Forward address '%s' does not make sense"
                                      % addr)
        if self._forward_exists(fw, addr):
            raise CerebrumError, "Forward address added already (%s)" % addr
        fw.add_forward(addr)
        return "OK, added '%s' as forward-address for '%s'" % (
            address, uname)

    # email remove_forward <account>+ <address>+
    # account can also be an e-mail address for pure forwardtargets
    all_commands['email_remove_forward'] = Command(
        ("email", "remove_forward"),
        AccountName(help_ref="account_name", repeat=True),
        EmailAddress(help_ref='email_address', repeat=True),
        perm_filter='can_email_forward_edit')
    def email_remove_forward(self, operator, uname, address):
        et, acc = self.__get_email_target_and_account(uname)
        if uname.count('@') and not acc:
            lp, dom = uname.split('@')
            ed = Email.EmailDomain(self.db)
            ed.find_by_domain(dom)
            self.ba.can_email_forward_edit(operator.get_entity_id(),
                                           domain=ed)
        else:
            self.ba.can_email_forward_edit(operator.get_entity_id(), acc)
        fw = Email.EmailForward(self.db)
        fw.find(et.email_target_id)
        addr = self._check_email_address(address)
        if addr == 'local' and acc:
            locals = self.__get_valid_email_addrs(fw)
        else:
            locals = [addr]
        removed = 0
        for a in locals:
            if self._forward_exists(fw, a):
                fw.delete_forward(a)
                removed += 1
        if not removed:
            raise CerebrumError, "No such forward address (%s)" % addr
        return "OK, removed '%s'" % address

    def _check_email_address(self, address):
        # To stop some typoes, we require that the address consists of
        # a local part and a domain, and the domain must contain at
        # least one period.  We also remove leading and trailing
        # whitespace.  We do an unanchored search as well so that an
        # address in angle brackets is accepted, e.g. either of
        # "jdoe@example.com" or "Jane Doe <jdoe@example.com>" is OK.
        address = address.strip()
        if address == 'local':
            return address
        if address.find("@") == -1:
            raise CerebrumError, "E-mail addresses must include the domain name"
        if not (re.match(r'[^@\s]+@[^@\s.]+\.[^@\s]+$', address) or
                re.search(r'<[^@>\s]+@[^@>\s.]+\.[^@>\s]+>$', address)):
            raise CerebrumError, "Invalid e-mail address (%s)" % address
        return address

    def _forward_exists(self, fw, addr):
        for r in fw.get_forward():
            if r['forward_to'] == addr:
                return True
        return False

    # email info <account>+
    all_commands['email_info'] = Command(
        ("email", "info"),
        AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_info',
        fs=FormatSuggestion([
        ("Type:             %s",
         ("target_type",)),
        #
        # target_type == Account
        #
        ("Account:          %s\nMail server:      %s (%s)",
         ("account", "server", "server_type")),
        ("Primary address:  %s",
         ("def_addr", )),
        ("Alias value:      %s",
         ("alias_value", )),
        # We use valid_addr_1 and (multiple) valid_addr to enable
        # programs to get the information reasonably easily, while
        # still keeping the suggested output format pretty.
        ("Valid addresses:  %s",
         ("valid_addr_1", )),
        ("                  %s",
         ("valid_addr",)),
        ("Mail quota:       %d MiB, warn at %d%% (not enforced)",
         ("dis_quota_hard", "dis_quota_soft")),
        ("Mail quota:       %d MiB, warn at %d%% (%s MiB used)",
         ("quota_hard", "quota_soft", "quota_used")),
        # TODO: change format so that ON/OFF is passed as separate value.
        # this must be coordinated with webmail code.
        ("Forwarding:       %s",
         ("forward_1", )),
        ("                  %s",
         ("forward", )),
        #
        # target_type == Mailman
        #
        ("Mailing list:     %s",
         ("mailman_list", )),
        ("Alias:            %s",
         ("mailman_alias_1", )),
        ("                  %s",
         ("mailman_alias", )),
        ("Request address:  %s",
         ("mailman_mailcmd_1", )),
        ("                  %s",
         ("mailman_mailcmd", )),
        ("Owner address:    %s",
         ("mailman_mailowner_1", )),
        ("                  %s",
         ("mailman_mailowner", )),
        # target_type == multi
        ("Forward to group: %s",
         ("multi_forward_gr",)),
        ("Expands to:       %s",
         ("multi_forward_1",)),
        ("                  %s",
         ("multi_forward",)),
        # target_type == file
        ("File:             %s\n"+
         "Save as:          %s",
         ("file_name", "file_runas")),
        # target_type == pipe
        ("Command:          %s\n"+
         "Run as:           %s",
         ("pipe_cmd", "pipe_runas")),
        # target_type == forward
        ("Address:          %s",
         ("fw_target",)),
        ("Forwarding:       %s (%s)",
         ("fw_addr_1", "fw_enable_1")),
        ("                  %s (%s)",
         ("fw_addr", "fw_enable")),
        #
        # both account and Mailman
        #
        ("Spam level:       %s (%s)\nSpam action:      %s (%s)",
         ("spam_level", "spam_level_desc", "spam_action", "spam_action_desc")),
        ]))
    def email_info(self, operator, uname):
        et, acc = self.__get_email_target_and_account(uname)
        ttype = et.email_target_type
        ttype_name = str(self.const.EmailTarget(ttype))

        ret = []
        if ttype not in (self.const.email_target_account,
                         self.const.email_target_Mailman,
                         self.const.email_target_pipe):
            ret += [ {'target_type': ttype_name } ]

        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.email_target_id)
        except Errors.NotFoundError:
            if ttype == self.const.email_target_account:
                ret.append({'def_addr': "<none>"})
        else:
            ret.append({'def_addr': self.__get_address(epat)})

        if ttype != self.const.email_target_Mailman:
            # We want to split the valid addresses into three
            # for Mailman, so there is special code for it there.
            addrs = self.__get_valid_email_addrs(et) or ["<none>"]
            ret.append({'valid_addr_1': addrs[0]})
            for addr in addrs[1:]:
                ret.append({"valid_addr": addr})

        if ttype == self.const.email_target_Mailman:
            ret += self._email_info_mailman(uname, et)
        elif ttype == self.const.email_target_multi:
            ret += self._email_info_multi(uname, et)
        elif ttype == self.const.email_target_file:
            ret += self._email_info_file(uname, et)
        elif ttype == self.const.email_target_pipe:
            ret += self._email_info_pipe(uname, et)
        elif ttype == self.const.email_target_forward:
            ret += self._email_info_forward(uname, et)
        elif (ttype == self.const.email_target_account or
              ttype == self.const.email_target_deleted):
            ret += self._email_info_account(operator, acc, et, addrs)
        else:
            raise CerebrumError, ("email info for target type %s isn't "
                                  "implemented") % ttype_name
        return ret

    def _email_info_account(self, operator, acc, et, addrs):
        self.ba.can_email_info(operator.get_entity_id(), acc)
        ret = self._email_info_basic(acc, et)
        #try:
        #    self.ba.can_email_info_detail(operator.get_entity_id(), acc)
        #except PermissionDenied:
        #    pass
        #else:
        #    ret += self._email_info_spam(et)
        #    ret += self._email_info_detail(acc)
        #    ret += self._email_info_forwarding(et, addrs)
        return ret

    def __get_valid_email_addrs(self, et, special=False):
        """Return a list of all valid e-mail addresses for the given
        EmailTarget.  Keep special domain names intact if special is
        True, otherwise re-write them into real domain names."""
        addrs = []
        for r in et.get_addresses(special=special):
            addrs.append(r['local_part'] + '@' + r['domain'])
        return addrs

    def _email_info_basic(self, acc, et):
        info = {}
        data = [ info ]
        if et.email_target_alias:
            info['alias_value'] = et.email_target_alias
        info["account"] = acc.account_name
        if et.email_server_id:
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
            info["server"] = es.name
            type = int(es.email_server_type)
            info["server_type"] = str(self.const.EmailServerType(type))
        else:
            info["server"] = "<none>"
            info["server_type"] = "N/A"
        return data

    def _email_info_spam(self, target):
        info = []
        esf = Email.EmailSpamFilter(self.db)
        try:
            esf.find(target.email_target_id)
            spam_lev = self.const.EmailSpamLevel(esf.email_spam_level)
            spam_act = self.const.EmailSpamAction(esf.email_spam_action)
            info.append({'spam_level':       str(spam_lev),
                         'spam_level_desc':  spam_lev._get_description(),
                         'spam_action':      str(spam_act),
                         'spam_action_desc': spam_act._get_description()})
        except Errors.NotFoundError:
            pass
        return info

#    def _email_info_detail(self, acc):
#        info = []
#        eq = Email.EmailQuota(self.db)
#        try:
#            eq.find_by_entity(acc.entity_id)
#            et = Email.EmailTarget(self.db)
#            et.find_by_entity(acc.entity_id)
#            es = Email.EmailServer(self.db)
#            es.find(et.email_server_id)
#            if es.email_server_type == self.const.email_server_type_cyrus:
#                pw = self.db._read_password(cereconf.CYRUS_HOST,
#                                            cereconf.CYRUS_ADMIN)
#                try:
#                    cyrus = cyruslib.CYRUS(es.name)
#                    cyrus.login(cereconf.CYRUS_ADMIN, pw)
#                    # TODO: use imaplib instead of cyruslib, and do
#                    # quotatrees properly.  cyruslib doesn't check to
#                    # see if it's a STORAGE quota or something else.
#                    # not very important for us, though.
#                    used, limit = cyrus.lq("user", acc.account_name)
#                    if used is None:
#                        used = 'N/A'
#                    else:
#                        used = str(used/1024)
#                except TimeoutException:
#                    used = 'DOWN'
#                except ConnectException, e:
#                    used = str(e)
#                info.append({'quota_hard': eq.email_quota_hard,
#                             'quota_soft': eq.email_quota_soft,
#                             'quota_used': used})
#            else:
#                info.append({'dis_quota_hard': eq.email_quota_hard,
#                             'dis_quota_soft': eq.email_quota_soft})
#        except Errors.NotFoundError:
#            pass
#        return info

    def _email_info_forwarding(self, target, addrs):
        info = []
        forw = []
        local_copy = ""
        ef = Email.EmailForward(self.db)
        ef.find(target.email_target_id)
        for r in ef.get_forward():
            if r['enable'] == 'T':
                enabled = "on"
            else:
                enabled = "off"
            if r['forward_to'] in addrs:
                local_copy = "+ local delivery (%s)" % enabled
            else:
                forw.append("%s (%s) " % (r['forward_to'], enabled))
        # for aesthetic reasons, print "+ local delivery" last
        if local_copy:
            forw.append(local_copy)
        if forw:
            info.append({'forward_1': forw[0]})
            for idx in range(1, len(forw)):
                info.append({'forward': forw[idx]})
        return info

    # The first address in the list becomes the primary address.
    _interface2addrs = {
        'post': ["%(local_part)s@%(domain)s"],
        'mailcmd': ["%(local_part)s-request@%(domain)s"],
        'mailowner': ["%(local_part)s-owner@%(domain)s",
                      "%(local_part)s-admin@%(domain)s",
                      "owner-%(local_part)s@%(domain)s"]
        }
    _mailman_pipe = "|/local/Mailman/mail/wrapper %(interface)s %(listname)s"
    _mailman_patt = r'\|/local/Mailman/mail/wrapper (\S+) (\S+)$'
    
    def _email_info_mailman(self, addr, et):
        m = re.match(self._mailman_patt, et.email_target_alias)
        if not m:
            raise CerebrumError, ("Unrecognised pipe command for Mailman list:"+
                                  et.email_target_alias)
        # We extract the official list name from the pipe command.
        interface, listname = m.groups()
        ret = [{'mailman_list': listname}]
        if listname.count('@') == 0:
            lp = listname
            dom = addr.split('@')[1]
        else:
            lp, dom = listname.split('@')
        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(dom)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            raise CerebrumError, ("Address %s exists, but the list it points "
                                  "to, %s, does not") % (addr, listname)
        # now find all e-mail addresses
        et.clear()
        et.find(ea.email_addr_target_id)
        addrs = self.__get_valid_email_addrs(et)
        ret += self._email_info_spam(et)
        ret += self._email_info_forwarding(et, addrs)
        aliases = []
        for r in et.get_addresses():
            a = "%(local_part)s@%(domain)s" % r
            if a == listname:
                continue
            aliases.append(a)
        if aliases:
            ret.append({'mailman_alias_1': aliases[0]})
            for idx in range(1, len(aliases)):
                ret.append({'mailman_alias': aliases[idx]})
        # all administrative addresses
        for iface in ('mailcmd', 'mailowner'):
            try:
                et.clear()
                et.find_by_alias(self._mailman_pipe % { 'interface': iface,
                                                        'listname': listname} )
                addrs = et.get_addresses()
                if addrs:
                    ret.append({'mailman_' + iface + '_1':
                                '%(local_part)s@%(domain)s' % addrs[0]})
                    for idx in range(1, len(addrs)):
                        ret.append({'mailman_' + iface:
                                    '%(local_part)s@%(domain)s' % addrs[idx]})
            except Errors.NotFoundError:
                pass
        return ret

    def _email_info_multi(self, addr, et):
        ret = []
        if et.email_target_entity_type != self.const.entity_group:
            ret.append({'multi_forward_gr': 'ENTITY TYPE OF %d UNKNOWN' %
                        et.email_target_entity_id})
        else:
            group = self.Group_class(self.db)
            acc = self.Account_class(self.db)
            try:
                group.find(et.email_target_entity_id)
            except Errors.NotFoundError:
                ret.append({'multi_forward_gr': 'Unknown group %d' %
                            et.email_target_entity_id})
                return ret
            ret.append({'multi_forward_gr': group.group_name})
            u, i, d = group.list_members()
            fwds = []
            for member_type, member_id in u:
                if member_type <> self.const.entity_account:
                    continue
                acc.clear()
                acc.find(member_id)
                try:
                    addr = acc.get_primary_mailaddress()
                except Errors.NotFoundError:
                    addr = "(account %s has no e-mail)" % acc.account_name
                fwds.append(addr)
            if fwds:
                ret.append({'multi_forward_1': fwds[0]})
                for idx in range(1, len(fwds)):
                    ret.append({'multi_forward': fwds[idx]})
        return ret

    def _email_info_file(self, addr, et):
        account_name = "<not set>"
        if et.email_target_using_uid:
            acc = self._get_account(et.email_target_using_uid, idtype='id')
            account_name = acc.account_name
        return [{'file_name': et.get_alias(),
                 'file_runas': account_name}]

    def _email_info_pipe(self, addr, et):
        acc = self._get_account(et.email_target_using_uid, idtype='id')
        data = [{'pipe_cmd': et.get_alias(),
                 'pipe_runas': acc.account_name}]
        return data

    def _email_info_forward(self, addr, et):
        data = []
        # et.email_target_alias isn't used for anything, it's often
        # a copy of one of the forward addresses, but that's just a
        # waste of bytes, really.
        ef = Email.EmailForward(self.db)
        try:
            ef.find(et.email_target_id)
        except Errors.NotFoundError:
            data.append({'fw_addr_1': '<none>', 'fw_enable': 'off'})
        else:
            forw = ef.get_forward()
            if forw:
                data.append({'fw_addr_1': forw[0]['forward_to'],
                             'fw_enable_1': self._onoff(forw[0]['enable'])})
            for idx in range(1, len(forw)):
                data.append({'fw_addr': forw[idx]['forward_to'],
                             'fw_enable': self._onoff(forw[idx]['enable'])})
        return data

    # email create_archive <list-address>
    all_commands['email_create_archive'] = Command(
        ("email", "create_archive"),
        EmailAddress(help_ref="mailman_list"),
        perm_filter="can_email_archive_create")
    def email_create_archive(self, operator, listname):
        """Create e-mail address for archiving messages.  Also adds a
        request to create the needed directories on the web server."""
        lp, dom = self._split_email_address(listname)
        ed = self._get_email_domain(dom)
        self.ba.can_email_archive_create(operator.get_entity_id(), ed)
        self._check_mailman_official_name(listname)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp + "-archive",
                                             ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, ("%s-archive@%s already exists" % (lp, dom))
        archive_user = 'www'
        archive_prog = '/site/mailpipe/bin/new-archive-monthly'
        arch = lp.lower() + "-archive"
        dc = dom.lower().split('.'); dc.reverse()
        archive_dir = "/uit/caesar/mailarkiv/" + ".".join(dc) + "/" + arch
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_pipe,
                    alias="|%s %s" % (archive_prog, archive_dir),
                    using_uid=self._get_account(archive_user).entity_id)
        et.write_db()
        ea = Email.EmailAddress(self.db)
        ea.populate(arch, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        # TODO: add bofh request to run mkdir on www
        return ("OK, now run ssh www 'mkdir -p %s; chown www %s; chmod o= %s'" %
                (archive_dir, archive_dir, archive_dir))

    # email primary_address <address>
    all_commands['email_primary_address'] = Command(
        ("email", "primary_address"),
        EmailAddress(),
        fs=FormatSuggestion([("New primary address: '%s'", ("address", ))]),
        perm_filter="is_postmaster")
    def email_primary_address(self, operator, addr):
        self.ba.is_postmaster(operator.get_entity_id())
        et, ea = self.__get_email_target_and_address(addr)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.email_target_id)
        except Errors.NotFoundError:
            epat.populate(ea.email_addr_id, parent=et)
        else:
            if epat.email_primaddr_id == ea.email_addr_id:
                return "No change: '%s'" % addr
            epat.email_primaddr_id = ea.email_addr_id
        epat.write_db()
        return {'address': addr}

    # email delete_archive <address>
    all_commands['email_delete_archive'] = Command(
        ("email", "delete_archive"),
        EmailAddress(),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_archive_delete")
    def email_delete_archive(self, operator, addr):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        et, acc = self.__get_email_target_and_account(addr)
        if et.email_target_type <> self.const.email_target_pipe:
            raise CerebrumError, "%s: Not an archive target" % addr
        # we can imagine passing along the name of the mailing list
        # to the auth function in the future.
        self.ba.can_email_archive_delete(operator.get_entity_id(), ed)
        # All OK, let's nuke it all.
        result = []
        ea = Email.EmailAddress(self.db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            result.append({'address': self.__get_address(ea)})
            ea.delete()
        et.delete()
        return result

    # email create_pipe <address> <uname> <command>
    all_commands['email_create_pipe'] = Command(
        ("email", "create_pipe"),
        EmailAddress(help_ref="email_address"),
        AccountName(),
        SimpleString(help_ref="command_line"),
        perm_filter="can_email_pipe_create")
    def email_create_pipe(self, operator, addr, uname, cmd):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_create(operator.get_entity_id(), ed)
        acc = self._get_account(uname)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "%s already exists" % addr
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_pipe, alias="|"+cmd,
                    using_uid=acc.entity_id)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        return "OK, created pipe address %s" % addr

    # email edit_pipe_command <address> <command>
    all_commands['email_edit_pipe_command'] = Command(
        ("email", "edit_pipe_command"),
        EmailAddress(),
        SimpleString(help_ref="command_line"),
        perm_filter="can_email_pipe_edit")
    def email_edit_pipe_command(self, operator, addr, cmd):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_edit(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            raise CerebrumError, "%s: No such address exists" % addr
        et = Email.EmailTarget(self.db)
        et.find(ea.email_addr_target_id)
        if et.email_target_type != self.const.email_target_pipe:
            raise CerebrumError, "%s is not connected to a pipe target" % addr
        et.email_target_alias = cmd
        et.write_db()
        return "OK, edited %s" % addr

    # email edit_pipe_user <address> <uname>
    all_commands['email_edit_pipe_user'] = Command(
        ("email", "edit_pipe_user"),
        EmailAddress(),
        AccountName(),
        perm_filter="can_email_pipe_edit")
    def email_edit_pipe_user(self, operator, addr, uname):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        self.ba.can_email_pipe_edit(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            raise CerebrumError, "%s: No such address exists" % addr
        et = Email.EmailTarget(self.db)
        et.find(ea.email_addr_target_id)
        if et.email_target_type != self.const.email_target_pipe:
            raise CerebrumError, "%s is not connected to a pipe target" % addr
        et.email_target_using_uid = self._get_account(uname).entity_id
        et.write_db()
        return "OK, edited %s" % addr

    # email create_domain <domainname> <description>
    all_commands['email_create_domain'] = Command(
        ("email", "create_domain"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="string_description"),
        perm_filter="can_email_domain_create")
    def email_create_domain(self, operator, domainname, desc):
        """Create e-mail domain."""
        self.ba.can_email_archive_delete(operator.get_entity_id())
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(domainname)
            raise CerebrumError, "%s: e-mail domain already exists" % domainname
        except Errors.NotFoundError:
            pass
        if not re.match(r'[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+', domainname):
            raise CerebrumError, "%s: illegal e-mail domain name" % domainname
        if len(desc) < 3:
            raise CerebrumError, "Please supply a better description"
        ed.populate(domainname, desc)
        ed.write_db()
        return "OK, domain '%s' created" % domainname

    # email domain_configuration on|off <domain> <category>+
    all_commands['email_domain_configuration'] = Command(
        ("email", "domain_configuration"),
        SimpleString(help_ref="on_or_off"),
        SimpleString(help_ref="email_domain"),
        SimpleString(help_ref="email_category", repeat=True),
        perm_filter="can_email_domain_create")
    def email_domain_configuration(self, operator, onoff, domainname, cat):
        """Change configuration for an e-mail domain."""
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        on = self._get_boolean(onoff)
        catcode = None
        for c in self.const.fetch_constants(_EmailDomainCategoryCode):
            if str(c).lower().startswith(cat.lower()):
                if catcode:
                    raise CerebrumError, ("'%s' does not uniquely identify "+
                                          "a configuration category") % cat
                catcode = c
        if catcode is None:
            raise CerebrumError, ("'%s' does not match any configuration "+
                                  "category") % cat
        if self._sync_category(ed, catcode, on):
            return "%s is now %s" % (str(catcode), onoff.lower())
        else:
            return "%s unchanged" % str(catcode)

    def _get_boolean(self, onoff):
        if onoff.lower() in ('on', 'true', 'yes'):
            return True
        elif onoff.lower() in ('off', 'false', 'no'):
            return False
        raise CerebrumError, "Enter one of ON or OFF, not %s" % onoff

    def _onoff(self, enable):
        if enable:
            return 'on'
        else:
            return 'off'

    def _has_category(self, domain, category):
        ccode = int(category)
        for r in domain.get_categories():
            if r['category'] == ccode:
                return True
        return False

    def _sync_category(self, domain, category, enable):
        """Enable or disable category with EmailDomain.  Returns False
        for no change or True for change."""
        if self._has_category(domain, category) == enable:
            return False
        if enable:
            domain.add_category(category)
        else:
            domain.remove_category(category)
        return True

    # email domain_info <domain>
    # this command is accessible for all
    all_commands['email_domain_info'] = Command(
        ("email", "domain_info"),
        SimpleString(help_ref="email_domain"),
        fs=FormatSuggestion([
        ("E-mail domain:    %s\n"+
         "Description:      %s",
         ("domainname", "description")),
        ("Configuration:    %s",
         ("category",)),
        ("Affiliation:      %s@%s",
         ("affil", "ou"))]))
    def email_domain_info(self, operator, domainname):
        ed = self._get_email_domain(domainname)
        ret = []
        ret.append({'domainname': domainname,
                    'description': ed.email_domain_description})
        for r in ed.get_categories():
            ret.append({'category': str(self.num2const[r['category']])})
        eed = Email.EntityEmailDomain(self.db)
        affiliations = {}
        for r in eed.list_affiliations(ed.email_domain_id):
            ou = self._get_ou(r['entity_id'])
            affname = "<any>"
            if r['affiliation']:
                affname = str(self.num2const[int(r['affiliation'])])
            affiliations[self._format_ou_name(ou)] = affname
        aff_list = affiliations.keys()
        aff_list.sort()
        for ou in aff_list:
            ret.append({'affil': affiliations[ou], 'ou': ou})
        return ret

    # email add_domain_affiliation <domain> <stedkode> [<affiliation>]
    all_commands['email_add_domain_affiliation'] = Command(
        ("email", "add_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(), Affiliation(optional=True),
        perm_filter="can_email_domain_create")
    def email_add_domain_affiliation(self, operator, domainname, sko, aff=None):
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        try:
            ou = self._get_ou(stedkode=sko)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % sko
        aff_id = None
        if aff:
            aff_id = int(self._get_affiliationid(aff))
        eed = Email.EntityEmailDomain(self.db)
        try:
            eed.find(ou.entity_id, aff_id)
        except Errors.NotFoundError:
            # We have a partially initialised object, since
            # the super() call finding the OU always succeeds.
            # Therefore we must not call clear()
            eed.populate_email_domain(ed.email_domain_id, aff_id)
            eed.write_db()
            count = self._update_email_for_ou(ou.entity_id, aff_id)
            # Perhaps we should return the values with a format
            # suggestion instead, but the message is informational,
            # and we have three different formats so it would be
            # awkward to do "right".
            return "OK, %d accounts updated" % count
        else:
            old_dom = eed.entity_email_domain_id
            if old_dom <> ed.email_domain_id:
                eed.entity_email_domain_id = ed.email_domain_id
                eed.write_db()
                count = self._update_email_for_ou(ou.entity_id, aff_id)
                ed.clear()
                ed.find(old_dom)
                return "OK (was %s), %d accounts updated" % \
                       (ed.email_domain_name, count)
            return "OK (no change)"

    def _update_email_for_ou(self, ou_id, aff_id):
        """Updates the e-mail addresses for all accounts where the
        given affiliation is their primary, and returns the number of
        modified accounts."""

        count = 0
        acc = self.Account_class(self.db)
        acc2 = self.Account_class(self.db)
        for r in acc.list_accounts_by_type(ou_id=ou_id, affiliation=aff_id):
            acc2.clear()
            acc2.find(r['account_id'])
            primary = acc2.get_account_types()[0]
            if (ou_id == primary['ou_id'] and
                (aff_id is None or aff_id == primary['affiliation'])):
                acc2.update_email_addresses()
                count += 1
        return count

    # email remove_domain_affiliation <domain> <stedkode> [<affiliation>]
    all_commands['email_remove_domain_affiliation'] = Command(
        ("email", "remove_domain_affiliation"),
        SimpleString(help_ref="email_domain"),
        OU(), Affiliation(optional=True),
        perm_filter="can_email_domain_create")
    def email_remove_domain_affiliation(self, operator, domainname, sko,
                                        aff=None):
        self.ba.can_email_domain_create(operator.get_entity_id())
        ed = self._get_email_domain(domainname)
        try:
            ou = self._get_ou(stedkode=sko)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % sko
        aff_id = None
        if aff:
            aff_id = int(self._get_affiliationid(aff))
        eed = Email.EntityEmailDomain(self.db)
        try:
            eed.find(ou.entity_id, aff_id)
        except Errors.NotFoundError:
            raise CerebrumError, "No such affiliation for domain"
        if eed.entity_email_domain_id <> ed.email_domain_id:
            raise CerebrumError, "No such affiliation for domain"
        eed.delete()
        return "OK, removed domain-affiliation for '%s'" % domainname

    # email create_forward <local-address> <remote-address>
    all_commands['email_create_forward'] = Command(
        ("email", "create_forward"),
        EmailAddress(),
        EmailAddress(),
        perm_filter="can_email_forward_create")
    def email_create_forward(self, operator, localaddr, remoteaddr):
        """Create a forward target, add localaddr as an address
        associated with that target, and add remoteaddr as a forward
        addresses."""
        lp, dom = self._split_email_address(localaddr)
        ed = self._get_email_domain(dom)
        self.ba.can_email_forward_create(operator.get_entity_id(), ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "Address %s already exists" % localaddr
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_forward)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        epat.populate(ea.email_addr_id, parent=et)
        epat.write_db()
        ef = Email.EmailForward(self.db)
        ef.find(et.email_target_id)
        addr = self._check_email_address(remoteaddr)
        try:
            ef.add_forward(addr)
        except Errors.TooManyRowsError:
            raise CerebrumError, "Forward address added already (%s)" % addr
        return "OK, created forward address '%s'" % localaddr

    # email create_list <list-address> [admin,admin,admin]
    all_commands['email_create_list'] = Command(
        ("email", "create_list"),
        EmailAddress(help_ref="mailman_list"),
        SimpleString(help_ref="mailman_admins", optional=True),
        perm_filter="can_email_list_create")
    def email_create_list(self, operator, listname, admins = None):
        """Create the e-mail addresses 'listname' needs to be a Mailman
        list.  Also adds a request to create the list on the Mailman
        server."""
        lp, dom = self._split_email_address(listname)
        ed = self._get_email_domain(dom)
        op = operator.get_entity_id()
        self.ba.can_email_list_create(op, ed)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "Address %s already exists" % listname
        try:
            self._get_account(lp)
        except CerebrumError:
            pass
        else:
            if lp not in ('drift',):
                # TBD: This exception list should probably not be
                # hardcoded here -- but it's not obvious whether it
                # should be a cereconf value (implying that only site
                # admins can modify the list) or a database table.
                raise CerebrumError, ("Won't create list %s, as %s is an "
                                      "existing username") % (listname, lp)
        self._register_list_addresses(listname, lp, dom)
        if admins:
            br = BofhdRequests(self.db, self.const)
            ea.clear()
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
            list_id = ea.email_addr_id
            admin_list = []
            for addr in admins.split(","):
                if addr.count('@') == 0:
                    admin_list.append(addr + "@ulrik.uit.no")
                else:
                    admin_list.append(addr)
            ea.clear()
            try:
                ea.find_by_address(admin_list[0])
            except Errors.NotFoundError:
                raise CerebrumError, "%s: unknown address" % admin_list[0]
            req = br.add_request(op, br.now, self.const.bofh_mailman_create,
                                 list_id, ea.email_addr_id, None)
            for addr in admin_list[1:]:
                ea.clear()
                try:
                    ea.find_by_address(addr)
                except Errors.NotFoundError:
                    raise CerebrumError, "%s: unknown address" % addr
                br.add_request(op, br.now, self.const.bofh_mailman_add_admin,
                               list_id, ea.email_addr_id, str(req))
        return "OK, list '%s' created" % listname

    # email create_list_alias <list-address> <new-alias>
    all_commands['email_create_list_alias'] = Command(
        ("email", "create_list_alias"),
        EmailAddress(help_ref="mailman_list_exist"),
        EmailAddress(help_ref="mailman_list"),
        perm_filter="can_email_list_create")
    def email_create_list_alias(self, operator, listname, address):
        """Create a secondary name for an existing Mailman list."""
        lp, dom = self._split_email_address(address)
        ed = self._get_email_domain(dom)
        self.ba.can_email_list_create(operator.get_entity_id(), ed)
        self._check_mailman_official_name(listname)
        try:
            self._get_account(lp)
        except CerebrumError:
            pass
        else:
            raise CerebrumError, ("Won't create list %s, as %s is an "
                                  "existing username") % (address, lp)
        # we _don't_ check for "more than 8 characters in local
        # part OR it contains hyphen" since we assume the people
        # who have access to this command know what they are doing
        self._register_list_addresses(listname, lp, dom)
        return "OK, list-alias '%s' created" % listname

    # email delete_list <list-address>
    all_commands['email_delete_list'] = Command(
        ("email", "delete_list"),
        EmailAddress(help_ref="mailman_list"),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_list_delete")
    def email_delete_list(self, operator, listname):
        lp, dom = self._split_email_address(listname)
        ed = self._get_email_domain(dom)
        op = operator.get_entity_id()
        self.ba.can_email_list_delete(op, ed)
        listname = self._check_mailman_official_name(listname)
        # All OK, let's nuke it all.
        result = []
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        list_id = ea.email_addr_id
        for interface in self._interface2addrs.keys():
            alias = self._mailman_pipe % { 'interface': interface,
                                           'listname': listname }
            try:
                et.clear()
                et.find_by_alias(alias)
                epat.clear()
                try:
                    epat.find(et.email_target_id)
                except Errors.NotFoundError:
                    pass
                else:
                    epat.delete()
                for r in et.get_addresses():
                    addr = '%(local_part)s@%(domain)s' % r
                    ea.clear()
                    ea.find_by_address(addr)
                    ea.delete()
                    result.append({'address': addr})
                et.delete()
            except Errors.NotFoundError:
                pass
        br = BofhdRequests(self.db, self.const)
        br.add_request(op, br.now, self.const.bofh_mailman_remove,
                       list_id, None, listname)
        return result

    def _split_email_address(self, addr):
        if addr.count('@') == 0:
            raise CerebrumError, \
                  "E-mail address (%s) must include domain" % addr
        lp, dom = addr.split('@')
        if addr != addr.lower() and \
           dom not in cereconf.LDAP['rewrite_email_domain']:
            raise CerebrumError, \
                  "E-mail address (%s) can't contain upper case letters" % addr
        return lp, dom

    def _get_mailman_list(self, listname):
        """Returns the official name for the list, or raise an error
        if listname isn't a Mailman list."""
        try:
            ea = Email.EmailAddress(self.db)
            ea.find_by_address(listname)
        except Errors.NotFoundError:
            raise CerebrumError, "No such mailman list %s" % listname
        et = Email.EmailTarget(self.db)
        et.find(ea.get_target_id())
        if not et.email_target_alias:
            raise CerebrumError, "%s isn't a Mailman list" % listname
        m = re.match(self._mailman_patt, et.email_target_alias)
        if not m:
            raise CerebrumError, ("Unrecognised pipe command for Mailman list:"+
                                  et.email_target_alias)
        return m.group(2)
    
    def _check_mailman_official_name(self, listname):
        mlist = self._get_mailman_list(listname)
        if mlist is None:
            raise CerebrumError, "%s is not a Mailman list" % listname
        # List names without complete e-mail address are probably legacy
        if (mlist.count('@') == 0 and listname.startswith(mlist + "@")
            or listname == mlist):
            return mlist
        raise CerebrumError, ("%s is not the official name of the list %s" %
                              (listname, mlist))

    def _register_list_addresses(self, listname, lp, dom):
        """Add list, owner and request addresses.  listname is the
        name in Mailman, which may be different from lp@dom, which is
        the basis for the local parts and domain of the addresses
        which should be added."""
        
        ed = Email.EmailDomain(self.db)
        ed.find_by_domain(dom)

        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, ("The address %s@%s is already in use" %
                                  (lp, dom))

        mailman = self._get_account("mailman", actype="PosixUser")

        for interface in self._interface2addrs.keys():
            targ = self._mailman_pipe % { 'interface': interface,
                                          'listname': listname }
            found_target = False
            for addr_format in self._interface2addrs[interface]:
                addr = addr_format % {'local_part': lp,
                                      'domain': dom}
                addr_lp, addr_dom = addr.split('@')
                # all addresses are in same domain, do an EmailDomain
                # lookup here if  _interface2addrs changes:
                try:
                    ea.clear()
                    ea.find_by_local_part_and_domain(addr_lp,
                                                     ed.email_domain_id)
                    raise CerebrumError, ("Can't add list %s, as the "
                                          "address %s is already in use"
                                          ) % (newaddr, addr)
                except Errors.NotFoundError:
                    pass
                if not found_target:
                    et.clear()
                    try:
                        et.find_by_alias_and_account(targ, mailman.entity_id)
                    except Errors.NotFoundError:
                        et.populate(self.const.email_target_Mailman,
                                    alias=targ, using_uid=mailman.entity_id)
                        et.write_db()
                ea.clear()
                ea.populate(addr_lp, ed.email_domain_id, et.email_target_id)
                ea.write_db()
                if not found_target:
                    epat.clear()
                    try:
                        epat.find(et.email_target_id)
                    except Errors.NotFoundError:
                        epat.clear()
                        epat.populate(ea.email_addr_id, parent=et)
                        epat.write_db()
                    found_target = True


    # email create_multi <multi-address> <group>
    all_commands['email_create_multi'] = Command(
        ("email", "create_multi"),
        EmailAddress(help_ref="email_address"),
        GroupName(help_ref="group_name_dest"),
        perm_filter="can_email_multi_create")
    def email_create_multi(self, operator, addr, group):
        """Create en e-mail target of type 'multi' expanding to
        members of group, and associate the e-mail address with this
        target."""
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        gr = self._get_group(group)
        self.ba.can_email_multi_create(operator.get_entity_id(), ed, gr)
        ea = Email.EmailAddress(self.db)
        try:
            ea.find_by_local_part_and_domain(lp, ed.email_domain_id)
        except Errors.NotFoundError:
            pass
        else:
            raise CerebrumError, "Address <%s> is already in use" % addr
        et = Email.EmailTarget(self.db)
        et.populate(self.const.email_target_multi,
                    entity_type = self.const.entity_group,
                    entity_id = gr.entity_id)
        et.write_db()
        ea.clear()
        ea.populate(lp, ed.email_domain_id, et.email_target_id)
        ea.write_db()
        epat = Email.EmailPrimaryAddressTarget(self.db)
        epat.populate(ea.email_addr_id, parent=et)
        epat.write_db()
        return "OK, multi-target for '%s' created" % addr

    # email delete_multi <address>
    all_commands['email_delete_multi'] = Command(
        ("email", "delete_multi"),
        EmailAddress(help_ref="email_address"),
        fs=FormatSuggestion([("Deleted address: %s", ("address", ))]),
        perm_filter="can_email_multi_delete")
    def email_delete_multi(self, operator, addr):
        lp, dom = self._split_email_address(addr)
        ed = self._get_email_domain(dom)
        et, acc = self.__get_email_target_and_account(addr)
        if et.email_target_type <> self.const.email_target_multi:
            raise CerebrumError, "%s: Not a multi target" % addr
        if et.email_target_entity_type <> self.const.entity_group:
            raise CerebrumError, "%s: Does not point to a group!" % addr
        gr = self._get_group(et.email_target_entity_id, idtype="id")
        self.ba.can_email_multi_delete(operator.get_entity_id(), ed, gr)
        epat = Email.EmailPrimaryAddressTarget(self.db)
        try:
            epat.find(et.email_target_id)
        except Errors.NotFoundError:
            # a multi target does not need a primary address
            pass
        else:
            # but if one exists, we require the user to supply that
            # address, not an arbitrary alias.
            if addr <> self.__get_address(epat):
                raise CerebrumError, ("%s is not the primary address of "+
                                      "the target") % addr
            epat.delete()
        # All OK, let's nuke it all.
        result = []
        ea = Email.EmailAddress(self.db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            result.append({'address': self.__get_address(ea)})
            ea.delete()
        return result

    # email create_rt queue address [host]
    # email delete_rt queue

    # email add_rt_address queue address
    # email remove_rt_address queue address
    #   duplicates email {add,remove}_address.  not necessary until
    #   someone other than postmaster needs this privelege.
    
    # email migrate
    all_commands['email_migrate'] = Command(
        ("email", "migrate"),
        AccountName(help_ref="account_name", repeat=True),
        perm_filter='can_email_migrate')
    def email_migrate(self, operator, uname):
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_migrate(op, acc)
        for r in acc.get_spread():
            if r['spread'] == int(self.const.spread_uit_imap):
                raise CerebrumError, "%s is already an IMAP user" % uname
        acc.add_spread(self.const.spread_uit_imap)
        if op <> acc.entity_id:
            # the local sysadmin should get a report as well, if
            # possible, so change the request add_spread() put in so
            # that he is named as the requestee.  the list of requests
            # may turn out to be empty, ie. processed already, but this
            # unlikely race condition is too hard to fix.
            br = BofhdRequests(self.db, self.const)
            for r in br.get_requests(operation=self.const.bofh_email_move,
                                     entity_id=acc.entity_id):
                br.delete_request(request_id=r['request_id'])
                br.add_request(op, r['run_at'], r['operation'], r['entity_id'],
                               r['destination_id'], r['state_data'])
        return 'OK'

    # email move
    all_commands['email_move'] = Command(
        ("email", "move"),
        AccountName(help_ref="account_name", repeat=True),
        SimpleString(help_ref='string_email_host'),
        perm_filter='can_email_move')
    def email_move(self, operator, uname, server):
        acc = self._get_account(uname)
        self.ba.can_email_move(operator.get_entity_id(), acc)
        et = Email.EmailTarget(self.db)
        et.find_by_entity(acc.entity_id)
        old_server = et.email_server_id
        es = Email.EmailServer(self.db)
        es.find_by_name(server)
        if old_server == es.entity_id:
            raise CerebrumError, "User is already at %s" % server
        et.email_server_id = es.entity_id
        et.write_db()
        if es.email_server_type == self.const.email_server_type_cyrus:
            spreads = [int(r['spread']) for r in acc.get_spread()]
            br = BofhdRequests(self.db, self.const)
            if not self.const.spread_uit_imap in spreads:
                # uit's add_spread mixin will not do much since
                # EmailTarget is set to a Cyrus server already.
                acc.add_spread(self.const.spread_uit_imap)
            # Create the mailbox.
            req = br.add_request(operator.get_entity_id(), br.now,
                                 self.const.bofh_email_create,
                                 acc.entity_id, et.email_server_id)
            # Now add a move request.
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_email_move,
                           acc.entity_id, old_server, state_data=req)
        else:
            # TBD: should we remove spread_uit_imap ?
            # It does not do much good to add to a bofh request, mvmail
            # can't handle this anyway.
            raise CerebrumError, "can't move to non-IMAP server" 
        return "OK, '%s' scheduled for move to '%s'" % (uname, server)

    # email quota <uname>+ hardquota-in-mebibytes [softquota-in-percent]
    all_commands['email_quota'] = Command(
        ('email', 'quota'),
        AccountName(help_ref='account_name', repeat=True),
        Integer(help_ref='number_size_mib'),
        Integer(help_ref='number_percent', optional=True),
        perm_filter='can_email_set_quota')
    def email_quota(self, operator, uname, hquota,
                    squota=cereconf.EMAIL_SOFT_QUOTA):
        acc = self._get_account(uname)
        op = operator.get_entity_id()
        self.ba.can_email_set_quota(op, acc)
        if not hquota.isdigit() or not str(squota).isdigit():
            raise CerebrumError, "Quota must be numeric"
        hquota = int(hquota)
        squota = int(squota)
        if hquota < 100:
            raise CerebrumError, "The hard quota can't be less than 100 MiB"
        if hquota > 1024*1024:
            raise CerebrumError, "The hard quota can't be more than 1 TiB"
        if squota < 10 or squota > 99:
            raise CerebrumError, ("The soft quota must be in the interval "+
                                  "10% to 99%")
        et = Email.EmailTarget(self.db)
        try:
            et.find_by_entity(acc.entity_id)
        except Errors.NotFoundError:
            raise CerebrumError, ("The account %s has no e-mail data "+
                                  "associated with it") % uname
        eq = Email.EmailQuota(self.db)
        change = False
        try:
            eq.find_by_entity(acc.entity_id)
            if eq.email_quota_hard <> hquota:
                change = True
            eq.email_quota_hard = hquota
            eq.email_quota_soft = squota
        except Errors.NotFoundError:
            eq.clear()
            eq.populate(squota, hquota, parent=et)
            change = True
        eq.write_db()
        if change:
            # If we're supposed to put a request in BofhdRequests we'll have to
            # be sure that the user getting the quota is a Cyrus-user. If not,
            # Cyrus will spew out errors telling us "user foo is not a cyrus-user".
            if not et.email_server_id:
                raise CerebrumError, ("The account %s has no e-mail server "+
                                      "associated with it") % uname
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
                    
            if es.email_server_type == self.const.email_server_type_cyrus:
                br = BofhdRequests(self.db, self.const)
                # if this operator has already asked for a quota change, but
                # process_bofh_requests hasn't run yet, delete the existing
                # request to avoid the annoying error message.
                for r in br.get_requests(operation=self.const.bofh_email_hquota,
                                         operator_id=op, entity_id=acc.entity_id):
                    br.delete_request(request_id=r['request_id'])
                br.add_request(op, br.now, self.const.bofh_email_hquota,
                               acc.entity_id, None)
        return "OK, set quota for '%s'" % uname

    # email spam_level <level> <uname>+
    all_commands['email_spam_level'] = Command(
        ('email', 'spam_level'),
        SimpleString(help_ref='spam_level'),
        AccountName(help_ref='account_name', repeat=True),
        perm_filter='can_email_spam_settings')
    def email_spam_level(self, operator, level, uname):
        """Set the spam level for the EmailTarget associated with username.
        It is also possible for super users to pass the name of a mailing
        list."""
        codes = self.const.fetch_constants(self.const.EmailSpamLevel,
                                           prefix_match=level)
        if len(codes) == 1:
            levelcode = codes[0]
        elif len(codes) == 0:
            raise CerebrumError, "Spam level code not found: %s" % level
        else:
            raise CerebrumError, ("'%s' does not uniquely identify a spam "+
                                  "level") % level
        et, acc = self.__get_email_target_and_account(uname)
        self.ba.can_email_spam_settings(operator.get_entity_id(), acc, et)
        esf = Email.EmailSpamFilter(self.db)
        try:
            esf.find(et.email_target_id)
            esf.email_spam_level = levelcode
        except Errors.NotFoundError:
            esf.clear()
            esf.populate(levelcode, self.const.email_spam_action_none,
                         parent=et)
        esf.write_db()
        return "OK, set spam-level for '%s'" % uname

    # email spam_action <action> <uname>+
    # 
    # (This code is cut'n'paste of email_spam_level(), only the call
    # to populate() had to be fixed manually.  It's hard to fix this
    # kind of code duplication cleanly.)
    all_commands['email_spam_action'] = Command(
        ('email', 'spam_action'),
        SimpleString(help_ref='spam_action'),
        AccountName(help_ref='account_name', repeat=True),
        perm_filter='can_email_spam_settings')
    def email_spam_action(self, operator, action, uname):
        """Set the spam action for the EmailTarget associated with username.
        It is also possible for super users to pass the name of a mailing
        list."""
        codes = self.const.fetch_constants(self.const.EmailSpamAction,
                                           prefix_match=action)
        if len(codes) == 1:
            actioncode = codes[0]
        elif len(codes) == 0:
            raise CerebrumError, "Spam action code not found: %s" % action
        else:
            raise CerebrumError, ("'%s' does not uniquely identify a spam "+
                                  "action") % action
        et, acc = self.__get_email_target_and_account(uname)
        self.ba.can_email_spam_settings(operator.get_entity_id(), acc, et)
        esf = Email.EmailSpamFilter(self.db)
        try:
            esf.find(et.email_target_id)
            esf.email_spam_action = actioncode
        except Errors.NotFoundError:
            esf.clear()
            esf.populate(self.const.email_spam_level_none, actioncode,
                         parent=et)
        esf.write_db()
        return "OK, set spam-action for '%s'" % uname

    # email tripnote on|off <uname> [<begin-date>]
    all_commands['email_tripnote'] = Command(
        ('email', 'tripnote'),
        SimpleString(help_ref='email_tripnote_action'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_toggle')
    def email_tripnote(self, operator, action, uname, when=None):
        if action == 'on':
            enable = True
        elif action == 'off':
            enable = False
        else:
            raise CerebrumError, ("Unknown tripnote action '%s', choose one "+
                                  "of on or off") % action
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_toggle(operator.get_entity_id(), acc)
        ev = Email.EmailVacation(self.db)
        ev.find_by_entity(acc.entity_id)
        # TODO: If 'enable' at this point actually is None (which, by
        # the looks of the if-else clause at the top seems
        # impossible), opposite_status won't be defined, and hence the
        # ._find_tripnote() call below will fail.
        if enable is not None:
            opposite_status = not enable
        date = self._find_tripnote(uname, ev, when, opposite_status)
        ev.enable_vacation(date, enable)
        ev.write_db()
        return "OK, set tripnote to '%s' for '%s'" % (action, uname)

    all_commands['email_list_tripnotes'] = Command(
        ('email', 'list_tripnotes'),
        AccountName(help_ref='account_name'),
        perm_filter='can_email_tripnote_toggle',
        fs=FormatSuggestion([
        ('%s%s -- %s: %s\n%s\n',
         ("dummy", format_day('start_date'), format_day('end_date'),
          "enable", "text"))]))
    def email_list_tripnotes(self, operator, uname):
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_toggle(operator.get_entity_id(), acc)
        try:
            self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
            hide = False
        except:
            hide = True
        ev = Email.EmailVacation(self.db)
        ev.find_by_entity(acc.entity_id)
        now = self._today()
        act_date = None
        for r in ev.get_vacation():
            if r['end_date'] is not None and r['start_date'] > r['end_date']:
                self.logger.warn(
                    "bogus tripnote for %s, start at %s, end at %s"
                    % (uname, r['start_date'], r['end_date']))
                ev.delete_vacation(r['start_date'])
                ev.write_db()
                continue
            if r['enable'] == 'F':
                continue
            if r['end_date'] is not None and r['end_date'] < now:
                continue
            if r['start_date'] > now:
                break
            # get_vacation() returns a list ordered by start_date, so
            # we know this one is newer.
            act_date = r['start_date']
        result = []
        for r in ev.get_vacation():
            text = r['vacation_text']
            if r['enable'] == 'F':
                enable = "OFF"
            elif r['end_date'] is not None and r['end_date'] < now:
                enable = "OLD"
            elif r['start_date'] > now:
                enable = "PENDING"
            else:
                enable = "ON"
            if act_date is not None and r['start_date'] == act_date:
                enable = "ACTIVE"
            elif hide:
                text = "<text is hidden>"
            lines = text.split('\n')
            if len(lines) > 3:
                lines[2] += "[...]"
            text = '\n'.join(lines[:3])
            # TODO: FormatSuggestion won't work with a format_day()
            # coming first, so we use an empty dummy string as a
            # workaround.
            result.append({'dummy': "",
                           'start_date': r['start_date'],
                           'end_date': r['end_date'],
                           'enable': enable,
                           'text': text})
        if result:
            return result
        else:
            return "No tripnotes for %s" % uname
    
    # email add_tripnote <uname> <text> <begin-date>[-<end-date>]
    all_commands['email_add_tripnote'] = Command(
        ('email', 'add_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='tripnote_text'),
        SimpleString(help_ref='string_from_to'),
        perm_filter='can_email_tripnote_edit')
    def email_add_tripnote(self, operator, uname, text, when=None):
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
        date_start, date_end = self._parse_date_from_to(when)
        now = self._today()
        if date_end is not None and date_end < now:
            raise CerebrumError, "Won't add already obsolete tripnotes"
        ev = Email.EmailVacation(self.db)
        ev.find_by_entity(acc.entity_id)
        for v in ev.get_vacation():
            if date_start is not None and v['start_date'] == date_start:
                raise CerebrumError, ("There's a tripnote starting on %s "+
                                      "already") % str(date_start)[:10]
        text = text.replace('\\n', '\n')
        ev.add_vacation(date_start, text, date_end, enable=True)
        ev.write_db()
        return "OK, added tripnote for '%s'" % uname

    # email remove_tripnote <uname> [<when>]
    all_commands['email_remove_tripnote'] = Command(
        ('email', 'remove_tripnote'),
        AccountName(help_ref='account_name'),
        SimpleString(help_ref='date', optional=True),
        perm_filter='can_email_tripnote_edit')
    def email_remove_tripnote(self, operator, uname, when=None):
        acc = self._get_account(uname)
        self.ba.can_email_tripnote_edit(operator.get_entity_id(), acc)
        # TBD: This variable isn't used; is this call a sign of rot,
        # or is it here for input validation?
        start = self._parse_date(when)
        ev = Email.EmailVacation(self.db)
        ev.find_by_entity(acc.entity_id)
        date = self._find_tripnote(uname, ev, when)
        ev.delete_vacation(date)
        ev.write_db()
        return "OK, removed tripnote for '%s'" % uname

    def _find_tripnote(self, uname, ev, when=None, enabled=None):
        vacs = ev.get_vacation()
        if enabled is not None:
            nv = []
            for v in vacs:
                if (v['enable'] == 'T') == enabled:
                    nv.append(v)
            vacs = nv
        if len(vacs) == 0:
            if enabled is None:
                raise CerebrumError, "User %s has no stored tripnotes" % uname
            elif enabled:
                raise CerebrumError, "User %s has no enabled tripnotes" % uname
            else:
                raise CerebrumError, "User %s has no disabled tripnotes" % uname
        elif len(vacs) == 1:
            return vacs[0]['start_date']
        elif when is None:
            raise CerebrumError, ("User %s has more than one tripnote, "+
                                  "specify which one by adding the "+
                                  "start date to command") % uname
        start = self._parse_date(when)
        best = None
        for r in vacs:
            delta = abs (r['start_date'] - start)
            if best is None or delta < best_delta:
                best = r['start_date']
                best_delta = delta
        # TODO: in PgSQL, date arithmetic is in days, but casting
        # it to int returns seconds.  The behaviour is undefined
        # in the DB-API.
        if abs(int(best_delta)) > 1.5*86400:
            raise CerebrumError, ("There are no tripnotes starting "+
                                  "at %s") % when
        return best

    # email update <uname>
    # Anyone can run this command.  Ideally, it should be a no-op,
    # and we should remove it when that is true.
    all_commands['email_update'] = Command(
        ('email', 'update'),
        AccountName(help_ref='account_name', repeat=True))
    def email_update(self, operator, uname):
        acc = self._get_account(uname)
        acc.update_email_addresses()
        return "OK, updated e-mail address for '%s'" % uname

    # (email virus)

    def __get_email_target_and_address(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the address object.  If there is no at-sign
        in address, assume it is an account name and return primary
        address.  Raises CerebrumError if address is unknown.
        """
        et = Email.EmailTarget(self.db)
        ea = Email.EmailAddress(self.db)
        if address.count('@') == 0:
            acc = self.Account_class(self.db)
            try:
                acc.find_by_name(address)
                # FIXME: We can't use Account.get_primary_mailaddress
                # since it rewrites special domains.
                et = Email.EmailTarget(self.db)
                et.find_by_entity(acc.entity_id)
                epa = Email.EmailPrimaryAddressTarget(self.db)
                epa.find(et.email_target_id)
                ea.find(epa.email_primaddr_id)
            except Errors.NotFoundError:
                raise CerebrumError, ("No such address: '%s'" % address)
        elif address.count('@') == 1:
            try:
                ea.find_by_address(address)
                et.find(ea.email_addr_target_id)
            except Errors.NotFoundError:
                raise CerebrumError, "No such address: '%s'" % address
        else:
            raise CerebrumError, "Malformed e-mail address (%s)" % address
        return et, ea

    def __get_email_target_and_account(self, address):
        """Returns a tuple consisting of the email target associated
        with address and the account if the target type is user.  If
        there is no at-sign in address, assume it is an account name.
        Raises CerebrumError if address is unknown."""
        et, ea = self.__get_email_target_and_address(address)
        acc = None
        if et.email_target_type in (self.const.email_target_account,
                                    self.const.email_target_deleted):
            acc = self._get_account(et.email_target_entity_id, idtype='id')
        return et, acc
    
    def __get_address(self, etarget):
        """The argument can be
        - EmailPrimaryAddressTarget
        - EmailAddress
        - EmailTarget (look up primary address and return that, throw
        exception if there is no primary address)
        - integer (use as email_target_id and look up that target's
        primary address)
        The return value is a text string containing the e-mail
        address.  Special domain names are not rewritten."""
        ea = Email.EmailAddress(self.db)
        if isinstance(etarget, (int, long, float)):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            # may throw exception, let caller handle it
            epat.find(etarget)
            ea.find(epat.email_primaddr_id)
        elif isinstance(etarget, Email.EmailTarget):
            epat = Email.EmailPrimaryAddressTarget(self.db)
            epat.find(etarget.email_target_id)
            ea.find(epat.email_primaddr_id)
        elif isinstance(etarget, Email.EmailPrimaryAddressTarget):
            ea.find(etarget.email_primaddr_id)
        elif isinstance(etarget, Email.EmailAddress):
            ea = etarget
        else:
            raise ValueError, "Unknown argument (%s)" % repr(etarget)
        ed = Email.EmailDomain(self.db)
        ed.find(ea.email_addr_domain_id)
        return ("%s@%s" % (ea.email_addr_local_part,
                           ed.email_domain_name))

    #
    # entity commands
    #
    all_commands['entity_info'] = None
    def entity_info(self, operator, entity_id):
        """Returns basic information on the given entity id"""
        entity = self._get_entity(id=entity_id)
        return self._entity_info(entity)

    def _entity_info(self, entity):
        result = {}
        result['type'] = self.num2str(entity.entity_type)
        result['entity_id'] = entity.entity_id
        if entity.entity_type in \
            (self.const.entity_group, self.const.entity_account): 
            result['creator_id'] = entity.creator_id
            result['create_date'] = entity.create_date
            result['expire_date'] = entity.expire_date
            # FIXME: Should be a list instead of a string, but text
            # clients doesn't know how to view such a list
            result['spread'] = ", ".join([str(self.const.Spread(r['spread']))
                                          for r in entity.get_spread()])
        if entity.entity_type == self.const.entity_group:
            result['name'] = entity.group_name
            result['description'] = entity.description
            result['visibility'] = entity.visibility
            try:
                result['gid'] = entity.posix_gid
            except AttributeError:
                pass    
        elif entity.entity_type == self.const.entity_account:
            result['name'] = entity.account_name
            result['owner_id'] = entity.owner_id
            #result['home'] = entity.home
           # TODO: de-reference disk_id
            #result['disk_id'] = entity.disk_id
           # TODO: de-reference np_type
           # result['np_type'] = entity.np_type
        elif entity.entity_type == self.const.entity_person:   
            result['name'] = entity.get_name(self.const.system_cached,
                                             getattr(self.const,
                                                     cereconf.DEFAULT_GECOS_NAME))
            result['export_id'] = entity.export_id
            result['birthdate'] =  entity.birth_date
            result['description'] = entity.description
            result['gender'] = self.num2str(entity.gender)
            # make boolean
            result['deceased'] = entity.deceased_date
            names = []
            for name in entity.get_all_names():
                source_system = self.num2str(name.source_system)
                name_variant = self.num2str(name.name_variant)
                names.append((source_system, name_variant, name.name))
            result['names'] = names    
            affiliations = []
            for row in entity.get_affiliations():
                affiliation = {}
                affiliation['ou'] = row['ou_id']
                affiliation['affiliation'] = self.num2str(row.affiliation)
                affiliation['status'] = self.num2str(row.status)
                affiliation['source_system'] = self.num2str(row.source_system)
                affiliations.append(affiliation)
            result['affiliations'] = affiliations     
        elif entity.entity_type == self.const.entity_ou:
            for attr in '''name acronym short_name display_name
                           sort_name'''.split():
                result[attr] = getattr(entity, attr)               
                
        return result
    
    # entity history
    all_commands['entity_history'] = None
    def entity_history(self, operator, entity_id, limit=100):
        entity = self._get_entity(id=entity_id)
        self.ba.can_show_history(operator.get_entity_id(), entity)
        result = self.db.get_log_events(any_entity=entity_id)
        events = []
        entities = Set()
        change_types = Set()
        # (dirty way of unwrapping DB-iterator) 
        result = [r for r in result]
        # skip all but the last entries 
        result = result[-limit:]
        for row in result:
            event = {}
            change_type = int(row['change_type_id'])
            change_types.add(change_type)
            event['type'] = change_type

            event['date'] = row['tstamp']
            event['subject'] = row['subject_entity']
            event['dest'] = row['dest_entity']
            params = row['change_params']
            if params:
                params = pickle.loads(params)
            event['params'] = params
            change_by = row['change_by']
            if change_by:
                entities.add(change_by)
                event['change_by'] = change_by
            else:
                event['change_by'] = row['change_program']
            entities.add(event['subject'])
            entities.add(event['dest'])
            events.append(event)
        # Resolve to entity_info, return as dict
        entities = dict([(str(e), self._entity_info(e)) 
                        for e in entities if e])
        # resolv change_types as well, return as dict
        change_types = dict([(str(t), self.change_type2details.get(t))
                        for t in change_types])
        return events, entities, change_types

    #
    # group commands
    #

    # group add
    all_commands['group_add'] = Command(
        ("group", "add"), AccountName(help_ref="account_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_add(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="account")

    # group gadd
    all_commands['group_gadd'] = Command(
        ("group", "gadd"), GroupName(help_ref="group_name_src", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_gadd(self, operator, src_name, dest_group,
                  group_operator=None):
        return self._group_add(operator, src_name, dest_group,
                               group_operator, type="group")

    def _group_add(self, operator, src_name, dest_group,
                  group_operator=None, type=None):
        if type == "group":
            src_entity = self._get_group(src_name)
        elif type == "account":
            src_entity = self._get_account(src_name)
        return self._group_add_entity(operator, src_entity, 
                                      dest_group, group_operator)    

    def _group_add_entity(self, operator, src_entity, dest_group,
                          group_operator=None):
        group_operator = self._get_group_opcode(group_operator)
        group_d = self._get_group(dest_group)
        if operator:
            self.ba.can_alter_group(operator.get_entity_id(), group_d)
        src_name = self._get_name_from_object(src_entity)
        # Make the error message for the most common operator error
        # more friendly.  Don't treat this as an error, useful if the
        # operator has specified more than one entity.
        if group_d.has_member(src_entity.entity_id, src_entity.entity_type,
                              group_operator):
            return "%s is already a member of %s" % (src_name, dest_group)
        # This can still fail, e.g., if the entity is a member with a
        # different operation.
        try:
            group_d.add_member(src_entity.entity_id, src_entity.entity_type,
                               group_operator)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        # Warn the user about NFS filegroup limitations.
        for spread_name in cereconf.NIS_SPREADS:
            fg_spread = getattr(self.const, spread_name)
            for row in group_d.get_spread():
                if row['spread'] == fg_spread:
                    count = self._group_count_memberships(src_entity.entity_id,
                                                          fg_spread)
                    if count > 16:
                        return ("WARNING: %s is a member of %d groups with "
                                "spread %s" % (src_name, count, fg_spread))
        return "OK, added %s to %s" % (src_name, dest_group)

    def _group_count_memberships(self, entity_id, spread):
        """Count how many groups of a given spread entity_id has
        entity_id as a member, either directly or indirectly."""
        groups = {}
        gr = Utils.Factory.get("Group")(self.db)
        for r in gr.list_groups_with_entity(entity_id):
            # TODO: list_member_groups recurses upwards and returns a
            # list with the "root" as the last element.  We should
            # actually look at just that root and recurse downwards to
            # generate group lists to process difference and
            # intersection correctly.  Seems a lot of work to support
            # something we don't currently use, and it's probably
            # better to improve the API of list_member_groups anyway.
            if r['operation'] != self.const.group_memberop_union:
                continue
            # It would be nice if list_groups_with_entity included the
            # spread column, but that would lead to duplicate rows.
            # So we do the filtering here.
            gr.clear()
            gr.find(r['group_id'])
            for sp_row in gr.get_spread():
                if (sp_row['spread'] == spread):
                    groups[int(r['group_id'])] = True
            for group_id in gr.list_member_groups(r['group_id'],
                                                  spreads=(spread,)):
                groups[group_id] = True
        return len(groups.keys())

    # group add_entity
    all_commands['group_add_entity'] = None
    def group_add_entity(self, operator, src_entity_id, dest_group_id,
                  group_operator=None):
        """Adds a entity to a group. Both the source entity and the group
           should be entity IDs"""          
        # tell _group_find later on that dest_group is a entity id          
        dest_group = 'id:%s' % dest_group_id
        src_entity = self._get_entity(id=src_entity_id)
        if not src_entity.entity_type in \
            (self.const.entity_account, self.const.entity_group):
            raise CerebrumError, \
              "Entity %s is not a legal type " \
              "to become group member" % src_entity_id
        return self._group_add_entity(operator, src_entity, dest_group,
                               group_operator)

    # group create
    all_commands['group_create'] = Command(
        ("group", "create"), GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="string_description"),
        fs=FormatSuggestion("Group created as a normal group, internal id: %i", ("group_id",)),
        perm_filter='can_create_group')
    def group_create(self, operator, groupname, description):
        self.ba.can_create_group(operator.get_entity_id())
        g = self.Group_class(self.db)
        g.populate(creator_id=operator.get_entity_id(),
                   visibility=self.const.group_visibility_all,
                   name=groupname, description=description)
        try:
            g.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(g.entity_id)}

    # group request, like group create, but only send request to
    # the ones with the access to the 'group create' command
    # Currently send email to brukerreg@usit.uit.no
    all_commands['group_request'] = Command(
        ("group", "request"), GroupName(help_ref="group_name_new"),
        SimpleString(help_ref="string_description"), SimpleString(help_ref="string_spread"),
	GroupName(help_ref="group_name_moderator"))    

    def group_request(self, operator, groupname, description, spread, moderator):
	opr = operator.get_entity_id()
        acc = self.Account_class(self.db)
	acc.find(opr)
        fromaddr = acc.get_primary_mailaddress()
	toaddr = cereconf.GROUP_REQUESTS_SENDTO
	spreadstring = "(" + spread + ")"
	spreads = []
	spreads = re.split(" ",spread)
	subject = "Cerebrum group create request %s" % groupname
	body = []
	body.append("Please create a new group:")
	body.append("")
	body.append("Groupname: %s." % groupname)
	body.append("Description:  %s" % description)
	body.append("Requested by: %s" % fromaddr)
	body.append("Moderator: %s" % moderator)
	body.append("")
	body.append("group create %s \"%s\"" % (groupname, description))
	for i in range(len(spreads)):
	    if (self._get_constant(spreads[i],"No such spread") in \
		[self.const.spread_uit_nis_fg,self.const.spread_ifi_nis_fg]):
                pg = PosixGroup.PosixGroup(self.db)
		if not pg.illegal_name(groupname):
		    body.append("group promote_posix %s" % groupname)
		else:
		    raise CerebrumError, "Illegal groupname, max 8 characters allowed."
		    break
	    else:
		pass	    
	body.append("spread add group %s %s" % (groupname, spreadstring))
	body.append("access grant Group-owner (%s) group %s" % (moderator, groupname))
        body.append("group info %s" % groupname)
	body.append("")
	body.append("")
        Utils.sendmail(toaddr, fromaddr, subject, "\n".join(body))
	return "Request sent to brukerreg@usit.uit.no"

    #  group def
    all_commands['group_def'] = Command(
        ('group', 'def'), AccountName(), GroupName(help_ref="group_name_dest"))
    def group_def(self, operator, accountname, groupname):
        account = self._get_account(accountname, actype="PosixUser")
        grp = self._get_group(groupname, grtype="PosixGroup")
        op = operator.get_entity_id()
        self.ba.can_set_default_group(op, account, grp)
        account.gid_id = grp.entity_id
        account.write_db()
        return "OK, set default-group for '%s' to '%s'" % (
            accountname, groupname)

    # group delete
    all_commands['group_delete'] = Command(
        ("group", "delete"), GroupName(), YesNo(help_ref="yes_no_force", default="No"),
        perm_filter='can_delete_group')
    def group_delete(self, operator, groupname, force=None):
        grp = self._get_group(groupname)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        if self._is_yes(force):
##             u, i, d = grp.list_members()
##             for op, tmp in ((self.const.group_memberop_union, u),
##                             (self.const.group_memberop_intersection, i),
##                             (self.const.group_memberop_difference, d)):
##                 for m in tmp:
##                     grp.remove_member(m[1], op)
            try:
                pg = self._get_group(groupname, grtype="PosixGroup")
                pg.delete()
            except CerebrumError:
                pass   # Not a PosixGroup
        self._remove_auth_target("group", grp.entity_id)
        self._remove_auth_role(grp.entity_id)
        grp.delete()
        return "OK, deleted group '%s'" % groupname

    # group remove
    all_commands['group_remove'] = Command(
        ("group", "remove"), AccountName(help_ref="account_name_member", repeat=True),
        GroupName(help_ref="group_name_dest", repeat=True),
        GroupOperation(optional=True), perm_filter='can_alter_group')
    def group_remove(self, operator, src_name, dest_group,
                     group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="account")

    # group gremove
    all_commands['group_gremove'] = Command(
        ("group", "gremove"), GroupName(repeat=True),
        GroupName(repeat=True), GroupOperation(optional=True),
        perm_filter='can_alter_group')
    def group_gremove(self, operator, src_name, dest_group,
                      group_operator=None):
        return self._group_remove(operator, src_name, dest_group,
                               group_operator, type="group")

    def _group_remove(self, operator, src_name, dest_group,
                      group_operator=None, type=None):
        if type == "group":
            src_entity = self._get_group(src_name)
        elif type == "account":
            src_entity = self._get_account(src_name)
        group_d = self._get_group(dest_group)
        return self._group_remove_entity(operator, src_entity, group_d,
                                         group_operator)

    def _group_remove_entity(self, operator, member, group,
                             group_operation):
        group_operation = self._get_group_opcode(group_operation)
        self.ba.can_alter_group(operator.get_entity_id(), group)
        member_name = self._get_name_from_object(member)
        if not group.has_member(member.entity_id, member.entity_type,
                                group_operation):
            return ("%s isn't a member of %s" %
                    (member_name, group.group_name))
        if member.entity_type == self.const.entity_account:
            try:
                pu = PosixUser.PosixUser(self.db)
                pu.find(member.entity_id)
                if pu.gid_id == group.entity_id:
                    raise CerebrumError, ("Can't remove %s from primary group" %
                                          member_name)
            except Errors.NotFoundError:
                pass
        try:
            group.remove_member(member.entity_id, group_operation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, removed '%s' from '%s'" % (member_name, group.group_name)

    # group remove_entity
    all_commands['group_remove_entity'] = None
    def group_remove_entity(self, operator, member_entity, group_entity,
                            group_operation):
        group = self._get_entity(id=group_entity)
        member = self._get_entity(id=member_entity)
        return self._group_remove_entity(operator, member, 
                                         group, group_operation)
                               
    
    # group info
    all_commands['group_info'] = Command(
        ("group", "info"), GroupName(),
        fs=FormatSuggestion([("Name:         %s\n" +
                              "Spreads:      %s\n" +
                              "Description:  %s\n" +
                              "Expire:       %s\n" +
                              "Entity id:    %i""",
                              ("name", "spread", "description",
                               format_day("expire_date"),
                               "entity_id")),
                             ("Moderator:    %s %s (%s)",
                              ('owner_type', 'owner', 'opset')),
                             ("Gid:          %i",
                              ('gid',)),
                             ("Members:      %i groups, %i accounts",
                              ('c_group_u', 'c_account_u')),
                             ("Members (intersection): %i groups, %i accounts",
                              ('c_group_i', 'c_account_i')),
                             ("Members (difference):   %i groups, %i accounts",
                              ('c_group_d', 'c_account_d'))]))
    def group_info(self, operator, groupname):
        # TODO: Group visibility should probably be checked against
        # operator for a number of commands
        try:
            grp = self._get_group(groupname, grtype="PosixGroup")
        except CerebrumError:
            grp = self._get_group(groupname)
        ret = [ self._entity_info(grp) ]
        # find owners
        aot = BofhdAuthOpTarget(self.db)
        targets = []
        for row in aot.list(target_type='group', entity_id=grp.entity_id):
            targets.append(int(row['op_target_id']))
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for row in ar.list_owners(targets):
            aos.clear()
            aos.find(row['op_set_id'])
            id = int(row['entity_id'])
            en = self._get_entity(id=id)
            if en.entity_type == self.const.entity_account:
                owner = en.account_name
            elif en.entity_type == self.const.entity_group:
                owner = en.group_name
            else:
                owner = '#%d' % id
            ret.append({'owner_type': str(self.num2const[int(en.entity_type)]),
                        'owner': owner,
                        'opset': aos.name})
        # Count group members of different types
        u, i, d = grp.list_members()
        
        for members, op in ((u, 'u'), (i, 'i'), (d, 'd')):
            tmp = {}
            for ret_pfix, entity_type in (
                ('c_group_', int(self.const.entity_group)),
                ('c_account_', int(self.const.entity_account))):
                tmp[ret_pfix+op] = len(
                    [x for x in members if int(x[0]) == entity_type])
            if [x for x in tmp.values() if x > 0]:
                ret.append(tmp)
        return ret

    # group list
    all_commands['group_list'] = Command(
        ("group", "list"), GroupName(),
        fs=FormatSuggestion("%-9s %-10s %s", ("op", "type", "name"),
                            hdr="%-9s %-10s %s" % ("MemberOp","Type","Name")))
    def group_list(self, operator, groupname):
        """List direct members of group"""
        def compare(a, b):
            return cmp(a['type'], b['type']) or cmp(a['name'], b['name'])
        group = self._get_group(groupname)
        ret = []
        # TBD: the default is to leave out include expired accounts or
        # groups.  How should we make the information about expired
        # members available?
        u, i, d = group.list_members(get_entity_name=True)
        for t, rows in ((str(self.const.group_memberop_union), u),
                        (str(self.const.group_memberop_intersection), i),
                        (str(self.const.group_memberop_difference), d)):
            unsorted = []
            for r in rows:
                # yes, we COULD have used row NAMES instead of
                # numbers, but somebody decided to return simple 
                # tuples instead of the usual db_row objects ...
                unsorted.append({'op': t,
                                 'id': r[1],
                                 'type': str(self.num2const[int(r[0])]),
                                 'name': r[2]})
            unsorted.sort(compare)
            ret.extend(unsorted)
        return ret

    # group list_expanded
    all_commands['group_list_expanded'] = Command(
        ("group", "list_expanded"), GroupName(),
        fs=FormatSuggestion("%8i %s", ("member_id", "name"), hdr="Id       Name"))
    def group_list_expanded(self, operator, groupname):
        """List members of group after expansion"""
        group = self._get_group(groupname)
        return [{'member_id': a[0],
                 'name': a[1]
                 } for a in group.get_members(get_entity_name=True)]

    # group personal <uname>+
    all_commands['group_personal'] = Command(
        ("group", "personal"), AccountName(repeat=True),
        fs=FormatSuggestion(
        "Personal group created and made primary, POSIX gid: %i\n"+
        "The user may have to wait a minute, then restart bofh to access\n"+
        "the 'group add' command", ("group_id",)),
        perm_filter='can_create_personal_group')
    def group_personal(self, operator, uname):
        """This is a separate command for convenience and consistency.
        A personal group is always a PosixGroup, and has the same
        spreads as the user."""
        acc = self._get_account(uname, actype="PosixUser")
        op = operator.get_entity_id()
        self.ba.can_create_personal_group(op, acc)
        # 1. Create group
        group = self.Group_class(self.db)
        try:
            group.find_by_name(uname)
            raise CerebrumError, "Group %s already exists" % uname
        except Errors.NotFoundError:
            group.populate(creator_id=op,
                           visibility=self.const.group_visibility_all,
                           name=uname,
                           description=('Personal file group for %s' % uname))
            group.write_db()
        # 2. Promote to PosixGroup
        pg = PosixGroup.PosixGroup(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        # 3. make user the owner of the group so he can administer it
        op_set = BofhdAuthOpSet(self.db)
        op_set.find_by_name('Group-owner')
        op_target = BofhdAuthOpTarget(self.db)
        op_target.populate(group.entity_id, 'group')
        op_target.write_db()
        role = BofhdAuthRole(self.db)
        role.grant_auth(acc.entity_id, op_set.op_set_id, op_target.op_target_id)
        # 4. make user a member of his personal group
        self._group_add(None, uname, uname, type="account")
        # 5. make this group the primary group
        acc.gid_id = group.entity_id
        acc.write_db()
        # 6. add spreads corresponding to its owning user
        self.__spread_sync_group(acc, group)
        return {'group_id': int(pg.posix_gid)}

    # group posix_create
    all_commands['group_promote_posix'] = Command(
        ("group", "promote_posix"), GroupName(),
        SimpleString(help_ref="string_description", optional=True),
        fs=FormatSuggestion("Group promoted to PosixGroup, posix gid: %i",
                            ("group_id",)), perm_filter='can_create_group')
    def group_promote_posix(self, operator, group, description=None):
        self.ba.can_create_group(operator.get_entity_id())
        is_posix = False
        try:
            self._get_group(group, grtype="PosixGroup")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixGroup" % group)

        group=self._get_group(group)
        pg = PosixGroup.PosixGroup(self.db)
        pg.populate(parent=group)
        try:
            pg.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'group_id': int(pg.posix_gid)}

    # group posix_demote
    all_commands['group_demote_posix'] = Command(
        ("group", "demote_posix"), GroupName(), perm_filter='can_delete_group')
    def group_demote_posix(self, operator, group):
        grp = self._get_group(group, grtype="PosixGroup")
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.delete()
        return "OK, demoted '%s'" % group
    
    # group search
    all_commands['group_search'] = Command(
        ("group", "search"), SimpleString(help_ref="string_group_filter"),
        fs=FormatSuggestion("%8i %-16s %s", ("id", "name", "desc"),
                            hdr="%8s %-16s %s" % ("Id", "Name", "Description")),
        perm_filter='can_search_group')
    def group_search(self, operator, filter=""):
        group = self.Group_class(self.db)
        if filter == "":
            raise CerebrumError, "No filter specified"
        filters = {'name': None,
                   'desc': None,
                   'spread': None,
                   'expired': "no"}
        rules = filter.split(",")
        for rule in rules:
            if rule.count(":"):
                filter_type, pattern = rule.split(":")
            else:
                filter_type = 'name'
                pattern = rule
            if filter_type not in filters:
                raise CerebrumError, "Unknown filter type: %s" % filter_type
            filters[filter_type] = pattern
        if filters['name'] == '*' and len(rules) == 1:
            raise CerebrumError, "Please provide a more specific filter"
        filter_expired = not self._get_boolean(filters['expired'])
        ret = []
        for r in group.search(spread=filters['spread'],
                              name=filters['name'],
                              description=filters['desc'],
                              filter_expired=filter_expired):
            ret.append({'id': r['group_id'],
                        'name': r['name'],
                        'desc': r['description'],
                        })
        return ret

    # group set_description
    all_commands['group_set_description'] = Command(
        ("group", "set_description"),
        GroupName(), SimpleString(help_ref="string_description"),
        perm_filter='can_delete_group')
    def group_set_description(self, operator, group, description):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.description = description
        grp.write_db()
        return "OK, description for group '%s' updated" % group

    # group set_expire
    all_commands['group_set_expire'] = Command(
        ("group", "set_expire"), GroupName(), Date(), perm_filter='can_delete_group')
    def group_set_expire(self, operator, group, expire):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.expire_date = self._parse_date(expire)
        grp.write_db()
        return "OK, set expire-date for '%s'" % group

    # group set_visibility
    all_commands['group_set_visibility'] = Command(
        ("group", "set_visibility"), GroupName(), GroupVisibility(),
        perm_filter='can_delete_group')
    def group_set_visibility(self, operator, group, visibility):
        grp = self._get_group(group)
        self.ba.can_delete_group(operator.get_entity_id(), grp)
        grp.visibility = self._map_visibility_id(visibility)
        grp.write_db()
        return "OK, set visibility for '%s'" % group

    # group user
    all_commands['group_user'] = Command(
        ('group', 'user'), AccountName(), fs=FormatSuggestion(
        "%-9s %-18s %s", ("memberop", "group", "spreads"),
        hdr="%-9s %-18s %s" % ("Operation", "Group", "Spreads")))
    def group_user(self, operator, accountname):
        account = self._get_account(accountname)
        group = self.Group_class(self.db)
        ret = []
        for row in group.list_groups_with_entity(account.entity_id):
            grp = self._get_group(row['group_id'], idtype="id")
            ret.append({'memberop': str(self.num2const[int(row['operation'])]),
                        'entity_id': grp.entity_id,
                        'group': grp.group_name,
                        'spreads': ",".join(["%s" % self.num2const[int(a['spread'])]
                                             for a in grp.get_spread()])})
        ret.sort(lambda a,b: cmp(a['group'], b['group']))
        return ret

    #
    # misc commands
    #

    # misc affiliations
    all_commands['misc_affiliations'] = Command(
        ("misc", "affiliations"),
        fs=FormatSuggestion("%-14s %-14s %s", ('aff', 'status', 'desc'),
                            hdr="%-14s %-14s %s" % ('Affiliation', 'Status',
                                                    'Description')))
    def misc_affiliations(self, operator):
        tmp = {}
        for co in self.const.fetch_constants(self.const.PersonAffStatus):
            aff = str(co.affiliation)
            if aff not in tmp:
                tmp[aff] = [{'aff': aff,
                             'status': '',
                             'desc': co.affiliation._get_description()}]
            tmp[aff].append({'aff': '',
                             'status': "%s" % co._get_status(),
                             'desc': co._get_description()})
        # fetch_constants returns a list sorted according to the name
        # of the constant.  Since the name of the constant and the
        # affiliation status usually are kept related, the list for
        # each affiliation will tend to be sorted as well.  Not so for
        # the affiliations themselves.
        keys = tmp.keys()
        keys.sort()
        ret = []
        for k in keys:
            for r in tmp[k]:
                ret.append(r)
        return ret

    all_commands['misc_change_request'] = Command(
        ("misc", "change_request"), Id(help_ref="id:request_id"), Date())
    def misc_change_request(self, operator, request_id, date):
        date = self._parse_date(date)
        br = BofhdRequests(self.db, self.const)
        old_req = br.get_requests(request_id=request_id)[0]
        if old_req['requestee_id'] != operator.get_entity_id():
            raise PermissionDenied("You are not the requestee")
        br.delete_request(request_id=request_id)
        br.add_request(operator.get_entity_id(), date,
                       old_req['operation'], old_req['entity_id'],
                       old_req['destination_id'],
                       old_req['state_data'])
        return "OK, altered request %s" % request_id

    # misc checkpassw
    # TBD: this command should be renamed "misc check_password"
    all_commands['misc_checkpassw'] = Command(
        ("misc", "checkpassw"), AccountPassword())
    def misc_checkpassw(self, operator, password):
        pc = PasswordChecker.PasswordChecker(self.db)
        try:
            pc.goodenough(None, password, uname="foobar")
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError, "Bad password: %s" % m
        ac = self.Account_class(self.db)
        crypt = ac.enc_auth_type_crypt3_des(password)
        md5 = ac.enc_auth_type_md5_crypt(password)
        return "OK.  crypt3-DES: %s   MD5-crypt: %s" % (crypt, md5)

    # misc clear_passwords
    all_commands['misc_clear_passwords'] = Command(
        ("misc", "clear_passwords"), AccountName(optional=True))
    def misc_clear_passwords(self, operator, account_name=None):
        operator.clear_state(state_types=('new_account_passwd', 'user_passwd'))
        return "OK, passwords cleared"


    all_commands['misc_dadd'] = Command(
        ("misc", "dadd"), SimpleString(help_ref='string_host'), DiskId(),
        perm_filter='can_create_disk')
    def misc_dadd(self, operator, hostname, diskname):
        host = self._get_host(hostname)
        self.ba.can_create_disk(operator.get_entity_id(), host)
        disk = Utils.Factory.get('Disk')(self.db)
        disk.populate(host.entity_id, diskname, 'uit disk')
        try:
            disk.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        if len(diskname.split("/")) != 4:
            return "OK.  Warning: disk did not follow expected pattern."
        return "OK, added disk '%s' at %s" % (diskname, hostname)

    all_commands['misc_dls'] = Command(
        ("misc", "dls"), SimpleString(help_ref='string_host'),
        fs=FormatSuggestion("%-8i %-8i %s", ("disk_id", "host_id", "path",),
                            hdr="DiskId   HostId   Path"))
    def misc_dls(self, operator, hostname):
        host = self._get_host(hostname)
        disks = {}
        disk = Utils.Factory.get('Disk')(self.db)
        for row in disk.list(host.host_id):
            disks[row['disk_id']] = {'disk_id': row['disk_id'],
                                     'host_id': row['host_id'],
                                     'path': row['path']}
        disklist = disks.keys()
        disklist.sort(lambda x, y: cmp(disks[x]['path'], disks[y]['path']))
        ret = []
        for d in disklist:
            ret.append(disks[d])
        return ret

    all_commands['misc_drem'] = Command(
        ("misc", "drem"), SimpleString(help_ref='string_host'), DiskId(),
        perm_filter='can_remove_disk')
    def misc_drem(self, operator, hostname, diskname):
        host = self._get_host(hostname)
        self.ba.can_remove_disk(operator.get_entity_id(), host)
        disk = self._get_disk(diskname, host_id=host.entity_id)[0]
        # FIXME: We assume that all destination_ids are entities,
        # which would ensure that the disk_id number can't represent a
        # different kind of entity.  The database does not constrain
        # this, however.
        br = BofhdRequests(self.db, self.const)
        if br.get_requests(destination_id=disk.entity_id):
            raise CerebrumError, ("There are pending requests. Use "+
                                  "'misc list_requests disk %s' to view "+
                                  "them.") % diskname
        account = self.Account_class(self.db)
        for row in account.list_account_home(disk_id=disk.entity_id,
                                             filter_expired=False):
            if row['disk_id'] is None:
                continue
            if row['status'] == int(self.const.home_status_on_disk):
                raise CerebrumError, ("One or more users still on disk " +
                                      "(e.g. %s)" % row['entity_name'])
            account.clear()
            account.find(row['account_id'])
            ah = account.get_home(row['home_spread'])
            account.set_homedir(
                current_id=ah['homedir_id'], disk_id=None,
                home=account.resolve_homedir(disk_path=row['path'], home=row['home']))
        self._remove_auth_target("disk", disk.entity_id)
        try:
            disk.delete()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, %s deleted" % diskname
    
    all_commands['misc_hadd'] = Command(
        ("misc", "hadd"), SimpleString(help_ref='string_host'),
        perm_filter='can_create_host')
    def misc_hadd(self, operator, hostname):
        self.ba.can_create_host(operator.get_entity_id())
        host = Utils.Factory.get('Host')(self.db)
        host.populate(hostname, 'uit host')
        try:
            host.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, added host '%s'" % hostname

    all_commands['misc_hrem'] = Command(
        ("misc", "hrem"), SimpleString(help_ref='string_host'),
        perm_filter='can_remove_host')
    def misc_hrem(self, operator, hostname):
        self.ba.can_remove_host(operator.get_entity_id())
        host = self._get_host(hostname)
        self._remove_auth_target("host", host.host_id)
        try:
            host.delete()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return "OK, %s deleted" % hostname

    def _remove_auth_target(self, target_type, target_id):
        """This function should be used whenever a potential target
        for authorisation is deleted.
        """
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        for r in aot.list(entity_id=target_id, target_type=target_type):
            aot.clear()
            aot.find(r['op_target_id'])
            # We remove all auth_role entries first so that there
            # are no references to this op_target_id, just in case
            # someone adds a foreign key constraint later.
            for role in ar.list(op_target_id = r["op_target_id"]):
                ar.revoke_auth(role['entity_id'], role['op_set_id'],
                               r['op_target_id'])
            aot.delete()

    def _remove_auth_role(self, entity_id):
        """This function should be used whenever a potentially
        authorised entity is deleted.
        """
        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        for r in ar.list(entity_id):
            ar.revoke_auth(entity_id, r['op_set_id'], r['op_target_id'])
            # Also remove targets if this was the last reference from
            # auth_role.
            remaining = ar.list(op_target_id=r['op_target_id'])
            if len(remaining) == 0:
                aot.clear()
                aot.find(r['op_target_id'])
                aot.delete()


    # misc list_passwords
    def misc_list_passwords_prompt_func(self, session, *args):
        """  - G�r inn i "vis-info-om-oppdaterte-brukere-modus":
  1 Skriv ut passordark
  1.1 Lister ut templates, ber bofh'er om � velge en
  1.1.[0] Spesifiser skriver (for template der dette tillates valgt av
          bofh'er)
  1.1.1 Lister ut alle aktuelle brukernavn, ber bofh'er velge hvilke
        som skal skrives ut ('*' for alle).
  1.1.2 (skriv ut ark/brev)
  2 List brukernavn/passord til skjerm
  """
        all_args = list(args[:])
        if not all_args:
            return {'prompt': "Velg#",
                    'map': [(("Alternativer",), None),
                            (("Skriv ut passordark",), "skriv"),
                            (("List brukernavn/passord til skjerm",), "skjerm")]}
        arg = all_args.pop(0)
        if(arg == "skjerm"):
            return {'last_arg': True}
        if not all_args:
            map = [(("Alternativer",), None)]
            n = 1
            for t in self._map_template():
                map.append(((t,), n))
                n += 1
            return {'prompt': "Velg template #", 'map': map,
                    'help_ref': 'print_select_template'}
        arg = all_args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(arg)
        if not tpl_lang.endswith("letter"):
            default_printer = session.get_state(state_type='default_printer')
            if default_printer:
                default_printer = default_printer[0]['state_data']
            if not all_args:
                ret = {'prompt': 'Oppgi skrivernavn'}
                if default_printer:
                    ret['default'] = default_printer
                return ret
            skriver = all_args.pop(0)
            if skriver != default_printer:
                session.clear_state(state_types=['default_printer'])
                session.store_state('default_printer', skriver)
                self.db.commit()
        if not all_args:
            n = 1
            map = [(("%8s %s", "uname", "operation"), None)]
            for row in self._get_cached_passwords(session):
                map.append((("%-12s %s", row['account_id'], row['operation']), n))
                n += 1
            if n == 1:
                raise CerebrumError, "no users"
            return {'prompt': 'Velg bruker(e)', 'last_arg': True,
                    'map': map, 'raw': True,
                    'help_ref': 'print_select_range',
                    'default': str(n-1)}

    all_commands['misc_list_passwords'] = Command(
        ("misc", "list_passwords"), prompt_func=misc_list_passwords_prompt_func,
        fs=FormatSuggestion("%-8s %-20s %s", ("account_id", "operation", "password"),
                            hdr="%-8s %-20s %s" % ("Id", "Operation", "Password")))
    def misc_list_passwords(self, operator, *args):
        if args[0] == "skjerm":
            return self._get_cached_passwords(operator)
        args = list(args[:])
        args.pop(0)
        tpl_lang, tpl_name, tpl_type = self._map_template(args.pop(0))
        skriver = None
        if not tpl_lang.endswith("letter"):
            skriver = args.pop(0)
        else:
            skriver = cereconf.PRINT_PRINTER
        selection = args.pop(0)
        cache = self._get_cached_passwords(operator)
        th = TemplateHandler(tpl_lang, tpl_name, tpl_type)
        tmp_dir = Utils.make_temp_dir(dir=cereconf.JOB_RUNNER_LOG_DIR,
                                      prefix="bofh_spool")
        out_name = "%s/%s.%s" % (tmp_dir, "job", tpl_type)
        out = file(out_name, "w")
        if th._hdr is not None:
            out.write(th._hdr)
        ret = []
        
        num_ok = 0
        for n in self._parse_range(selection):
            n -= 1
            try:
                account = self._get_account(cache[n]['account_id'])
            except IndexError:
                raise CerebrumError("Number not in valid range")
            mapping = {'uname': cache[n]['account_id'],
                       'password': cache[n]['password'],
                       'account_id': account.entity_id,
                       'lopenr': ''}
            if tpl_lang.endswith("letter"):
                mapping['barcode'] = '%s/barcode_%s.eps' % (
                    tmp_dir, account.entity_id)
                try:
                    th.make_barcode(account.entity_id, mapping['barcode'])
                except IOError, msg:
                    raise CerebrumError(msg)
            if account.owner_type == self.const.entity_group:
                grp = self._get_group(account.owner_id, idtype='id')
                mapping['group'] = grp.group_name
            elif account.owner_type == self.const.entity_person:    
                person = self._get_person('entity_id', account.owner_id)
                fullname = person.get_name(self.const.system_cached, self.const.name_full)
                mapping['fullname'] =  fullname
            else:
                raise CerebrumError("Unsupported owner type. Please use the 'to screen' option")
            if tpl_lang.endswith("letter"):
                address = None
                for source, kind in ((self.const.system_lt, self.const.address_post),
                                     (self.const.system_fs, self.const.address_post),
                                     (self.const.system_fs, self.const.address_post_private)):
                    address = person.get_entity_address(source = source, type = kind)
                    if address:
                        break
  
                if not address:
                    ret.append("Error: Couldn't get authoritative address for %s" % account.account_name)
                    continue
                address = address[0]
                alines = address['address_text'].split("\n")+[""]
                mapping['address_line1'] = fullname
                mapping['address_line2'] = alines[0]
                mapping['address_line3'] = alines[1]
                mapping['zip'] = address['postal_number']
                mapping['city'] = address['city']
                mapping['country'] = address['country']

                mapping['birthdate'] = person.birth_date.strftime('%Y-%m-%d')
                mapping['emailadr'] =  "TODO"  # We probably don't need to support this...
            num_ok += 1
            out.write(th.apply_template('body', mapping, no_quote=('barcode',)))
        if not (num_ok > 0):
            raise CerebrumError("Errors extracting required information: %s" % "+n".join(ret))
        if th._footer is not None:
            out.write(th._footer)
        out.close()
        try:
            account = self._get_account(operator.get_entity_id(), idtype='id')
            th.spool_job(out_name, tpl_type, skriver, skip_lpr=0,
                         lpr_user=account.account_name,
                         logfile="%s/spool.log" % tmp_dir)
        except IOError, msg:
            raise CerebrumError(msg)
        ret.append("OK: %s/%s.%s spooled @ %s for %s" % (
            tpl_lang, tpl_name, tpl_type, skriver, selection))
        return "\n".join(ret)

    all_commands['misc_list_requests'] = Command(
        ("misc", "list_requests"), SimpleString(
        help_ref='string_bofh_request_search_by', default='requestee'),
        SimpleString(help_ref='string_bofh_request_target', default='<me>'),
        fs=FormatSuggestion("%-6i %-10s %-16s %-15s %-10s %-20s %s",
                            ("id", "requestee", format_time("when"),
                             "op", "entity", "destination", "args"),
                            hdr="%-6s %-10s %-16s %-15s %-10s %-20s %s" % \
                            ("Id", "Requestee", "When", "Op", "Entity",
                             "Destination", "Arguments")))
    def misc_list_requests(self, operator, search_by, destination):
        br = BofhdRequests(self.db, self.const)
        ret = []

        if destination == '<me>':
            destination = self._get_account(operator.get_entity_id(), idtype='id')
            destination = destination.account_name
        if search_by == 'requestee':
            account = self._get_account(destination)
            rows = br.get_requests(operator_id=account.entity_id, given=True)
        elif search_by == 'operation':
            try:
                destination = int(self.const.BofhdRequestOp('br_'+destination))
            except Errors.NotFoundError:
                raise CerebrumError("Unknown request operation %s" % destination)
            rows = br.get_requests(operation=destination)
        elif search_by == 'disk':
            disk_id = self._get_disk(destination)[1]
            rows = br.get_requests(destination_id=disk_id)
        elif search_by == 'account':
            account = self._get_account(destination)
            rows = br.get_requests(entity_id=account.entity_id)
        else:
            raise CerebrumError("Unknown search_by criteria")

        for r in rows:
            op = self.num2const[int(r['operation'])]
            dest = None
            if op in (self.const.bofh_move_user, self.const.bofh_move_request):
                disk = self._get_disk(r['destination_id'])[0]
                dest = disk.path
            elif op in (self.const.bofh_move_give,):
                dest = self._get_entity_name(self.const.entity_group,
                                             r['destination_id'])
            if r['requestee_id'] is None:
                requestee = ''
            else:
                requestee = self._get_entity_name(self.const.entity_account, r['requestee_id'])
            ret.append({'when': r['run_at'],
                        'requestee': requestee,
                        'op': str(op),
                        'entity': self._get_entity_name(self.const.entity_account, r['entity_id']),
                        'destination': dest,
                        'args': r['state_data'],
                        'id': r['request_id']
                        })
        ret.sort(lambda a,b: cmp(a['id'], b['id']))
        return ret

    all_commands['misc_cancel_request'] = Command(
        ("misc", "cancel_request"),
        SimpleString(help_ref='id:request_id'))
    def misc_cancel_request(self, operator, req):
        if req.isdigit():
            req_id = int(req)
        else:
            raise CerebrumError, "Request-ID must be a number"
        br = BofhdRequests(self.db, self.const)
        if not br.get_requests(request_id=req_id):
            raise CerebrumError, "Request ID %d not found" % req_id
        self.ba.can_cancel_request(operator.get_entity_id(), req_id)
        br.delete_request(request_id=req_id)
        return "OK, %s canceled" % req

    all_commands['misc_reload'] = Command(
        ("misc", "reload"), 
        perm_filter='is_superuser')
    def misc_reload(self, operator):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        self.server.read_config()
        return "OK, server-config reloaded"

    # misc stedkode <pattern>
    all_commands['misc_stedkode'] = Command(
        ("misc", "stedkode"), SimpleString(),
        fs=FormatSuggestion([
        (" %06s    %s",
         ('stedkode', 'short_name')),
        ("   affiliation %-7s @%s",
         ('affiliation', 'domain'))],
         hdr="Stedkode   Organizational unit"))
    def misc_stedkode(self, operator, pattern):
        output = []
        ou = self.OU_class(self.db)
        if re.match(r'[0-9]{1,6}$', pattern):
            fak = [ pattern[0:2] ]
            inst = [ pattern[2:4] ]
            avd = [ pattern[4:6] ]
            if len(fak[0]) == 1:
                fak = [ int(fak[0]) * 10 + x for x in range(10) ]
            if len(inst[0]) == 1:
                inst = [ int(inst[0]) * 10 + x for x in range(10) ]
            if len(avd[0]) == 1:
                avd = [ int(avd[0]) * 10 + x for x in range(10) ]
            # the following loop may look scary, but we will never
            # call get_stedkoder() more than 10 times.
            for f in fak:
                for i in inst:
                    if i == '':
                        i = None
                    for a in avd:
                        if a == '':
                            a = None
                        for r in ou.get_stedkoder(fakultet=f, institutt=i,
                                                  avdeling=a):
                            ou.clear()
                            ou.find(r['ou_id'])
                            output.append({'stedkode':
                                           '%02d%02d%02d' % (ou.fakultet,
                                                             ou.institutt,
                                                             ou.avdeling),
                                           'short_name':
                                           ou.short_name})
        else:
            if pattern.count('%') == 0:
                pattern = '%' + pattern + '%'
            for r in ou.get_stedkoder_by_name(pattern):
                ou.clear()
                ou.find(r['ou_id'])
                output.append({'stedkode':
                               '%02d%02d%02d' % (ou.fakultet,
                                                 ou.institutt,
                                                 ou.avdeling),
                               'short_name': ou.short_name})
        if len(output) == 1:
            eed = Email.EntityEmailDomain(self.db)
            try:
                eed.find(ou.ou_id)
            except Errors.NotFoundError:
                pass
            ed = Email.EmailDomain(self.db)
            for r in eed.list_affiliations():
                affname = "<any>"
                if r['affiliation']:
                    affname = str(self.num2const[int(r['affiliation'])])
                ed.clear()
                ed.find(r['domain_id'])
                output.append({'affiliation': affname,
                               'domain': ed.email_domain_name})
        return output

    # misc user_passwd
    # TBD: this command should be renamed "misc check_user_password"
    all_commands['misc_user_passwd'] = Command(
        ("misc", "user_passwd"), AccountName(), AccountPassword())
    def misc_user_passwd(self, operator, accountname, password):
        ac = self._get_account(accountname)
        if isinstance(password, unicode):  # crypt.crypt don't like unicode
            password = password.encode('iso8859-1')
        # Only people who can set the password are allowed to check it
        self.ba.can_set_password(operator.get_entity_id(), ac)
        old_pass = ac.get_account_authentication(self.const.auth_type_md5_crypt)
        salt = old_pass[:old_pass.rindex('$')]
        if ac.enc_auth_type_md5_crypt(password, salt=salt) == old_pass:
            return "Password is correct"
        return "Incorrect password"


    #
    # perm commands
    #

    # perm opset_list
    all_commands['perm_opset_list'] = Command(
        ("perm", "opset_list"), 
        fs=FormatSuggestion("%-6i %s", ("id", "name"), hdr="Id     Name"),
        perm_filter='is_superuser')
    def perm_opset_list(self, operator):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aos = BofhdAuthOpSet(self.db)
        ret = []
        for r in aos.list():
            ret.append({'id': r['op_set_id'],
                        'name': r['name']})
        return ret

    # perm opset_show
    all_commands['perm_opset_show'] = Command(
        ("perm", "opset_show"), SimpleString(help_ref="string_op_set"),
        fs=FormatSuggestion("%-6i %-16s %s", ("op_id", "op", "attrs"),
                            hdr="%-6s %-16s %s" % ("Id", "op", "Attributes")),
        perm_filter='is_superuser')
    def perm_opset_show(self, operator, name):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(name)
        ret = []
        for r in aos.list_operations():
            c = AuthConstants(int(r['op_code']))
            ret.append({'op': str(c),
                        'op_id': r['op_id'],
                        'attrs': ", ".join(
                ["%s" % r2['attr'] for r2 in aos.list_operation_attrs(r['op_id'])])})
        return ret

    # perm target_list
    all_commands['perm_target_list'] = Command(
        ("perm", "target_list"), SimpleString(help_ref="string_perm_target"),
        Id(optional=True),
        fs=FormatSuggestion("%-8i %-15i %-10s %-18s %s",
                            ("tgt_id", "entity_id", "target_type", "name", "attrs"),
                            hdr="%-8s %-15s %-10s %-18s %s" % (
        "TargetId", "TargetEntityId", "TargetType", "TargetName", "Attrs")),
        perm_filter='is_superuser')
    def perm_target_list(self, operator, target_type, entity_id=None):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        ret = []
        if target_type.isdigit():
            rows = aot.list(target_id=target_type)
        else:
            rows = aot.list(target_type=target_type, entity_id=entity_id)
        for r in rows:
            if r['target_type'] == 'group':
                name = self._get_entity_name(self.const.entity_group, r['entity_id'])
            elif r['target_type'] == 'disk':
                name = self._get_entity_name(self.const.entity_disk, r['entity_id'])
            elif r['target_type'] == 'host':
                name = self._get_entity_name(self.const.entity_host, r['entity_id'])
            else:
                name = "unknown"
            ret.append({'tgt_id': r['op_target_id'],
                        'entity_id': r['entity_id'],
                        'name': name,
                        'target_type': r['target_type'],
                        'attrs': r['attr'] or '<none>'})
        return ret

    # perm add_target
    all_commands['perm_add_target'] = Command(
        ("perm", "add_target"),
        SimpleString(help_ref="string_perm_target_type"), Id(),
        SimpleString(help_ref="string_attribute", optional=True),
        perm_filter='is_superuser')
    def perm_add_target(self, operator, target_type, entity_id, attr=None):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        if entity_id.isdigit():
            entity_id = int(entity_id)
        else:
            raise CerebrumError("Integer entity_id expected; got %r" %
                                (entity_id,))
        aot = BofhdAuthOpTarget(self.db)
        aot.populate(entity_id, target_type, attr)
        aot.write_db()
        return "OK, target id=%d" % aot.op_target_id

    # perm del_target
    all_commands['perm_del_target'] = Command(
        ("perm", "del_target"), Id(help_ref="id:op_target"),
        perm_filter='is_superuser')
    def perm_del_target(self, operator, op_target_id, attr):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aot = BofhdAuthOpTarget(self.db)
        aot.find(op_target_id)
        aot.delete()
        return "OK, target %s, attr=%s deleted" % (op_target_id, attr)

    # perm list
    all_commands['perm_list'] = Command(
        ("perm", "list"), Id(help_ref='id:entity_ext'),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_list(self, operator, entity_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        if entity_id.startswith("group:"):
            entities = [ self._get_group(entity_id.split(":")[-1]).entity_id ]
        elif entity_id.startswith("account:"):
            account = self._get_account(entity_id.split(":")[-1])
            group = self.Group_class(self.db)
            entities = [account.entity_id]
            for row in group.list_groups_with_entity(account.entity_id):
                if row['operation'] == int(self.const.group_memberop_union):
                    entities.append(row['group_id'])
        else:
            if not entity_id.isdigit():
                raise CerebrumError("Expected entity-id")
            entities = [entity_id]
        bar = BofhdAuthRole(self.db)
        ret = []
        for r in bar.list(entities):
            ret.append({'entity_id': self._get_entity_name(None, r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    # perm grant
    all_commands['perm_grant'] = Command(
        ("perm", "grant"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"), perm_filter='is_superuser')
    def perm_grant(self, operator, entity_id, op_set_name, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(op_set_name)

        bar.grant_auth(entity_id, aos.op_set_id, op_target_id)
        return "OK, granted %s@%s to %s" % (op_set_name, op_target_id,
                                            entity_id)

    # perm revoke
    all_commands['perm_revoke'] = Command(
        ("perm", "revoke"), Id(), SimpleString(help_ref="string_op_set"),
        Id(help_ref="id:op_target"), perm_filter='is_superuser')
    def perm_revoke(self, operator, entity_id, op_set_name, op_target_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(op_set_name)
        bar.revoke_auth(entity_id, aos.op_set_id, op_target_id)
        return "OK, revoked  %s@%s from %s" % (op_set_name, op_target_id,
                                            entity_id)

    # perm who_has_perm
    all_commands['perm_who_has_perm'] = Command(
        ("perm", "who_has_perm"), SimpleString(help_ref="string_op_set"),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_who_has_perm(self, operator, op_set_name):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        aos = BofhdAuthOpSet(self.db)
        aos.find_by_name(op_set_name)
        bar = BofhdAuthRole(self.db)
        ret = []
        for r in bar.list(op_set_id=aos.op_set_id):
            ret.append({'entity_id': self._get_entity_name(None, r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    # perm who_owns
    all_commands['perm_who_owns'] = Command(
        ("perm", "who_owns"), Id(help_ref="id:entity_ext"),
        fs=FormatSuggestion("%-8s %-8s %-8i",
                            ("entity_id", "op_set_id", "op_target_id"),
                            hdr="%-8s %-8s %-8s" %
                            ("entity_id", "op_set_id", "op_target_id")),
        perm_filter='is_superuser')
    def perm_who_owns(self, operator, id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        bar = BofhdAuthRole(self.db)
        if id.startswith("group:"):
            group = self._get_group(id.split(":")[-1])
            aot = BofhdAuthOpTarget(self.db)
            target_ids = []
            for r in aot.list(target_type='group', entity_id=group.entity_id):
                target_ids.append(r['op_target_id'])
        elif id.startswith("account:"):
            account = self._get_account(id.split(":")[-1])
            disk = Utils.Factory.get('Disk')(self.db)
            try:
                tmp = account.get_home(self.const.spread_uit_nis_user)
                disk.find(tmp[0])
            except Errors.NotFoundError:
                raise CerebrumError, "Unknown disk for user"
            aot = BofhdAuthOpTarget(self.db)
            target_ids = []
            for r in aot.list(target_type='global_host'):
                target_ids.append(r['op_target_id'])
            for r in aot.list(target_type='disk', entity_id=disk.entity_id):
                target_ids.append(r['op_target_id'])
            for r in aot.list(target_type='host', entity_id=disk.host_id):
                if (not r['attr'] or 
                    re.compile(r['attr']).match(disk.path.split("/")[-1]) != None):
                    target_ids.append(r['op_target_id'])
        else:
            if not id.isdigit():
                raise CerebrumError("Expected target-id")
            target_ids = [int(id)]
        if not target_ids:
            raise CerebrumError("No target_ids for %s" % id)
        ret = []
        for r in bar.list_owners(target_ids):
            ret.append({'entity_id': self._get_entity_name(None, r['entity_id']),
                        'op_set_id': self.num2op_set_name[int(r['op_set_id'])],
                        'op_target_id': r['op_target_id']})
        return ret

    #
    # person commands
    #

    # person accounts
    all_commands['person_accounts'] = Command(
        ("person", "accounts"), PersonId(),
        fs=FormatSuggestion("%6i %-10s %s", ("account_id", "name", format_day("expire")),
                            hdr="%6s %-10s %s" % ("Id", "Name", "Expire")))
    def person_accounts(self, operator, id):
        if id.find(":") == -1 and not id.isdigit():
            ac = self._get_account(id)
            id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(id))
        account = self.Account_class(self.db)
        ret = []
        for r in account.list_accounts_by_owner_id(person.entity_id,
                                                   filter_expired=False):
            account = self._get_account(r['account_id'], idtype='id')

            ret.append({'account_id': r['account_id'],
                        'name': account.account_name,
                        'expire': account.expire_date})
        return ret

    def _person_affiliation_add_helper(self, operator, person, ou, aff, aff_status):
        """Helper-function for adding an affiliation to a person with
        permission checking.  person is expected to be a person
        object, while ou, aff and aff_status should be the textual
        representation from the client"""
        aff = self._get_affiliationid(aff)
        aff_status = self._get_affiliation_statusid(aff, aff_status)
        ou = self._get_ou(stedkode=ou)

        # Assert that the person already have the affiliation
        has_aff = False
        for a in person.get_affiliations():
            if a['ou_id'] == ou.entity_id and a['affiliation'] == aff:
                if a['status'] <> aff_status:
                    raise CerebrumError, \
                          "Person has conflicting aff_status for this ou/affiliation combination"
                has_aff = True
                break
        if not has_aff:
            self.ba.can_add_affiliation(operator.get_entity_id(), person, ou, aff, aff_status)
            if (aff == self.const.affiliation_ansatt or
                aff == self.const.affiliation_student):
                raise PermissionDenied(
                    "Student/Ansatt affiliation can only be set by FS/LT")
            person.add_affiliation(ou.entity_id, aff,
                                   self.const.system_manual, aff_status)
            person.write_db()
        return ou, aff, aff_status

    # person affilation_add
    all_commands['person_affiliation_add'] = Command(
        ("person", "affiliation_add"), PersonId(), OU(), Affiliation(), AffiliationStatus(),
        perm_filter='can_add_affiliation')
    def person_affiliation_add(self, operator, person_id, ou, aff, aff_status):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status)
        return "OK, added %s@%s to %s" % (aff, self._format_ou_name(ou), person.entity_id)

    # person affilation_remove
    all_commands['person_affiliation_remove'] = Command(
        ("person", "affiliation_remove"), PersonId(), OU(), Affiliation(),
        perm_filter='can_remove_affiliation')
    def person_affiliation_remove(self, operator, person_id, ou, aff):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        self.ba.can_remove_affiliation(operator.get_entity_id(), person, ou, aff)
        for row in person.list_affiliations(person_id=person.entity_id,
                                            affiliation=aff):
            if row['ou_id'] != int(ou.entity_id):
                continue
            if int(row['source_system']) not \
                   in [int(self.const.system_fs), int(self.const.system_lt)]:
                person.delete_affiliation(ou.entity_id, aff,
                                          row['source_system'])
        return "OK, removed %s@%s from %s" % (aff, self._format_ou_name(ou), person.entity_id)

    # person create
    all_commands['person_create'] = Command(
        ("person", "create"), PersonId(),
        Date(help_ref='date_birth'), PersonName(help_ref="person_name_full"), OU(),
        Affiliation(), AffiliationStatus(),
        fs=FormatSuggestion("Created: %i",
        ("person_id",)), perm_filter='can_create_person')
    def person_create(self, operator, person_id, bdate, person_name,
                      ou, affiliation, aff_status):
        stedkode = ou
        try:
            ou = self._get_ou(stedkode=ou)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown OU (%s)" % ou
        try:
            aff = self._get_affiliationid(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown affiliation type (%s)" % affiliation
        self.ba.can_create_person(operator.get_entity_id(), ou, aff)
        person = Utils.Factory.get('Person')(self.db)
        person.clear()
        # TBD: The current implementation of ._parse_date() should
        # handle None input just fine; if that implementation is
        # correct, this test can be removed.
        if bdate is not None:
            bdate = self._parse_date(bdate)
            if bdate > self._today():
                raise CerebrumError, "Please check the date of birth, cannot register date_of_birth > now"
        if person_id:
            id_type, id = self._map_person_id(person_id)
        else:
            id_type = None
        gender = self.const.gender_unknown
        if id_type is not None and id:
            if id_type == self.const.externalid_fodselsnr:
                try:
                    if fodselsnr.er_mann(id):
                        gender = self.const.gender_male
                    else:
                        gender = self.const.gender_female
                except fodselsnr.InvalidFnrError, msg:
                    raise CerebrumError("Invalid birth-no: '%s'" % msg)
                try:
                    person.find_by_external_id(self.const.externalid_fodselsnr, id)
                    raise CerebrumError("A person with that fnr already exists")
                except Errors.TooManyRowsError:
                    raise CerebrumError("A person with that fnr already exists")
                except Errors.NotFoundError:
                    pass
                person.clear()
                person.affect_external_id(self.const.system_manual,
                                          self.const.externalid_fodselsnr)
                person.populate_external_id(self.const.system_manual,
                                            self.const.externalid_fodselsnr,
                                            id)
        person.populate(bdate, gender,
                        description='Manually created')
        person.affect_names(self.const.system_manual, self.const.name_full)
        person.populate_name(self.const.name_full,
                             person_name.encode('iso8859-1'))
        try:
            person.write_db()
            self._person_affiliation_add_helper(
                operator, person, stedkode, str(aff), aff_status)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        return {'person_id': person.entity_id}

    # person find
    all_commands['person_find'] = Command(
        ("person", "find"), PersonSearchType(), SimpleString(),
        SimpleString(optional=True),
        fs=FormatSuggestion("%6i   %10s   %-12s  %s",
                            ('id', format_day('birth'), 'account', 'name'),
                            hdr="%6s   %10s   %-12s  %s" % \
                            ('Id', 'Birth', 'Account', 'Name')))
    def person_find(self, operator, search_type, value, filter=None):
        # TODO: Need API support for this
        matches = []
        idcol = 'person_id'
        if search_type == 'person_id':
            person = self._get_person(*self._map_person_id(value))
            matches = [{'person_id': person.entity_id}]
        else:
            person = Utils.Factory.get('Person')(self.db)
            person.clear()
            if search_type == 'name':
                if len(value.strip(" \t%_")) < 3:
                    raise CerebrumError, \
                          "You must specify at least three letters of the name"
                if '%' not in value and '_' not in value:
                    # Add wildcards to start and end of value.
                    value = '%' + value + '%'
                matches = person.list_persons_by_name(
                    value,
                    name_variant=self.const.name_full,
                    source_system=self.const.system_cached,
                    return_name=True,
                    case_sensitive=(value != value.lower()))
            elif search_type == 'fnr':
                matches = person.list_external_ids(
                    id_type=self.const.externalid_fodselsnr,
                    external_id=value)
                idcol = 'entity_id'
            elif search_type == 'date':
                matches = person.find_persons_by_bdate(self._parse_date(value))
            elif search_type == 'stedkode':
                ou = self._get_ou(stedkode=value)
                if filter is not None:
                    try:
                        filter=self.const.PersonAffiliation(filter)
                    except Errors.NotFoundError:
                        raise CerebrumError, "Invalid affiliation %s" % affiliation
                matches = person.list_affiliations(ou_id=ou.entity_id,
                                                   affiliation=filter)
            else:
                raise CerebrumError, "Unknown search type (%s)" % search_type
        ret = []
        seen = {}
        person = Utils.Factory.get('Person')(self.db)
        acc = self.Account_class(self.db)
        for row in matches:
            # We potentially get multiple rows for a person when
            # s/he has more than one source system or affiliation.
            p_id = row[idcol]
            if p_id in seen:
                continue
            seen[p_id] = True
            person.clear()
            person.find(p_id)
            if row.has_key('name'):
                pname = row['name']
            else:
                pname = person.get_name(self.const.system_cached,
                                        getattr(self.const,
                                                cereconf.DEFAULT_GECOS_NAME))

            # Person.get_primary_account will not return expired
            # users.  Account.get_account_types will return the
            # primary account for the user, but it might be expired,
            # so further filtering should be done if a "perfect"
            # result is required.
            accounts = acc.get_account_types(owner_id=p_id,
                                             filter_expired=False)
            if accounts:
                acc.clear()
                acc.find(accounts[0]['account_id'])
                account_name = acc.account_name
            else:
                account_name = "<none>"
            # Ideally we'd fetch the authoritative last name, but
            # it's a lot of work.  We cheat and use the last word
            # of the name, which should work for 99.9% of the users.
            ret.append({'id': p_id,
                        'birth': person.birth_date,
                        'export_id': person.export_id,
                        'account': account_name,
                        'name': pname,
                        'lastname': pname.split(" ")[-1] })
        ret.sort(lambda a,b: (cmp(a['lastname'], b['lastname']) or
                              cmp(a['name'], b['name'])))
        return ret
    
    # person info
    all_commands['person_info'] = Command(
        ("person", "info"), PersonId(),
        fs=FormatSuggestion([
        ("Name:          %s\n" +
         "Export ID:     %s\n" +
         "Birth:         %s\n" +
         "Affiliations:  %s [from %s] (last: %s)",
         ("name", "export_id", format_day("birth"),
          "affiliation_1", "source_system_1","last_date_1")),
        ("               %s [from %s] (last: %s)",
         ("affiliation", "source_system","last_date")),
        ("Fnr:           %s [from %s]",
         ("fnr", "fnr_src"))
        ]))
    def person_info(self, operator, person_id):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        data = [{'name': person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME)),
                 'export_id': person.export_id,
                 'birth': person.birth_date,
                 'entity_id': person.entity_id}]
        affiliations = []
        sources = []
        last_dates = []
        for row in person.list_affiliations(person_id=person.entity_id,include_last=True):
            ou = self._get_ou(ou_id=row['ou_id'])
            date = row['last_date'].strftime("%Y-%m-%d")
            last_dates.append(date)
            affiliations.append("%s@%s" % (
                self.const.PersonAffStatus(row['status']),
                self._format_ou_name(ou)))
            sources.append(str(self.const.AuthoritativeSystem(row['source_system'])))
        if affiliations:
            data[0]['affiliation_1'] = affiliations[0]
            data[0]['source_system_1'] = sources[0]
            data[0]['last_date_1'] = last_dates[0]
        else:
            data[0]['affiliation_1'] = "<none>"
            data[0]['source_system_1'] = "<nowhere>"
            data[0]['last_date_1'] = "<none>"
        for i in range(1, len(affiliations)):
            data.append({'affiliation': affiliations[i],
                         'source_system': sources[i],
                         'last_date': last_dates[i]})
        account = self.Account_class(self.db)
        account_ids = [int(r['account_id'])
                       for r in account.list_accounts_by_owner_id(person.entity_id)]
        if (self.ba.is_superuser(operator.get_entity_id()) or
            operator.get_entity_id() in account_ids):
            for row in person.get_external_id(id_type=self.const.externalid_fodselsnr):
                data.append({'fnr': row['external_id'],
                             'fnr_src': str(
                    self.const.AuthoritativeSystem(row['source_system']))})
        return data

    # person set_id
    all_commands['person_set_id'] = Command(
        ("person", "set_id"), PersonId(help_ref="person_id:current"),
        PersonId(help_ref="person_id:new"))
    def person_set_id(self, operator, current_id, new_id):
        person = self._get_person(*self._map_person_id(current_id))
        idtype, id = self._map_person_id(new_id)
        self.ba.can_set_person_id(operator.get_entity_id(), person, idtype)
        person.affect_external_id(self.const.system_manual, idtype)
        person.populate_external_id(self.const.system_manual,
                                    idtype, id)
        person.write_db()
        return "OK, set '%s' as new id for '%s'" % (new_id, current_id)

    #person set_name
    all_commands['person_set_name'] = Command(
	("person", "set_name"),PersonId(help_ref="person_id_other"),
	PersonName(help_ref="person_name_full"),
	fs=FormatSuggestion("Name altered for: %i",
        ("person_id",)),
	perm_filter='can_create_person')
    def person_set_name(self, operator, person_id, person_fullname):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_create_person(operator.get_entity_id())        
	for a in person.get_affiliations():
	    if (int(a['source_system']) in
                [int(self.const.system_fs), int(self.const.system_lt)]):
		raise PermissionDenied("You are not allowed to alter names.")
	    else:
		pass
	    person.affect_names(self.const.system_manual, self.const.name_full)
	    person.populate_name(self.const.name_full,
				 person_fullname.encode('iso8859-1'))
	    try:
		person.write_db()
	    except self.db.DatabaseError, m:
		raise CerebrumError, "Database error: %s" % m
	    return {'person_id': person.entity_id}

    # person clear_name
    all_commands['person_clear_name'] = Command(
	("person", "clear_name"),PersonId(help_ref="person_id_other"),
	SourceSystem(help_ref="source_system", optional=True),
	fs=FormatSuggestion("Name removed for: %i",
        ("person_id",)),
	perm_filter='is_superuser')
    def person_clear_name(self, operator, person_id, source_system):
        person = self._get_person(*self._map_person_id(person_id))
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        if not source_system in cereconf.SYSTEM_LOOKUP_ORDER:
            raise CerebrumError("No such source system")
        for x in [self.const.name_first, self.const.name_last]:
            try:
                person.get_name(getattr(self.const, source_system), x)
            except Errors.NotFoundError:
                raise CerebrumError("No name registered from %s" % source_system)
            try:
                person._delete_name(getattr(self.const, source_system), x)
                person._update_cached_names()
            except:
                raise CerebrumError("Could not delete name from %s", source_system)
        return "Removed name from %s for %s" % (source_system, person_id)

    # person student_info
    all_commands['person_student_info'] = Command(
        ("person", "student_info"), PersonId(),
        fs=FormatSuggestion([
        ("Studieprogrammer: %s, %s, %s, %s, tildelt=%s->%s privatist: %s",
         ("studprogkode", "studieretningkode", "studierettstatkode", "studentstatkode", 
	  format_day("dato_tildelt"), format_day("dato_gyldig_til"), "privatist")),
        ("Eksamensmeldinger: %s (%s), %s",
         ("ekskode", "programmer", format_day("dato"))),
        ("Utd. plan: %s, %s, %d, %s",
         ("studieprogramkode", "terminkode_bekreft", "arstall_bekreft",
          format_day("dato_bekreftet"))),
        ("Semesterreg: %s, %s, betalt: %s, endret: %s",
         ("regformkode", "betformkode", format_day("dato_betaling"),
          format_day("dato_regform_endret")))
        ]),
        perm_filter='can_get_student_info')
    def person_student_info(self, operator, person_id):
        person = self._get_person(*self._map_person_id(person_id))
        self.ba.can_get_student_info(operator.get_entity_id(), person)
        fnr = person.get_external_id(id_type=self.const.externalid_fodselsnr,
                                     source_system=self.const.system_fs)
        if not fnr:
            raise CerebrumError("No matching fnr from FS")
        fodselsdato, pnum = fodselsnr.del_fnr(fnr[0]['external_id'])
        har_opptak = {}
        ret = []
        try:
            db = Database.connect(user="ureg2000", service="FSPROD.uit.no",
                                  DB_driver='Oracle')
        except Database.DatabaseError, e:
            self.logger.warn("Can't connect to FS (%s)" % e)
            raise CerebrumError("Can't connect to FS, try later")
        fs = FS(db)
        for row in fs.student.get_studierett(fodselsdato, pnum):
            har_opptak["%s" % row['studieprogramkode']] = \
                            row['status_privatist']
            ret.append({'studprogkode': row['studieprogramkode'],
                        'studierettstatkode': row['studierettstatkode'],
                        'studentstatkode': row['studentstatkode'],
			'studieretningkode': row['studieretningkode'],
                        'dato_tildelt': DateTime.DateTimeFromTicks(row['dato_studierett_tildelt']),
                        'dato_gyldig_til': DateTime.DateTimeFromTicks(row['dato_studierett_gyldig_til']),
                        'privatist': row['status_privatist']})

        for row in fs.student.get_eksamensmeldinger(fodselsdato, pnum):
            programmer = []
            for row2 in fs.info.get_emne_i_studieprogram(row['emnekode']):
                if har_opptak.has_key("%s" % row2['studieprogramkode']):
                    programmer.append(row2['studieprogramkode'])
            ret.append({'ekskode': row['emnekode'],
                        'programmer': ",".join(programmer),
                        'dato': DateTime.DateTimeFromTicks(row['dato_opprettet'])})
                      
        for row in fs.student.get_utdanningsplan(fodselsdato, pnum):
            ret.append({'studieprogramkode': row['studieprogramkode'],
                        'terminkode_bekreft': row['terminkode_bekreft'],
                        'arstall_bekreft': row['arstall_bekreft'],
                        'dato_bekreftet': DateTime.DateTimeFromTicks(row['dato_bekreftet'])})

        for row in fs.student.get_semreg(fodselsdato, pnum):
            ret.append({'regformkode': row['regformkode'],
                        'betformkode': row['betformkode'],
                        'dato_betaling': DateTime.DateTimeFromTicks(row['dato_betaling']),
                        'dato_regform_endret': DateTime.DateTimeFromTicks(row['dato_regform_endret'])})
        db.close()
        return ret

    # person user_priority
    all_commands['person_set_user_priority'] = Command(
        ("person", "set_user_priority"), AccountName(),
        SimpleString(help_ref='string_old_priority'),
        SimpleString(help_ref='string_new_priority'))
    def person_set_user_priority(self, operator, account_name,
                                 old_priority, new_priority):
        account = self._get_account(account_name)
        person = self._get_person('entity_id', account.owner_id)
        self.ba.can_set_person_user_priority(operator.get_entity_id(), account)
        try:
            old_priority = int(old_priority)
            new_priority = int(new_priority)
        except ValueError:
            raise CerebrumError, "priority must be a number"
        ou = None
        affiliation = None
        for row in account.get_account_types(filter_expired=False):
            if row['priority'] == old_priority:
                ou = row['ou_id']
                affiliation = row['affiliation']
        if ou is None:
            raise CerebrumError("Must specify an existing priority")
        account.set_account_type(ou, affiliation, new_priority)
        account.write_db()
        return "OK, set priority=%i for %s" % (new_priority, account_name)

    all_commands['person_list_user_priorities'] = Command(
        ("person", "list_user_priorities"), PersonId(),
        fs=FormatSuggestion(
        "%8s %8i %s", ('uname', 'priority', 'affiliation'),
        hdr="%8s %8s %s" % ("Uname", "Priority", "Affiliation")))
    def person_list_user_priorities(self, operator, person_id):
        ac = Utils.Factory.get('Account')(self.db)
        person = self._get_person(*self._map_person_id(person_id))
        ret = []
        for row in ac.get_account_types(all_persons_types=True,
                                        owner_id=person.entity_id):
            ac2 = self._get_account(row['account_id'], idtype='id')
            ou = self._get_ou(ou_id=row['ou_id'])
            ret.append({'uname': ac2.account_name,
                        'priority': row['priority'],
                        'affiliation': '%s@%s' % (
                self.num2const[int(row['affiliation'])], self._format_ou_name(ou))})
            ## This seems to trigger a wierd python bug:
            ## self.num2const[int(row['affiliation'], self._format_ou_name(ou))])})
        return ret

    #
    # quarantine commands
    #

    # quarantine disable
    all_commands['quarantine_disable'] = Command(
        ("quarantine", "disable"), EntityType(default="account"), Id(),
        QuarantineType(), Date(), perm_filter='can_disable_quarantine')
    def quarantine_disable(self, operator, entity_type, id, qtype, date):
        entity = self._get_entity(entity_type, id)
        date = self._parse_date(date)
        qconst = self._get_constant(qtype, "No such quarantine")
        qtype = int(qconst)
        self.ba.can_disable_quarantine(operator.get_entity_id(), entity, qtype)
        entity.disable_entity_quarantine(qtype, date)
        return "OK, disabled quarantine %s for %s" % (
            qconst, self._get_name_from_object (entity))

    # quarantine list
    all_commands['quarantine_list'] = Command(
        ("quarantine", "list"),
        fs=FormatSuggestion("%-16s  %1s  %-17s %s",
                            ('name', 'lock', 'shell', 'desc'),
                            hdr="%-15s %-4s %-17s %s" % \
                            ('Name', 'Lock', 'Shell', 'Description')))
    def quarantine_list(self, operator):
        ret = []
        for c in self.const.fetch_constants(self.const.Quarantine):
            lock = 'N'; shell = '-'
            rule = cereconf.QUARANTINE_RULES.get(str(c), {})
            if 'lock' in rule:
                lock = 'Y'
            if 'shell' in rule:
                shell = rule['shell'].split("/")[-1]
            ret.append({'name': "%s" % c,
                        'lock': lock,
                        'shell': shell,
                        'desc': c._get_description()})
        return ret

    # quarantine remove
    all_commands['quarantine_remove'] = Command(
        ("quarantine", "remove"), EntityType(default="account"), Id(), QuarantineType(),
        perm_filter='can_remove_quarantine')
    def quarantine_remove(self, operator, entity_type, id, qtype):
        entity = self._get_entity(entity_type, id)
        qconst = self._get_constant(qtype, "No such quarantine")
        qtype = int(qconst)
        self.ba.can_remove_quarantine(operator.get_entity_id(), entity, qtype)
        entity.delete_entity_quarantine(qtype)
        return "OK, removed quarantine %s for %s" % (
            qconst, self._get_name_from_object (entity))

    # quarantine set
    all_commands['quarantine_set'] = Command(
        ("quarantine", "set"), EntityType(default="account"), Id(repeat=True),
        QuarantineType(), SimpleString(help_ref="string_why"),
        SimpleString(help_ref="string_from_to"), perm_filter='can_set_quarantine')
    def quarantine_set(self, operator, entity_type, id, qtype, why, date):
        date_start, date_end = self._parse_date_from_to(date)
        entity = self._get_entity(entity_type, id)
        qconst = self._get_constant(qtype, "No such quarantine")
        qtype = int(qconst)
        self.ba.can_set_quarantine(operator.get_entity_id(), entity, qtype)
        rows = entity.get_entity_quarantine(type=qtype)
        if rows:
            raise CerebrumError("User already has a quarantine of this type")
        try:
            entity.add_entity_quarantine(qtype, operator.get_entity_id(), why, date_start, date_end)
        except AttributeError:    
            raise CerebrumError("Quarantines cannot be set on %s" % entity_type)
        return "OK, set quarantine %s for %s" % (
            qconst, self._get_name_from_object (entity))

    # quarantine show
    all_commands['quarantine_show'] = Command(
        ("quarantine", "show"), EntityType(default="account"), Id(),
        fs=FormatSuggestion("%-14s %-16s %-16s %-14s %-8s %s",
                            ('type', format_time('start'), format_time('end'),
                             format_day('disable_until'), 'who', 'why'),
                            hdr="%-14s %-16s %-16s %-14s %-8s %s" % \
                            ('Type', 'Start', 'End', 'Disable until', 'Who',
                             'Why')),
        perm_filter='can_show_quarantines')
    def quarantine_show(self, operator, entity_type, id):
        ret = []
        entity = self._get_entity(entity_type, id)
        self.ba.can_show_quarantines(operator.get_entity_id(), entity)
        for r in entity.get_entity_quarantine():
            acc = self._get_account(r['creator_id'], idtype='id')
            ret.append({'type': "%s" % self.num2const[int(r['quarantine_type'])],
                        'start': r['start_date'],
                        'end': r['end_date'],
                        'disable_until': r['disable_until'],
                        'who': acc.account_name,
                        'why': r['description']})
        return ret
    #
    # spread commands
    #

    # spread add
    all_commands['spread_add'] = Command(
        ("spread", "add"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
    def spread_add(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spreadconst = self._get_constant(spread, "No such spread")
        spread = int(spreadconst)
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        try:
            entity.add_spread(spread)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        if entity_type == 'account':
            self.__spread_sync_group(entity)
        return "OK, added spread %s for %s" % (
            spreadconst, self._get_name_from_object (entity))

    # spread list
    all_commands['spread_list'] = Command(
        ("spread", "list"),
        fs=FormatSuggestion("%-14s %s", ('name', 'desc'),
                            hdr="%-14s %s" % ('Name', 'Description')))
    def spread_list(self, operator):
        ret = []
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _SpreadCode):
                ret.append({'name': "%s" % tmp, 'desc': unicode(tmp._get_description(), 'iso8859-1')})
        return ret

    # spread remove
    all_commands['spread_remove'] = Command(
        ("spread", "remove"), EntityType(default='account'), Id(), Spread(),
        perm_filter='can_add_spread')
    def spread_remove(self, operator, entity_type, id, spread):
        entity = self._get_entity(entity_type, id)
        spreadconst = self._get_constant(spread, "No such spread")
        spread = int(spreadconst)
        self.ba.can_add_spread(operator.get_entity_id(), entity, spread)
        entity.delete_spread(spread)
        if entity_type == 'account':
            self.__spread_sync_group(entity)
        return "OK, removed spread %s from %s" % (
            spreadconst, self._get_name_from_object (entity))

    def __spread_sync_group(self, account, group=None):
        """Make sure the group has the NIS spreads corresponding to
        the NIS spreads of the account.  The account and group
        arguments may be passed as Entity objects.  If group is None,
        the group with the same name as account is modified, if it
        exists."""
        
        if account.np_type or account.owner_type == self.const.entity_group:
            return

        if group is None:
            name = account.get_name(self.const.account_namespace)
            try:
                group = self._get_group(name)
            except CerebrumError:
                return

        # FIXME: Identifying personal groups is not a very precise
        # process.  One alternative would be to use the description:
        #
        # if not group.description.startswith('Personal file group for '):
        #     return
        #
        # The alternative is to use the bofhd_auth tables to see if
        # the account has the 'Group-owner' op_set for this group, and
        # this is implemented below.

        op_set = BofhdAuthOpSet(self.db)
        op_set.find_by_name('Group-owner')

        baot = BofhdAuthOpTarget(self.db)
        targets = baot.list(entity_id=group.entity_id)
        if len(targets) == 0:
            return
        bar = BofhdAuthRole(self.db)
        is_moderator = False
        for auth in bar.list(op_target_id=targets[0]['op_target_id']):
            if (auth['entity_id'] == account.entity_id and
                auth['op_set_id'] == op_set.op_set_id):
                is_moderator = True
        if not is_moderator:
            return

        mapping = { int(self.const.spread_uit_nis_user):
                    int(self.const.spread_uit_nis_fg),
                    int(self.const.spread_uit_ad_account):
                    int(self.const.spread_uit_ad_group),
                    int(self.const.spread_ifi_nis_user):
                    int(self.const.spread_ifi_nis_fg) }
        wanted = []
        for r in account.get_spread():
            spread = int(r['spread'])
            if spread in mapping:
                wanted.append(mapping[spread])
        for r in group.get_spread():
            spread = int(r['spread'])
            if not spread in mapping.values():
                pass
            elif spread in wanted:
                wanted.remove(spread)
            else:
                group.delete_spread(spread)
        for spread in wanted:
            group.add_spread(spread)

    #
    # user commands
    #

    # user affiliation_add
    all_commands['user_affiliation_add'] = Command(
        ("user", "affiliation_add"), AccountName(), OU(), Affiliation(), AffiliationStatus(),
        perm_filter='can_add_account_type')
    def user_affiliation_add(self, operator, accountname, ou, aff, aff_status):
        account = self._get_account(accountname)
        person = self._get_person('entity_id', account.owner_id)
        ou, aff, aff_status = self._person_affiliation_add_helper(
            operator, person, ou, aff, aff_status)
        self.ba.can_add_account_type(operator.get_entity_id(), account, ou, aff, aff_status)
        account.set_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, added %s@%s to %s" % (aff, self._format_ou_name(ou),
                                          accountname)

    # user affiliation_remove
    all_commands['user_affiliation_remove'] = Command(
        ("user", "affiliation_remove"), AccountName(), OU(), Affiliation(),
        perm_filter='can_remove_account_type')
    def user_affiliation_remove(self, operator, accountname, ou, aff): 
        account = self._get_account(accountname)
        aff = self._get_affiliationid(aff)
        ou = self._get_ou(stedkode=ou)
        self.ba.can_remove_account_type(operator.get_entity_id(),
                                        account, ou, aff)
        account.del_account_type(ou.entity_id, aff)
        account.write_db()
        return "OK, removed %s@%s from %s" % (aff, self._format_ou_name(ou),
                                              accountname)

    def _user_create_prompt_func_helper(self, ac_type, session, *args):
        """A prompt_func on the command level should return
        {'prompt': message_string, 'map': dict_mapping}
        - prompt is simply shown.
        - map (optional) maps the user-entered value to a value that
          is returned to the server, typically when user selects from
          a list."""
        all_args = list(args[:])

        if not all_args:
            return {'prompt': "Person identification",
                    'help_ref': "user_create_person_id"}
        arg = all_args.pop(0)
        if arg.startswith("group:"):
            group_owner = True
        else:
            group_owner = False
        if not all_args or group_owner:
            if group_owner:
                group = self._get_group(arg.split(":")[1])
                if all_args:
                    all_args.insert(0, group.entity_id)
                else:
                    all_args = [group.entity_id]
            else:
                c = self._find_persons(arg)
                map = [(("%-8s %s", "Id", "Name"), None)]
                for i in range(len(c)):
                    person = self._get_person("entity_id", c[i]['person_id'])
                    map.append((
                        ("%8i %s", int(c[i]['person_id']),
                         person.get_name(self.const.system_cached, self.const.name_full)),
                        int(c[i]['person_id'])))
                if not len(map) > 1:
                    raise CerebrumError, "No persons matched"
                return {'prompt': "Choose person from list",
                        'map': map,
                        'help_ref': 'user_create_select_person'}
        owner_id = all_args.pop(0)
        if not group_owner:
            person = self._get_person("entity_id", owner_id)
            existing_accounts = []
            account = self.Account_class(self.db)
            for r in account.list_accounts_by_owner_id(person.entity_id):
                account = self._get_account(r['account_id'], idtype='id')
                if account.expire_date:
                    exp = account.expire_date.strftime('%Y-%m-%d')
                else:
                    exp = '<not set>'
                existing_accounts.append("%-10s %s" % (account.account_name,
                                                       exp))
            if existing_accounts:
                existing_accounts = "Existing accounts:\n%-10s %s\n%s\n" % (
                    "uname", "expire", "\n".join(existing_accounts))
            else:
                existing_accounts = ''
            if existing_accounts:
                if not all_args:
                    return {'prompt': "%sContinue? (y/n)" % existing_accounts}
                yes_no = all_args.pop(0)
                if not yes_no == 'y':
                    raise CerebrumError, "Command aborted at user request"
            if not all_args:
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s@%s" % (
                        self.const.PersonAffStatus(aff['status']),
                        self._format_ou_name(ou))
                    map.append((("%s", name),
                                {'ou_id': int(aff['ou_id']), 'aff': int(aff['affiliation'])}))
                if not len(map) > 1:
                    raise CerebrumError(
                        "Person has no affiliations. Try person affiliation_add")
                return {'prompt': "Choose affiliation from list", 'map': map}
            affiliation = all_args.pop(0)
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type'}
            np_type = all_args.pop(0)
        if ac_type == 'PosixUser':
            if not all_args:
                return {'prompt': "Default filegroup"}
            filgruppe = all_args.pop(0)
            if not all_args:
                return {'prompt': "Shell", 'default': 'bash'}
            shell = all_args.pop(0)
            if not all_args:
                return {'prompt': "Disk", 'help_ref': 'disk'}
            disk = all_args.pop(0)
        if not all_args:
            ret = {'prompt': "Username", 'last_arg': True}
            posix_user = PosixUser.PosixUser(self.db)
            if not group_owner:
                try:
                    person = self._get_person("entity_id", owner_id)
                    fname, lname = [
                        person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last) ]
                    sugg = posix_user.suggest_unames(self.const.account_namespace, fname, lname)
                    if sugg:
                        ret['default'] = sugg[0]
                except ValueError:
                    pass    # Failed to generate a default username
            return ret
        raise CerebrumError, "Client called prompt func with too many arguments"

    def user_create_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('PosixUser', session, *args)

    def _user_create_set_account_type(self, account,
                                      owner_id, ou_id, affiliation):
        person = self._get_person('entity_id', owner_id)
        try:
            affiliation=self.const.PersonAffiliation(affiliation)
            # make sure exist
            int(affiliation)
        except Errors.NotFoundError:
            raise CerebrumError, "Invalid affiliation %s" % affiliation
        for aff in person.get_affiliations():
            if aff['ou_id'] == ou_id and aff['affiliation'] == affiliation:
                break
        else:
            raise CerebrumError, \
                "Owner did not have any affiliation %s" % affiliation        
        account.set_account_type(ou_id, affiliation)
        
    # user create
    all_commands['user_create'] = Command(
        ('user', 'create'), prompt_func=user_create_prompt_func,
        fs=FormatSuggestion("Created uid=%i", ("uid",)),
        perm_filter='can_create_user')
    def user_create(self, operator, *args):
        if args[0].startswith('group:'):
            group_id, np_type, filegroup, shell, home, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = int(self._get_constant(np_type, "Unknown account type"))
        else:
            if len(args) == 7:
                idtype, person_id, affiliation, filegroup, shell, home, uname = args
            else:
                idtype, person_id, yes_no, affiliation, filegroup, shell, home, uname = args
            owner_type = self.const.entity_person
            owner_id = self._get_person("entity_id", person_id).entity_id
            np_type = None
            
        group=self._get_group(filegroup, grtype="PosixGroup")
        posix_user = PosixUser.PosixUser(self.db)
        uid = posix_user.get_free_uid()
        shell = self._get_shell(shell)
        if home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hardcoded path")
            disk_id, home = None, home[1:]
        posix_user.clear()
        gecos = None
        expire_date = None
        self.ba.can_create_user(operator.get_entity_id(), owner_id, disk_id)

        posix_user.populate(uid, group.entity_id, gecos, shell, name=uname,
                            owner_type=owner_type,
                            owner_id=owner_id, np_type=np_type,
                            creator_id=operator.get_entity_id(),
                            expire_date=expire_date)
        try:
            posix_user.write_db()
            for spread in cereconf.BOFHD_NEW_USER_SPREADS:
                posix_user.add_spread(self._get_constant(spread,
                                                         "No such spread"))
            homedir_id = posix_user.set_homedir(
                disk_id=disk_id, home=home,
                status=self.const.home_status_not_created)
            posix_user.set_home(self.const.spread_uit_nis_user, homedir_id)
            # For correct ordering of ChangeLog events, new users
            # should be signalled as "exported to" a certain system
            # before the new user's password is set.  Such systems are
            # flawed, and should be fixed.
            passwd = posix_user.make_passwd(uname)
            posix_user.set_password(passwd)
            # And, to write the new password to the database, we have
            # to .write_db() one more time...
            posix_user.write_db()
            if len(args) != 6:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(posix_user, owner_id,
                                                   ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(posix_user.entity_id),
                                                    'password': passwd})
        return {'uid': uid}

    # user delete
    all_commands['user_delete'] = Command(
        ("user", "delete"), AccountName(), perm_filter='can_delete_user')
    def user_delete(self, operator, accountname):
        # TODO: How do we delete accounts?
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        if account.is_deleted():
            raise CerebrumError, "User is already deleted"
        br = BofhdRequests(self.db, self.const)
        br.add_request(operator.get_entity_id(), br.now,
                       self.const.bofh_delete_user,
                       account.entity_id, None,
                       state_data=int(self.const.spread_uit_nis_user))
        return "User %s queued for deletion immediately" % account.account_name

        # raise NotImplementedError, "Feel free to implement this function"

    all_commands['user_set_disk_quota'] = Command(
        ("user", "set_disk_quota"), AccountName(), Integer(help_ref="disk_quota_size"),
        Date(help_ref="disk_quota_expire_date"), SimpleString(help_ref="string_why"),
        perm_filter='can_set_disk_quota')
    def user_set_disk_quota(self, operator, accountname, size, date, why):
        account = self._get_account(accountname)
        try:
            age = DateTime.strptime(date, '%Y-%m-%d') - DateTime.now()
        except:
            raise CerebrumError, "Error parsing date"
        why = why.strip()
        if len(why) < 3:
            raise CerebrumError, "Why cannot be blank"
        unlimited = forever = False
        if age.days > 185:
            forever = True
        try:
            size = int(size)
        except ValueError:
            raise CerebrumError, "Expected int as size"
        if size > 1024 or size < 0:    # "unlimited" for perm-check = +1024M
            unlimited = True
        self.ba.can_set_disk_quota(operator.get_entity_id(), account,
                                   unlimited=unlimited, forever=forever)
        home = account.get_home(self.const.spread_uit_nis_user)
        _date = self._parse_date(date)
        if size < 0:               # Unlimited
            size = None
        dq = DiskQuota(self.db)
        dq.set_quota(home['homedir_id'], override_quota=size,
                     override_expiration=_date, description=why)
        return "OK, quota overridden for %s" % accountname

    # user gecos
    all_commands['user_gecos'] = Command(
        ("user", "gecos"), AccountName(), PosixGecos(),
        perm_filter='can_set_gecos')
    def user_gecos(self, operator, accountname, gecos):
        account = self._get_account(accountname, actype="PosixUser")
        # Set gecos to NULL if user requests a whitespace-only string.
        self.ba.can_set_gecos(operator.get_entity_id(), account)
        # TBD: Should we allow 8-bit characters?
        if isinstance(gecos, unicode):
            raise CerebrumError, "GECOS can only contain US-ASCII."
        account.gecos = gecos.strip() or None
        account.write_db()
        # TBD: As the 'gecos' attribute lives in class PosixUser,
        # which is ahead of AccountEmailMixin in the MRO of 'account',
        # the write_db() method of AccountEmailMixin will receive a
        # "no updates happened" from its call to superclasses'
        # write_db().  Is there a better way to solve this kind of
        # problem than by adding explicit calls to one if the mixin's
        # methods?  The following call will break if anyone tries this
        # code with an Email-less cereconf.CLASS_ACCOUNT.
        account.update_email_addresses()
        return "OK, set gecos for %s to '%s'" % (accountname, gecos)

    # user history
    all_commands['user_history'] = Command(
        ("user", "history"), AccountName(),
        perm_filter='can_show_history')
    def user_history(self, operator, accountname):
        account = self._get_account(accountname)
        self.ba.can_show_history(operator.get_entity_id(), account)
        ret = []
        for r in self.db.get_log_events(0, subject_entity=account.entity_id):
            ret.append(self._format_changelog_entry(r))
        return "\n".join(ret)

    # user info
    all_commands['user_info'] = Command(
        ("user", "info"), AccountName(),
        fs=FormatSuggestion([("Username:      %s\n"+
                              "Spreads:       %s\n" +
                              "Affiliations:  %s\n" +
                              "Expire:        %s\n" +
                              "Home:          %s (status: %s)\n" +
                              "Entity id:     %i\n" +
                              "Owner id:      %i (%s: %s)",
                              ("username", "spread", "affiliations",
                               format_day("expire"),
                               "home", "home_status", "entity_id", "owner_id",
                               "owner_type", "owner_desc")),
                             ("Disk quota:    %s MiB",
                              ("disk_quota",)),
                             ("DQ override:   %s MiB (until %s: %s)",
                              ("dq_override", format_day("dq_expire"), "dq_why")),
                             ("UID:           %i\n" +
                              "Default fg:    %i=%s\n" +
                              "Gecos:         %s\n" +
                              "Shell:         %s",
                              ('uid', 'dfg_posix_gid', 'dfg_name', 'gecos',
                               'shell')),
                             ("Quarantined:   %s",
                              ("quarantined",)),
                             "Email:         %s\n"]))
    def user_info(self, operator, accountname):
        is_posix = False
        try: 
            account = self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            account = self._get_account(accountname)
        if account.is_deleted() and not self.ba.is_superuser(operator.get_entity_id()):
            raise CerebrumError("User is deleted")
        affiliations = []
        for row in account.get_account_types(filter_expired=False):
            ou = self._get_ou(ou_id=row['ou_id'])
            affiliations.append("%s@%s" % (self.num2const[int(row['affiliation'])],
                                           self._format_ou_name(ou)))
        try:
            tmp = account.get_home(self.const.spread_uit_ldap_account)
            home_status = "%s" % self.num2const[int(tmp['status'])]
        except Errors.NotFoundError:
            tmp = {'disk_id': None, 'home': None, 'status': None,
                   'homedir_id': None}
            home_status = None

        try:
            einfo = self.email_info(operator, accountname)
            email_default = einfo[0]['def_addr']
        except Exception,m:
            email_default = "None"

        ret = {'entity_id': account.entity_id,
               'username': account.account_name,
               'email': email_default,
               'spread': ",".join(["%s" % self.num2const[int(a['spread'])]
                                   for a in account.get_spread()]),
               'affiliations': (",\n" + (" " * 15)).join(affiliations),
               'expire': account.expire_date,
               'home_status': home_status,
               'owner_id': account.owner_id,
               'owner_type': str(self.num2const[int(account.owner_type)])}
        try:
            self.ba.can_show_disk_quota(operator.get_entity_id(), account)
            can_see_quota = True
        except PermissionDenied:
            can_see_quota = False
        if tmp['homedir_id'] and can_see_quota:
            try:
                dq = DiskQuota(self.db)
                dq_row = dq.get_quota(tmp['homedir_id'])
                ret['disk_quota'] = dq_row['quota']
                if dq_row['quota'] is not None:
                    ret['disk_quota'] = str(dq_row['quota'])
                # Only display recent quotas
                days_left = ((dq_row['override_expiration'] or DateTime.Epoch) -
                             DateTime.now()).days
                if days_left > -30:
                    ret['dq_override'] = dq_row['override_quota']
                    if dq_row['override_quota'] is not None:
                        ret['dq_override'] = str(dq_row['override_quota'])
                    ret['dq_expire'] = dq_row['override_expiration']
                    ret['dq_why'] = dq_row['description']
                    if days_left < 0:
                        ret['dq_why'] += " [INACTIVE]"
            except Errors.NotFoundError:
                pass

        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            ret['owner_desc'] = person.get_name(self.const.system_cached,
                                                getattr(self.const,
                                                        cereconf.DEFAULT_GECOS_NAME))
        else:
            grp = self._get_group(account.owner_id, idtype='id')
            ret['owner_desc'] = grp.group_name

        ret['home']=account.resolve_homedir(disk_id=tmp['disk_id'],
                                            home=tmp['home'])
        if is_posix:
            group = self._get_group(account.gid_id, idtype='id', grtype='PosixGroup')
            ret['uid'] = account.posix_uid
            ret['dfg_posix_gid'] = group.posix_gid
            ret['dfg_name'] = group.group_name
            ret['gecos'] = account.gecos
            ret['shell'] = str(self.num2const[int(account.shell)])
        # TODO: Return more info about account
        quarantined = None
        now = DateTime.now()
        for q in account.get_entity_quarantine():
            if q['start_date'] <= now:
                if (q['end_date'] is not None and
                    q['end_date'] < now):
                    quarantined = 'expired'
                elif (q['disable_until'] is not None and
                    q['disable_until'] > now):
                    quarantined = 'disabled'
                else:
                    quarantined = 'active'
                    break
            else:
                quarantined = 'pending'
        if quarantined:
            ret['quarantined'] = quarantined
        return ret


    def _map_template(self, num=None):
        """If num==None: return list of avail templates, else return
        selected template """
        tpls = []
        n = 1
        keys = cereconf.BOFHD_TEMPLATES.keys()
        keys.sort()
        for k in keys:
            for tpl in cereconf.BOFHD_TEMPLATES[k]:
                tpls.append("%s" % (tpl[2]))
                if num is not None and n == int(num):
                    return (k, tpl[0], tpl[1])
                n += 1
        if num is not None:
            raise CerebrumError, "Unknown template selected"
        return tpls

    def _get_cached_passwords(self, operator):
        ret = []
        for r in operator.get_state():
            # state_type, entity_id, state_data, set_time
            if r['state_type'] in ('new_account_passwd', 'user_passwd'):
                ret.append({'account_id': self._get_entity_name(
                    self.const.entity_account, r['state_data']['account_id']),
                            'password': r['state_data']['password'],
                            'operation': r['state_type']})
        return ret

    all_commands['user_find'] = Command(
        ("user", "find"), UserSearchType(), SimpleString(), SimpleString(optional=True),
        YesNo(default='n', help_ref='yes_no_include_expired'),
        fs=FormatSuggestion("%6i   %-12s %s",
                            ('entity_id', 'username', format_day("expire")),
                            hdr="%6s   %-10s   %-12s" % \
                            ('Id', 'Uname', 'Expire-date')))
    def user_find(self, operator, search_type, value,
                  include_expired="n", filter=None,
                  perm_filter='is_superuser'):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        acc = self.Account_class(self.db)
        if search_type == 'stedkode':
            ou = self._get_ou(stedkode=value)
            if filter is not None:
                try:
                    filter=self.const.PersonAffiliation(filter)
                except Errors.NotFoundError:
                    raise CerebrumError, "Invalid affiliation %s" % affiliation
            include_expired = include_expired.lower().startswith("n")
            rows=acc.list_accounts_by_type(ou_id=ou.entity_id, affiliation=filter,
                                           filter_expired=not include_expired)
        elif search_type == 'host':
            host = self._get_host(value)
            rows = acc.list_account_home(host_id=int(host.entity_id))
        elif search_type == 'disk':
            disk = self._get_disk(value)[0]
            rows = acc.list_account_home(disk_id=int(disk.entity_id))
        else:
            raise CerebrumError, "Unknown search type (%s)" % search_type
        ac_ids = [int(r['account_id']) for r in rows]
        ac_ids.sort()
        ret = []
        for a in ac_ids:
            acc.clear()
            acc.find(a)
            ret.append({'entity_id': a,
                        'expire': acc.expire_date,
                        'username': acc.account_name})
        return ret

    # user move
    def user_move_prompt_func(self, session, *args):
        all_args = list(args[:])
        print all_args
        if not all_args:
            mt = MoveType()
            return mt.get_struct(self)
        mtype = all_args.pop(0)
        if not all_args:
            an = AccountName()
            return an.get_struct(self)
        ac_name = all_args.pop(0)
        if mtype in ("immediate", "batch", "nofile", "hard_nofile"):
            if not all_args:
                di = DiskId()
                r = di.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif mtype in ("student", "student_immediate", "confirm", "cancel"):
            return {'last_arg': True}
        elif mtype in ("request",):
            if not all_args:
                di = DiskId()
                return di.get_struct(self)
            disk = all_args.pop(0)
            if not all_args:
                ss = SimpleString(help_ref="string_why")
                r = ss.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        elif mtype in ("give",):
            if not all_args:
                who = GroupName()
                return who.get_struct(self)
            who = all_args.pop(0)
            if not all_args:
                ss = SimpleString(help_ref="string_why")
                r = ss.get_struct(self)
                r['last_arg'] = True
                return r
            return {'last_arg': True}
        raise CerebrumError, "Bad user_move command (%s)" % mtype
        
    all_commands['user_move'] = Command(
        ("user", "move"), prompt_func=user_move_prompt_func,
        perm_filter='can_move_user')
    def user_move(self, operator, move_type, accountname, *args):
        ifi_spread_warn = ""
        ifi_spread = False
        account = self._get_account(accountname)
        if account.is_expired():
            raise CerebrumError, "Account %s has expired" % account.account_name
        br = BofhdRequests(self.db, self.const)
        spread = int(self.const.spread_uit_nis_user)
        if move_type in ("immediate", "batch", "nofile"):
            disk_id = self._get_disk(args[0])[1]
            if disk_id is None:
                raise CerebrumError, "Bad destination disk"
            self.ba.can_move_user(operator.get_entity_id(), account, disk_id)
            for r in account.get_spread():
                if r['spread'] == int(self.const.spread_ifi_nis_user):
                    ifi_spread = True
            if ifi_spread and not re.match(r'^/ifi/', args[0]):
                ifi_spread_warn = "WARNING: moving user with a NIS_user@ifi-spread to a non-IFI disk.\n"
            if move_type == "immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               self.const.bofh_move_user_now,
                               account.entity_id, disk_id, state_data=spread)
                return ifi_spread_warn + "Command queued for immediate execution."
            elif move_type == "batch":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, disk_id, state_data=spread)
                return ifi_spread_warn + "Move queued for execution at %s." % br.batch_time 
            elif move_type == "nofile":
                ah = account.get_home(spread)
                account.set_homedir(current_id=ah['homedir_id'],
                                    disk_id=disk_id)
                account.write_db()
                return ifi_spread_warn + "User moved."
        elif move_type in ("hard_nofile",):
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hard_nofile")
            ah = account.get_home(spread)
            account.set_homedir(current_id=ah['homedir_id'], home=args[0])
            return "OK, user moved to hardcoded homedir"
        elif move_type in ("student", "student_immediate", "confirm", "cancel"):
            self.ba.can_give_user(operator.get_entity_id(), account)
            if move_type == "student":
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_student,
                               account.entity_id, None, state_data=spread)
                return "student-move queued for execution at %s" % br.batch_time
            elif move_type == "student_immediate":
                br.add_request(operator.get_entity_id(), br.now,
                               self.const.bofh_move_student,
                               account.entity_id, None, state_data=spread)
                return "student-move queued for immediate execution"
            elif move_type == "confirm":
                r = br.get_requests(entity_id=account.entity_id,
                                    operation=self.const.bofh_move_request)
                if not r:
                    raise CerebrumError, "No matching request found"
                br.delete_request(account.entity_id,
                                  operation=self.const.bofh_move_request)
                # Flag as authenticated
                br.add_request(operator.get_entity_id(), br.batch_time,
                               self.const.bofh_move_user,
                               account.entity_id, r[0]['destination_id'],
                               state_data=spread)
                return "move queued for execution at %s" % br.batch_time
            elif move_type == "cancel":
                # TBD: Should superuser delete other request types as well?
                count = 0
                for tmp in br.get_requests(entity_id=account.entity_id):
                    if tmp['operation'] in (
                        self.const.bofh_move_student, self.const.bofh_move_user,
                        self.const.bofh_move_give, self.const.bofh_move_request,
                        self.const.bofh_move_user_now):
                        count += 1
                        br.delete_request(request_id=tmp['request_id'])
                return "OK, %i bofhd requests deleted" % count
        elif move_type in ("request",):
            disk, why = args[0], args[1]
            disk_id = self._get_disk(disk)[1]
            if len(why) > 80:
                raise CerebrumError, \
                      "Too long explanation, maximum length is 80"
            self.ba.can_receive_user(operator.get_entity_id(), account, disk_id)
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_request,
                           account.entity_id, disk_id, why)
            return "OK, request registered"
        elif move_type in ("give",):
            self.ba.can_give_user(operator.get_entity_id(), account)
            group, why = args[0], args[1]
            group = self._get_group(group)
            if len(why) > 80:
                raise CerebrumError, \
                      "Too long explanation, maximum length is 80"
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_move_give,
                           account.entity_id, group.entity_id, why)
            return "OK, 'give' registered"

    # user password
    all_commands['user_password'] = Command(
        ('user', 'password'), AccountName(), AccountPassword(optional=True))
    def user_password(self, operator, accountname, password=None):
        account = self._get_account(accountname)
        self.ba.can_set_password(operator.get_entity_id(), account)
        if password is None:
            password = account.make_passwd(accountname)
        else:	# UIT: hack to allow bofh_admin set a specific password on a user.
            if ((operator.get_entity_id() <> account.entity_id) and
                (self._get_entity_name(None,operator.get_entity_id()) != "bofh_admin")):
                raise CerebrumError, \
                      "Cannot specify password for another user."
            if isinstance(password, unicode):  # crypt.crypt don't like unicode
                password = password.encode('iso8859-1')
        try:
            pc = PasswordChecker.PasswordChecker(self.db)
            pc.goodenough(account, password)
        except PasswordChecker.PasswordGoodEnoughException, m:
            raise CerebrumError, "Bad password: %s" % m
        account.set_password(password)
        try:
            account.write_db()
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("user_passwd", {'account_id': int(account.entity_id),
                                             'password': password})
        # Remove "weak password" quarantine
        for r in account.get_entity_quarantine():
            if int(r['quarantine_type']) == self.const.quarantine_autopassord:
                account.delete_entity_quarantine(self.const.quarantine_autopassord)

        if account.get_entity_quarantine():
            return "OK.  Warning: user has quarantine"
        return "Password altered. Please use misc list_password to print or view the new password."
    
    # user promote_posix
    all_commands['user_promote_posix'] = Command(
        ('user', 'promote_posix'), AccountName(), GroupName(),
        PosixShell(default="bash"), DiskId(),
        perm_filter='can_create_user')
    def user_promote_posix(self, operator, accountname, dfg=None, shell=None,
                          home=None):
        is_posix = False
        try:
            self._get_account(accountname, actype="PosixUser")
            is_posix = True
        except CerebrumError:
            pass
        if is_posix:
            raise CerebrumError("%s is already a PosixUser" % accountname)
        account = self._get_account(accountname)
        pu = PosixUser.PosixUser(self.db)
        old_uid = self._lookup_old_uid(account.entity_id)
        if old_uid is None:
            uid = pu.get_free_uid()
        else:
            uid = old_uid
        group = self._get_group(dfg, grtype='PosixGroup')
        shell = self._get_shell(shell)
        if not home:
            raise CerebrumError("home cannot be empty")
        elif home[0] != ':':  # Hardcoded path
            disk_id, home = self._get_disk(home)[1:3]
        else:
            if not self.ba.is_superuser(operator.get_entity_id()):
                raise PermissionDenied("only superusers may use hardcoded path")
            disk_id, home = None, home[1:]
        if account.owner_type == self.const.entity_person:
            person = self._get_person("entity_id", account.owner_id)
        else:
            person = None
        self.ba.can_create_user(operator.get_entity_id(), person, disk_id)
        pu.populate(uid, group.entity_id, None, shell, parent=account)
        pu.write_db()
        homedir_id = pu.set_homedir(
            disk_id=disk_id, home=home,
            status=self.const.home_status_not_created)
        pu.set_home(self.const.spread_uit_nis_user,
                    homedir_id)
        if old_uid is None:
            tmp = ', new uid=%i' % uid
        else:
            tmp = ', reused old uid=%i' % old_uid
        return "OK, promoted %s to posix user%s" % (accountname, tmp)

    # user posix_delete
    all_commands['user_demote_posix'] = Command(
        ('user', 'demote_posix'), AccountName(), perm_filter='can_create_user')
    def user_demote_posix(self, operator, accountname):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("currently limited to superusers")
        user = self._get_account(accountname, actype="PosixUser")
        user.delete_posixuser()
        return "OK, %s was demoted" % accountname

    def user_create_basic_prompt_func(self, session, *args):
        return self._user_create_prompt_func_helper('Account', session, *args)
    
    # user create
    all_commands['user_reserve'] = Command(
        ('user', 'create_reserve'), prompt_func=user_create_basic_prompt_func,
        fs=FormatSuggestion("Created account_id=%i", ("account_id",)),
        perm_filter='is_superuser')
    def user_reserve(self, operator, *args):
        if args[0].startswith('group:'):
            group_id, np_type, uname = args
            owner_type = self.const.entity_group
            owner_id = self._get_group(group_id.split(":")[1]).entity_id
            np_type = int(self._get_constant(np_type, "Unknown account type"))
            affiliation = None
            owner_type = self.const.entity_group
        else:
            if len(args) == 4:
                idtype, person_id, affiliation, uname = args
            else:
                idtype, person_id, yes_no, affiliation, uname = args
            person = self._get_person("entity_id", person_id)
            owner_type, owner_id = self.const.entity_person, person.entity_id
            np_type = None
        account = self.Account_class(self.db)
        account.clear()
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may reserve users")
        account.populate(uname,
                         owner_type,  # Owner type
                         owner_id,
                         np_type,                      # np_type
                         operator.get_entity_id(),  # creator_id
                         None)                      # expire_date
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        try:
            account.write_db()
            if affiliation is not None:
                ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
                self._user_create_set_account_type(
                    account, person.entity_id, ou_id, affiliation)
        except self.db.DatabaseError, m:
            raise CerebrumError, "Database error: %s" % m
        operator.store_state("new_account_passwd", {'account_id': int(account.entity_id),
                                                    'password': passwd})
        return {'account_id': int(account.entity_id)}

    def __group_ids2name(self, group_ids):
        ret = []
        ret_tuple = True
        if not isinstance(group_ids, (tuple, list)):
            ret_tuple = False
            group_ids = [group_ids]
        elif group_ids is None:
            return None
        group = self.Group_class(self.db)
        for g_id in group_ids:
            group.clear()
            try:
                group.find(g_id)
            except Errors.NotFoundError:
                pass
            ret.append(group.group_name)
        if ret_tuple:
            return ret
        return ret[0]

    def __user_restore_check_changelog(self, account):
        """Find group memberships etc. from changelog.  Returns a
        tuple: (old_uid, old_default_group_name, old_groups,
        old_perm_groups).  Note that perm_groups are not in old_groups"""
        
        old_uid, old_gid = None, None
        old_spreads = {}
        old_groups = {}
        delete_date = account.expire_date.strftime('%Y-%m-%d')
        for row in self.db.get_log_events(subject_entity=account.entity_id,
                                          types=[self.const.posix_demote,
                                                 self.const.spread_del,
                                                 self.const.group_rem]):
            if row['change_params'] is not None:
                change_params = pickle.loads(row['change_params'])
            if row['change_type_id'] == int(self.const.posix_demote):
                old_uid, old_gid = change_params['uid'], change_params['gid']
            elif row['tstamp'].strftime('%Y-%m-%d') == delete_date:
                if row['change_type_id'] == int(self.const.spread_del):
                    old_spreads[change_params['spread']] = 1
                elif row['change_type_id'] == int(self.const.group_rem):
                    old_groups[int(row['dest_entity'])] = 1
        ar = BofhdAuthRole(self.db)
        perm_groups = {}
        if old_groups:
            for row in ar.list(entity_ids=old_groups.keys()):
               perm_groups[int(row['entity_id'])] = 1
            for k in perm_groups.keys():
                del old_groups[k]
        return (old_uid, self.__group_ids2name(old_gid), old_spreads.keys(),
                self.__group_ids2name(old_groups.keys()),
                self.__group_ids2name(perm_groups.keys()))

    def _user_restore_helper(self, session, *args):
        """Returns a normal prompt_func dict + a choices key
        containing a dict of all choices if the command is complete"""
        all_args = list(args[:])
        if not all_args:
            return {'prompt': "Enter owner id",
                    'help_ref': "user_create_person_id"}
        owner_id = all_args.pop(0)
        if not all_args:
            return {'prompt': "Enter account name",
                    'help_ref': "account_name"}
        account = self._get_account(all_args.pop(0))
        if owner_id.startswith('group:'):
            owner_id = self._get_group(owner_id.split(":")[1]).entity_id
        else:
            id_type, id = self._map_person_id(owner_id)
            if id_type not in ('entity_id', self.const.externalid_fodselsnr):
                raise CerebrumError, "Must specify fnr or entity_id"
            owner_id = self._get_person(id_type, id).entity_id
        if owner_id != account.owner_id:
            raise CerebrumError("Owner id and account does not match!")
        if not account.is_expired():
            raise CerebrumError, "Cannot resore an account that isn't expired"
        if account.owner_type == self.const.entity_person:
            person = self._get_person('entity_id', account.owner_id)
            name = person.get_name(self.const.system_cached,
                                   getattr(self.const,
                                           cereconf.DEFAULT_GECOS_NAME))
            if person.birth_date:
                bd = person.birth_date.strftime('%Y-%m-%d')
            else:
                bd = '<not set>'
            extra_msg = "\nRestoring '%s', belonging to '%s' (born %s)\n" % (
                account.account_name, name, bd)
        else:
            grp = self._get_group(account.owner_id, idtype='id')
            extra_msg = "Restoring '%s', belonging to group: '%s'\n" % (
                grp.group_name)
        extra_msg += ('NOTE: Please assert that the above line is correct '
                      'before proceeding!\n\n')
        choices = {'account': account}
        old_uid, old_gid, old_spreads, old_groups, perm_groups = \
                 self.__user_restore_check_changelog(account)
        # Spreads
        if not all_args:
            return {'prompt': "%sSpreads" % extra_msg,
                    'default': ','.join(
                ["%s" % self.const.Spread(x) for x in old_spreads])}
        choices['spreads'] = all_args.pop(0)
        days_since_deletion = (DateTime.now() - account.expire_date).days
        # Groups
        if not all_args:
            ret = {'prompt': "Groups (comma separated)",
                   'default': ','.join(["%s" % x for x in old_groups])}
            if perm_groups:
                ret['prompt'] = (
                    '\nNOTE: Membership to the following permission group(s) '
                    'will NOT be restored: %s\n\n%s' % (",".join(perm_groups),
                                                      ret['prompt']))
            return ret
        choices['groups'] = all_args.pop(0)
        # spesific to posix users
        if old_uid is not None:
            is_superuser = self.ba.is_superuser(session.get_entity_id())
            if not all_args:
                return {'prompt': "Default filegroup",
                        'default': '%s' % old_gid}
            choices['dfg'] = all_args.pop(0)
            if not all_args:
                homes = account.get_homes()
                ret = {'prompt': "Disk", 'help_ref': 'disk'}
                if homes:
                    ret['default'] = self._get_disk(homes[0]['disk_id']
                                                    )[0].path
                elif not is_superuser:
                    raise PermissionDenied(
                        "Can't find an old home dir for this user")
                if days_since_deletion > 180 and not is_superuser:
                    ret['prompt'] = (
                        'WARNING: You are not authorized to restore the old '
                        'homedirectory.  If you continue, a new empty '
                        'homedirectory will be built for the user.\n%s' %
                        ret['prompt'])
                return ret
            choices['disk'] = all_args.pop(0)
            if not all_args:
                ret = {'prompt': "Restore old homedir data?", 'default': 'no'}
                if days_since_deletion <= 180:
                    ret['default'] = 'yes'
                return ret
            choices['old_homedir_bool'] = all_args.pop(0)
        # Mail
        if not all_args:
            ret = {'prompt': "Restore old mailbox data?", 'default': 'no'}
            if days_since_deletion <= 180:
                ret['default'] = 'yes'
            return ret
        choices['old_mailbox_bool'] = all_args.pop(0)
        return {'last_arg': True, 'choices': choices}

    def user_restore_prompt_func(self, session, *args):
        ret = self._user_restore_helper(session, *args)
        if ret.has_key('choices'):
            del(ret['choices'])
        return ret
    
    # user restore
    all_commands['user_restore'] = Command(
        ('user', 'restore'), prompt_func=user_restore_prompt_func,
        perm_filter='is_superuser')
    def user_restore(self, operator, *args):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        args = self._user_restore_helper(operator, *args)['choices']
        account = args['account']
        days_since_deletion = (DateTime.now() - account.expire_date).days
        if args.has_key('dfg'):
            pu = PosixUser.PosixUser(self.db)
            try:
                pu.find(account.entity_id)
                raise CerebrumError("Trying to restore someone who already is a PosixUser")
            except Errors.NotFoundError:
                pu.clear()
            old_uid, old_gid, old_spreads, old_groups, perm_groups = \
                     self.__user_restore_check_changelog(account)

            # Must own group is delete +14 days ago, or the user wasn't
            # previously member of the group
            group = self._get_group(args['dfg'], grtype='PosixGroup')
            if days_since_deletion > 14 or args['dfg'] not in old_groups:
                self.ba.can_alter_group(operator.get_entity_id(), group.entity_id)
            pu.populate(old_uid, group.entity_id, None,
                        self.const.posix_shell_bash, parent=account)
            pu.expire_date = None
            pu.write_db()
        else:
            pu = account
            old_uid, old_gid, old_spreads, old_groups, perm_groups = \
                     self.__user_restore_check_changelog(account)

        # Spreads
        if args['spreads']:
            for s in [self._get_constant(x) for x in args['spreads'].split(",")]:
                # TODO: permissions?
                pu.add_spread(s)        
        # Add homedir entry.  We prefer to reuse the old one if it exists
        if not args.get('old_homedir_bool', 'n').startswith('y'):
            # Trigger homedir creation in process_changes.py
            # TBD: a bofhd_request would be cleaner?
            for row in pu.get_homes():
                pu.clear_home(row['spread'])
            kwargs = {'status': self.const.home_status_not_created}
        else:
            kwargs = {'status': self.const.home_status_pending_restore}
        if isinstance(pu, PosixUser.PosixUser):
            disk_id, home = self._get_disk(args['disk'])[1:3]
            homes = account.get_homes()
            kwargs.update({'disk_id': disk_id, 'home': home})

            if homes:
                homedir_id = kwargs['current_id'] = homes[0]['homedir_id']
                pu.set_homedir(**kwargs)
            else:
                homedir_id = pu.set_homedir(**kwargs)
            for s in ([getattr(self.const, x) for x in cereconf.HOME_SPREADS]):
                if str(s) in args['spreads'].split(","):
                    pu.set_home(s, homedir_id)
        # Groups
        if args['groups']:
            for g in args['groups'].split(","):
                if g == args.get('dfg', None):
                    continue  # already processed
                group = self._get_group('name:%s' % g)
                if days_since_deletion > 14 or g.encode('iso8859-1') not in old_groups:
                    self.ba.can_alter_group(operator.get_entity_id(),
                                            group.entity_id)
                group.add_member(pu.entity_id, pu.entity_type,
                                 self.const.group_memberop_union)
        br = BofhdRequests(self.db, self.const)
        n_req = 0
        if args.get('old_homedir_bool', 'n').startswith('y'):
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_homedir_restore,
                           pu.entity_id, disk_id)
            n_req += 1
        if args.get('old_mailbox_bool', 'n').startswith('y'):
            for anti_action in br.get_conflicts(self.const.bofh_email_restore):
                for r in br.get_requests(entity_id=pu.entity_id,
                                         operation=anti_action):
                    br.delete_request(request_id=r['request_id'])
            br.add_request(operator.get_entity_id(), br.now,
                           self.const.bofh_email_restore,
                           pu.entity_id, disk_id)
            n_req += 1
        return ("'%s' restored.  See 'user info' for details. "
                "Added %i jobs to restore queue.") % (account.account_name,
                                                   n_req)

    # user set_disk_status
    all_commands['user_set_disk_status'] = Command(
        ('user', 'set_disk_status'), AccountName(),
        SimpleString(help_ref='string_disk_status'),
        perm_filter='is_superuser')
    def user_set_disk_status(self, operator, accountname, status):
        try:
            status = self.const.AccountHomeStatus(status)
            int(status)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown status"
        account = self._get_account(accountname)
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        ah = account.get_home(self.const.spread_uit_nis_user)
        account.set_homedir(current_id=ah['homedir_id'], status=status)
        return "OK, set home-status for %s to %s" % (accountname, status)

    # user set_expire
    all_commands['user_set_expire'] = Command(
        ('user', 'set_expire'), AccountName(), Date(),
        perm_filter='can_delete_user')
    def user_set_expire(self, operator, accountname, date):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.expire_date = self._parse_date(date)
        account.write_db()
        return "OK, set expire-date for %s to %s" % (accountname, date)

    # user set_np_type
    all_commands['user_set_np_type'] = Command(
        ('user', 'set_np_type'), AccountName(), SimpleString(help_ref="string_np_type"),
        perm_filter='can_delete_user')
    def user_set_np_type(self, operator, accountname, np_type):
        account = self._get_account(accountname)
        self.ba.can_delete_user(operator.get_entity_id(), account)
        account.np_type = self._map_np_type(np_type)
        account.write_db()
        return "OK, set np-type for %s to %s" % (accountname, np_type)

    def user_set_owner_prompt_func(self, session, *args):
        all_args = list(args[:])
        if not all_args:
            return {'prompt': 'Account name'}
        account_name = all_args.pop(0)
        if not all_args:
            return {'prompt': 'Entity type (group/person)',
                    'default': 'person'}
        entity_type = all_args.pop(0)
        if not all_args:
            return {'prompt': 'Id of the type specified above'}
        id = all_args.pop(0)
        if entity_type == 'person':
            if not all_args:
                person = self._get_person(*self._map_person_id(id))
                map = [(("%-8s %s", "Num", "Affiliation"), None)]
                for aff in person.get_affiliations():
                    ou = self._get_ou(ou_id=aff['ou_id'])
                    name = "%s@%s" % (
                        self.const.PersonAffStatus(aff['status']),
                        self._format_ou_name(ou))
                    map.append((("%s", name),
                                {'ou_id': int(aff['ou_id']), 'aff': int(aff['affiliation'])}))
                if not len(map) > 1:
                    raise CerebrumError(
                        "Person has no affiliations. Try person affiliation_add")
                return {'prompt': "Choose affiliation from list", 'map': map,
                        'last_arg': True}
        else:
            if not all_args:
                return {'prompt': "Enter np_type",
                        'help_ref': 'string_np_type',
                        'last_arg': True}
            np_type = all_args.pop(0)
        raise CerebrumError, "Client called prompt func with too many arguments"

    all_commands['user_set_owner'] = Command(
        ("user", "set_owner"), prompt_func=user_set_owner_prompt_func,
        perm_filter='is_superuser')
    def user_set_owner(self, operator, *args):
        if args[1] == 'person':
            accountname, entity_type, id, affiliation = args
            new_owner = self._get_person(*self._map_person_id(id))
        else:
            accountname, entity_type, id, np_type = args
            new_owner = self._get_entity(entity_type, id)
            np_type = int(self._get_constant(np_type, "Unknown account type"))

        account = self._get_account(accountname)
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("only superusers may assign account ownership")
        new_owner = self._get_entity(entity_type, id)
        if account.owner_type == self.const.entity_person:
            for row in account.get_account_types(filter_expired=False):
                account.del_account_type(row['ou_id'], row['affiliation'])
        account.owner_type = new_owner.entity_type
        account.owner_id = new_owner.entity_id
        if args[1] == 'group':
            account.np_type = np_type
        account.write_db()
        if new_owner.entity_type == self.const.entity_person:
            ou_id, affiliation = affiliation['ou_id'], affiliation['aff']
            self._user_create_set_account_type(account, account.owner_id,
                                               ou_id, affiliation)
        return "OK, set owner of %s to %s" % (
            accountname,  self._get_name_from_object(new_owner))

    # user shell
    all_commands['user_shell'] = Command(
        ("user", "shell"), AccountName(), PosixShell(default="bash"))
    def user_shell(self, operator, accountname, shell=None):
        account = self._get_account(accountname, actype="PosixUser")
        shell = self._get_shell(shell)
        self.ba.can_set_shell(operator.get_entity_id(), account, shell)
        account.shell = shell
        account.write_db()
        return "OK, set shell for %s to %s" % (accountname, shell)

    # user student_create
    all_commands['user_student_create'] = Command(
        ('user', 'student_create'), PersonId())
    def user_student_create(self, operator, person_id):
        raise CerebrumError, "Not implemented"

    #
    # commands that are noe available in jbofh, but used by other clients
    #

    all_commands['get_persdata'] = None

    def get_persdata(self, operator, uname):
        ac = self._get_account(uname)
        person_id = "entity_id:%i" % ac.owner_id
        person = self._get_person(*self._map_person_id(person_id))
        ret = {
            'is_personal': len(ac.get_account_types()),
            'fnr': [{'id': r['external_id'],
                     'source': "%s" % self.num2const[r['source_system']]}
                    for r in person.get_external_id(id_type=self.const.externalid_fodselsnr)]
            }
        ac_types = ac.get_account_types(all_persons_types=True)        
        if ret['is_personal']:
            ac_types.sort(lambda x,y: int(x['priority']-y['priority']))
            for at in ac_types:
                ac2 = self._get_account(at['account_id'], idtype='id')
                ret.setdefault('users', []).append(
                    (ac2.account_name, '%s@ulrik.uit.no' % ac2.account_name,
                     at['priority'], at['ou_id'], "%s" % self.num2const[int(at['affiliation'])]))
            # TODO: kall ac.list_accounts_by_owner_id(ac.owner_id) for
            # � hente ikke-personlige konti?
        ret['home'] = ac.resolve_homedir(disk_id=ac.disk_id, home=ac.home)
        ret['navn'] = {'cached': person.get_name(
            self.const.system_cached, self.const.name_full)}
        try:
            ret['work_title'] = person.get_name(
                self.const.system_lt, self.const.name_work_title)
        except Errors.NotFoundError:
            pass
        try:
            ret['personal_title'] = person.get_name(
                self.const.system_lt, self.const.name_personal_title)
        except Errors.NotFoundError:
            pass
        return ret

    #
    # misc helper functions.
    # TODO: These should be protected so that they are not remotely callable
    #

    def _get_account(self, id, idtype=None, actype="Account"):
        if actype == 'Account':
            account = self.Account_class(self.db)
        elif actype == 'PosixUser':
            account = PosixUser.PosixUser(self.db)
        account.clear()
        try:
            if idtype is None:
                if id.find(":") != -1:
                    idtype, id = id.split(":", 1)
                    if len(id) == 0:
                        raise CerebrumError, "Must specify id"
                else:
                    idtype = 'name'
            if idtype == 'name':
                account.find_by_name(id, self.const.account_namespace)
            elif idtype == 'id':
                if isinstance(id, str) and not id.isdigit():
                    raise CerebrumError, "Entity id must be a number"
                account.find(id)
            else:
                raise CerebrumError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find %s with %s=%s" % (actype, idtype, id)
        return account

    def _get_email_domain(self, name):
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(name)
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown e-mail domain (%s)" % name
        return ed

    def _get_host(self, name):
        host = Utils.Factory.get('Host')(self.db)
        try:
            if isinstance(name, int):
                host.find(name)
            else:
                host.find_by_name(name)
            return host
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown host: %s" % name

    def _get_group(self, id, idtype=None, grtype="Group"):
        if grtype == "Group":
            group = self.Group_class(self.db)
        elif grtype == "PosixGroup":
            group = PosixGroup.PosixGroup(self.db)
        try:
            group.clear()
            if idtype is None:
                if id.count(':'):
                    idtype, id = id.split(':', 1)
                else:
                    idtype='name'
            if idtype == 'name':
                group.find_by_name(id)
            elif idtype == 'id':
                group.find(id)
            else:
                raise CerebrumError, "unknown idtype: '%s'" % idtype
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find %s with %s=%s" % (grtype, idtype, id)
        return group

    def _get_shell(self, shell):
        if shell == 'bash':
            return self.const.posix_shell_bash
        return self._get_constant(shell, "Unknown shell")
    
    def _get_opset(self, opset):
        aos = BofhdAuthOpSet(self.db)
        try:
            aos.find_by_name(opset)
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find op set with name %s" % opset
        return aos

    def _format_ou_name(self, ou):
        return "%02i%02i%02i (%s)" % (ou.fakultet, ou.institutt, ou.avdeling,
                                      ou.short_name)

    def _get_ou(self, ou_id=None, stedkode=None):
        ou = self.OU_class(self.db)
        ou.clear()
        try:
            if ou_id is not None:
                ou.find(ou_id)
            else:
                if len(stedkode) != 6 or not stedkode.isdigit():
                    raise CerebrumError("Expected 6 digits in stedkode")
                ou.find_stedkode(stedkode[0:2], stedkode[2:4], stedkode[4:6],
                                 institusjon=cereconf.DEFAULT_INSTITUSJONSNR)
            return ou
        except Errors.NotFoundError:
            raise CerebrumError, "Unknown stedkode"

    def _get_group_opcode(self, operator):
        if operator is None:
            return self.const.group_memberop_union
        if operator == 'union':
            return self.const.group_memberop_union
        if operator == 'intersection':
            return self.const.group_memberop_intersection
        if operator == 'difference':
            return self.const.group_memberop_difference
        raise CerebrumError("unknown group opcode: '%s'" % operator)

    def _get_entity(self, idtype=None, id=None):
        if id is None:
            raise CerebrumError, "Invalid id"
        if idtype == 'account':
            return self._get_account(id)
        if idtype == 'person':
            return self._get_person(*self._map_person_id(id))
        if idtype == 'group':
            return self._get_group(id)
        if idtype is None:
            try:
                int(id)
            except ValueError:
                raise CerebrumError, "Expected int as id"
            ety = Entity.Entity(self.db)
            return ety.get_subclassed_object(id)
        raise CerebrumError, "Invalid idtype"

    def _find_persons(self, arg):
        if arg.isdigit() and len(arg) > 10:  # finn personer fra fnr
            arg = 'fnr:%s' % arg
        ret = []
        person = Utils.Factory.get('Person')(self.db)
        person.clear()
        if arg.find(":") != -1:
            idtype, value = arg.split(":")
            if not value:
                raise CerebrumError, "Unable to parse person id %r" % arg
            if idtype == 'exp':
                person.clear()
                try:
                    person.find_by_export_id(value)
                    ret.append({'person_id': person.entity_id})
                except Errors.NotFoundError:
                    raise CerebrumError, "Unkown person id %r" % arg
            elif idtype == 'entity_id':
                person.clear()
                try:
                    person.find(value)
                    ret.append({'person_id': person.entity_id})
                except Errors.NotFoundError:
                    raise CerebrumError, "Unkown person id %r" % arg
            elif idtype == 'fnr':
                for ss in [self.const.system_fs, self.const.system_lt,
                           self.const.system_manual, self. const.system_x]:
                    try:
                        person.clear()
                        person.find_by_external_id(
                            self.const.externalid_fodselsnr, value,
                            source_system=ss)
                        ret.append({'person_id': person.entity_id})
                    except Errors.NotFoundError:
                        pass
        elif arg.find("-") != -1:
            # finn personer p� f�dselsdato
            ret = person.find_persons_by_bdate(self._parse_date(arg))

        else:
            raise CerebrumError, "Unable to parse person id %r" % arg
        return ret

    def _get_person(self, idtype, id):
        person = Utils.Factory.get('Person')(self.db)
        person.clear()
        try:
            if str(idtype) == 'account_name':
                ac = self._get_account(id)
                id = ac.owner_id
                idtype = "entity_id"
            if isinstance(idtype, _CerebrumCode):
                person.find_by_external_id(idtype, id)
            elif idtype == 'entity_id':
                if isinstance(id, str) and not id.isdigit():
                    raise CerebrumError, "Entity id must be a number"
                person.find(id)
            else:
                raise CerebrumError, "Unknown idtype"
        except Errors.NotFoundError:
            raise CerebrumError, "Could not find person with %s=%s" % (idtype, id)
        except Errors.TooManyRowsError:
            raise CerebrumError, "ID not unique %s=%s" % (idtype, id)
        return person

    def _map_person_id(self, id):
        """Map <idtype:id> to const.<idtype>, id.  Recognizes
        f�dselsnummer without <idtype>.  Also recognizes entity_id"""
        if id.isdigit() and len(id) >= 10:
            return self.const.externalid_fodselsnr, id
        if id.find(":") == -1:
            self._get_account(id)  # We assume this is an account
            return "account_name", id

        id_type, id = id.split(":", 1)
        if id_type != 'entity_id':
            id_type = self.external_id_mappings.get(id_type, None)
        if id_type is not None:
            if len(id) == 0:
                raise CerebrumError, "id cannot be blank"
            return id_type, id
        raise CerebrumError, "Unknown person_id type"

    def _get_name_from_object(self, entity):
        # optimise for common case
        if isinstance(entity, self.Account_class):
            return entity.account_name
        elif isinstance(entity, self.Group_class):
            return entity.group_name
        else:
            # TODO: extend as needed for quasi entity classes like Disk
            return self._get_entity_name(entity.entity_type, entity.entity_id)

    def _get_entity_name(self, type, id):
        if type is None:
            ety = Entity.Entity(self.db)
            ety.find(id)
            type = self.num2const[int(ety.entity_type)]
        if type == self.const.entity_account:
            acc = self._get_account(id, idtype='id')
            return acc.account_name
        elif type == self.const.entity_group:
            group = self._get_group(id, idtype='id')
            return group.get_name(self.const.group_namespace)
        elif type == self.const.entity_disk:
            disk = Utils.Factory.get('Disk')(self.db)
            disk.find(id)
            return disk.path
        elif type == self.const.entity_host:
            host = Utils.Factory.get('Host')(self.db)
            host.find(id)
            return host.name
        else:
            return "%s:%s" % (type, id)

    def _get_disk(self, path, host_id=None, raise_not_found=True):
        disk = Utils.Factory.get('Disk')(self.db)
        try:
            if isinstance(path, (str, unicode)):
                disk.find_by_path(path, host_id)
            else:
                disk.find(path)
            return disk, disk.entity_id, None
        except Errors.NotFoundError:
            if raise_not_found:
                raise CerebrumError("Unknown disk: %s" % path)
            return disk, None, path

    def _map_np_type(self, np_type):
        # TODO: Assert _AccountCode
        return int(self._get_constant(np_type, "Unknown account type"))
        
    def _map_visibility_id(self, visibility):
        # TODO: Assert _VisibilityCode
        return int(self._get_constant(visibility, "No such visibility type"))


    def _is_yes(self, val):
        if isinstance(val, str) and val.lower() in ('y', 'yes', 'ja', 'j'):
            return True
        return False

    # The next two functions require all affiliations to be in upper case,
    # and all affiliation statuses to be in lower case.  If this changes,
    # the user will have to type exact case.
    def _get_affiliationid(self, code_str):
        try:
            c = self.const.PersonAffiliation(code_str.upper())
            # force a database lookup to see if it's a valid code
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation")

    def _get_affiliation_statusid(self, affiliation, code_str):
        try:
            c = self.const.PersonAffStatus(affiliation, code_str.lower())
            int(c)
            return c
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation status")

    def _get_constant(self, const_str, err_msg="Could not find constant"):
        if self.str2const.has_key(const_str):
            return self.str2const[const_str]
        raise CerebrumError("%s: %s" % (err_msg, const_str))

    def _parse_date_from_to(self, date):
        date_start = self._today()
        date_end = None
        if date:
            tmp = date.split("--")
            if len(tmp) == 2:
                date_start = self._parse_date(tmp[0])
                date_end = self._parse_date(tmp[1])
            elif len(tmp) == 1:
                date_end = self._parse_date(date)
            else:
                raise CerebrumError, "Incorrect date specification: %s." % date
        return (date_start, date_end)

    def _parse_date(self, date):
        if not date:
            # TBD: Is this correct behaviour?  mx.DateTime.DateTime
            # objects allow comparison to None, although that is
            # hardly what we expect/want.
            return None
        if isinstance(date, DateTime.DateTimeType):
            date = date.Format("%Y-%m-%d")
        try:
            y, m, d = [int(x) for x in date.split('-')]
        except ValueError:
            raise CerebrumError, "Dates must be numeric"
        # TODO: this should be a proper delta, but rather than using
        # pgSQL specific code, wait until Python has standardised on a
        # Date-type.
        if y > 2050:
            raise CerebrumError, "Too far into the future: %s" % date
	if y < 1800:
	    raise CerebrumError, "Too long ago: %s" % date
        try:
            return DateTime.Date(y, m, d)
        except:
            raise CerebrumError, "Illegal date: %s" % date

    def _today(self):
        return self._parse_date("%d-%d-%d" % time.localtime()[:3])

    def _parse_range(self, selection):
        lst = []
        try:
            for part in selection.split():
                idx = part.find('-')
                if idx != -1:
                    for n in range(int(part[:idx]), int(part[idx+1:])+1):
                        if n not in lst:
                            lst.append(n)
                else:
                    part = int(part)
                    if part not in lst:
                        lst.append(part)
        except ValueError:
            raise CerebrumError, "Error parsing range '%s'" % selection
        lst.sort()
        return lst

    def _format_from_cl(self, format, val):
        if val is None:
            return ''

        if format == 'affiliation':
            return str(self.const.PersonAffiliation(val))
        elif format == 'disk':
            disk = Utils.Factory.get('Disk')(self.db)
            try:
                disk.find(val)
                return disk.path
            except Errors.NotFoundError:
                return "deleted_disk:%s" % val
        elif format == 'date':
            if isinstance(val, str):
                return val
            else:                
                return val.date
        elif format == 'timestamp':
            return str(val)
        elif format == 'entity':
            return self._get_entity_name(None, int(val))
        elif format == 'extid':
            return str(self.const.EntityExternalId(val))
        elif format == 'homedir':
            return 'homedir_id:%s' % val
        elif format == 'id_type':
            return str(self.const.ChangeType(val))
        elif format == 'home_status':
            return str(self.const.AccountHomeStatus(val))
        elif format == 'int':
            return str(val)
        elif format == 'name_variant':
            return str(self.const.PersonName(val))
        elif format == 'ou':
            ou = self._get_ou(ou_id=val)
            return self._format_ou_name(ou)
        elif format == 'quarantine_type':
            return str(self.const.Quarantine(val))
        elif format == 'source_system':
            return str(self.const.AuthoritativeSystem(val))
        elif format == 'spread_code':
            return str(self.const.Spread(val))
        elif format == 'string':
            return str(val)
        elif format == 'trait':
            return str(self.const.EntityTrait(val))
        elif format == 'value_domain':
            return str(self.const.ValueDomain(val))
        else:
            self.logger.warn("bad cl format: %s", repr((format, val)))
            return ''

    def _format_changelog_entry(self, row):
        dest = row['dest_entity']
        if dest is not None:
            try:
                dest = self._get_entity_name(None, dest)
            except Errors.NotFoundError:
                pass
        this_cl_const = self.num2const[int(row['change_type_id'])]

        msg = this_cl_const.msg_string % {
            'subject': self._get_entity_name(None, row['subject_entity']),
            'dest': dest}

        # Append information from change_params to the string.  See
        # _ChangeTypeCode.__doc__
        if row['change_params']:
            params = pickle.loads(row['change_params'])
        else:
            params = {}

        if this_cl_const.format:
            for f in this_cl_const.format:
                repl = {}
                for part in re.findall(r'%\([^\)]+\)s', f):
                    fmt_type, key = part[2:-2].split(':')
                    repl['%%(%s:%s)s' % (fmt_type, key)] = self._format_from_cl(
                        fmt_type, params.get(key, None))
                if [x for x in repl.values() if x]:
                    for k, v in repl.items():
                        f = f.replace(k, v)
                    msg += ", " + f
        changed_by=row['change_by']
        try:
            changed_by = self._get_entity_name(None, row['change_by'])
        except Errors.NotFoundError:
            changed_by = "NotFound"
        except Exception,m:
            changed_by = m
        by = row['change_program'] or changed_by
        return "%s [%s]: %s" % (row['tstamp'], by, msg)

    def _lookup_old_uid(self, account_id):
        uid = None
        for r in self.db.get_log_events(
            0, subject_entity=account_id, types=[self.const.posix_demote]):
            uid = pickle.loads(r['change_params'])['uid']
        return uid

# arch-tag: 98930b8a-4170-453a-a5db-34177f3ac40f
