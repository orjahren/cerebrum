# -*- coding: utf-8 -*-
#
# Copyright 2007-2016 University of Oslo, Norway
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
u""" HiOF bohfd email module. """

import imaplib
import socket
import cereconf

from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.modules import Email

from Cerebrum.modules.bofhd import cmd_param
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum.modules.bofhd.bofhd_core import BofhdCommandBase
from Cerebrum.modules.bofhd.bofhd_email import BofhdEmailMixin
from Cerebrum.modules.bofhd.bofhd_utils import copy_func, copy_command
from Cerebrum.modules.no.hiof import bofhd_hiof_help
from Cerebrum.modules.no.uio.bofhd_uio_cmds import TimeoutException
from Cerebrum.modules.no.uio.bofhd_uio_cmds import ConnectException
from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as UiOBofhdExtension


def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))


uio_helpers = [
    '_format_ou_name',
    '_get_affiliationid',
    '_get_host',
]

# Decide which email mixins to use
email_mixin_commands = [
    'email_add_address',
    'email_add_domain_affiliation',
    'email_create_domain',
    'email_domain_configuration',
    'email_domain_info',
    'email_info',
    'email_primary_address',
    'email_reassign_address',
    'email_remove_address',
    'email_remove_domain_affiliation',
    'email_update',
]


@copy_command(
    BofhdEmailMixin,
    'default_email_commands', 'all_commands',
    commands=email_mixin_commands)
@copy_func(
    UiOBofhdExtension,
    methods=uio_helpers)
class BofhdExtension(BofhdEmailMixin, BofhdCommandBase):

    OU_class = Utils.Factory.get('OU')

    all_commands = {}
    authz = BofhdAuth

    @classmethod
    def get_help_strings(cls):
        return (bofhd_hiof_help.group_help,
                bofhd_hiof_help.command_help,
                bofhd_hiof_help.arg_help)

    def _email_info_basic(self, acc, et):
        """ Basic email info. """
        info = {}
        data = [info, ]
        if et.email_target_alias is not None:
            info['alias_value'] = et.email_target_alias
        info["account"] = acc.account_name
        if et.email_server_id:
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)
            info["server"] = es.name
            info["server_type"] = "N/A"
        else:
            info["server"] = "<none>"
            info["server_type"] = "N/A"
        return data

    def _email_info_detail(self, acc):
        """ Get quotas from Cerebrum, and usage from Cyrus. """
        # NOTE: Very similar to ofk/giske and uio

        info = []
        eq = Email.EmailQuota(self.db)

        # Get quota and usage
        try:
            eq.find_by_target_entity(acc.entity_id)
            et = Email.EmailTarget(self.db)
            et.find_by_target_entity(acc.entity_id)
            es = Email.EmailServer(self.db)
            es.find(et.email_server_id)

            if es.email_server_type == self.const.email_server_type_cyrus:
                used = 'N/A'
                limit = None
                pw = self.db._read_password(cereconf.CYRUS_HOST,
                                            cereconf.CYRUS_ADMIN)
                try:
                    cyrus = imaplib.IMAP4(es.name)
                    # IVR 2007-08-29 If the server is too busy, we do not want
                    # to lock the entire bofhd.
                    # 5 seconds should be enough
                    cyrus.socket().settimeout(5)
                    cyrus.login(cereconf.CYRUS_ADMIN, pw)
                    res, quotas = cyrus.getquota("user." + acc.account_name)
                    cyrus.socket().settimeout(None)
                    if res == "OK":
                        for line in quotas:
                            try:
                                folder, qtype, qused, qlimit = line.split()
                                if qtype == "(STORAGE":
                                    used = str(int(qused)/1024)
                                    limit = int(qlimit.rstrip(")"))/1024
                            except ValueError:
                                # line.split fails e.g. because quota isn't set
                                # on server
                                folder, junk = line.split()
                                self.logger.warning(
                                    "No IMAP quota set for '%s'" %
                                    acc.account_name)
                                used = "N/A"
                                limit = None
                except (TimeoutException, socket.error):
                    used = 'DOWN'
                except ConnectException as e:
                    used = str(e)
                info.append({'quota_hard': eq.email_quota_hard,
                             'quota_soft': eq.email_quota_soft,
                             'quota_used': used})
                if limit is not None and limit != eq.email_quota_hard:
                    info.append({'quota_server': limit})
            else:
                # Just get quotas
                info.append({'dis_quota_hard': eq.email_quota_hard,
                             'dis_quota_soft': eq.email_quota_soft})
        except Errors.NotFoundError:
            pass
        return info

    #
    # email replace_server [username] [servername]
    #
    all_commands['email_replace_server'] = cmd_param.Command(
        ('email', 'replace_server'),
        cmd_param.AccountName(help_ref='account_name'),
        cmd_param.SimpleString(),
        fs=cmd_param.FormatSuggestion(
            "Ok, new email server: %s", ('new_server', )),
        perm_filter='can_email_address_add')

    def email_replace_server(self, operator, user, server_name):
        """ Replace the server for an email target. """
        if not self.ba.is_postmaster(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        et = self._get_email_target_for_account(user)
        es = Email.EmailServer(self.db)
        es.clear()
        try:
            es.find_by_name(server_name)
        except Errors.NotFoundError:
            raise CerebrumError("No such server: '%s'" % server_name)
        if et.email_server_id != es.entity_id:
            et.email_server_id = es.entity_id
            try:
                et.write_db()
            except self.db.DatabaseError, m:
                raise CerebrumError("Database error: %s" % m)
        else:
            raise CerebrumError(
                "No change, from-server equeals to-server: %s" % server_name)
        return {'new_server': server_name, }
