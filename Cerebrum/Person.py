# -*- coding: iso-8859-1 -*-
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

"""

"""

import cereconf
from Cerebrum.Entity import \
     Entity, EntityContactInfo, EntityAddress, EntityQuarantine
from Cerebrum import Utils
from Cerebrum import Errors

class MissingOtherException(Exception): pass
class MissingSelfException(Exception): pass


class Person(EntityContactInfo, EntityAddress, EntityQuarantine, Entity):
    __read_attr__ = ('__in_db', '_affil_source', '__affil_data',
                     '_extid_source', '_extid_types')
    __write_attr__ = ('birth_date', 'gender', 'description', 'deceased')

    def clear(self):
        "Clear all attributes associating instance with a DB entity."
        self.__super.clear()
        self.clear_class(Person)
        self.__updated = []

        # TODO: The following attributes are currently not in
        #       Person.__slots__, which means they will stop working
        #       once all Entity classes have been ported to use the
        #       mark_update metaclass.
        self._external_id= {}
        # Person names:
        self._pn_affect_source = None
        self._pn_affect_variants = None
        self._name_info = {}

    def delete(self):
        # Remove person from person_external_id, person_name,
        # person_affiliation, person_affiliation_source, person_info.
        # Super will remove the entity from the mix-in classes
        for r in self.get_external_id():
            self._delete_external_id(r['source_system'], r['id_type'])
        for r in self.get_all_names():
            self._delete_name(r['source_system'], r['name_variant'])
        for r in self.get_affiliations(include_deleted=True):
            self.nuke_affiliation(r['ou_id'], r['affiliation'],
                                  r['source_system'], r['status'])
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_info]
        WHERE person_id=:e_id""", {'e_id': self.entity_id})
        self.__super.delete()

    def populate(self, birth_date, gender, description=None, deceased='F',
                 parent=None):
        """Set instance's attributes without referring to the Cerebrum DB."""
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity.populate(self, self.const.entity_person)
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
        self.birth_date = birth_date
        self.gender = gender
        self.description = description
        self.deceased = deceased

    def __eq__(self, other):
        """Define == operator for Person objects."""
        assert isinstance(other, Person)
        identical = self.__super.__eq__(other)
        if not identical:
            if cereconf.DEBUG_COMPARE:
                print "Person.super.__eq__ = %s" % identical
            return False

