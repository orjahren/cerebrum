# -*- coding: utf-8 -*-
# Copyright 2004-2019 University of Oslo, Norway
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

from collections import defaultdict     # Requires Python 2.5
from itertools   import imap

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.PosixExport import PosixExport

class PosixExport_AffiliationMixin(PosixExport):
    """Add affiliations to LDIF users from PosixExport"""
    # Based on OrgLDIF and the obsolete Cerebrum.modules.no.uit.PosixLDIF.

    def setup_ldif(self):
        if hasattr(self, 'steder'): return
        self.__super.setup_ldif()
        # Prepare to include eduPersonAffiliation, taken from OrgLDIF.
        self.org_ldif = Factory.get('OrgLDIF')(self.db, self.logger)
        self.org_ldif.init_eduPersonAffiliation_lookup()
        # Prepare to include uitAffiliation
        self.steder = {}
        self.account_aff = account_aff = defaultdict(list)
        for row in self.posix_user.list_accounts_by_type():
            account_aff[int(row['account_id'])].append(
                (row['affiliation'], int(row['ou_id'])))
        account_aff.default_factory = None

    def id2stedkode(self, ou_id):
        try:
            return self.steder[ou_id]
        except KeyError:
            ou = self.org_ldif.ou
            ou.clear()
            try:
                ou.find(ou_id)
            except Errors.NotFoundError:
                raise CerebrumError, "Stedkode unknown for ou_id %d" % ou_id
            ret = self.steder[ou_id] = \
                  "%02d%02d%02d" % (ou.fakultet, ou.institutt, ou.avdeling)
            return ret

    def ldif_user(self, data):
        # Add eduPersonAffiliation
        ret = dn, entry = self.__super.ldif_user(data)

        # eduPersonAffiliation (taken from OrgLDIF)
        owner_id = self.a_id2owner.get(data.account_id)
        added    = self.org_ldif.affiliations.get(owner_id)
        if added:
            added = self.org_ldif.attr_unique(self.org_ldif.select_list(
                self.org_ldif.eduPersonAff_selector, owner_id, added))
            if added:
                entry['eduPersonAffiliation'] = added

        return ret

class PosixExport_PersGrpMixin(PosixExport):
    """Class for hacking members of {meta_ansatt,ansatt}@<sko> groups.

    These groups contain *people* rather than accounts.
    Unfortunately, for a period of about 6-8 weeks we need to push
    employees' primary accounts to UIT-nismaps from certain groups.

    For certain groups (i.e. groups with certain traits) we'll collect
    direct account members of groups AND primary accounts of person
    members of groups.  In all cases user_spread is used as a filter,
    and it's always an account that must have this spread if it is to
    be exported to a group.
    """

    # IVR 2010-03-10:
    # A number of groups at UiT (ansatt-* -- autogenerated
    # based on employment data) have people, rather than accounts as
    # members. However, in order to help vortex, we expand temporarily
    # these groups in such a fashion, that export to LDAP entails
    # remapping person_id to its primary user's id.

    def build_option_parser(self):
        self.__super.build_option_parser()
        o = self.parser.add_option
        o("-R", "--pers-group", dest="pers_group",
          help="Add primary accounts of persons to netgroups.",
          default=False, action="store_true")

    def parse_options(self):
        self.__super.parse_options()
        if self.opts.pers_group and not (self.opts.netgroup_spread and
                                         self.opts.user_spread):
            self.usage("-R requires -N and -P")

    def load_posix_users(self):
        if hasattr(self, 'pers2acc'): return
        if self.opts.pers_group:
            # Load {person_id -> primary account_id} for the relevant users
            rows = Factory.get('Account')(self.db).list_accounts_by_type(
                primary_only=True, account_spread=self.spreads.user)
            self.pers2acc = dict(
                (int(r['person_id']), int(r['account_id'])) for r in rows)
        self.__super.load_posix_users()

    def expand_netgroup(self, g_id, member_type, member_spread):
        ret = self.__super.expand_netgroup(g_id, member_type, member_spread)
        if self.opts.pers_group and member_type == self.co.entity_account:
            self.group.clear()
            self.group.find(g_id)
            if (not self.EMULATE_POSIX_LDIF
                or self.group.has_spread(self.co.spread_ldap_group)) and \
                   self.group.has_spread(self.co.spread_uit_nis_ng):
                groups, non_groups = ret
                for row in self.group.search_members(
                        group_id=g_id, member_type=self.co.entity_person):
                    person_id = int(row['member_id'])
                    try:
                        uname = self.e_id2name[self.pers2acc[person_id]]
                    except KeyError:
                        # We just ignore missing primary accounts.
                        if person_id in self.pers2acc:
                            self.logger.warn("Netgroup %d += unknown user %d",
                                             g_id, self.pers2acc[person_id])
                    else:
                        if "_" not in uname:
                            non_groups.add(uname)
        return ret


