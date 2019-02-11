#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2016 University of Oslo, Norway
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
""" This is a bofhd module for access commands.

"""

import re
import six

import cereconf

from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.modules import Email
from Cerebrum.modules.dns.Subnet import Subnet, SubnetError
from Cerebrum.modules.bofhd.auth import (BofhdAuthOpSet,
                                         BofhdAuthOpTarget,
                                         BofhdAuthRole)
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.cmd_param import (
    AccountName,
    Command,
    DiskId,
    EntityType,
    FormatSuggestion,
    GroupName,
    OpSet,
    OU,
    SimpleString,
)


class BofhdAccessAuth(BofhdAuth):
    """Auth for access * commands"""
    pass


class BofhdAccessCommands(BofhdCommonMethods):
    """Bofhd extension with access commands"""

    all_commands = {}
    hidden_commands = {}

    authz = BofhdAccessAuth
    omit_parent_commands = set()
    parent_commands = False

    #
    # access disk <path>
    #
    all_commands['access_disk'] = Command(
        ('access', 'disk'),
        DiskId(),
        fs=FormatSuggestion(
            "%-16s %-9s %s", ("opset", "type", "name"),
            hdr="%-16s %-9s %s" % ("Operation set", "Type", "Name")
        ))

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

    #
    # access group <group>
    #
    all_commands['access_group'] = Command(
        ('access', 'group'),
        GroupName(help_ref='group_name_id'),
        fs=FormatSuggestion(
            "%-16s %-9s %s", ("opset", "type", "name"),
            hdr="%-16s %-9s %s" % ("Operation set", "Type", "Name")
        ))

    def access_group(self, operator, group):
        return self._list_access("group", group)

    #
    # access host <hostname>
    #
    all_commands['access_host'] = Command(
        ('access', 'host'),
        SimpleString(help_ref="string_host"),
        fs=FormatSuggestion(
            "%-16s %-16s %-9s %s", ("opset", "attr", "type", "name"),
            hdr="%-16s %-16s %-9s %s" % ("Operation set", "Pattern", "Type",
                                         "Name")
        ))

    def access_host(self, operator, host):
        return self._list_access("host", host)

    #
    # access maildom <maildom>
    #
    all_commands['access_maildom'] = Command(
        ('access', 'maildom'),
        SimpleString(help_ref="email_domain"),
        fs=FormatSuggestion(
            "%-16s %-9s %s", ("opset", "type", "name"),
            hdr="%-16s %-9s %s" % ("Operation set", "Type", "Name")
        ))

    def access_maildom(self, operator, maildom):
        # TODO: Is this an email command? Should it be moved to bofhd_email?
        return self._list_access("maildom", maildom)

    #
    # access ou <ou>
    #
    all_commands['access_ou'] = Command(
        ('access', 'ou'),
        OU(),
        fs=FormatSuggestion(
            "%-16s %-16s %-9s %s", ("opset", "attr", "type", "name"),
            hdr="%-16s %-16s %-9s %s" % ("Operation set", "Affiliation",
                                         "Type", "Name")
        ))

    def access_ou(self, operator, ou):
        return self._list_access("ou", ou)

    #
    # access user <account>
    #
    all_commands['access_user'] = Command(
        ('access', 'user'),
        AccountName(),
        fs=FormatSuggestion(
            "%-14s %-5s %-20s %-7s %-9s %s",
            ("opset", "target_type", "target", "attr", "type", "name"),
            hdr="%-14s %-5s %-20s %-7s %-9s %s" %
            ("Operation set", "TType", "Target", "Attr", "Type", "Name")
        ))

    def access_user(self, operator, user):
        # This is more tricky than the others, we want to show anyone with
        # access, through OU, host or disk.  (not global_XXX, though.)
        #
        # Note that there is no auth-type 'account', so you can't be granted
        # direct access to a specific user.

        acc = self._get_account(user)
        # Make lists of the disks and hosts associated with the user
        disks = {}
        hosts = {}
        disk = Utils.Factory.get("Disk")(self.db)
        for r in acc.get_homes():
            # Disk for archived users may not exist anymore
            try:
                disk_id = int(r['disk_id'])
            except TypeError:
                continue
            if disk_id not in disks:
                disk.clear()
                disk.find(disk_id)
                disks[disk_id] = disk.path
                if disk.host_id is not None:
                    basename = disk.path.split("/")[-1]
                    host_id = int(disk.host_id)
                    if host_id not in hosts:
                        hosts[host_id] = []
                    hosts[host_id].append(basename)
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
        ret.sort(lambda x, y: (cmp(x['opset'].lower(), y['opset'].lower()) or
                               cmp(x['name'], y['name'])))
        return ret

    #
    # access global_group
    #
    all_commands['access_global_group'] = Command(
        ('access', 'global_group'),
        fs=FormatSuggestion(
            "%-16s %-9s %s", ("opset", "type", "name"),
            hdr="%-16s %-9s %s" % ("Operation set", "Type", "Name")
        ))

    def access_global_group(self, operator):
        return self._list_access("global_group")

    #
    # access global_host
    #
    all_commands['access_global_host'] = Command(
        ('access', 'global_host'),
        fs=FormatSuggestion(
            "%-16s %-9s %s", ("opset", "type", "name"),
            hdr="%-16s %-9s %s" % ("Operation set", "Type", "Name")
        ))

    def access_global_host(self, operator):
        return self._list_access("global_host")

    #
    # access global_maildom
    #
    all_commands['access_global_maildom'] = Command(
        ('access', 'global_maildom'),
        fs=FormatSuggestion(
            "%-16s %-9s %s", ("opset", "type", "name"),
            hdr="%-16s %-9s %s" % ("Operation set", "Type", "Name")
        ))

    def access_global_maildom(self, operator):
        return self._list_access("global_maildom")

    #
    # access global_ou
    #
    all_commands['access_global_ou'] = Command(
        ('access', 'global_ou'),
        fs=FormatSuggestion(
            "%-16s %-16s %-9s %s", ("opset", "attr", "type", "name"),
            hdr="%-16s %-16s %-9s %s" % ("Operation set", "Affiliation",
                                         "Type", "Name")
        ))

    def access_global_ou(self, operator):
        return self._list_access("global_ou")

    #
    # access global_dns
    #
    all_commands['access_global_dns'] = Command(
        ('access', 'global_dns'),
        fs=FormatSuggestion(
            "%-16s %-16s %-9s %s", ("opset", "attr", "type", "name"),
            hdr="%-16s %-16s %-9s %s" % ("Operation set", "Affiliation",
                                         "Type", "Name")
        ))

    def access_global_dns(self, operator):
        return self._list_access("global_dns")

    def access_global_person(self, operator):
        return self._list_access("global_person")

    def _list_access(self, target_type, target_name=None, empty_result="None"):
        target_id, target_type, target_auth = self._get_access_id(target_type,
                                                                  target_name)
        ret = []
        ar = BofhdAuthRole(self.db)
        aos = BofhdAuthOpSet(self.db)
        for r in self._get_auth_op_target(target_id, target_type,
                                          any_attr=True):
            attr = str(r['attr'] or '')
            for r2 in ar.list(op_target_id=r['op_target_id']):
                aos.clear()
                aos.find(r2['op_set_id'])
                ety = self._get_entity(ident=r2['entity_id'])
                ret.append({
                    'opset': aos.name,
                    'attr': attr,
                    'type': six.text_type(self.const.EntityType(
                        ety.entity_type)),
                    'name': self._get_name_from_object(ety),
                })
        ret.sort(lambda a, b: (cmp(a['opset'], b['opset']) or
                               cmp(a['name'], b['name'])))
        return ret or empty_result

    #
    # access grant <opset name> <who> <type> <on what> [<attr>]
    #
    all_commands['access_grant'] = Command(
        ('access', 'grant'),
        OpSet(),
        GroupName(help_ref="id:target:group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(optional=True, help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='can_grant_access')

    def access_grant(self, operator, opset, group, entity_type,
                     target_name=None, attr=None):
        return self._manipulate_access(self._grant_auth, operator, opset,
                                       group, entity_type, target_name, attr)

    #
    # access revoke <opset name> <who> <type> <on what> [<attr>]
    #
    all_commands['access_revoke'] = Command(
        ('access', 'revoke'),
        OpSet(),
        GroupName(help_ref="id:target:group"),
        EntityType(default='group', help_ref="auth_entity_type"),
        SimpleString(help_ref="auth_target_entity"),
        SimpleString(optional=True, help_ref="auth_attribute"),
        perm_filter='can_grant_access')

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
        target_type.

        """
        opset = self._get_opset(opset)
        gr = self.util.get_target(group, default_lookup="group",
                                  restrict_to=['Account', 'Group'])
        target_id, target_type, target_auth = self._get_access_id(
            entity_type, target_name)
        operator_id = operator.get_entity_id()
        if target_auth is None and not self.ba.is_superuser(operator_id):
            raise PermissionDenied("Currently limited to superusers")
        else:
            self.ba.can_grant_access(operator_id, target_auth,
                                     target_type, target_id, opset)
        self._validate_access(entity_type, opset, attr)
        return change_func(gr.entity_id, opset, target_id, target_type, attr,
                           group, target_name)

    def _get_access_id(self, target_type, target_name):
        """Get required data for granting access to an operation target.

        :param str target_type: The type of

        :rtype: tuple
        :returns:
            A three element tuple with information about the operation target:

              1. The entity_id of the target entity (int)
              2. The target type (str)
              3. The `intval` of the operation constant for granting access to
                 the given target entity.

        """
        func_name = "_get_access_id_%s" % target_type
        if func_name not in dir(self):
            raise CerebrumError("Unknown id type {}".format(target_type))
        return self.__getattribute__(func_name)(target_name)

    def _validate_access(self, target_type, opset, attr):
        func_name = "_validate_access_%s" % target_type
        if func_name not in dir(self):
            raise CerebrumError("Unknown type %s" % target_type)
        return self.__getattribute__(func_name)(opset, attr)

    def _get_access_id_disk(self, target_name):
        return (self._get_disk(target_name)[1],
                self.const.auth_target_type_disk,
                self.const.auth_grant_disk)

    def _validate_access_disk(self, opset, attr):
        # TODO: check if the opset is relevant for a disk
        if attr is not None:
            raise CerebrumError("Can't specify attribute for disk access")

    def _get_access_id_group(self, target_name):
        target = self._get_group(target_name)
        return (target.entity_id, self.const.auth_target_type_group,
                self.const.auth_grant_group)

    def _validate_access_group(self, opset, attr):
        # TODO: check if the opset is relevant for a group
        if attr is not None:
            raise CerebrumError("Can't specify attribute for group access")

    # These three should *really* not be here, but due to this being the
    # place that "access grant" & friends are defined, this is where
    # the dns-derived functions need to be too
    def _get_access_id_dns(self, target):
        sub = Subnet(self.db)
        sub.find(target.split('/')[0])
        return (sub.entity_id,
                self.const.auth_target_type_dns,
                self.const.auth_grant_dns)

    def _validate_access_dns(self, opset, attr):
        # TODO: check if the opset is relevant for a dns-target
        if attr is not None:
            raise CerebrumError("Can't specify attribute for dns access")

    def _get_access_id_global_dns(self, target_name):
        if target_name:
            raise CerebrumError("You can't specify an address")
        return None, self.const.auth_target_type_global_dns, None

    def _validate_access_global_dns(self, opset, attr):
        if attr:
            raise CerebrumError("You can't specify a pattern with global_dns.")

    # access dns <dns-target>
    all_commands['access_dns'] = Command(
        ('access', 'dns'),
        SimpleString(),
        fs=FormatSuggestion(
            "%-16s %-9s %-9s %s", ("opset", "type", "level", "name"),
            hdr="%-16s %-9s %-9s %s" % ("Operation set", "Type",
                                        "Level", "Name")
        ))

    def access_dns(self, operator, dns_target):
        ret = []
        if '/' in dns_target:
            # Asking for rights on subnet; IP not of interest
            for accessor in self._list_access("dns", dns_target,
                                              empty_result=[]):
                accessor["level"] = "Subnet"
                ret.append(accessor)
        else:
            # Asking for rights on IP; need to provide info about
            # rights on the IP's subnet too
            for accessor in self._list_access("dns", dns_target + '/',
                                              empty_result=[]):
                accessor["level"] = "Subnet"
                ret.append(accessor)
            for accessor in self._list_access("dns", dns_target,
                                              empty_result=[]):
                accessor["level"] = "IP"
                ret.append(accessor)
        return ret

    def _get_access_id_global_group(self, group):
        if group is not None and group != "":
            raise CerebrumError("Cannot set domain for global access")
        return None, self.const.auth_target_type_global_group, None

    def _validate_access_global_group(self, opset, attr):
        if attr is not None:
            raise CerebrumError("Can't specify attribute for global group")

    def _get_access_id_global_person(self, person):
        # if person is not None and person != "":
        #     raise CerebrumError("Cannot set domain for global access")
        return None, self.const.auth_target_type_global_person, None

    def _validate_access_global_person(self, opset, attr):
        if attr:
            raise CerebrumError(
                "You can't specify a pattern with global_person.")

    def _get_access_id_host(self, target_name):
        target = self._get_host(target_name)
        return (target.entity_id, self.const.auth_target_type_host,
                self.const.auth_grant_host)

    def _validate_access_host(self, opset, attr):
        if attr is not None:
            if attr.count('/'):
                raise CerebrumError("The disk pattern should only contain "
                                    "the last component of the path.")
            try:
                re.compile(attr)
            except re.error as e:
                raise CerebrumError("Syntax error in regexp: {}".format(e))

    def _get_access_id_global_host(self, target_name):
        if target_name is not None and target_name != "":
            raise CerebrumError("You can't specify a hostname")
        return None, self.const.auth_target_type_global_host, None

    def _validate_access_global_host(self, opset, attr):
        if attr is not None:
            raise CerebrumError(
                "You can't specify a pattern with global_host.")

    def _get_access_id_maildom(self, dom):
        ed = Email.EmailDomain(self.db)
        try:
            ed.find_by_domain(dom)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown e-mail domain (%s)" % dom)
        return (ed.entity_id, self.const.auth_target_type_maildomain,
                self.const.auth_grant_maildomain)

    def _validate_access_maildom(self, opset, attr):
        if attr is not None:
            raise CerebrumError("No attribute with maildom.")

    def _get_access_id_global_maildom(self, dom):
        if dom is not None and dom != '':
            raise CerebrumError("Cannot set domain for global access")
        return None, self.const.auth_target_type_global_maildomain, None

    def _validate_access_global_maildom(self, opset, attr):
        if attr is not None:
            raise CerebrumError("No attribute with global maildom.")

    def _get_access_id_ou(self, ou):
        ou = self._get_ou(stedkode=ou)
        return (ou.entity_id, self.const.auth_target_type_ou,
                self.const.auth_grant_ou)

    def _validate_access_ou(self, opset, attr):
        if attr is not None:
            try:
                int(self.const.PersonAffiliation(attr))
            except Errors.NotFoundError:
                raise CerebrumError("Unknown affiliation '{}'".format(attr))

    def _get_access_id_global_ou(self, ou):
        if ou is not None and ou != '':
            raise CerebrumError("Cannot set OU for global access")
        return None, self.const.auth_target_type_global_ou, None

    def _validate_access_global_ou(self, opset, attr):
        if not attr:
            # This is a policy decision, and should probably be
            # elsewhere.
            raise CerebrumError(
                "Must specify affiliation for global ou access")
        try:
            int(self.const.PersonAffiliation(attr))
        except Errors.NotFoundError:
            raise CerebrumError("Unknown affiliation: %s" % attr)

    #
    # access list_opsets
    #
    all_commands['access_list_opsets'] = Command(
        ('access', 'list_opsets'),
        fs=FormatSuggestion("%s", ("opset",), hdr="Operation set"))

    def access_list_opsets(self, operator):
        baos = BofhdAuthOpSet(self.db)
        ret = []
        for r in baos.list():
            ret.append({'opset': r['name']})
        ret.sort(lambda x, y: cmp(x['opset'].lower(), y['opset'].lower()))
        return ret

    #
    # access list_alterable [group/maildom/host/disk] [username]
    #
    hidden_commands['access_list_alterable'] = Command(
        ('access', 'list_alterable'),
        SimpleString(optional=True),
        AccountName(optional=True),
        fs=FormatSuggestion(
            "%10d %15s     %s", ("entity_id", "entity_type", "entity_name")
        )
    )

    def access_list_alterable(self, operator, target_type='group',
                              access_holder=None):
        """List entities that access_holder can moderate."""

        if access_holder is None:
            account_id = operator.get_entity_id()
        else:
            account = self._get_account(access_holder, actype="PosixUser")
            account_id = account.entity_id

        if not (account_id == operator.get_entity_id() or
                self.ba.is_superuser(operator.get_entity_id())):
            raise PermissionDenied("You do not have permission for this"
                                   " operation")

        result = list()
        matches = self.ba.list_alterable_entities(account_id, target_type)
        if len(matches) > cereconf.BOFHD_MAX_MATCHES_ACCESS:
            raise CerebrumError("More than {:d} ({:d}) matches. Refusing to "
                                "return result".format(
                                    cereconf.BOFHD_MAX_MATCHES_ACCESS,
                                    len(matches)))
        for row in matches:
            try:
                entity = self._get_entity(ident=row["entity_id"])
            except Errors.NotFoundError:
                self.logger.warn(
                    "Non-existent entity (%s) referenced from auth_op_target",
                    row["entity_id"])
                continue
            etype = self.const.EntityType(entity.entity_type)
            ename = self._get_entity_name(entity.entity_id, entity.entity_type)
            tmp = {"entity_id": row["entity_id"],
                   "entity_type": six.text_type(etype),
                   "entity_name": ename}
            if entity.entity_type == self.const.entity_group:
                tmp["description"] = entity.description

            result.append(tmp)
        return result

    #
    # access show_opset <opset name>
    #
    all_commands['access_show_opset'] = Command(
        ('access', 'show_opset'),
        OpSet(),
        fs=FormatSuggestion(
            "%-16s %-16s %s", ("op", "attr", "desc"),
            hdr="%-16s %-16s %s" % ("Operation", "Attribute", "Description")
        ))

    def access_show_opset(self, operator, opset=None):
        baos = BofhdAuthOpSet(self.db)
        try:
            baos.find_by_name(opset)
        except Errors.NotFoundError:
            raise CerebrumError("Unknown operation set: '{}'".format(opset))
        ret = []
        for r in baos.list_operations():
            entry = {
                'op': six.text_type(self.const.AuthRoleOp(r['op_code'])),
                'desc': self.const.AuthRoleOp(r['op_code']).description,
            }
            attrs = []
            for r2 in baos.list_operation_attrs(r['op_id']):
                attrs += [r2['attr']]
            if not attrs:
                attrs = [""]
            for a in attrs:
                entry_with_attr = entry.copy()
                entry_with_attr['attr'] = a
                ret += [entry_with_attr]
        ret.sort(lambda x, y: (cmp(x['op'], y['op']) or
                               cmp(x['attr'], y['attr'])))
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
    # access list <owner> [target_type]
    #
    all_commands['access_list'] = Command(
        ('access', 'list'),
        SimpleString(help_ref='id:target:group'),
        SimpleString(help_ref='string_perm_target_type_access', optional=True),
        fs=FormatSuggestion(
            "%-14s %-16s %-30s %-7s",
            ("opset", "target_type", "target", "attr"),
            hdr="%-14s %-16s %-30s %-7s" %
            ("Operation set", "Target type", "Target", "Attr")
        ))

    def access_list(self, operator, owner, target_type=None):
        """
        List everything an account or group can operate on. Only direct
        ownership is reported: the entities an account can access due to group
        memberships will not be listed. This does not include unpersonal users
        owned by groups.

        :param operator: operator in bofh session
        :param owner: str name of owner object
        :param target_type: the type of the target
        :return: List of everything an account or group can operate on
        """

        ar = BofhdAuthRole(self.db)
        aot = BofhdAuthOpTarget(self.db)
        aos = BofhdAuthOpSet(self.db)
        co = self.const
        owner_id = self.util.get_target(owner, default_lookup="group",
                                        restrict_to=[]).entity_id
        ret = []
        for role in ar.list(owner_id):
            aos.clear()
            aos.find(role['op_set_id'])
            for r in aot.list(target_id=role['op_target_id']):
                if target_type is not None and r['target_type'] != target_type:
                    continue
                if r['entity_id'] is None:
                    target_name = "N/A"
                elif r['target_type'] == co.auth_target_type_maildomain:
                    # FIXME: EmailDomain is not an Entity.
                    ed = Email.EmailDomain(self.db)
                    try:
                        ed.find(r['entity_id'])
                    except (Errors.NotFoundError, ValueError):
                        self.logger.warn("Non-existing entity (e-mail domain) "
                                         "in auth_op_target {}:{:d}"
                                         .format(r['target_type'],
                                                 r['entity_id']))
                        continue
                    target_name = ed.email_domain_name
                elif r['target_type'] == co.auth_target_type_ou:
                    ou = self.OU_class(self.db)
                    try:
                        ou.find(r['entity_id'])
                    except (Errors.NotFoundError, ValueError):
                        self.logger.warn("Non-existing entity (ou) in "
                                         "auth_op_target %s:%d" %
                                         (r['target_type'], r['entity_id']))
                        continue
                    target_name = "%02d%02d%02d (%s)" % (ou.fakultet,
                                                         ou.institutt,
                                                         ou.avdeling,
                                                         ou.short_name)
                elif r['target_type'] == co.auth_target_type_dns:
                    s = Subnet(self.db)
                    # TODO: should Subnet.find() support ints as input?
                    try:
                        s.find('entity_id:%s' % r['entity_id'])
                    except (Errors.NotFoundError, ValueError, SubnetError):
                        self.logger.warn("Non-existing entity (subnet) in "
                                         "auth_op_target %s:%d" %
                                         (r['target_type'], r['entity_id']))
                        continue
                    target_name = "%s/%s" % (s.subnet_ip, s.subnet_mask)
                else:
                    try:
                        ety = self._get_entity(ident=r['entity_id'])
                        target_name = self._get_name_from_object(ety)
                    except (Errors.NotFoundError, ValueError):
                        self.logger.warn("Non-existing entity in "
                                         "auth_op_target %s:%d" %
                                         (r['target_type'], r['entity_id']))
                        continue
                ret.append({
                    'opset': aos.name,
                    'target_type': r['target_type'],
                    'target': target_name,
                    'attr': r['attr'] or "",
                })
        ret.sort(lambda a, b: (cmp(a['target_type'], b['target_type']) or
                               cmp(a['target'], b['target'])))
        return ret

    def _revoke_auth(self, entity_id, opset, target_id, target_type, attr,
                     entity_name, target_name):
        op_target_id = self._get_auth_op_target(target_id, target_type, attr)
        if not op_target_id:
            raise CerebrumError("No one has matching access to {}"
                                .format(target_name))
        ar = BofhdAuthRole(self.db)
        rows = ar.list(entity_id, opset.op_set_id, op_target_id)
        if len(rows) == 0:
            return "%s doesn't have %s access to %s %s" % (
                entity_name, opset.name, six.text_type(target_type),
                target_name)
        ar.revoke_auth(entity_id, opset.op_set_id, op_target_id)
        # See if the op_target has any references left, delete it if not.
        rows = ar.list(op_target_id=op_target_id)
        if len(rows) == 0:
            aot = BofhdAuthOpTarget(self.db)
            aot.find(op_target_id)
            aot.delete()
        return "OK, revoked %s access for %s from %s %s" % (
            opset.name, entity_name, six.text_type(target_type), target_name)

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
            return "OK, granted %s access %s to %s %s" % (
                entity_name, opset.name, six.text_type(target_type),
                target_name)
        return "%s already has %s access to %s %s" % (
            entity_name, opset.name, six.text_type(target_type), target_name)

    def _get_opset(self, opset):
        aos = BofhdAuthOpSet(self.db)
        try:
            aos.find_by_name(opset)
        except Errors.NotFoundError:
            raise CerebrumError("Could not find op set with name %s" % opset)
        return aos