# The affiliation comparison stuff below seems to suffer from bitrot
# -- and with the current write_db() API, I'm not sure that we really
# *need* this functionality in __eq__().
#
##         if hasattr(self, '_affil_source'):
##             source = self._affil_source
##             for affected_affil in self._pa_affected_affiliations:
##                 other_dict = {}
##                 for t in other.get_affiliations():
##                     if t.source_system == source:
##                         # Not sure why this casting to int is required
##                         # on PostgreSQL
##                         other_dict[int(t.ou_id)] = t.status
##                 for t_ou_id, t_status in \
##                         self._pa_affiliations.get(affected_affil, []):
##                     # Not sure why this casting to int is required on
##                     # PostgreSQL
##                     t_ou_id = int(t_ou_id)
##                     if other_dict.has_key(t_ou_id):
##                         if other_dict[t_ou_id] <> t_status:
##                             if cereconf.DEBUG_COMPARE:
##                                 print "PersonAffiliation.__eq__ = %s" % False
##                             return False
##                         del other_dict[t_ou_id]
##                 if len(other_dict) != 0:
##                     if cereconf.DEBUG_COMPARE:
##                         print "PersonAffiliation.__eq__ = %s" % False
##                     return False
        if cereconf.DEBUG_COMPARE:
            print "PersonAffiliation.__eq__ = %s" % identical
        if not identical:
            return False

        if self._pn_affect_source is not None:
            for type in self._pn_affect_variants:
                other_name = other.get_name(self._pn_affect_source, type)
                my_name = self._name_info.get(type, None)
                if my_name != other_name:
                    identical = False
                    break
        if cereconf.DEBUG_COMPARE:
            print "PersonName.__eq__ = %s" % identical
        if not identical:
            return False

        identical = ((other.birth_date == self.birth_date) and
                     (other.gender == int(self.gender)) and
                     (other.description == self.description) and
                     (other.deceased == self.deceased))
        if cereconf.DEBUG_COMPARE:
            print "Person.__eq__ = %s" % identical
        return identical

    def write_db(self):
        """Sync instance with Cerebrum database.

        After an instance's attributes has been set using .populate(),
        this method syncs the instance with the Cerebrum database.

        If you want to populate instances with data found in the
        Cerebrum database, use the .find() method.

        """
        self.__super.write_db()
        if self.__updated:
            is_new = not self.__in_db
            if is_new:
                self.execute("""
                INSERT INTO [:table schema=cerebrum name=person_info]
                  (entity_type, person_id, export_id, birth_date, gender,
                   deceased, description)
                VALUES
                  (:e_type, :p_id, :exp_id, :b_date, :gender, :deceased, :desc)""",
                             {'e_type': int(self.const.entity_person),
                              'p_id': self.entity_id,
                              'exp_id': 'exp-'+str(self.entity_id),
                              'b_date': self.birth_date,
                              'gender': int(self.gender),
                              'deceased': 'F',
                              'desc': self.description})
                self._db.log_change(self.entity_id, self.const.person_create, None)
            else:
                self.execute("""
                UPDATE [:table schema=cerebrum name=person_info]
                SET export_id=:exp_id, birth_date=:b_date, gender=:gender,
                    deceased=:deceased, description=:desc
                WHERE person_id=:p_id""",
                             {'exp_id': 'exp-'+str(self.entity_id),
                              'b_date': self.birth_date,
                              'gender': int(self.gender),
                              'deceased': 'F',
                              'desc': self.description,
                              'p_id': self.entity_id})
                self._db.log_change(self.entity_id, self.const.person_update, None)
        else:
            is_new = None

        # Handle external_id
        if hasattr(self, '_extid_source'):
            types = list(self._extid_types[:])
            did_update = False
            for row in self.get_external_id(source_system=self._extid_source):
                if int(row['id_type']) not in self._extid_types:
                    continue
                tmp = self._external_id.get(int(row['id_type']), None)
                if tmp is None:
                    did_update = True
                    self._delete_external_id(self._extid_source, row['id_type'])
                elif tmp <> row['external_id']:
                    did_update = True
                    self._set_external_id(self._extid_source, row['id_type'],
                                          tmp, update=True)
                types.remove(int(row['id_type']))
            for type in types:
                if self._external_id.has_key(type):
                    did_update = True
                    self._set_external_id(self._extid_source, type,
                                          self._external_id[type])
            if did_update and is_new <> 1:
                is_new = False

        # Handle PersonAffiliations
        if hasattr(self, '_affil_source'):
            source = self._affil_source
            # db_affil is used to see if the exact affiliation exists
            # (or did exist earlier, and is marked as deleted)
            db_affil = {}
            # db_prim is used to see if a row with that primary key
            # exists.
	    db_prim = {}
            for (t_person_id, t_ou_id, t_affiliation, t_source,
                 t_status, deleted_date) in \
                 self.get_affiliations(include_deleted = True):
                if source == t_source:
                    idx = "%d:%d:%d" % (t_ou_id, t_affiliation, t_status)
                    db_affil[idx] = deleted_date
		    db_prim['%s:%s' % (t_ou_id, t_affiliation)] = idx
            pop_affil = self.__affil_data
            for prim in pop_affil.keys():
                idx = "%s:%d" % (prim, pop_affil[prim])
                if db_affil.has_key(idx):
                    # this affiliation, including status, exists in the
                    # database already, but we may have to resurrect it
                    # if it's deleted.
                    if db_affil[idx] is not None:
                        ou_id, affil, status = [int(x) for x in idx.split(":")]
                        self.add_affiliation(ou_id, affil, source, status)
                    del db_affil[idx]
                else:
                    # this may be a completely new affiliation, or just a
                    # change in status.
                    ou_id, affil, status = [int(x) for x in idx.split(":")]
                    self.add_affiliation(ou_id, affil, source, status)
                    if is_new <> 1:
                        is_new = False
                    if db_prim.has_key(prim):
                        # it was only a change of status.  make sure
                        # the loop below won't delete the affiliation.
                        del db_affil[db_prim[prim]]
            # delete all the remaining affiliations.  some of them
            # are already marked as deleted.
            for idx in db_affil.keys():
                if db_affil[idx] is None:
                    ou_id, affil, status = [int(x) for x in idx.split(":")]
                    self.delete_affiliation(ou_id, affil, source)
                    if is_new <> 1:
                        is_new = False

        # If affect_names has not been called, we don't care about
        # names
        if self._pn_affect_source is not None:
            updated_name = False
            for variant in self._pn_affect_variants:
                try:
                    if not self._compare_names(variant, self):
                        n = self._name_info.get(variant)
                        self._update_name(self._pn_affect_source, variant, self._name_info[variant])
                        is_new = False
                        updated_name = True
                except MissingOtherException:
                    if self._name_info.has_key(variant):
                        self._set_name(self._pn_affect_source, variant,
                                       self._name_info[variant])
                        if is_new <> 1:
                            is_new = False
                        updated_name = True
                except MissingSelfException:
                    self._delete_name(self._pn_affect_source, variant)
                    is_new = False
                    updated_name = True
            if updated_name:
                self._update_cached_fullname()
            # Clear affect_name() settings
            self._pn_affect_source = None
            self._pn_affect_variants = None
            self._name_info = {}

        # TODO: Handle external_id
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def new(self, birth_date, gender, description=None, deceased='F'):
        """Register a new person."""
        self.populate(birth_date, gender, description, deceased)
        self.write_db()
        self.find(self.entity_id)

    def find(self, person_id):
        """Associate the object with the person whose identifier is person_id.

        If person_id isn't an existing entity identifier,
        NotFoundError is raised.

        """
        self.__super.find(person_id)
        (self.export_id, self.birth_date, self.gender,
         self.deceased, self.description) = self.query_1(
            """SELECT export_id, birth_date, gender,
                      deceased, description
               FROM [:table schema=cerebrum name=person_info]
               WHERE person_id=:p_id""", {'p_id': person_id})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []

    def affect_external_id(self, source, *types):
        self._extid_source = source
        self._extid_types = [int(x) for x in types]

    def populate_external_id(self, source_system, id_type, external_id):
        if not hasattr(self, '_extid_source'):
            raise ValueError, \
                  "Must call affect_external_id"
        elif self._extid_source != source_system:
            raise ValueError, \
                  "Can't populate multiple `source_system`s w/o write_db()."
        self._external_id[int(id_type)] = external_id

    def _delete_external_id(self, source_system, id_type):
        self.execute("""DELETE FROM [:table schema=cerebrum name=person_external_id]
        WHERE person_id=:p_id AND id_type=:id_type AND source_system=:src""",
                     {'p_id': self.entity_id,
                      'id_type': int(id_type),
                      'src': int(source_system)})
        self._db.log_change(self.entity_id, self.const.person_ext_id_del, None,
                            change_params={'id_type': int(id_type),
                                           'src': int(source_system)})

    def _set_external_id(self, source_system, id_type, external_id,
                         update=False):
        if update:
            sql = """UPDATE [:table schema=cerebrum name=person_external_id]
            SET external_id=:ext_id
            WHERE person_id=:p_id AND id_type=:id_type AND source_system=:src"""
            self._db.log_change(self.entity_id, self.const.person_ext_id_mod, None,
                                change_params={'id_type': int(id_type),
                                               'src': int(source_system),
                                               'value': external_id})
        else:
            sql = """INSERT INTO [:table schema=cerebrum name=person_external_id]
            (person_id, id_type, source_system, external_id)
            VALUES (:p_id, :id_type, :src, :ext_id)"""
            self._db.log_change(self.entity_id, self.const.person_ext_id_add, None,
                                change_params={'id_type': int(id_type),
                                               'src': int(source_system),
                                               'value': external_id})
        self.execute(sql, {'p_id': self.entity_id,
                           'id_type': int(id_type),
                           'src': int(source_system),
                           'ext_id': external_id})

    def get_external_id(self, source_system=None, id_type=None):
        cols = {'person_id': int(self.entity_id)}
        if source_system is not None:
            cols['source_system'] = int(source_system)
        if id_type is not None:
            cols['id_type'] = int(id_type)
        return self.query("""
        SELECT id_type, source_system, external_id
        FROM [:table schema=cerebrum name=person_external_id]
        WHERE %s""" % " AND ".join(["%s=:%s" % (x, x)
                                   for x in cols.keys()]), cols)

    def list_external_ids(self, source_system=None, id_type=None):
        cols = {}
        for t in ('source_system', 'id_type'):
            if locals()[t] is not None:
                cols[t] = int(locals()[t])
        where = " AND ".join(["%s=:%s" % (x, x)
                             for x in cols.keys() if cols[x] is not None])
        if len(where) > 0:
            where = "WHERE %s" % where
        return self.query("""
        SELECT person_id, id_type, source_system, external_id
        FROM [:table schema=cerebrum name=person_external_id]
        %s""" % where, cols, fetchall=False)

    def find_persons_by_bdate(self, bdate):
        return self.query("""
        SELECT person_id FROM [:table schema=cerebrum name=person_info]
        WHERE to_date(birth_date, 'YYYY-MM-DD')=:bdate""", locals())


    def find_persons_by_name(self, name, case_sensitive=True):
        if case_sensitive:
            where = "name LIKE :name"
        else:
            name = name.lower()
            where = "LOWER(name) LIKE :name"
        return self.query("""
        SELECT DISTINCT person_id FROM [:table schema=cerebrum name=person_name]
        WHERE """ + where, locals())

    def find_by_external_id(self, id_type, external_id, source_system=None):
        binds = {'id_type': int(id_type),
                 'ext_id': external_id }
        where = ""
        if source_system is not None:
            binds['src'] = int(source_system)
            where = " AND source_system=:src"
        person_id = self.query_1("""
        SELECT DISTINCT person_id
        FROM [:table schema=cerebrum name=person_external_id]
        WHERE id_type=:id_type AND external_id=:ext_id %s""" % where, binds)
        self.find(person_id)

    def find_by_export_id(self, export_id):
        person_id = self.query_1("""
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]
        WHERE export_id=:export_id""", locals())
        self.find(person_id)

    def _compare_names(self, type, other):
        """Returns True if names are equal.

        self must be a populated object."""

        try:
            tmp = other.get_name(self._pn_affect_source, type)
            if len(tmp) == 0:
                raise KeyError
        except:
            raise MissingOtherException 
        try:
            myname = self._name_info[type]
        except:
            raise MissingSelfException
