#!/usr/bin/env python2
# encoding: utf-8
#
# Copyright 2015 University of Oslo, Norway
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
u""" This is a bofhd module for setting consent. """

import cerebrum_path
import cereconf

from Cerebrum.modules.bofhd.errors import CerebrumError
from .bofhd_consent_auth import BofhdAuth as ConsentAuth

from Cerebrum.modules.bofhd.bofhd_core import BofhdCommonMethods
from Cerebrum.modules.bofhd.cmd_param import (Parameter,
                                              Command,
                                              Id,
                                              FormatSuggestion)

from .Consent import EntityConsentMixin


class ConsentType(Parameter):
    u""" Consent type parameter. """
    _type = 'consent_type'
    _help_ref = 'consent_type'


def format_datetime(field):
    u""" Date format for FormatSuggestion. """
    fmt = "yyyy-MM-dd HH:mm:SS"  # 19 characters wide
    return ":".join((field, "date", fmt))


class BofhdExtension(BofhdCommonMethods):

    u""" Commands for getting, setting and unsetting consent. """

    hidden_commands = {}  # Not accessible through bofh
    all_commands = {}

    def __init__(self, server):
        """
        """
        super(BofhdExtension, self).__init__(server)
        self.ba = ConsentAuth(self.db)
        self.util = server.util
        # POST:
        for attr in ('ConsentType', 'EntityConsent'):
            if not hasattr(self.const, attr):
                raise RuntimeError('consent: Missing consent constant types')

    def get_help_strings(self):
        u""" Help strings for consent commands. """
        group_help = {
            'consent': 'Commands for handling consents', }

        command_help = {
            'consent': {
                'consent_set': self.consent_set.__doc__,
                'consent_unset': self.consent_unset.__doc__,
                'consent_info': self.consent_info.__doc__,
                'consent_list': self.consent_list.__doc__, }, }

        arg_help = {
            'consent_type': ['type', 'Enter consent type',
                             "'consent list' lists defined consents"], }

        return (group_help, command_help, arg_help)

    def check_consent_support(self, entity):
        u""" Assert that entity has EntityConsentMixin.

        :param Cerebrum.Entity entity: The entity to check.

        :raise NotImplementedError: If entity lacks consent support.

        """
        entity_type = self.const.EntityType(entity.entity_type)
        if not isinstance(entity, EntityConsentMixin):
            raise NotImplementedError(
                u"Entity type '%s' does not support consent." %
                entity_type)

    #
    # consent set <ident> <consent_type>
    #
    all_commands['consent_set'] = Command(
        ('consent', 'set'),
        Id(help_ref="id:target:account"),
        ConsentType(),
        fs=FormatSuggestion(
            "OK: Set consent '%s' (%s) for %s '%s' (entity_id=%s)",
            ('consent_name', 'consent_type', 'entity_type', 'entity_name',
             'entity_id')),
        perm_filter='can_set_consent')

    def consent_set(self, operator, entity_ident, consent_ident):
        """ Set a consent for an entity. """
        entity = self.util.get_target(entity_ident, restrict_to=[])
        self.ba.can_set_consent(operator.get_entity_id(), entity)
        self.check_consent_support(entity)
        consent = self.const.human2constant(
            consent_ident, const_type=self.const.EntityConsent)
        consent_type = self.const.ConsentType(consent.consent_type)
        entity_name = self._get_entity_name(entity.entity_id,
                                            entity.entity_type)
        entity.set_consent(consent)
        entity.write_db()
        return {
            'consent_name': str(consent),
            'consent_type': str(consent_type),
            'entity_id': entity.entity_id,
            'entity_type': str(self.const.EntityType(entity.entity_type)),
            'entity_name': entity_name,
        }

    #
    # consent unset <ident> <consent_type>
    #
    all_commands['consent_unset'] = Command(
        ('consent', 'unset'),
        Id(help_ref="id:target:account"),
        ConsentType(),
        fs=FormatSuggestion(
            "OK: Removed consent '%s' (%s) for %s '%s' (entity_id=%s)",
            ('consent_name', 'consent_type', 'entity_type', 'entity_name',
             'entity_id')),
        perm_filter='can_unset_consent')

    def consent_unset(self, operator, entity_ident, consent_ident):
        """ Remove a previously set consent. """
        entity = self.util.get_target(entity_ident, restrict_to=[])
        self.ba.can_unset_consent(operator.get_entity_id(), entity)
        self.check_consent_support(entity)
        consent = self.const.human2constant(
            consent_ident, const_type=self.const.EntityConsent)
        consent_type = self.const.ConsentType(consent.consent_type)
        entity_name = self._get_entity_name(entity.entity_id,
                                            entity.entity_type)
        entity.remove_consent(consent)
        entity.write_db()
        return {
            'consent_name': str(consent),
            'consent_type': str(consent_type),
            'entity_id': entity.entity_id,
            'entity_type': str(self.const.EntityType(entity.entity_type)),
            'entity_name': entity_name,
        }

    #
    # consent info <ident>
    #
    all_commands['consent_info'] = Command(
        ('consent', 'info'),
        Id(help_ref="id:target:account"),
        fs=FormatSuggestion(
            '%-15s %-8s %-20s %-20s %s',
            ('consent_name',
             'consent_type',
             format_datetime('consent_time_set'),
             format_datetime('consent_time_expire'),
             'consent_description'),
            hdr='%-15s %-8s %-20s %-20s %s' % (
                'Name', 'Type', 'Set at', 'Expires at', 'Description')),
        perm_filter='can_show_consent_info')

    def consent_info(self, operator, ident):
        u""" View all set consents for a given entity. """
        entity = self.util.get_target(ident, restrict_to=[])
        self.check_consent_support(entity)
        self.ba.can_show_consent_info(operator.get_entity_id(), entity)

        consents = []
        for row in entity.list_consents(entity_id=entity.entity_id,
                                        filter_expired=False):
            consent = self.const.EntityConsent(row['consent_code'])
            consent_type = self.const.ConsentType(consent.consent_type)
            consents.append({
                'consent_name': str(consent),
                'consent_type': str(consent_type),
                'consent_time_set': row['time_set'],
                'consent_time_expire': row['expiry'],
                'consent_description': row['description'], })
        if not consents:
            name = self._get_entity_name(entity.entity_id, entity.entity_type)
            raise CerebrumError(
                "'%s' (entity_type=%s, entity_id=%s) has no consents set" % (
                    name,
                    self.const.EntityType(entity.entity_type),
                    entity.entity_id))
        return consents

    #
    # consent list
    #
    all_commands['consent_list'] = Command(
        ('consent', 'list'),
        fs=FormatSuggestion(
            '%-15s  %-8s  %s',
            ('consent_name', 'consent_type', 'consent_description'),
            hdr='%-16s %-9s %s' % ('Name', 'Type', 'Description')),
        perm_filter='can_list_consents')

    def consent_list(self, operator):
        u""" List all consent types. """
        self.ba.can_list_consents(operator.get_entity_id())
        consents = []
        for consent in self.const.fetch_constants(self.const.EntityConsent):
            consent_type = self.const.ConsentType(consent.consent_type)
            consents.append({
                'consent_name': str(consent),
                'consent_type': str(consent_type),
                'consent_description': consent.description, })
        if not consents:
            raise CerebrumError("No consent types defined yet")
        return consents


if __name__ == '__main__':
    del cerebrum_path
    del cereconf
