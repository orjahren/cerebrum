#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2011, 2012 University of Oslo, Norway
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
This module handles all functionality related to 'roles' and 'atoms', as used
in Cfengine-configuration.
"""
import cerebrum_path, cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory, prepare_string, argument_to_sql
from Cerebrum.Entity import EntityName

Entity_class = Factory.get("Entity")

class PolicyComponent(EntityName, Entity_class):
    """Base class for policy component, i.e. roles and atoms."""

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('component_name', 'description', 'foundation', 'create_date')

    def __init__(self, db):
        super(PolicyComponent, self).__init__(db)

    def clear(self):
        """Clear all data residing in this component instance."""
        self.__super.clear()
        self.clear_class(PolicyComponent)
        self.__updated = []

    def new(self, entity_type, component_name, description, foundation, create_date=None):
        """Insert a new policy component into the database.

        This will be called by subclasses in order to have the entity_type set
        appropriately."""
        # TODO: is this correct syntax? running self.populate() runs the
        # subclass' populate, which doesn't have entity_type as an argument
        PolicyComponent.populate(self, entity_type=entity_type, component_name=component_name,
                      description=description, foundation=foundation,
                      create_date=create_date)
        self.write_db()
        # TODO: why have find() here? find creates bugs here, and Group does not
        # have that. Don't know what's correct to do.
        #self.find(self.entity_id)

    def populate(self, entity_type, component_name, description, foundation,
                 create_date=None):
        """Populate a component instance's attributes."""
        Entity_class.populate(self, entity_type)
        # If __in_db is present, it must be True; calling populate on an
        # object where __in_db is present and False is very likely a
        # programming error.
        #
        # If __in_db is not present, we'll set it to False.
        try:
            if not self.__in_db:
                raise RuntimeError("populate() called multiple times.")
        except AttributeError:
            self.__in_db = False

        self.entity_type = entity_type
        self.component_name = component_name
        self.description = description
        self.foundation = foundation
        if not self.__in_db or create_date is not None:
            self.create_date = create_date

    def write_db(self):
        """Write component instance to database.

        If this instance has a ``entity_id`` attribute (inherited from
        class Entity), this Component entity is already present in the
        Cerebrum database, and we'll use UPDATE to bring the instance
        in sync with the database.

        Otherwise, a new entity_id is generated and used to insert
        this object.
        """
        self.__super.write_db()
        if not self.__updated:
            return

        is_new = not self.__in_db

        if is_new:
            cols = [('entity_type', ':e_type'),
                    ('component_id', ':component_id'),
                    ('description', ':description'),
                    ('foundation', ':foundation'),]
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=hostpolicy_component] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                                    {'e_type': int(self.entity_type),
                                     'component_id': self.entity_id,
                                     'description': self.description,
                                     'foundation': self.foundation,
                                     # The create_date might not be included
                                     # in the binds, but it's safe to put it
                                     # here in any case. If it's not in binds,
                                     # it's not included from here.
                                     'create_date': self.create_date})
            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.const.hostpolicy_atom_create
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.const.hostpolicy_role_create
            else:
                raise RuntimeError('Unknown entity_type=%s for entity_id=%s' %
                                   (self.entity_type, self.entity_id))
            self._db.log_change(self.entity_id, event, None)
            self.add_entity_name(self.const.hostpolicy_component_namespace,
                                 self.component_name)
        else:
            cols = [('description', ':description'),
                    ('foundation', ':foundation'),]
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            self.execute("""
            UPDATE [:table schema=cerebrum name=hostpolicy_component]
            SET %(defs)s
            WHERE component_id=:component_id""" %
                    {'defs': ", ".join(["%s=%s" % x for x in cols])},
                    {'component_id': self.entity_id,
                     'description': self.description,
                     'foundation': self.foundation,
                     'create_date': self.create_date})
                   

            # TODO: check if any in __updated before do changes. no need to
            # log then either, except if update_entity_name doesn't do that

            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.const.hostpolicy_atom_mod
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.const.hostpolicy_role_mod
            else:
                raise RuntimeError('Unknown entity_type=%s for entity_id=%s' %
                                   (self.entity_type, self.entity_id))
            self._db.log_change(self.entity_id, event, None, change_params=binds)

            if 'component_name' in self.__updated:
                self.update_entity_name(self.const.hostpolicy_component_namespace,
                                        self.component_name)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        """Deletes this policy component from DB."""
        if self.__in_db:

            # TODO: might have to delete its relations?

            self.execute("""
            DELETE FROM [:table schema=cerebrum name=hostpolicy_component]
            WHERE component_id=:component_id""", 
                                        {'component_id': self.entity_id})
            if self.entity_type == self.const.entity_hostpolicy_atom:
                event = self.const.hostpolicy_atom_delete
            elif self.entity_type == self.const.entity_hostpolicy_role:
                event = self.const.hostpolicy_role_delete
            else:
                raise RuntimeError("Unknown entity_type=%s for entity_id=%s" %
                                    (self.entity_type, self.entity_id))
            self._db.log_change(self.entity_id, event, None)
        self.__super.delete()

    def find(self, component_id):
        """Fill this component instance with data from the database."""
        self.__super.find(component_id)
        (self.description, self.foundation, self.create_date,
         self.component_name) = self.query_1(
            """SELECT 
                co.description, co.foundation, co.create_date, en.entity_name
            FROM
                [:table schema=cerebrum name=hostpolicy_component] co,
                [:table schema=cerebrum name=entity_name] en
            WHERE
                en.entity_id = co.component_id AND
                en.value_domain = :domain AND
                co.component_id = :component_id
            """, {'component_id': component_id,
                  'domain': self.const.hostpolicy_component_namespace,})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        # drop changes, since we got them from db:
        self.__updated = []

    def find_by_name(self, component_name):
        self.__super.find_by_name(component_name, self.const.hostpolicy_component_namespace)

    def add_policy(self, dns_owner_id):
        """Add this instance as a policy to a given dns_owner_id (host)."""
        # TODO: give this method another name? Doesn't make much sense now with:
        # policy.add_policy(host)

        # TODO: check that mutex constraints are fullfilled!

        # TODO: other checks before executing the change?

        self.execute("""
            INSERT INTO [:table schema=cerebrum name=hostpolicy_host_policy]
              (dns_owner_id, policy_id)
            VALUES (:dns_owner, :policy_id)""",
                {'dns_owner': int(dns_owner_id),
                 'policy_id': self.entity_id})
        self._db.log_change(self.entity_id,
                            self.const.hostpolicy_policy_add, dns_owner_id)

    def remove_policy(self, dns_owner_id):
        """Remove this instance from a given dns_owner_id (host)."""
        # TODO: give this method another name? Doesn't make much sense now with:
        # policy.add_policy(host)

        # TODO: anything to check before executing the change?
        self.execute("""
            DELETE FROM [:table schema=cerebrum name=hostpolicy_host_policy]
            WHERE 
                policy_id = :policy AND 
                dns_owner_id = :dns_owner""", {'policy': self.entity_id, 
                                               'dns_owner': dns_owner_id})
        self._db.log_change(self.entity_id,
                            self.const.hostpolicy_policy_remove, dns_owner_id)

    def search_hostpolicies(self, policy_id=None, host_name=None,
                            dns_owner_id=None, policy_name=None):
        """List out all hostpolicies together with their dns owners."""
        # TODO: do we need functionality for searching for indirect
        # relationships too?

        # TODO: make use of the input parameters

        return self.query("""
            SELECT DISTINCT
                co.entity_type AS entity_type,
                hp.policy_id AS policy_id,
                hp.dns_owner_id AS dns_owner_id,
                en1.entity_name AS dns_owner_name,
                en2.entity_name AS policy_name
            FROM
              [:table schema=cerebrum name=hostpolicy_component] co,
              [:table schema=cerebrum name=hostpolicy_host_policy] hp,
              [:table schema=cerebrum name=dns_owner] dnso,
              [:table schema=cerebrum name=entity_name] en1,
              [:table schema=cerebrum name=entity_name] en2
            WHERE 
              co.component_id = hp.policy_id AND
              hp.dns_owner_id = dnso.dns_owner_id AND
              en1.entity_id = hp.dns_owner_id AND
              en2.entity_id = hp.policy_id""")

    def search(self, entity_id=None, entity_type=None, description=None,
               foundation=None, name=None):
        """Search for components that satisfy given criteria.

        @type component_id: int or sequence of ints.
        @param component_id:
            Component ids to search for. If given, only the given components
            are returned.

        @type entity_type: int or sequence of ints.
        @param entity_type:
            If given, only components of the given type(s) are returned.

        @type description: basestring
        @param description:
            Filter the results by their description. May contain SQL wildcard
            characters.

        @type foundation: basestring
        @param foundation:
            Filter the results by their foundation variable. May contain SQL
            wildcard characters.

        @rtype: iterable db-rows
        @return:
            An iterable with db-rows with information about each component
            that matched the given criterias.
        """
        # TODO: add fetchall as an option?
        where = ['en.entity_id = co.component_id']
        binds = dict()

        if entity_type is not None:
            where.append(argument_to_sql(entity_type, 'co.entity_type',
                                         binds, int))
        if description is not None:
            where.append('(LOWER(co.description) LIKE :description)')
            binds['description'] = prepare_string(description)
        if foundation is not None:
            where.append('(LOWER(co.foundation) LIKE :foundation)')
            binds['foundation'] = prepare_string(foundation)
        if name is not None:
            where.append('(LOWER(en.entity_name) LIKE :name)')
            binds['name'] = prepare_string(name)
        return self.query("""
            SELECT DISTINCT co.entity_type AS entity_type,
                            co.component_id AS component_id,
                            co.description AS description,
                            co.foundation AS foundation,
                            co.create_date AS create_date,
                            en.entity_name AS name
            FROM 
              [:table schema=cerebrum name=hostpolicy_component] co,
              [:table schema=cerebrum name=entity_name] en
            WHERE
              %(where)s
            """ % {'where': ' AND '.join(where)}, binds)

