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
"""AD sync functionality specific to UiA.

The (new) AD sync is supposed to be able to support most of the functionality
that is required for the different instances. There are still, however,
functionality that could not be implemented generically, and is therefore put
here.

Note: You should put as little as possible in subclasses of the AD sync, as it
then gets harder and harder to improve the code without too much extra work by
testing all the subclasses.

"""

import cerebrum_path
import cereconf
import adconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.Email import EmailTarget, EmailQuota

from Cerebrum.modules.ad2.ADSync import BaseSync, UserSync, GroupSync
from Cerebrum.modules.ad2.CerebrumData import CerebrumUser, CerebrumGroup
from Cerebrum.modules import Email
from Cerebrum.modules.ad2.ConfigUtils import ConfigError

class UiAUserSync(UserSync):

    """ Override of the Usersync, for UiA specific, complex behaviour. """

    def configure(self, config_args):
        """Override the configuration for setting specific variables for UiA
        user sync.

        """
        super(UiAUserSync, self).configure(config_args)

        if 'forward_sync' in config_args:
            if config_args['forward_sync'] not in adconf.SYNCS:
                raise ConfigError("Illegal name for 'forward_sync' parameter: "
                                  "%s. The sync with this name is not found in "
                                  "the configuration file." 
                                  % config_args['forward_sync'])
            self.config['forward_sync'] = config_args['forward_sync']
        if 'distgroup_sync' in config_args:
            if config_args['distgroup_sync'] not in adconf.SYNCS:
                raise ConfigError("Illegal name for 'distgroup_sync' parameter:"
                                  " %s. The sync with this name is not found in"
                                  " the configuration file." 
                                  % config_args['distgroup_sync'])
            # No sense in running distgroupsync without running forward_sync
            # first.
            if not 'forward_sync' in self.config:
                raise ConfigError("'distgroup_sync' parameter is defined in the"
                                  " configuration, while 'forward_sync'"
                                  " parameter is missing. 'distgroup_sync'"
                                  " depends on 'forward_sync' and cannot be run"
                                  " if the latter is missing.")
            self.config['distgroup_sync'] = config_args['distgroup_sync']


    def fullsync(self):
        """Usually fullsync method is never subclassed. But for UiA there is
        a need to do it because usersync is tightly connected with sync of
        forward-addresses and distribution groups. All 3 syncs share information
        and depend on each other. So UserSync for UiA now triggers ForwardSync
        and DistGroupSync from inside itself, if the two latter are present
        in the configuration.

        """
        super(UiAUserSync, self).fullsync()
        if self.config.has_key('forward_sync'):
            self.logger.debug("Running forward sync")
            forward_sync_class = self.get_class(
                                     sync_type = self.config['forward_sync'])
            forward_sync = forward_sync_class(self.entities, self.addr2username,
                                              self.db, self.logger)
            forward_conf = adconf.SYNCS[self.config['sync_type']].copy()
            for k, v in adconf.SYNCS[self.config['forward_sync']].iteritems():
                forward_conf[k] = v
            forward_conf['sync_type'] = self.config['sync_type']
            forward_sync.configure(forward_conf)
            forward_sync.fullsync()
        if self.config.has_key('distgroup_sync'):
            self.logger.debug("Running distribution groups sync")
            distgroup_sync_class = self.get_class(
                                     sync_type = self.config['distgroup_sync'])
            distgroup_sync = distgroup_sync_class(
                                            forward_sync.entities,
                                            forward_sync.distgroup_user_members,
                                            self.db, self.logger)
            distgroup_conf = adconf.SYNCS[self.config['sync_type']].copy()
            for k, v in adconf.SYNCS[self.config['distgroup_sync']].iteritems():
                distgroup_conf[k] = v
            distgroup_conf['sync_type'] = self.config['sync_type']
            distgroup_sync.configure(distgroup_conf)
            distgroup_sync.fullsync()

    def attribute_mismatch(self, ent, atr, c, a):
        """Compare an attribute between Cerebrum and AD, UiA-wize.

        This method ignores certain Exchange attributes if the user has the
        spread `account@exchange`. For anything else, `super` is doing the rest.

        This is a temporary hack, while waiting for the functionality in
        CRB-523. Users with the spread "account@exchange" will be provisioned
        through the new Exchange integration for Exchange 2013. The regular
        AD-sync updated attributes for Exchange 2010 (spread account@exch_old).
        The two Exchange versions are using some of the same AD attributes, but
        they're using them differently, which creates conflicts with the two
        syncs. The quick solution here is to ignore certain exchange attributes
        if the user has the new Exchange spread.

        """
        # List of the attributes that Exchange 2013 needs, and which we
        # therefore should ignore:
        exch2013attrs = ('homemdb', 'msexchhomeservername', 'mdbusedefaults',
                         'deliverandredirect', 'mdboverquotalimit',
                         'mdboverhardquotalimit', 'mdbstoragequota',
                         'proxyaddresses', 'targetaddress', 'homemta',
                         'legacyexchangedn', 'mail', 'msexchmailboxguid',
                         'msexchpoliciesexcluded', 'msexchpoliciesincluded',
                         'msexchuserculture',
                         )
        # Force not updating certain Exchange attributes when user has spread
        # for Exchange 2013 (which are updated through event_daemon):
        if (self.co.spread_exchange_account in ent.spreads and
                atr.lower() in exch2013attrs):
            self.logger.debug3('Ignoring Exchange 2013 attribute "%s" for %s',
                               atr, ent)
            return (False, None, None)
        return super(UiAUserSync, self).attribute_mismatch(ent, atr, c, a)