class PosixExportMemberOf(PosixExport):
    """LDAP users += attr uitMemberOf + objectclass uitMembership."""

    if False:                           # Memoize?
      def main(self):
        # We memoize group expansion, since we will be reusing them.
        self.__ng_cache = {}
        self.__fg_cache = {}
        self.__super.main()

      def expand_filegroup(self, gid):
        ret = self.__fg_cache.get(gid)
        if ret is None:
            ret = self.__fg_cache[gid] = self.__super.expand_filegroup(gid)
        return ret

      def expand_netgroup(self, *args):
        ret = self.__ng_cache.get(args)
        if ret is None:
            ret = self.__ng_cache[args] = self.__super.expand_netgroup(*args)
        return ret

    def setup_ldif(self):
        if hasattr(self, 'user2fg'): return
        self.__super.setup_ldif()
        if not self.opts.user_spread: return

        self.user2fg, self.user2ng, self.ng2ng = \
            user2fg, user2ng, ng2ng = map(defaultdict, [set]*3)

        # Build {user -> filegroups} mapping
        self.find_groups('filegroup')
        for g_id, gname in self.filegroups.iteritems():
            if g_id in self.g_id2gid:
                for user in self.expand_filegroup(g_id):
                    user2fg[user].add(gname)

        # Build {netgroup/user -> netgroups} mappings
        self.find_groups('netgroup')
        kind = (self.co.entity_account, self.spreads.user)
        for g_id, gname in self.netgroups.iteritems():
            groups, users = self.expand_netgroup(g_id, *kind)
            for subgroup in groups:
                ng2ng[subgroup].add(gname)
            for user in users:
                user2ng[user].add(gname)
        self.clear_groups()

        # Make {netgroup->netgroup} mapping non-recursive
        oldcnt, cnt = -1, 0
        while oldcnt != cnt:
            oldcnt, cnt = cnt, sum(imap(len, ng2ng.itervalues()))
            for gname, groups in ng2ng.iteritems():
                for subgroup in tuple(groups):
                    groups.update(ng2ng.get(subgroup, ()))

        self.fg_dnsplit = ("cn=", "," + self.fgrp_dn)
        self.ng_dnsplit = ("cn=", "," + self.ngrp_dn)

    def ldif_user(self, data):
        ret = dn, entry = self.__super.ldif_user(data)
        fg_dnsplit, ng_dnsplit = self.fg_dnsplit, self.ng_dnsplit
        fgroups = self.user2fg.pop(data.uname, ())
        ngroups = self.user2ng.pop(data.uname, ())
        for g in tuple(ngroups):
            for subgroup in self.ng2ng.get(g, ()):
                ngroups.update(subgroup)
        group_DNs =     [g.join(fg_dnsplit) for g in sorted(fgroups)]
        group_DNs.extend(g.join(ng_dnsplit) for g in sorted(ngroups))
        entry['uitMemberOf'] = group_DNs
        entry['objectClass'].append('uitMembership')
        return ret

if PosixExport.EMULATE_POSIX_LDIF:
    class PosixExportMemberOf(PosixExport):
        pass
