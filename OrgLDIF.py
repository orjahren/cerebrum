# -*- coding: utf-8 -*-
# Copyright 2004-2014 University of Oslo, Norway
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

import re
import pickle
from os.path import join as join_paths
from Cerebrum.modules.no.OrgLDIF import *
from Cerebrum.modules import LDIFutils
from Cerebrum.Constants import _PersonAffiliationCode, _PersonAffStatusCode

# Replace these characters with spaces in OU RDNs.
ou_rdn2space_re = re.compile('[#\"+,;<>\\\\=\0\\s]+')

class OrgLDIFUiTMixin(norEduLDIFMixin):
    """Mixin class for norEduLDIFMixin(OrgLDIF) with UiT modifications."""

    from cereconf import LDAP_PERSON
    if not LDAP_PERSON['dn'].startswith('ou='):

      def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']

    else:
      # Hacks for old LDAP structure

      def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']
        # Used by make_ou_dn() for for migration to ny-ldap.uit.no:
        self.used_new_DNs = {}
        self.ou_quarantined = {}
        self.dn2new_structure = {'ou=organization,dc=uit,dc=no':
                                 'cn=organization,dc=uit,dc=no',
                                 'ou=--,ou=organization,dc=uit,dc=no':
                                 'cn=organization,dc=uit,dc=no'}

    def init_ou_dump(self):
        self.__super.init_ou_dump()
        self.get_ou_quarantines()
        ou2parent = dict((c,p) for p,ous in self.ou_tree.items() for c in ous)
        class Id2ou(dict):
            # For missing id2ous, cache and return nearest parent or None
            def __missing__(self, key):
                val = self[key] = self[ou2parent.get(key)]
                return val
        self.ou_id2ou_uniq_id = Id2ou(self.ou_id2ou_uniq_id)
        self.ou_id2ou_uniq_id.setdefault(None, None)

    def test_omit_ou(self):
        return (not self.ou.has_spread(self.const.spread_ou_publishable)) or \
            self.ou_quarantined.get(self.ou.entity_id,False)

    def get_ou_quarantines(self):
        for row in self.ou.list_entity_quarantines(
                entity_types = self.const.entity_ou,
                quarantine_types = self.const.quarantine_ou_notvalid,
                only_active=True):
            self.ou_quarantined[int(row['entity_id'])] = True

    def make_ou_dn(self, entry, parent_dn):
        # Change from superclass:
        # Replace special characters with spaces instead of escaping them.
        # Replace multiple whitespace with a single space.  strip() the result.
        # Add fake attributes as info to migration scripts at ny-ldap.uit.no,
        # which needs to undo the above hacks: '#dn' with the new DN, and
        # '#remove: ou' for OU values that are added by this method.
        new_structure_dn = self.__super.make_ou_dn(
            entry, self.dn2new_structure[parent_dn])
        norm_new_dn = normalize_string(new_structure_dn)
        if norm_new_dn in self.used_new_DNs:
            new_structure_dn = "%s=%s+%s" % (
                self.FEIDE_attr_ou_id, entry[self.FEIDE_attr_ou_id][0],
                new_structure_dn)
        self.used_new_DNs[norm_new_dn] = True
        entry['#dn'] = (new_structure_dn,)
        rdn_ou = ou_rdn2space_re.sub(' ', entry['ou'][0]).strip()
        entry['ou'] = self.attr_unique(entry['ou'], normalize_string)
        ou_count = len(entry['ou'])
        entry['ou'].insert(0, rdn_ou)
        entry['ou'] = self.attr_unique(entry['ou'], normalize_string)
        if len(self.attr_unique(entry['ou'], normalize_string)) > ou_count:
            entry['#remove: ou'] = (rdn_ou,)
        dn = self.__super.make_ou_dn(entry, parent_dn)
        self.dn2new_structure.setdefault(dn, new_structure_dn)
        return dn

    def init_attr2id2contacts(self):
        # Change from superclass: Include 'mobile' as well.
        s = getattr(self.const, cereconf.LDAP['contact_source_system'])
        c = [(a, self.get_contacts(contact_type  = t,
                                   source_system = s,
                                   convert       = self.attr2syntax[a][0],
                                   verify        = self.attr2syntax[a][1],
                                   normalize     = self.attr2syntax[a][2]))
             for a,s,t in (('telephoneNumber', s, self.const.contact_phone),
                           ('mobile', s, self.const.contact_mobile_phone),
                           ('facsimileTelephoneNumber',
                            s, self.const.contact_fax),
                           ('labeledURI', None, self.const.contact_url))]
        self.id2labeledURI    = c[-1][1]
        self.attr2id2contacts = [v for v in c if v[1]]

    def make_address(self, sep,
                     p_o_box, address_text, postal_number, city, country):
        # Changes from superclass:
        # Weird algorithm for when to use p_o_box.
        # Append "Blindern" to postbox.
        if country:
            country = self.const.Country(country).country
        if (p_o_box and int(postal_number or 0) / 100 == 3):
            address_text = "Pb. %s - Blindern" % p_o_box
        else:
            address_text = (address_text or "").strip()
        post_nr_city = None
        if city or (postal_number and country):
            post_nr_city = " ".join(filter(None, (postal_number,
                                                  (city or "").strip())))
        val = "\n".join(filter(None, (address_text, post_nr_city, country)))
        if sep == '$':
            val = postal_escape_re.sub(hex_escape_match, val)
        return iso2utf(val.replace("\n", sep))

    def init_person_course(self):
        """Populate dicts with a person's course information."""
        timer = self.make_timer("Processing person courses...")
        self.ownerid2urnlist = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "ownerid2urnlist.pickle")))
        timer("...person courses done.")

    def init_person_groups(self):
        """Populate dicts with a person's group information."""
        timer = self.make_timer("Processing person groups...")
        self.person2group = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "personid2group.pickle")))
        timer("...person groups done.")

    def init_person_dump(self, use_mail_module):
        """Suplement the list of things to run before printing the
        list of people."""
        self.__super.init_person_dump(use_mail_module)
        self.init_person_course()
        self.init_person_groups()

    def init_person_titles(self):
        # Change from original: Search titles first by system_lookup_order,
        # then within each system let personal title override work title.
        timer = self.make_timer("Fetching personal titles...")
        titles = {}
        for name_type in (self.const.personal_title, self.const.work_title):
            for row in self.person.search_name_with_language(
                                       entity_type=self.const.entity_person,
                                       name_variant=name_type,
                                       name_language=self.languages):
                titles.setdefault(int(row['entity_id']), {}).setdefault(
                    int(row['name_language']), iso2utf(row['name']))
        self.person_titles = dict([(p_id, t.items())
                                   for p_id, t in titles.items()])
        timer("...personal titles done.")

    def make_uitPersonScopedAffiliation(self, p_id, pri_aff, pri_ou):
        # [primary|secondary]:<affiliation>@<status>/<stedkode>
        ret = []
        pri_aff_str, pri_status_str = pri_aff
        for aff, status, ou in self.affiliations[p_id]:
            # populate the caches
            if self.aff_cache.has_key(aff):
                aff_str = self.aff_cache[aff]
            else:
                aff_str = str(self.const.PersonAffiliation(aff))
                self.aff_cache[aff] = aff_str
            if self.status_cache.has_key(status):
                status_str = self.status_cache[status]
            else:
                status_str = str(self.const.PersonAffStatus(status).str)
                self.status_cache[status] = status_str
            p = 'secondary'
            if aff_str == pri_aff_str and status_str == pri_status_str and ou == pri_ou:
                p = 'primary'
            ou = self.ou_id2ou_uniq_id[ou]
            if ou:
                ret.append(''.join((p,':',aff_str,'/',status_str,'@',ou)))
        return ret

    def make_person_entry(self, row):
        """Add data from person_course to a person entry."""
        dn, entry, alias_info = self.__super.make_person_entry(row)
        p_id = int(row['person_id'])
        if not dn:
            return dn, entry, alias_info
        if self.ownerid2urnlist.has_key(p_id):
            # Some of the chars in the entitlements are outside ascii
            if entry.has_key('eduPersonEntitlement'):
                entry['eduPersonEntitlement'].extend(self.ownerid2urnlist[p_id])
            else:
                entry['eduPersonEntitlement'] = self.ownerid2urnlist[p_id]
        entry['uitPersonID'] = str(p_id)
        if self.person2group.has_key(p_id):
            # TODO: remove member and uitPersonObject after transition period
            entry['uitMemberOf'] = entry['member'] = self.person2group[p_id]
            entry['objectClass'].extend(('uitMembership', 'uitPersonObject'))

        pri_edu_aff, pri_ou, pri_aff = self.make_eduPersonPrimaryAffiliation(p_id)
        entry['uitPersonScopedAffiliation'] = self.make_uitPersonScopedAffiliation(p_id, pri_aff, pri_ou)
        if 'uitPersonObject' not in entry['objectClass']:
            entry['objectClass'].extend(('uitPersonObject',))

        # Check if there exists «avvikende» addresses, if so, export them instead:
        addrs = self.addr_info.get(p_id)
        post  = addrs and addrs.get(int(self.const.address_other_post))
        if post:
            a_txt, p_o_box, p_num, city, country = post
            post = self.make_address("$", p_o_box,a_txt,p_num,city,country)
            if post:
                entry['postalAddress'] = (post,)
        street = addrs and addrs.get(int(self.const.address_other_street))
        if street:
            a_txt, p_o_box, p_num, city, country = street
            street = self.make_address(", ", None,a_txt,p_num,city,country)
            if street:
                entry['street'] = (street,)

        return dn, entry, alias_info

    def _calculate_edu_OUs(self, p_ou, s_ous):
        return s_ous


    def init_person_selections(self, *args, **kwargs):
        """ Extend with UiT settings for person selections.

        This is especially for `no.uit.OrgLDIF.is_person_visible()`, as UiT has
        some special needs in how to interpret visibility of persons due to
        affiliations for reservation and consent, which behaves differently in
        SAPUiT and FS.

        """
        self.__super.init_person_selections(*args, **kwargs)
        # Set what affiliations that should be checked for visibility from SAP
        # and FS. The default is to set the person to NOT visible, which happens
        # for all persons that doesn't have _any_ of the affiliations defined
        # here.
        self.visible_sap_affs = (int(self.const.affiliation_ansatt),)
        tilkn_aff = int(self.const.affiliation_tilknyttet)
        self.visible_sap_statuses = (
            (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_stip)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_frida_reg)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_innkjoper)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_assosiert_person)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_forsker)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_emeritus)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_gjesteforsker)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_bilag)),
            (tilkn_aff, int(self.const.affiliation_tilknyttet_ekst_partner)),
            )
        student = int(self.const.affiliation_student)
        self.fs_aff_statuses = (
            (student, int(self.const.affiliation_status_student_aktiv)),
            (student, int(self.const.affiliation_status_student_drgrad)))
        self.sap_res = self.init_person_group("SAP-elektroniske-reservasjoner")
        self.fs_samtykke = self.init_person_group("FS-aktivt-samtykke")

    def is_person_visible(self, person_id):
        """ Override with UiT specific visibility.

        At UiT, visibility is controlled differently depending on what source
        system the person is from. SAPUiT has reservations, while FS has active
        consents. Since we don't fetch source systems per affiliation from
        Cerebrum in `OrgLDIF`, we only guess.

        The reason for this override, is to support priority. SAP has priority
        over FS, which can't be implemented through the configuration as of
        today.

        Note that the settings in `cereconf.LDAP_PERSON['visible_selector']` is
        ignored by this override. The list of affiliations are hardcoded in the
        method `init_person_selections`.

        """
        # TODO: this could be changed to check the trait 'reserve_public'
        # later, so we don't have to check group memberships.
        #
        # The trait behaves in the following manner:
        # Every person should be 'invisible', except if:
        #  * The person has a trait of the type 'reserve_public', and
        #  * The trait's numval is set to 0
        # This means that a missing trait should be considered as a reservation.


        p_affs = self.affiliations[person_id]
        # If there is an affiliation from SAP then consider
        # reservations/permissions from SAP only.
        for (aff, status, ou) in p_affs:
            if aff in self.visible_sap_affs:
                return person_id not in self.sap_res
            if (aff, status) in self.visible_sap_statuses:
                return person_id not in self.sap_res
        # Otherwise, if there is an affiliaton STUDENT/<aktiv or drgrad>,
        # check for permission from FS to make the person visible.
        for (aff, status, ou) in p_affs:
            if (aff, status) in self.fs_aff_statuses:
                return person_id in self.fs_samtykke
        # Otherwise hide the person.
        return False