class UiACerebrumUser(CerebrumUser):
    """UiA specific behaviour and attributes for a user object."""

    def calculate_ad_values(self):
        """Adding UiA specific attributes."""
        super(UiACerebrumUser, self).calculate_ad_values()

        # Hide all accounts that are not primary accounts:
        self.set_attribute('MsExchHideFromAddressLists',
                           not self.is_primary_account)


class UiACerebrumDistGroup(CerebrumGroup):
    """
    This class represent a virtual Cerebrum distribution group that
    contain contact objecs per user at UiA.
    """
    def __init__(self, logger, config, entity_id, entity_name, 
                 description = None):
        """
        CerebrumDistGroup constructor
        
        """
        super(UiACerebrumDistGroup, self).__init__(logger, config, entity_id,
                                                   entity_name, description)

    def calculate_ad_values(self):
        """
        Calculate AD attrs from Cerebrum data.
        
        """
        super(UiACerebrumDistGroup, self).calculate_ad_values()
        self.set_attribute('Member', ["CN=" + y.ad_id + "," + y.ou
                                      for y in self.forwards_data['members']])


class UiAForwardSync(BaseSync):
    """Sync for Cerebrum forward mail addresses in AD for UiA.

    """

    default_ad_object_class = 'contact'

    def __init__(self, account_entities, addr2username, *args, **kwargs):
        """Instantiate forward addresses specific functionality.

        @type account_entities: dict of user entities
        @param account_entities: 
            AD-entities that are created by the user sync, that is run 
            before this sync. These objects contain information about all
            forward addresses that need to be synchronized in this sync.

        @type addr2username: string -> string dict
        @param addr2username:
            The mapping of email address to the name of the account,
            that owns it. 

        """
        super(UiAForwardSync, self).__init__(*args, **kwargs)
        self.ac = Factory.get('Account')(self.db)
        self.accounts = account_entities
        self.distgroup_user_members = {}
        self.addr2username = addr2username

    def configure(self, config_args):
        """Override the configuration for setting forward specific vars."""
        super(UiAForwardSync, self).configure(config_args)
        # Which spreads the accounts should have for their forward-addresses
        # to be synchronized
        self.config['account_spreads'] = config_args['account_spreads']

    def fetch_cerebrum_entities(self):
        """Fetch the forward addresses information from Cerebrum, 
        that should be compared against AD. The forward addresses that
        belong to the accounts with specified spreads are fetched.
        
        The configuration is used to know what to cache. All data is put in a
        list, and each entity is put into an object from
        L{Cerebrum.modules.ad2.CerebrumData} or a subclass, to make it 
        easier to later compare with AD objects.

        Could be subclassed to fetch more data about each entity to support
        extra functionality from AD and to override settings.

        """
        # Get accounts that have all the needed spreads
        self.logger.debug2("Fetching accounts with needed spreads")
        accounts_dict = {}
        account_sets_list = []
        for spread in self.config['account_spreads']:
            tmp_set = set([(row['account_id'], row['name']) for row in
                    list(self.ac.search(spread = spread))])
            account_sets_list.append(tmp_set)
        entity_id2uname = set.intersection(*account_sets_list)

        # Create an AD-object for every forward fetched.
        self.logger.debug("Making forward AD-objects")
        for entity_id, username in entity_id2uname:
            ent = self.accounts.get(username)
            if ent:
                for tmp_addr in ent.maildata.get('forward', []):
                    # Forwarding can sometimes be enabled to the address which
                    # is simply alias for the default email. Such addresses
                    # are ignored
                    if tmp_addr in ent.maildata.get('alias', []):
                        continue
                    # Check if forwarding is enabled to an address in 'uia.no'
                    # domain.
                    nickname, domain = tmp_addr.split('@')
                    # The forward addresses in the local domain should not 
                    # have a corresponding forward object created in AD.
                    # Instead, we have to mark the user entity that owns
                    # the mail for the inclusion to a corresponding 
                    # distribution group.
                    owner_name = self.addr2username.get(tmp_addr.lower())
                    if owner_name:
                        owner_ent = self.accounts.get(owner_name)
                        if owner_ent:
                            self.distgroup_user_members[username] = owner_ent
                            continue
                    # Create an AD-object for the forward address.
                    # The name is composed according to UiA's requirements.
                    name = "Forward_for_%s__%s" % (username, tmp_addr)
                    if len(name) > 64:
                        name = "Forward_for_%s__%s" % (username, ent.entity_id)
                    self.entities[name] = self.cache_entity(ent.entity_id, name)
                    # Some of the forward object attributes are composed based 
                    # on the owner's username and forward address itself, 
                    # so save it for future use.
                    self.entities[name].forwards_data['uname'] = username
                    self.entities[name].forwards_data['addr'] = tmp_addr


