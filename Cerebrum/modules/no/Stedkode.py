# -*- coding: utf-8 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

"""Norwegian higher education-specific OU extension.

This module implements extensions to the standard Cerebrum OU class
that are specific to the higher education sector in Norway.  The
following additional properties are defined:

  - fakultet
  - institutt
  - avdeling
  - institusjon
"""

from Cerebrum.OU import OU
from Cerebrum.Utils import Factory
import cereconf
import six

__version__ = "1.1"


@six.python_2_unicode_compatible
class Stedkode(OU):

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('landkode', 'institusjon', 'fakultet', 'institutt',
                      'avdeling',)

    def __init__(self, database):
        """

        """
        self.__super.__init__(database)
        self.clear()

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        self.clear_class(Stedkode)
        self.__updated = []

    def populate(self, fakultet, institutt, avdeling, institusjon=None,
                 landkode=0, parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            self.__super.populate()
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False
        self.landkode = int(landkode)
        self.fakultet = int(fakultet)
        self.institutt = int(institutt)
        self.avdeling = int(avdeling)
        self.institusjon = int(institusjon)

    def __eq__(self, other):
        assert isinstance(other, Stedkode), repr(other)
        identical = self.__super.__eq__(other)
        if not identical:
            return False
        identical = ((other.fakultet == self.fakultet) and
                     (other.institutt == self.institutt) and
                     (other.avdeling == self.avdeling) and
                     (other.institusjon == self.institusjon) and
                     (other.landkode == self.landkode))
        return identical

    def __str__(self):
        return '{:02d}{:02d}{:02d}'.format(
            self.fakultet, self.institutt, self.avdeling)
        return "landkode=%s, institusjon=%s, stedkode=%s-%s-%s" % (
            self.landkode, self.institusjon, self.fakultet, self.institutt,
            self.avdeling)

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If `as_object' isn't specified (or is None), the instance is
        written as a new entry to the Cerebrum database.  Otherwise,
        the object overwrites the Entity entry corresponding to the
        instance `as_object'.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=stedkode]
              (ou_id, landkode, institusjon, fakultet, institutt, avdeling)
            VALUES
              (:ou_id, :landkode, :institusjon, :fakultet, :institutt,
               :avdeling)""", {'ou_id': self.entity_id,
                               'landkode': self.landkode,
                               'institusjon': self.institusjon,
                               'fakultet': self.fakultet,
                               'institutt': self.institutt,
                               'avdeling': self.avdeling})
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=stedkode]
            SET landkode=:landkode, institusjon=:institusjon,
                fakultet=:fakultet, institutt=:institutt,
                avdeling=:avdeling
            WHERE ou_id=:ou_id""", {'ou_id': self.entity_id,
                                    'landkode': int(self.landkode),
                                    'institusjon': int(self.institusjon),
                                    'fakultet': int(self.fakultet),
                                    'institutt': int(self.institutt),
                                    'avdeling': int(self.avdeling)})
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        if self.__in_db:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=stedkode]
            WHERE ou_id=:ou_id""", {'ou_id': self.entity_id})
        self.__super.delete()

    def find(self, ou_id):
        self.__super.find(ou_id)
        (self.landkode, self.institusjon, self.fakultet, self.institutt,
         self.avdeling,) = self.query_1("""
        SELECT landkode, institusjon, fakultet, institutt, avdeling
        FROM [:table schema=cerebrum name=stedkode]
        WHERE ou_id = :ou_id""", locals())
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_stedkode(self, fakultet, institutt, avdeling, institusjon,
                      landkode=0):
        if institusjon is None:   # Temporary to trap old code
            raise ValueError("You must specify institusjon")
        ou_id = self.query_1("""
        SELECT ou_id FROM [:table schema=cerebrum name=stedkode]
        WHERE
          landkode = :landkode AND
          institusjon = :institusjon AND
          fakultet = :fakultet AND
          institutt = :institutt AND
          avdeling = :avdeling""", locals())
        self.find(ou_id)

    def find_sko(self, stedkode, institusjon=cereconf.DEFAULT_INSTITUSJONSNR,
                 landkode=0):
        """ find ou by full stedkode """

        if len(stedkode) != 6 or not stedkode.isdigit():
            raise ValueError("Expected a six-digit stedkode.")

        fakultet = stedkode[0:2]
        institutt = stedkode[2:4]
        avdeling = stedkode[4:6]

        self.find_stedkode(fakultet, institutt, avdeling, institusjon, landkode)

    def get_stedkoder(self, landkode=0,
                      institusjon=cereconf.DEFAULT_INSTITUSJONSNR,
                      fakultet=None, institutt=None, avdeling=None):
        sql = """
        SELECT ou_id, landkode, institusjon, fakultet, institutt, avdeling
        FROM [:table schema=cerebrum name=stedkode]
        WHERE
          landkode = :landkode AND
          institusjon = :institusjon """
        if fakultet is not None:
            sql += "AND fakultet = :fakultet "
        if institutt is not None:
            sql += "AND institutt = :institutt "
        if avdeling is not None:
            sql += "AND avdeling = :avdeling "
        return self.query(sql, locals())

    def get_stedkode(self):
        return "%02d%02d%02d" % (self.fakultet, self.institutt, self.avdeling)


class SkoCache(object):
    """ Make a mapping from ou_id to stedkode and OU name for all OUs"""

    def __init__(self, db):
        co = Factory.get('Constants')(db)
        ou = Factory.get('OU')(db)

        self._ou2sko = dict(
            (row['ou_id'], ("%02d%02d%02d" % (row['fakultet'],
                                              row['institutt'],
                                              row['avdeling'])))
            for row in ou.get_stedkoder())

        self._ou2name = dict(
            (row['entity_id'], row['name'])
            for row in ou.search_name_with_language(
                name_variant=co.ou_name_display,
                name_language=co.language_nb))

    def get_sko(self, ou_id):
        ou_id = int(ou_id)
        try:
            return self._ou2sko[ou_id]
        except:
            raise CerebrumError("Could not find stedkode for ou_id %s" %ou_id)

    def get_name(self, ou_id):
        ou_id = int(ou_id)
        try:
            return self._ou2name[ou_id]
        except:
            raise CerebrumError("Could not find OU name for ou_id %s" %ou_id)
