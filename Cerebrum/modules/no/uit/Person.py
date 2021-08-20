#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2003-2019 University of Oslo, Norway
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
from __future__ import unicode_literals

from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.Utils import argument_to_sql


class UiTPersonMixin(Person.Person):
    """
    This class provides an UiT-specific extension to the core Person class.
    """

    # This REALLY shoulda been in Entity class, but since we havent extended
    # that class already, we set it here instead. Extening the Entity class for
    # a single function doesnt make sense!
    def get_country_code(self, code_str):
        """
        Get a given country code id.

        :return: The code int value, or None if the code was not found.
        """
        for row in self.list_country_codes():
            if row['code_str'] == code_str:
                return row['code']
        return None

    def has_e_reservation(self):
        """Check if a person has an electronic listing reservation."""
        # TODO: In use by UiT code, but the trait is not automatically updated.
        #       Used to mirror `PersonUiOMixin.has_e_reservation`. Forcing it
        #       to be false for now.
        return False

    def list_deceased(self):
        ret = {}
        for row in self.query(
                """
                  SELECT pi.person_id, pi.deceased_date
                  FROM [:table schema=cerebrum name=person_info] pi
                  WHERE pi.deceased_date IS NOT NULL
                """):
            ret[int(row['person_id'])] = row['deceased_date']
            return ret

    def _compare_names(self, type, other):
        """Returns True if names are equal.
        self must be a populated object."""
        try:
            tmp = other.get_name(self._pn_affect_source, type)
            if tmp is None:
                raise KeyError
        except Exception:
            raise Person.MissingOtherException
        try:
            myname = self._name_info[type]
        except Exception:
            raise Person.MissingSelfException
        return tmp == myname

    def list_names(self, source_system=None, variant=None):
        """Return all names, optionally filtered on source_system or variant"""
        binds = dict()
        conditions = []

        if source_system is not None:
            cond = argument_to_sql(source_system, 'source_system', binds, int)
            conditions.append(cond)
        if variant is not None:
            cond = argument_to_sql(variant, 'name_variant', binds, int)
            conditions.append(cond)

        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        return self.query(
            """
              SELECT *
              FROM [:table schema=cerebrum name=person_name]
            """ + where,
            binds)