class UiADistGroupSync(BaseSync):
    """Sync for Cerebrum distribution groups in AD for UiA.

    """

    default_ad_object_class = 'group'


    def __init__(self, forward_objects, user_objects, *args, **kwargs):
        """Instantiate forward addresses specific functionality.

        @type forward_objects: dict of forward entities
        @param forward_objects: 
            AD-entities that are created by the forward sync, that is run 
            before this sync. These objects will be used as members of
            distribution groups.

        @type user_objects: dict of user entities
        @param user_objects:
            AD entities that are created by the user sync that is run before
            both forward sync and this sync. These objects may be used as
            members of distribution groups.

        """
        super(UiADistGroupSync, self).__init__(*args, **kwargs)
        self.forwards = forward_objects
        # For local forward addresses we have to include a corresponding
        # user object in AD as a member of the group. Such objects are
        # passed through this variable.
        self.user_members = user_objects

    def fetch_cerebrum_entities(self):
        """Create distribution groups out of forward addresses information
        to compare them against AD. The forward addresses are received upon
        class' initialization.
        
        """
        self.logger.debug("Making distribution groups")
        
        for forward_name, forward_entity in self.forwards.iteritems():
            name = forward_entity.forwards_data['uname']
            if name in self.entities:
                # Add the forward-object to the group
                self.entities[name].forwards_data['members'].append(
                                                                 forward_entity)
            else:
                self.entities[name] = self.cache_entity(
                    forward_entity.entity_id, name, 
                    description = 'Samlegruppe for brukerens forwardadresser')
                self.entities[name].forwards_data['members'] = [forward_entity]

        # For local forward addresses we have to include user objects, 
        # as members to a distribution group
        for username, user_entity in self.user_members.iteritems():
            if username in self.entities:
                self.entities[username].forwards_data['members'].append(
                                                                    user_entity)
            else:
                self.entities[username] = self.cache_entity(
                    user_entity.entity_id, username, 
                    description = 'Samlegruppe for brukerens forwardadresser')
                self.entities[username].forwards_data['members'] = [
                                                                   user_entity,]