class Role(PolicyComponent):
    def new(self, component_name, description, foundation, create_date=None):
        self.__super.new(self.const.entity_hostpolicy_role, component_name,
                     description, foundation, create_date)

    def populate(self, component_name, description, foundation,
                 create_date=None):
        self.__super.populate(self.const.entity_hostpolicy_role, component_name,
                              description, foundation, create_date)

    def find_by_name(self, component_name):
        self.__super.find_by_name(component_name)
        # TODO: this does not work atomically - could create problems when
        # working with threads!
        if self.entity_type != self.const.entity_hostpolicy_role:
            self.clear()
            raise Errors.NotFoundError('Could not find role with name: %s' %
                                       component_name)

    def add_relationship(self, relationship_code, target_id):
        """Add a relationship of given type between this role and a target
        component (atom or role).

        @type relationship_code: int
        @param relationship_code:
            The relationship constant that defines the kind of relationship the
            source and target will have.
        """
        self.execute("""
            INSERT INTO [:table schema=cerebrum name=hostpolicy_relationship]
              (source_policy, relationship, target_policy)
            VALUES (:source, :rel, :target)""",
                {'source': self.entity_id,
                 'rel': int(relationship_code),
                 'target': target_id})
        self._db.log_change(self.entity_id,
                            self.const.hostpolicy_relationship_add, target_id)

    def remove_relationship(self, relationship_code, target_id):
        """Remove a relationship of given type between this role and a target
        component (atom or role)."""
        # TODO: check that the relationship actually exists? Group.remove_member
        # doesn't do that, so don't know what's correcty for the API.
        self.execute("""
            DELETE FROM [:table schema=cerebrum name=hostpolicy_relationship]
            WHERE 
                source_policy = :source AND 
                target_policy = :target AND
                relationship  = :rel""", {'source': self.entity_id, 
                                          'target': target_id,
                                          'rel': relationship_code})
        self._db.log_change(self.entity_id,
                            self.const.hostpolicy_relationship_remove, target_id)

    def search(self, *args, **kwargs):
        """Sarch for roles by different criterias."""
        return self.__super.search(entity_type=self.const.entity_hostpolicy_role,
                                   *args, **kwargs)

    # TODO: should search_relations be moved to PolicyComponent? Roles have
    # relations, but Atoms could be target of a relation, but should they "know"
    # about this?
    def search_relations(self, source_id=None, target_id=None,
                         relationship_code=None):
        """Search for role relations by different criterias.

        @type source_id: int or sequence of ints
        @param source_id:
            If given, all relations that has the given components as source
            are returned.

        @type target_id: int or sequence of ints
        @param target_id:
            If given, all relations that has the given components as targets
            are returned.

        @type relationship_code: int or sequence of ints
        @param relationship_code:
            If given, only relations of the given type(s) are returned.

        @rtype: iterable with db-rows
        @return:
            An iterator with db-rows with data about each relationship.
        """
        binds = dict()
        tables = ['[:table schema=cerebrum name=hostpolicy_component] co1',
                # TODO: do we really need data from hostpolicy_component?
                  '[:table schema=cerebrum name=hostpolicy_component] co2',
                  '[:table schema=cerebrum name=entity_name] en1',
                  '[:table schema=cerebrum name=entity_name] en2',
                  '[:table schema=cerebrum name=hostpolicy_relationship] re',
                  '[:table schema=cerebrum name=hostpolicy_relationship_code] rc']
        where = ['(re.relationship = rc.code)',
                 '(en1.entity_id = re.source_policy)',
                 '(en2.entity_id = re.target_policy)',
                 '(co1.component_id = re.source_policy)',
                 '(co2.component_id = re.target_policy)']
        if source_id is not None:
            where.append(argument_to_sql(source_id, 're.source_policy', binds, int))
        if target_id is not None:
            where.append(argument_to_sql(target_id, 're.target_policy', binds, int))
        if relationship_code is not None:
            where.append(argument_to_sql(relationship_code, 're.relationship', binds, int))
        return self.query("""
            SELECT DISTINCT co1.entity_type AS source_entity_type,
                            co2.entity_type AS target_entity_type,
                            en1.entity_name AS source_name,
                            en2.entity_name AS target_name,
                            rc.code_str AS relationship_str,
                            re.source_policy AS source_id,
                            re.target_policy AS target_id,
                            re.relationship AS relationship_id
            FROM %(tables)s
            WHERE %(where)s
            """ % {'where': ' AND '.join(where),
                   'tables': ', '.join(tables)},
                binds)

class Atom(PolicyComponent):
    def new(self, component_name, description, foundation, create_date=None):
        self.__super.new(self.const.entity_hostpolicy_atom, component_name,
                     description, foundation, create_date)

    def populate(self, component_name, description, foundation,
                 create_date=None):
        self.__super.populate(self.const.entity_hostpolicy_atom, component_name,
                              description, foundation, create_date)

    def find_by_name(self, component_name):
        self.__super.find_by_name(component_name)
        # TODO: this does not work atomically - could create problems when
        # working with threads!
        if self.entity_type != self.const.entity_hostpolicy_atom:
            self.clear()
            raise Errors.NotFoundError('Could not find atom with name: %s' %
                                       component_name)

    def search(self, *args, **kwargs):
        """Search for atoms by different criterias."""
        return self.__super.search(entity_type=self.const.entity_hostpolicy_atom,
                                   *args, **kwargs)

