# -*- coding: utf-8 -*-
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

# kbj005 2015.02.16: copied from /cerebrum/lib/python2.7/site-packages/Cerebrum/modules/no/hih

"""Mixin for OrgLDIF for UiT."""

from collections import defaultdict
from os.path import join as join_paths
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.OrgLDIF import *
from Cerebrum.modules.LDIFutils import *
from pprint import pprint
        
class OrgLDIFUiTMixin(OrgLDIF):
    def __init__(self, db, logger):
        self.__super.__init__(db, logger)
        self.attr2syntax['mobile'] = self.attr2syntax['telephoneNumber']

    def init_person_course(self):
        """Populate dicts with a person's course information."""
        timer = make_timer(self.logger,"Processing person courses...")
        self.ownerid2urnlist = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "ownerid2urnlist.pickle")))
        timer("...person courses done.")
    
    def init_person_groups(self):
        """Populate dicts with a person's group information."""
        timer = make_timer(self.logger,"Processing person groups...")
        self.person2group = pickle.load(file(
            join_paths(ldapconf(None, 'dump_dir'), "personid2group.pickle")))
        timer("...person groups done.")

    def init_person_dump(self, use_mail_module):
        """Suplement the list of things to run before printing the
        list of people."""
        self.__super.init_person_dump(use_mail_module)
        self.init_person_course()
        self.init_person_groups()

    
    def init_attr2id2contacts(self):
        """Override to include more, local data from contact info."""
        self.__super.init_attr2id2contacts()
        sap, fs = self.const.system_sap, self.const.system_fs
        c = [(a, self.get_contacts(contact_type  = t,
                                   source_system = s,
                                   convert       = self.attr2syntax[a][0],
                                   verify        = self.attr2syntax[a][1],
                                   normalize     = self.attr2syntax[a][2]))
             for a,s,t in (('mobile', fs, self.const.contact_mobile_phone),)]
        self.attr2id2contacts.extend((v for v in c if v[1]))

    def update_org_object_entry(self, entry):
        # Changes from superclass:
        # Add attributes needed by UiT.
        self.__super.update_org_object_entry(entry)
  
        if entry.has_key('o'):
            entry['o'].append(['University of Tromsoe','Universitetet i Tromso'])
        else:
            entry['o'] = (['University of Tromsoe','Universitetet i Tromso'])
  
        if entry.has_key('eduOrgLegalName'):
            entry['eduOrgLegalName'].append(['Universitetet i Tromso','University of Tromsoe'])
        else:
            entry['eduOrgLegalName'] = (['Universitetet i Tromso','University of Tromsoe'])
        
        entry['norEduOrgNIN'] = (['NO970422528'])


    def update_ou_entry(self, entry):
        # Changes from superclass:
            # Add object class norEduOrg and its attr norEduOrgUniqueIdentifier
        entry['objectClass'].append('norEduOrg')
        entry['norEduOrgUniqueIdentifier'] = self.norEduOrgUniqueID

        # ?? Are these needed?
        # entry['objectClass'].append('eduOrg')
        # entry['objectClass'].append('norEduObsolete')

    # 
    # override of OrgLDIF.init_ou_structure() with filtering of expired ous
    # 
    def init_ou_structure(self):
        # Set self.ou_tree = dict {parent ou_id: [child ou_id, ...]}
        # where the root OUs have parent id None.
        timer = make_timer(self.logger, "Fetching OU tree...")
        self.ou.clear()
        ou_list = self.ou.get_structure_mappings(
            self.const.OUPerspective(cereconf.LDAP_OU['perspective']), filter_expired = True)
        self.logger.debug("OU-list length: %d", len(ou_list))
        self.ou_tree = {None: []}  # {parent ou_id or None: [child ou_id...]}
        for ou_id, parent_id in ou_list:
            if parent_id is not None:
                parent_id = int(parent_id)
            self.ou_tree.setdefault(parent_id, []).append(int(ou_id))
        timer("...OU tree done.")
    
   
    def generate_system_object(self,outfile):
        entry= {'objectClass':['top','uioUntypedObject']}
        self.ou_dn = "cn=system,dc=uit,dc=no"
        outfile.write(entry_string(self.ou_dn,entry))
    
    def make_uioPersonScopedAffiliation(self, p_id, pri_aff, pri_ou):
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
       
   
    def init_account_info(self):
        # Set self.acc_name        = dict {account_id: user name}.
        # Set self.acc_passwd      = dict {account_id: password hash}.
        # Set self.acc_quarantines = dict {account_id: [quarantine list]}.
        # Set acc_locked_quarantines = acc_quarantines or separate dict
        timer = make_timer(self.logger, "Fetching account information...")
        timer2 = make_timer(self.logger)
        db = Factory.get('Database')()
        #account_obj = Factory.get('Account')(db)
        self.acc_name = acc_name = {}
        self.acc_passwd = {}
        self.acc_locked_quarantines = self.acc_quarantines = acc_quarantines = defaultdict(list)
        for row in self.account.list_account_authentication(
                auth_type=int(self.const.auth_type_md5_crypt)):
            

            #filter out sito accounts
            self.logger.debug("processing account:%s" % row['entity_name'])
            if len(row['entity_name']) == 7:
                if row['entity_name'][-1] == 's':
                    self.logger.debug("filtering out account:%s" %row['entity_name'])
                    continue
                
            account_id = int(row['account_id'])
            acc_name[account_id] = row['entity_name']
            self.acc_passwd[account_id] = row['auth_data']

        timer2("...account quarantines...")
        nonlock_quarantines = [
            int(self.const.Quarantine(code))
            for code in getattr(cereconf, 'QUARANTINE_FEIDE_NONLOCK', ())]
        if nonlock_quarantines:
            self.acc_locked_quarantines = acc_locked_quarantines = defaultdict(list)
        for row in self.account.list_entity_quarantines(
                entity_ids=self.accounts,
                only_active=True,
                entity_types=self.const.entity_account):
            qt = int(row['quarantine_type'])
            entity_id = int(row['entity_id'])
            acc_quarantines[entity_id].append(qt)
            if nonlock_quarantines and qt not in nonlock_quarantines:
                acc_locked_quarantines[entity_id].append(qt)
        timer("...account information done.")
   