#        if isinstance(myname, unicode):
#            return unicode(tmp, 'iso8859-1') == myname
        return tmp == myname

    def _set_name(self, source_system, variant, name):
        # Class-internal use only
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=person_name]
          (person_id, name_variant, source_system, name)
        VALUES (:p_id, :n_variant, :src, :name)""",
                     {'p_id': self.entity_id,
                      'n_variant': int(variant),
                      'src': int(source_system),
                      'name': name})
        self._db.log_change(self.entity_id, self.const.person_name_add, None,
                            change_params={'src': int(source_system),
                                           'name': name,
                                           'name_variant': int(variant)})

    def _delete_name(self, source, variant):
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_name]
        WHERE
          person_id=:p_id AND
          source_system=:src AND
          name_variant=:n_variant""",
                     {'p_id': self.entity_id,
                      'src': int(source),
                      'n_variant': int(variant)})
        self._db.log_change(self.entity_id,
                            self.const.person_name_del, None,
                            change_params={'src': int(source),
                            'name_variant': int(variant)})

    def _update_name(self, source_system, variant, name):
        # Class-internal use only
        self.execute("""
        UPDATE [:table schema=cerebrum name=person_name]
        SET name=:name
        WHERE
          person_id=:p_id AND
          source_system=:src AND
          name_variant=:n_variant""",
                     {'name': name,
                      'p_id': self.entity_id,
                      'src': int(source_system),
                      'n_variant': int(variant)})
        self._db.log_change(self.entity_id, self.const.person_name_mod, None,
                            change_params={'src': int(source_system),
                                           'name': name,
                                           'name_variant': int(variant)})

    def _update_cached_fullname(self):
	"""Update the persons cached names if it has been modified.
	The  names is determined by evaluating the name variants
	by using the source system order defined by
	cereconf.SYSTEM_LOOKUP_ORDER.

	A ValueError is raised if the not any names couldn't be established.
	"""
	p = Person(self._db)
	p.find(self.entity_id)
	for ss in cereconf.SYSTEM_LOOKUP_ORDER:
	    full_name = {}
	    for n_part in ('name_first','name_last','name_full'):
		try:
		    full_name[n_part] = p.get_name(getattr(self.const, ss),
						getattr(self.const, n_part))
		except Errors.NotFoundError:
		    continue
	    if len(full_name) == 0:
		continue
	    if 'name_full' not in full_name.keys():
		full_name['name_full'] =  " ".join((full_name['name_first'],
							full_name['name_last']))
	    for attrs,new_name in full_name.items():
		try:
		    old_name = self.get_name(self.const.system_cached,
						getattr(self.const,attrs))
		    if old_name != new_name:
			self._update_name(self.const.system_cached,
					getattr(self.const,attrs),
					new_name)
		except Errors.NotFoundError:
		    self._set_name(self.const.system_cached,
					getattr(self.const,attrs),
					new_name)
            return
        raise ValueError, "Bad name for %s / %s" % (self.entity_id,
                                                    self._name_info)

    def list_person_name_codes(self):
        return self.query("""
        SELECT code, description
        FROM [:table schema=cerebrum name=person_name_code]""")

    def list_person_affiliation_codes(self):
        return self.query("""
        SELECT code, code_str, description
        FROM [:table schema=cerebrum name=person_affiliation_code]""")

    def get_name(self, source_system, variant):
        """Return the name with the given variant"""
        return self.query_1("""
        SELECT name
        FROM [:table schema=cerebrum name=person_name]
        WHERE
          person_id=:p_id AND
          name_variant=:n_variant AND
          source_system=:src""",
                            {'p_id': self.entity_id,
                             'n_variant': int(variant),
                             'src': int(source_system)})

    def get_all_names(self):
        # TBD: It may be a miss-design that we have the get_name
        # method as well.  Could use optional keyword args to this
        # method for the same effect (like get_external_id).
        return self.query("""
        SELECT *
        FROM [:table schema=cerebrum name=person_name]
        WHERE person_id=:p_id""",
                            {'p_id': self.entity_id})

    def affect_names(self, source, *variants):
        self._pn_affect_source = source
        if variants is None:
            raise NotImplementedError
        self._pn_affect_variants = variants

    def populate_name(self, variant, name):
        if (not self._pn_affect_source or
            str(variant) not in ["%s" % v for v in self._pn_affect_variants]):
            raise ValueError, "Improper API usage, must call affect_names()"
        self._name_info[variant] = name

    def populate_affiliation(self, source_system, ou_id=None,
                             affiliation=None, status=None):
        if not hasattr(self, '_affil_source'):
            self._affil_source = source_system
            self.__affil_data = {}
        elif self._affil_source <> source_system:
            raise ValueError, \
                  "Can't populate multiple `source_system`s w/o write_db()."
        if ou_id is None:
            return
        idx = "%d:%d" % (ou_id, affiliation)
        self.__affil_data[idx] = int(status)

    def get_affiliations(self, include_deleted=False):
        return self.list_affiliations(self.entity_id,
                                      include_deleted = include_deleted)

    def list_affiliations(self, person_id=None, source_system=None,
                          affiliation=None, status=None, ou_id=None,
                          include_deleted=False, fetchall = True):
        cols = {}
        for t in ('person_id', 'affiliation', 'source_system', 'status', \
								'ou_id'):
            if locals()[t] is not None:
                cols[t] = int(locals()[t])
        tests = ["%s=:%s" % (x, x) for x in cols.keys()
                 if cols[x] is not None]
        if not include_deleted:
            tests.append("(deleted_date IS NULL OR deleted_date > [:now])")
        where = " AND ".join(tests)
        if len(where) > 0:
            where = "WHERE %s" % where

        return self.query("""
        SELECT person_id, ou_id, affiliation, source_system, status,
          deleted_date
        FROM [:table schema=cerebrum name=person_affiliation_source]
        %s""" % where, cols, fetchall = fetchall)

    def add_affiliation(self, ou_id, affiliation, source, status):
        binds = {'ou_id': int(ou_id),
                 'affiliation': int(affiliation),
                 'source': int(source),
                 'status': int(status),
                 'p_id': self.entity_id,
                 }
        # If needed, add to table 'person_affiliation'.
        try:
            self.query_1("""
            SELECT 'yes'
            FROM [:table schema=cerebrum name=person_affiliation]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation""", binds)
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=person_affiliation]
              (person_id, ou_id, affiliation)
            VALUES (:p_id, :ou_id, :affiliation)""", binds)
            self._db.log_change(self.entity_id,
                                self.const.person_aff_add, None)
        try:
            self.query_1("""
            SELECT 'yes'
            FROM [:table schema=cerebrum name=person_affiliation_source]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)
            self.execute("""
            UPDATE [:table schema=cerebrum name=person_affiliation_source]
            SET status=:status, last_date=[:now], deleted_date=NULL
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation AND
              source_system=:source""", binds)
            self._db.log_change(self.entity_id,
                                self.const.person_aff_src_mod, None)
        except Errors.NotFoundError:
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=person_affiliation_source]
              (person_id, ou_id, affiliation, source_system, status)
            VALUES (:p_id, :ou_id, :affiliation, :source, :status)""",
                         binds)
            self._db.log_change(self.entity_id,
                                self.const.person_aff_src_add, None)

    def delete_affiliation(self, ou_id, affiliation, source):
        binds = {'ou_id': int(ou_id),
                 'affiliation': int(affiliation),
                 'source': int(source),
                 'p_id': self.entity_id,
                 }
        self.execute("""
        UPDATE [:table schema=cerebrum name=person_affiliation_source]
        SET deleted_date=[:now]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation AND
          source_system=:source""", binds)
        self._db.log_change(self.entity_id,
                            self.const.person_aff_src_del, None)
        # This method doesn't touch table 'person_affiliation', nor
        # does it try to do any actual deletion of rows from table
        # 'person_affiliation_source'; these tasks are in the domain
        # of various database cleanup procedures.

    def nuke_affiliation(self, ou_id, affiliation, source, status):
        p_id = self.entity_id
        # This method shouldn't be used lightly; see
        # .delete_affiliation().
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=person_affiliation_source]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation AND
          source_system=:source""", locals())
        self._db.log_change(self.entity_id,
                            self.const.person_aff_src_del, None)
        remaining_affiliations = self.query("""
        SELECT 'yes'
        FROM [:table schema=cerebrum name=person_affiliation_source]
        WHERE
          person_id=:p_id AND
          ou_id=:ou_id AND
          affiliation=:affiliation""", locals())
        if not remaining_affiliations:
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=person_affiliation]
            WHERE
              person_id=:p_id AND
              ou_id=:ou_id AND
              affiliation=:affiliation""", locals())
            self._db.log_change(self.entity_id,
                                self.const.person_aff_del, None)

    def get_accounts(self):
        acc = Utils.Factory.get('Account')(self._db)
        return acc.list_accounts_by_owner_id(self.entity_id)

    def get_primary_account(self):
        """Returns the account_id of SELF.entity_id's primary account"""
        acc = Utils.Factory.get("Account")(self._db)
        # get_account_types *must* return its results sorted
        accounts = acc.get_account_types(True, self.entity_id)
        if accounts:
            return accounts[0].account_id
        else:
            return None
        # fi
    # end get_primary_account

    def getdict_external_id2primary_account(self, id_type):
        """
        Returns a dictionary mapping all existing external ids of given
        ID_TYPE to the corresponding primary account.
        
        This is a *convenience* function. The very same thing can be
        accomplished with get_primary_account() + Account.find() and a
        suitable number of database lookups
        """

        result = dict()

        # NB! outer joins are not necessary here. Not displaying FNRs with
        # missing accounts is quite alright.
        for row in self.query("""
            SELECT
              DISTINCT pei.external_id, en.entity_name
            FROM
              [:table schema=cerebrum name=person_external_id] pei,
              [:table schema=cerebrum name=account_type] at,
              [:table schema=cerebrum name=entity_name] en
            WHERE
              pei.id_type = :id_type AND
              pei.person_id = at.person_id AND
              at.priority = (SELECT
                               min(at2.priority)
                             FROM
                               [:table schema=cerebrum name=account_type] at2
                             WHERE
                               at2.person_id = pei.person_id) AND
              at.account_id = en.entity_id
            """, {"id_type" : int(id_type)}):
            result[row.external_id] = row.entity_name
        # od

        return result
    # end getdict_external_id2primary_account


    def list_persons(self):
        """Return all person ids."""
        return self.query("""
        SELECT person_id
        FROM [:table schema=cerebrum name=person_info]""")


    def list_persons_name(self, source_system=None, name_type=None):
        str = ""
        if name_type == None:
            str = "= %d" % int(self.const.name_full)
        elif isinstance(name_type, list):
            str = "IN (%d" % int(name_type[0])
            for tuple in name_type[1:]:
                str += ", %d" % int(tuple)
            str += ")"
        else:
            str = "= %d" % int(name_type)
        if source_system:
            str += " AND source_system = %d" % int(source_system)

        return self.query("""
        SELECT DISTINCT person_id, name_variant, name
        FROM [:table schema=cerebrum name=person_name]
        WHERE name_variant %s""" % str)


    def getdict_persons_names(self, source_system=None, name_types=None):
        if name_types is None:
            name_types = self.const.name_full
        if isinstance(name_types, (list, tuple)):
            selection = "IN (%s)" % ", ".join(map(str, map(int, name_types)))
        else:
            selection = "= %d" % int(name_types)
        if source_system is not None:
            selection += " AND source_system = %d" % int(source_system)
        result = {}
        for id, variant, name in self.query("""
        SELECT DISTINCT person_id, name_variant, name
        FROM [:table schema=cerebrum name=person_name]
        WHERE name_variant %s""" % selection):
            id   = int(id)
            info = result.get(id)
            if info is None:
                result[id] = {int(variant): name}
            else:
                info[int(variant)] = name
        return result


    def list_persons_atype_extid(self, spread=None, include_quarantines=False):
        """Multiple join to increase performance on LDAP-dump.

        TBD: Maybe this should be nuked in favor of pure dumps like
             list_persons."""
        efrom = ecols = ""
        if include_quarantines:
            efrom = """
            LEFT JOIN [:table schema=cerebrum name=entity_quarantine] eq
              ON at.account_id=eq.entity_id"""
            ecols = ", eq.quarantine_type"
        if spread is not None:
            efrom += """
            JOIN [:table schema=cerebrum name=entity_spread] es
              ON pi.person_id=es.entity_id AND es.spread=:spread"""

        return self.query("""
        SELECT DISTINCT pi.person_id, pi.birth_date, at.account_id, pei.external_id,
          at.ou_id, at.affiliation %(ecols)s
	FROM
          [:table schema=cerebrum name=person_info] pi
          JOIN [:table schema=cerebrum name=account_type] at
            ON at.person_id = pi.person_id AND
               at.priority = (
                 SELECT MIN(priority)
                 FROM [:table schema=cerebrum name=account_type] at2
                 WHERE at2.person_id = pi.person_id)
	  %(efrom)s
          JOIN [:table schema=cerebrum name=person_external_id] pei
            ON pi.person_id = pei.person_id
          """ % locals(), {'spread': spread,}, fetchall=False)


    def list_extended_person(self, spread=None, include_quarantines=False,
                             include_mail=False):
        """Multiple join to increase performance on LDAP-dump."""
        efrom = ecols = ""
        if include_quarantines:
            efrom = """
            LEFT JOIN [:table schema=cerebrum name=entity_quarantine] eq
              ON at.account_id=eq.entity_id"""
            ecols = ", eq.quarantine_type"
        if spread is not None:
            efrom += """
            JOIN [:table schema=cerebrum name=entity_spread] es
              ON pi.person_id=es.entity_id AND es.spread=:spread"""
        if include_mail:
            ecols += ", ea.local_part, ed.domain"
            efrom += """
            LEFT JOIN [:table schema=cerebrum name=email_target] et
              ON at.account_id=et.entity_id AND
                 et.target_type=:em_type AND
                 et.entity_type=:et_type
            LEFT JOIN [:table schema=cerebrum name=email_primary_address] epa
              ON et.target_id=epa.target_id
            LEFT JOIN [:table schema=cerebrum name=email_address] ea
              ON epa.address_id=ea.address_id
            LEFT JOIN [:table schema=cerebrum name=email_domain] ed
              ON ea.domain_id=ed.domain_id"""

        return self.query("""
        SELECT DISTINCT pi.person_id, pi.birth_date, pei.external_id,
          pn.name, en.entity_name, eci.contact_value, aa.auth_data,
          at.ou_id, at.affiliation, pas.status, eci3.contact_value AS fax,
          pn2.name AS title, pn3.name AS personal_title, ead.address_text,
          ead.postal_number, ead.city, ead.country,
          ead1.address_text AS post_text, ead1.postal_number AS post_postal,
          ead1.city AS post_city, ead1.country AS post_country ,
          aa1.auth_data AS auth_crypt, ead1.p_o_box AS post_box %(ecols)s
        FROM
          [:table schema=cerebrum name=person_info] pi
          JOIN [:table schema=cerebrum name=account_type] at
            ON at.person_id = pi.person_id AND
               at.priority = (
                 SELECT MIN(priority)
                 FROM [:table schema=cerebrum name=account_type] at2
                 WHERE at2.person_id = pi.person_id)
          %(efrom)s
          JOIN  [:table schema=cerebrum name=person_name] pn
            ON pn.person_id = pi.person_id AND
               pn.source_system = :pn_ss AND
               pn.name_variant = :pn_nv
          JOIN [:table schema=cerebrum name=person_external_id] pei
            ON pi.person_id = pei.person_id
          LEFT JOIN [:table schema=cerebrum name=account_authentication] aa
            ON aa.account_id = at.account_id AND
               aa.method = [:get_constant name=auth_type_md5_crypt]
          LEFT JOIN [:table schema=cerebrum name=account_authentication] aa1
            ON aa1.account_id = at.account_id AND
               aa1.method = [:get_constant name=auth_type_crypt3_des]
          LEFT JOIN [:table schema=cerebrum name=person_name] pn2
            ON pn2.person_id = pi.person_id AND
               pn2.name_variant = :pn_ti
          LEFT JOIN [:table schema=cerebrum name=person_name] pn3
            ON pn3.person_id = pi.person_id AND
               pn3.name_variant = :pn_pti
          LEFT JOIN [:table schema=cerebrum name=entity_name] en
            ON en.entity_id = at.account_id AND
               en.value_domain = :vd
          LEFT JOIN [:table schema=cerebrum name=entity_contact_info] eci
             ON eci.entity_id = pi.person_id AND
                contact_type = [:get_constant name=contact_phone] AND
                eci.contact_pref = (
                  SELECT MIN(contact_pref)
                  FROM [:table schema=cerebrum name=entity_contact_info] eci2
                  WHERE eci2.entity_id = pi.person_id)
          LEFT JOIN [:table schema=cerebrum name=entity_contact_info] eci3
             ON eci3.entity_id = pi.person_id AND
                eci3.contact_type = [:get_constant name=contact_fax] AND
                eci3.contact_pref = (
                  SELECT MIN(contact_pref)
                  FROM [:table schema=cerebrum name=entity_contact_info] eci4
                  WHERE eci4.entity_id = pi.person_id)
          LEFT JOIN [:table schema=cerebrum name=person_affiliation_source] pas
             ON pi.person_id = pas.person_id AND
                at.affiliation = pas.affiliation AND
                at.ou_id = pas.ou_id AND
                pas.source_system = (
                  SELECT MIN(source_system)
                  FROM [:table schema=cerebrum name=person_affiliation_source]
                       pas2
                  WHERE pi.person_id = pas2.person_id AND
                        at.affiliation = pas2.affiliation AND
                        at.ou_id = pas2.ou_id)
          LEFT JOIN [:table schema=cerebrum name=entity_address] ead
             ON ead.entity_id=pi.person_id AND
                ead.address_type=[:get_constant name=address_street] AND
                ead.source_system=[:get_constant name=system_lt]
          LEFT JOIN [:table schema=cerebrum name=entity_address] ead1
             ON ead1.entity_id=pi.person_id AND
                ead1.address_type=[:get_constant name=address_post] AND
                ead1.source_system=[:get_constant name=system_lt]
          """ % locals(),
                          {'vd': int(self.const.account_namespace),
                           'spread': spread,
                           'pn_ss': int(self.const.system_cached),
                           'pn_nv': int(self.const.name_full),
                           'pn_ti': int(self.const.name_work_title),
                           'pn_pti': int(self.const.name_personal_title),
                           'eci_phone': int(self.const.contact_phone),
                           'et_type': int(self.const.entity_account),
                           'aa_method': int(self.const.auth_type_md5_crypt),
                           'em_type' : int(self.const.email_target_account),
                           'et_type': int(self.const.entity_account)})

