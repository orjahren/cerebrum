# -*- coding: iso-8859-1 -*-
# Copyright 2003 University of Oslo, Norway
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

"""

"""

import cereconf
from Cerebrum.Entity import Entity


class Disk(Entity):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('host_id', 'path', 'description')

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        self.clear_class(Disk)
        self.__updated = []

    def populate(self, host_id, path, description, parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_disk)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.host_id = host_id
        self.path = path
        self.description = description

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=disk_info]
              (entity_type, host_id, disk_id, path, description)
            VALUES (:e_type, :host_id, :disk_id, :path, :description)
                    """,
                         {'e_type': int(self.const.entity_disk),
                          'host_id': self.host_id,
                          'disk_id': self.entity_id,
                          'path': self.path,
                          'description': self.description})
            self._db.log_change(self.entity_id, self.const.disk_add, None)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=disk_info]
            SET path=:path, description=:description
            WHERE disk_id=:disk_id""",
                         {'path': self.path,
                          'disk_id': self.entity_id,
                          'description': self.description})
            self._db.log_change(self.entity_id, self.const.disk_mod, None)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def __eq__(self, other):
        """Overide the == test for objects."""
        assert isinstance(other, OU)
        if not self.__super.__eq__(other):
            return False
        identical = ((other.path == self.path) and
                     (other.description == self.description))
        if cereconf.DEBUG_COMPARE:
            print "Disk.__eq__ = %s" % identical
        return identical

    def find(self, disk_id):
        """Associate the object with the Disk whose identifier is disk_id.

        If disk_id isn't an existing Disk identifier,
        NotFoundError is raised."""
        self.__super.find(disk_id)
        (self.host_id, self.path, self.description) = self.query_1("""
        SELECT host_id, path, description
        FROM [:table schema=cerebrum name=disk_info]
        WHERE disk_id=:disk_id""", {'disk_id': disk_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_path(self, path, host_id=None):
        """Attempt to uniquely identify the disk."""
        host_qry = ""
        if host_id is not None:
            host_qry = "AND host_id=:host_id"
        entity_id = self.query_1("""
        SELECT disk_id
        FROM [:table schema=cerebrum name=disk_info]
        WHERE path=:path %s""" % host_qry,
                                 {'path': path,
                                  'host_id': host_id})
        self.find(entity_id)

    def list(self):
        # Note: This syntax requires Oracle >= 9
        return self.query("""
        SELECT count(account_id), di.disk_id, di.host_id, di.path
        FROM [:table schema=cerebrum name=disk_info] di
          LEFT JOIN [:table schema=cerebrum name=account_info] ai
            ON di.disk_id=ai.disk_id
        GROUP BY di.disk_id, di.host_id, di.path""")

class Host(Entity):
    __read_attr__ = ('__in_db',)
    __write_attr__ = ('name', 'description')

    def clear(self):
        """Clear all attributes associating instance with a DB entity."""
        self.__super.clear()
        self.clear_class(Host)
        self.__updated = []

    def populate(self, name, description, parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_host)
        # If __in_db is present, it must be True; calling populate on
        # an object where __in_db is present and False is very likely
        # a programming error.
        #
        # If __in_db in not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError, "populate() called multiple times."
        except AttributeError:
            self.__in_db = False
        self.name = name
        self.description = description

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method."""
        self.__super.write_db()
        if not self.__updated:
            return
        is_new = not self.__in_db
        if is_new:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=host_info]
              (entity_type, host_id, name, description)
            VALUES (:e_type, :host_id, :name, :description)
                    """,
                         {'e_type': int(self.const.entity_host),
                          'host_id': self.entity_id,
                          'name': self.name,
                          'description': self.description})
            self._db.log_change(self.entity_id, self.const.host_add, None)
        else:
            self.execute("""
            UPDATE [:table schema=cerebrum name=host_info]
            SET name=:name, description=:description
            WHERE host_id=:host_id""",
                         {'name': self.name,
                          'host_id': self.entity_id,
                          'description': self.description})
            self._db.log_change(self.entity_id, self.const.host_mod, None)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def __eq__(self, other):
        """Overide the == test for objects."""
        assert isinstance(other, OU)
        if not self.__super.__eq__(other):
            return False
        identical = ((other.name == self.name) and
                     (other.description == self.description))
        if cereconf.DEBUG_COMPARE:
            print "Host.__eq__ = %s" % identical
        return identical

    def find(self, host_id):
        """Associate the object with the Host whose identifier is host_id.

        If host_id isn't an existing Host identifier,
        NotFoundError is raised."""
        self.__super.find(host_id)
        (self.host_id, self.name, self.description) = self.query_1("""
        SELECT host_id, name, description
        FROM [:table schema=cerebrum name=host_info]
        WHERE host_id=:host_id""", {'host_id': host_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def find_by_name(self, name):
        """Associate the object with the Host whose name is name.

        If name isn't an existing Host identifier,
        NotFoundError is raised."""
        entity_id = self.query_1("""
        SELECT host_id
        FROM [:table schema=cerebrum name=host_info]
        WHERE name=:name""", {'name': name})
        self.find(entity_id)

