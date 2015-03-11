#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""OU mixin for the TSD project.

A TSD project is stored as an OU, which then needs some extra functionality,
e.g. by using the acronym as a unique identifier - the project name - and the
project ID stored as an external ID. When a project has finished, we will
delete all details about the project, except the project's OU and its external
ID and acronym, to avoid reuse of the project ID and name for later projects.
"""

import re
from mx import DateTime

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Database import DatabaseError
from Cerebrum.OU import OU
from Cerebrum.Utils import Factory
from Cerebrum.modules import dns
from Cerebrum.modules.EntityTrait import EntityTrait

from Cerebrum.modules.tsd import TSDUtils


class OUTSDMixin(OU, EntityTrait):
    """
    Mixin of OU for TSD. Projects in TSD are stored as OUs, which then has to
    be unique.
    """
    def find_by_tsd_projectid(self, project_id):
        """TSD specific helper method for finding an OU by the project's ID.

        In TSD, each project is stored as an OU, with the project ID stored as
        an external ID.
        """
        return self.find_by_external_id(
            entity_type=self.const.entity_ou,
            id_type=self.const.externalid_project_id,
            external_id=project_id)

    def find_by_tsd_projectname(self, project_name):
        """TSD specific helper method for finding an OU by the project's name.

        In TSD, each project is stored as an OU, with the acronym as the unique
        project name.

        TODO: All project OUs could be stored under the same OU, if we need
        other OUs than project OUs.
        """
        matched = self.search_tsd_projects(name=project_name, exact_match=True)
        if not matched:
            raise Errors.NotFoundError("Unknown project: %s" % project_name)
        if len(matched) != 1:
            raise Errors.TooManyRowsError(
                "Found several OUs with given name: %s" % project_name)
        return self.find(matched[0]['entity_id'])

    def search_tsd_projects(self, name=None, exact_match=True):
        """Search method for finding projects by given input.

        TODO: Only project name is in use for now. Fix it if we need more
        functionality.

        @type name: string
        @param name: The project name.

        @type exact_match: bool
        @param exact_match:
            If it should search for the exact name, or through an sql query
            with LIKE.

        @rtype: list of db-rows
        @return:
            The db rows for each project. Each element contains what is
            returned from L{search_name_with_language}.
        """
        return self.search_name_with_language(
            entity_type=self.const.entity_ou,
            name_variant=self.const.ou_name_acronym,
            # TODO: name_language=self.const.language_en,
            name=name, exact_match=exact_match)

    def _validate_project_name(self, name):
        """Check if a given project name is valid.

        Project names are used as prefix for most of the project's entities,
        like accounts, groups and machines. We need to make sure that the name
        doesn't cause problems for e.g. AD.

        Some requirements:

        - Can not contain spaces. TODO: Why?

        - Can not contain commas. This is due to AD's way of identifying
          objects. Example: CN=username,OU=projectname,DC=tsd,DC=uio,DC=no.

        - Can not contain the SQL wildcards ? and %. This is a convenience
          limit, to be able to use Cerebrum's existing API without
          modifications.

        - Can not contain control characters.

        - Should not contains characters outside of ASCII. This is due to
          Cerebrum's lack of unicode support, and to avoid unexpected encoding
          issues.

        - TBD: A maximum length in the name? AD probably has a limit. As a
          prefix, it should be a bit less than AD's limit.

        In practice, we only accept regular alphanumeric characters in ASCII,
        in addition to some punctuation characters, like colon, dash and
        question marks. This would need to be extended in the future.

        @raise Errors.CerebrumError: If the given project name was not accepted
        """
        # TODO: whitelisting accepted characters, might want to extend the list
        # with characters I've forgotten:
        m = re.search('[^A-Za-z0-9_\-:;\*"\'\#\&\=!\?]', name)
        if m:
            raise Errors.CerebrumError(
                'Invalid characters in projectname: %s' % m.group())
        if len(name) < 3:
            raise Errors.CerebrumError('Project name too short')
        if len(name) > 8:  # TBD: or 6?
            raise Errors.CerebrumError('Project name is too long')
        return True

    def get_project_name(self):
        """Shortcut for getting the given OU's project name."""
        return self.get_name_with_language(self.const.ou_name_acronym,
                                           self.const.language_en)

    def get_project_id(self):
        """Shortcut for getting the given OU's project ID."""
        ret = self.get_external_id(id_type=self.const.externalid_project_id)
        if ret:
            return ret[0]['external_id']
        raise Errors.NotFoundError(
            'Mandatory project ID not found for %s' % self.entity_id)

    def get_project_int(self):
        """Shortcut for getting the "integer" for the project.

        An integer is needed e.g. to map a project to a subnet and/or VLAN. For
        now, is this mapped from the number in the project ID, so p01 would
        become 1 and p21 would become 21. This might be changed in the future
        when we reach p99.
        """
        projectid = self.get_project_id()
        return int(projectid[1:])

    def is_approved(self):
        """Check if this project is approved by TSD-admins.

        The approval is registered through a quarantine.

        @rtype: bool
        @return: True if the project is approved.
        """
        return not tuple(self.get_entity_quarantine(
            type=self.const.quarantine_not_approved,
            only_active=True))

    def add_name_with_language(self, name_variant, name_language, name):
        """Override to be able to verify project names (acronyms)."""
        if name_variant == self.const.ou_name_acronym:
            # TODO: Do we accept *changing* project names?

            # Validate the format of the acronym. The project name is used as a
            # prefix for other entities, like accounts, groups and machines, so
            # we need to be careful.
            self._validate_project_name(name)

            # TODO: check name_language too
            matched = self.search_name_with_language(
                entity_type=self.const.entity_ou,
                name_variant=self.const.ou_name_acronym,
                # TODO: name_language
                name=name)
            if any(r['name'] == name for r in matched):
                raise Errors.CerebrumError('Acronym already in use: %s' % name)
        return self.__super.add_name_with_language(name_variant, name_language,
                                                   name)

    def get_next_free_project_id(self):
        """Return the next project ID that is not in use."""
        while True:
            try:
                candidate = 'p%02d' % self.nextval('tsd_project_id_seq')
            except DatabaseError:
                # Raised by tsd_project_id_seq
                raise Errors.CerebrumError('No more available project IDs!')
            # The next test seems silly, but the sequence object is new
            # compared to TSD. It doesn't do much extra to have this
            # test + loop, and it is a simple method to sync tsd_project_id_seq
            # with old project ids.
            if not list(self.list_external_ids(
                    id_type=self.const.externalid_project_id,
                    external_id=candidate)
            ):
                return candidate

    def populate_external_id(self, source_system, id_type, external_id):
        """Subclass to avoid changing the project IDs and reuse them."""
        # Check that the ID is not in use:
        if id_type == self.const.externalid_project_id:
            for row in self.list_external_ids(id_type=id_type,
                                              external_id=external_id):
                raise Errors.CerebrumError("Project ID already in use")

        return self.__super.populate_external_id(source_system,
                                                 id_type,
                                                 external_id)

    def create_project(self, project_name):
        """Shortcut for creating a project in TSD with necessary data.

        Note that this method calls `write_db`.

        :param str project_name:
            A unique, short project name to use to identify the project.
            This is not the *project ID*, which is created automatically.

        :rtype: str
        :return:
            The generated project ID for the new project. `self` is populated
            with the new project.
        """
        # Check if given project name is already in use:
        if tuple(self.search_tsd_projects(name=project_name,
                                          exact_match=True)):
            raise Errors.CerebrumError(
                'Project name already taken: %s' % project_name)
        self.populate()
        self.write_db()
        # Generate a project ID:
        self.affect_external_id(self.const.system_cached,
                                self.const.externalid_project_id)
        pid = self.get_next_free_project_id()
        self.populate_external_id(self.const.system_cached,
                                  self.const.externalid_project_id, pid)
        self.write_db()
        # Store the project name:
        self.add_name_with_language(name_variant=self.const.ou_name_acronym,
                                    name_language=self.const.language_en,
                                    name=project_name)
        self.write_db()
        return pid

    def setup_project(self, creator_id, vlan=None):
        """Set up an approved project properly.

        By setting up a project we mean:

         - Create the required project groups, according to config.
         - Reserve a vlan and subnet for the project.
         - Create the required project machines.

        More setup should be added here in the future, as this method should be
        called from all imports and jobs that creates TSD projects.

        Note that the given OU must have been set up with a proper project ID,
        stored as an `external_id`, and a project name, stored as an acronym,
        before this method could be called. The project must already be
        approved for this to happen, i.e. not in quarantine.

        :param int creator_id:
            The creator of the project. Either the `entity_id` of the
            administrator that created the project or a system user.

        :param int vlan:
            If given, sets the VLAN number to give to the project's subnets.
        """
        if not self.is_approved():
            raise Errors.CerebrumError("Project is not approved, cannot setup")
        self._setup_project_dns(creator_id, vlan)
        self._setup_project_hosts(creator_id)
        self._setup_project_groups(creator_id)
        self._setup_project_posix(creator_id)

    def _setup_project_groups(self, creator_id):
        """Setup the groups belonging to the given project.

        @type creator_id: int
        @param creator_id:
            The creator of the project. Either the entity_id of the
            administrator that created the project or a system user.
        """
        projectid = self.get_project_id()
        gr = Factory.get("PosixGroup")(self._db)
        ac = Factory.get('Account')(self._db)
        pe = Factory.get('Person')(self._db)

        def _create_group(groupname, desc, spreads):
            """Helper function for creating a group.

            @type groupname: string
            @param groupname: The name of the new group. Gets prefixed by the
                project-ID.

            @type desc: string
            @param desc: The description that should get stored at the new
                group.

            @type spreads: list of str
            @param spreads:
                A list of strcode for spreads that the group should have.
            """
            groupname = '-'.join((projectid, groupname))
            gr.clear()
            try:
                gr.find_by_name(groupname)
                # If group already exists, we skip creating it.
            except Errors.NotFoundError:
                gr.clear()
                gr.populate(creator_id, self.const.group_visibility_all,
                            groupname, desc)
                gr.write_db()
            # Each group is linked to the project by a project trait:
            gr.populate_trait(code=self.const.trait_project_group,
                              target_id=self.entity_id, date=DateTime.now())
            gr.write_db()
            # Add defined spreads:
            for strcode in spreads:
                spr = self.const.Spread(strcode)
                if not gr.has_spread(spr):
                    gr.add_spread(spr)
                    gr.write_db()

        for suffix, desc, spreads in getattr(cereconf,
                                             'TSD_PROJECT_GROUPS', ()):
            _create_group(suffix, desc, spreads)

        def _get_persons_accounts(person_id):
            """Helper method for getting this project's accounts for a person.

            Only the accounts related to this project OU are returned.

            @type person_id: int
            @param person_id:
                Only return the accounts belonging to the given person.

            @rtype: generator (yielding ints)
            @return:
                The persons accounts' entity_ids.
            """
            return (r['account_id'] for r in
                    ac.list_accounts_by_type(person_id=person_id,
                                             ou_id=self.entity_id))

        # Update group memberships:
        for grname, members in getattr(cereconf, 'TSD_GROUP_MEMBERS',
                                       dict()).iteritems():
            grname = '-'.join((projectid, grname))
            gr.clear()
            try:
                gr.find_by_name(grname)
            except Errors.NotFoundError:
                # Group not created, skipping
                continue
            for mem in members:
                memtype, memvalue = mem.split(':')
                if memtype == 'group':
                    gr2 = Factory.get('Group')(self._db)
                    gr2.find_by_name('-'.join((projectid, memvalue)))
                    if not gr.has_member(gr2.entity_id):
                        gr.add_member(gr2.entity_id)
                elif memtype == 'person_aff':
                    # Fetch the correct affiliation, handle both a single
                    # "AFFILIATION" and the "AFFILIATION/status" format:
                    try:
                        af, st = memvalue.split('/')
                    except ValueError:
                        aff = self.const.PersonAffiliation(memvalue)
                        status = None
                    else:
                        aff = self.const.PersonAffiliation(af)
                        status = self.const.PersonAffStatus(aff, st)
                    for row in pe.list_affiliations(ou_id=self.entity_id,
                                                    affiliation=aff,
                                                    status=status):
                        for a_id in _get_persons_accounts(row['person_id']):
                            if not gr.has_member(a_id):
                                gr.add_member(a_id)
                else:
                    raise Exception("Unknown member type in: %s" % mem)
            gr.write_db()

    def get_next_free_vlan(self):
        """Get the first VLAN number that is not in use.

        :rtype: int
        :return: An available VLAN number not used by anyone.

        :raise Errors.CerebrumError: If no VLAN is available.
        """
        taken_vlans = set()
        subnet = dns.Subnet.Subnet(self._db)
        for row in subnet.search():
            taken_vlans.add(row['vlan_number'])
        subnet6 = dns.IPv6Subnet.IPv6Subnet(self._db)
        for row in subnet6.search():
            taken_vlans.add(row['vlan_number'])
        # TODO: Do we need a max value?
        for min, max in getattr(cereconf, 'VLAN_RANGES', ()):
            i = min
            while i <= max:
                if i not in taken_vlans:
                    return i
                i += 1
        raise Errors.CerebrumError("No free VLAN left")

    def _setup_project_dns(self, creator_id, vlan=None):
        """Setup a new project's DNS info, like subnet and VLAN.

        :param int creator_id:
            The entity_id for the user who executes this.

        :param int vlan:
            If given, overrides what VLAN number to set for the project's
            subnets, as long as it is larger than `cereconf.SUBNET_START`.
            If set to None, the first free VLAN will be chosen.
        """
        projectid = self.get_project_id()
        etrait = EntityTrait(self._db)
        if not vlan:
            vlan = self.get_next_free_vlan()
        try:
            vlan = int(vlan)
        except ValueError:
            raise Errors.CerebrumError('VLAN not valid: %s' % (vlan,))
        # Checking if the VLAN is in one of the ranges
        for min, max in getattr(cereconf, 'VLAN_RANGES', ()):
            if vlan >= min and vlan <= max:
                break
        else:
            raise Errors.CerebrumError('VLAN out of range: %s' % vlan)

        # TODO: Find a better way for mapping between project ID and VLAN:
        intpid = self.get_project_int()
        subnetstart, subnet6start = self._generate_subnets_for_project_id(
            project_id=intpid)

        for cls, trait, start, my_subnets in (
                (dns.Subnet.Subnet, self.const.trait_project_subnet,
                 subnetstart, self.ipv4_subnets),
                (dns.IPv6Subnet.IPv6Subnet, self.const.trait_project_subnet6,
                 subnet6start, self.ipv6_subnets)):
            sub = cls(self._db)
            try:
                sub.find(start)
            except dns.Errors.SubnetError:
                sub.populate(start, "Subnet for project %s" % projectid, vlan)
                sub.write_db()
            else:
                if sub.entity_id not in my_subnets:
                    raise Exception("Subnet %s exists, but does not belong"
                                    " to %s" % (start, projectid))
            etrait.clear()
            etrait.find(sub.entity_id)
            etrait.populate_trait(trait, date=DateTime.now(),
                                  target_id=self.entity_id)
            etrait.write_db()

        # TODO: Reserve 10 PTR addresses in the start of the subnet!

    def _generate_subnets_for_project_id(self, project_id):
        """Calculate which IPv4 and IPv6 subnets should be assigned to a project.

        :param int project_id:
            The entity ID of the project.

        :rtype: tuple of strings
        :return: The (ipv4, ipv6) subnet.
        """
        # This algorithm will only work until we hit project number 32768,
        # at that point the subnets will be invalid, like: 10.256.0.0/24
        if project_id > 32767:
            raise Errors.CerebrumError(
                'Project ID cannot be higher than 32767')
        # we start at 10.128.0.0/24 for project_id=0
        n = 32768 + project_id
        # second octet, third octet
        quotient, remainder = divmod(n, 256)
        return (cereconf.SUBNET_START % (quotient, remainder),
                cereconf.SUBNET_START_6 % hex(n)[2:])

    def _setup_project_hosts(self, creator_id):
        """Setup the hosts initially needed for the given project."""
        projectid = self.get_project_id()
        host = dns.HostInfo.HostInfo(self._db)

        vm_trait = self.get_trait(self.const.trait_project_vm_type)
        vm_type = 'win_vm'
        if vm_trait:
            vm_type = vm_trait['strval']

        if vm_type in ('win_vm', 'win_and_linux_vm'):
            # Create a Windows host for the whole project
            hostname = '%s-win01.tsd.usit.no.' % projectid
            hinfo = 'IBM-PC\tWINDOWS'
            dnsowner = self._populate_dnsowner(hostname)
            try:
                host.find_by_dns_owner_id(dnsowner.entity_id)
            except Errors.NotFoundError:
                host.populate(dnsowner.entity_id, hinfo)
            host.hinfo = hinfo
            host.write_db()
            for comp in getattr(cereconf, 'TSD_HOSTPOLICIES_WIN', ()):
                TSDUtils.add_host_to_policy_component(self._db,
                                                      dnsowner.entity_id, comp)

    def _setup_project_posix(self, creator_id):
        """Setup POSIX data for the project."""
        ac = Factory.get('Account')(self._db)
        pu = Factory.get('PosixUser')(self._db)
        for row in ac.list_accounts_by_type(
                ou_id=self.entity_id,
                affiliation=self.const.affiliation_project):
            ac.clear()
            ac.find(row['account_id'])
            pu.clear()
            try:
                pu.find(ac.entity_id)
            except Errors.NotFoundError:
                pu.clear()
                uid = pu.get_free_uid()
                pu.populate(uid, None, None, self.const.posix_shell_bash,
                            parent=ac, creator_id=creator_id)
                pu.write_db()

    def _populate_dnsowner(self, hostname):
        """Create or update a DnsOwner connected to the given project.

        The DnsOwner is given a trait, to affiliate it with this project-OU.

        This should rather be put in the DNS module, but due to its complexity,
        its weird layout, and my lack of IQ points to understand it, I started
        just using its API instead.

        :param str hostname: The given *FQDN* for the host.

        :rtype: DnsOwner object
        :return:
            The DnsOwner object that is created or updated.
        """
        dns_owner = dns.DnsOwner.DnsOwner(self._db)
        dnsfind = dns.Utils.Find(self._db, cereconf.DNS_DEFAULT_ZONE)
        ipv6number = dns.IPv6Number.IPv6Number(self._db)
        aaaarecord = dns.AAAARecord.AAAARecord(self._db)
        ipnumber = dns.IPNumber.IPNumber(self._db)
        arecord = dns.ARecord.ARecord(self._db)

        try:
            dns_owner.find_by_name(hostname)
        except Errors.NotFoundError:
            # TODO: create owner here?
            dns_owner.populate(self.const.DnsZone(cereconf.DNS_DEFAULT_ZONE),
                               hostname)
            dns_owner.write_db()
        # Affiliate with project:
        dns_owner.populate_trait(self.const.trait_project_host,
                                 target_id=self.entity_id)
        dns_owner.write_db()
        for (subnets, ipnum, record, ipstr) in (
                (self.ipv6_subnets, ipv6number, aaaarecord, "IPv6"),
                (self.ipv4_subnets, ipnumber, arecord, "IPv4")):
            # TODO: check if dnsowner already has an ip address.
            try:
                ip = dnsfind.find_free_ip(subnets.next(), no_of_addrs=1)[0]
            except StopIteration:
                raise Errors.NotFoundError("No %s-subnet for project %s" %
                                           (ipstr, self.get_project_id()))
            ipnum.populate(ip)
            ipnum.write_db()
            record.populate(dns_owner.entity_id, ipnum.entity_id)
            record.write_db()
        return dns_owner

    def get_project_subnets(self):
        """Get the subnets that are affiliated with the given project.

        This is mostly a wrapper around `list_traits` for fetching the
        affiliations traits for subnets, as that is how
        subnet-to-project-affiliations are represented.

        Both IPv4 and IPv6 subnets are returned. The type could be identified
        by each returned element's item `entity_type` (and `code`, as it's two
        different trait types).

        :rtype: generator
        :return: A list of traits db-rows for each subnet. Each element's
            values that might be relevant are `entity_id`, `entity_type`,
            `code` and `date`. The other values might not be used.
        """
        for row in self.list_traits(code=(self.const.trait_project_subnet6,
                                          self.const.trait_project_subnet),
                                    target_id=self.entity_id):
            yield row

    @property
    def ipv4_subnets(self):
        """ Read-only attribute with the IPv4 subnets for this project. """
        return (row['entity_id'] for row in self.get_project_subnets()
                if row['code'] == self.const.trait_project_subnet)

    @property
    def ipv6_subnets(self):
        """ Read-only attribute with the IPv6 subnets for this project. """
        return (row['entity_id'] for row in self.get_project_subnets()
                if row['code'] == self.const.trait_project_subnet6)

    def get_pre_approved_persons(self):
        """Get a list of pre approved persons by their fnr.

        This is a list of persons that has already been granted access to a
        project, but have not asked for the access yet. The list is stored in a
        trait, but is automatically split by spaces for ease of use.

        @rtype: set
        @return: A set of identifiers for each pre approved person.
        """
        tr = self.get_trait(self.const.trait_project_persons_accepted)
        if tr is None:
            return set()
        return set(tr['strval'].split(','))

    def add_pre_approved_persons(self, ids):
        """Pre approve persons to the project by their external IDs.

        The list of pre approved persons for the project gets extended with the
        new list.

        @type ids: iterator
        @param ids: All the external IDs for all the pre approved persons.
        """
        approvals = self.get_pre_approved_persons()
        approvals.update(ids)
        # TODO: check if this works!
        self.populate_trait(code=self.const.trait_project_persons_accepted,
                            date=DateTime.now(), strval=','.join(approvals))
        return True

    def terminate(self):
        """Remove all of a project, except its project ID and name (acronym).

        The project's entities are deleted by this method, so use with care!

        For the OU object, it does almost the same as L{delete} except from
        deleting the entity itself.
        """
        self.write_db()
        ent = EntityTrait(self._db)
        # Delete affiliated entities
        # Delete the project's users:
        ac = Factory.get('Account')(self._db)
        for row in ac.list_accounts_by_type(ou_id=self.entity_id):
            ac.clear()
            ac.find(row['account_id'])
            ac.delete()
        # Remove every trace of person affiliations to the project:
        pe = Factory.get('Person')(self._db)
        for row in pe.list_affiliations(ou_id=self.entity_id,
                                        include_deleted=True):
            pe.clear()
            pe.find(row['person_id'])
            pe.nuke_affiliation(ou_id=row['ou_id'],
                                affiliation=row['affiliation'],
                                source=row['source_system'],
                                status=row['status'])
            pe.write_db()
        # Remove all project's groups:
        gr = Factory.get('Group')(self._db)
        for row in gr.list_traits(code=self.const.trait_project_group,
                                  target_id=self.entity_id):
            gr.clear()
            gr.find(row['entity_id'])
            gr.delete()
        # Delete all subnets
        subnet = dns.Subnet.Subnet(self._db)
        subnet6 = dns.IPv6Subnet.IPv6Subnet(self._db)
        for row in ent.list_traits(code=(self.const.trait_project_subnet6,
                                         self.const.trait_project_subnet),
                                   target_id=self.entity_id):
            ent.clear()
            ent.find(row['entity_id'])
            ent.delete_trait(row['code'])
            ent.write_db()
            if row['code'] == self.const.trait_project_subnet:
                subnet.clear()
                subnet.find(row['entity_id'])
                subnet.delete()
            if row['code'] == self.const.trait_project_subnet6:
                subnet6.clear()
                subnet6.find(row['entity_id'])
                subnet6.delete()
        # Remove all project's DnsOwners (hosts):
        dnsowner = dns.DnsOwner.DnsOwner(self._db)
        for row in ent.list_traits(code=self.const.trait_project_host,
                                   target_id=self.entity_id):
            # TODO: Could we instead update the Subnet classes to use
            # Factory.get('Entity'), and make use of EntityTrait there to
            # handle this?
            ent.clear()
            ent.find(row['entity_id'])
            ent.delete_trait(row['code'])
            ent.write_db()
            dnsowner.clear()
            dnsowner.find(row['entity_id'])
            dnsowner.delete()
        # Remove all data from the OU except for:
        # The project ID and project name
        for tr in tuple(self.get_traits()):
            self.delete_trait(tr)
        for row in self.get_spread():
            self.delete_spread(row['spread'])
        for row in self.get_contact_info():
            self.delete_contact_info(row['source_system'],
                                     row['contact_type'])
        for row in self.get_entity_address():
            self.delete_entity_address(row['source_system'],
                                       row['address_type'])
        for row in self.search_name_with_language(entity_id=self.entity_id):
            # The project name must not be removed, to avoid reuse
            if row['name_variant'] == self.const.ou_name_acronym:
                continue
            self.delete_name_with_language(row['name_variant'])
        self.write_db()
