# -*- coding: iso-8859-1 -*-
# Copyright 2002-2008 University of Oslo, Norway
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

"""API for accessing the core group structures in Cerebrum.

Note that even though the database allows us to define groups in
``group_info`` without giving the group a name in ``entity_name``, it
would probably turn out to be a bad idea if one tried to use groups in
that fashion.  Hence, this module **requires** the caller to supply a
name when constructing a Group object."""

import mx
from mx.DateTime import now

import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Entity import EntityName, EntityQuarantine, \
     EntityExternalId, EntitySpread
from Cerebrum.Utils import argument_to_sql
try:
    set()
except NameError:
    try:
        from sets import Set as set
    except ImportError:    
        from Cerebrum.extlib.sets import Set as set


def prepare_string(value):
    value = value.replace("*", "%")
    value = value.replace("?", "_")
    value = value.lower()
    return value
# end prepare_string


Entity_class = Utils.Factory.get("Entity")
class Group(EntityQuarantine, EntityExternalId, EntityName,
            EntitySpread, Entity_class):

    __read_attr__ = ('__in_db',)
    __write_attr__ = ('description', 'visibility', 'creator_id',
                      'create_date', 'expire_date', 'group_name')

    def clear(self):
        self.__super.clear()
        self.clear_class(Group)
        self.__updated = []

    def populate(self, creator_id, visibility, name,
                 description=None, create_date=None, expire_date=None,
                 parent=None):
        """Populate group instance's attributes without database access."""
        # TBD: Should this method call self.clear(), or should that be
        # the caller's responsibility?
        if parent is not None:
            self.__xerox__(parent)
        else:
            Entity_class.populate(self, self.const.entity_group)
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
        self.creator_id = creator_id
        self.visibility = int(visibility)
        self.description = description
        if not self.__in_db or create_date is not None:
            # If the previous operation was find, self.create_date will
            # have a value, while populate usually is not called with
            # a create_date argument.  This check avoids a group_mod
            # change-log entry caused when this is the only change to the entity
            self.create_date = create_date
        self.expire_date = expire_date
        # TBD: Should this live in EntityName, and not here?  If yes,
        # the attribute should probably have a more generic name than
        # "group_name".
        self.group_name = name

    def is_expired(self):
        now = mx.DateTime.now()
        if self.expire_date is None or self.expire_date >= now:
            return False
        return True

    def illegal_name(self, name):
        """Return a string with error message if groupname is illegal"""
        return False

    def write_db(self):
        """Write group instance to database.

        If this instance has a ``entity_id`` attribute (inherited from
        class Entity), this Group entity is already present in the
        Cerebrum database, and we'll use UPDATE to bring the instance
        in sync with the database.

        Otherwise, a new entity_id is generated and used to insert
        this object.

        """
        self.__super.write_db()
        if not self.__updated:
            return
        if 'group_name' in self.__updated:
            tmp = self.illegal_name(self.group_name)
            if tmp:
                raise self._db.IntegrityError, "Illegal groupname: %s" % tmp

        is_new = not self.__in_db
        if is_new:
            cols = [('entity_type', ':e_type'),
                    ('group_id', ':g_id'),
                    ('description', ':desc'),
                    ('visibility', ':visib'),
                    ('creator_id', ':creator_id')]
            # Columns that have default values through DDL.
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            if self.expire_date is not None:
                cols.append(('expire_date', ':exp_date'))
            self.execute("""
            INSERT INTO [:table schema=cerebrum name=group_info] (%(tcols)s)
            VALUES (%(binds)s)""" % {'tcols': ", ".join([x[0] for x in cols]),
                                     'binds': ", ".join([x[1] for x in cols])},
                         {'e_type': int(self.const.entity_group),
                          'g_id': self.entity_id,
                          'desc': self.description,
                          'visib': int(self.visibility),
                          'creator_id': self.creator_id,
                          # Even though the following two bind
                          # variables will only be used in the query
                          # when their values aren't None, there's no
                          # reason we should take extra steps to avoid
                          # including them here.
                          'create_date': self.create_date,
                          'exp_date': self.expire_date})
            self._db.log_change(self.entity_id, self.const.group_create, None)
            self.add_entity_name(self.const.group_namespace, self.group_name)
        else:
            cols = [('description', ':desc'),
                    ('visibility', ':visib'),
                    ('creator_id', ':creator_id')]
            if self.create_date is not None:
                cols.append(('create_date', ':create_date'))
            cols.append(('expire_date', ':exp_date'))
            self.execute("""
            UPDATE [:table schema=cerebrum name=group_info]
            SET %(defs)s
            WHERE group_id=:g_id""" % {'defs': ", ".join(
                ["%s=%s" % x for x in cols if x[0] <> 'group_id'])},
                         {'g_id': self.entity_id,
                          'desc': self.description,
                          'visib': int(self.visibility),
                          'creator_id': self.creator_id,
                          # Even though the following two bind
                          # variables will only be used in the query
                          # when their values aren't None, there's no
                          # reason we should take extra steps to avoid
                          # including them here.
                          'create_date': self.create_date,
                          'exp_date': self.expire_date})
            self._db.log_change(self.entity_id, self.const.group_mod, None)
            self.update_entity_name(self.const.group_namespace, self.group_name)
        ## EntityName.write_db(self, as_object)
        del self.__in_db
        self.__in_db = True
        self.__updated = []
        return is_new

    def delete(self):
        if self.__in_db:
            # Empty this group's set of members.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_member]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})

            # Empty this group's memberships.
            # IVR 2008-06-06 TBD: Is this really wise? I.e. should the caller
            # of delete() make sure that all memberships have been removed?
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_member]
            WHERE member_id=:g_id""", {'g_id': self.entity_id})
            
            # Remove name of group from the group namespace.
            try:
                self.delete_entity_name(self.const.group_namespace)
            except Errors.NotFoundError:
                # This group does not have a name. It is an error, but it does
                # not really matter, since the group is being removed.
                pass
            # Remove entry in table `group_info'.
            self.execute("""
            DELETE FROM [:table schema=cerebrum name=group_info]
            WHERE group_id=:g_id""", {'g_id': self.entity_id})
            self._db.log_change(self.entity_id, self.const.group_destroy, None)
        # Class Group is a core class; when its delete() method is
        # called, the underlying Entity object is also removed.
        self.__super.delete()

    ## TBD: Do we really need __eq__ methods once all Entity subclass
    ## instances properly keep track of their __updated attributes?
    def __eq__(self, other):
        assert isinstance(other, Group)
        if (self.creator_id == other.creator_id
            and self.visibility == other.visibility
            and self.group_name == other.group_name
            and self.description == other.description
            # The 'create_date' attributes should only be included in
            # the comparison of it is set in both objects.
            and (self.create_date is None
                 or other.create_date is None
                 or self.create_date == other.create_date)
            and (self.expire_date is None
                 or other.expire_date is None
                 or self.expire_date == other.expire_date)):
            # TBD: Should this compare member sets as well?
            return self.__super.__eq__(other)
        return False

    def new(self, creator, visibility, name,
            description=None, create_date=None, expire_date=None):
        """Insert a new group into the database."""
        self.populate(creator, visibility, name, description,
                      create_date, expire_date)
        self.write_db()

    def find(self, group_id):
        """Connect object to group with ``group_id`` in database."""
        self.__super.find(group_id)
        (self.description, self.visibility, self.creator_id,
         self.create_date, self.expire_date, self.group_name) = \
         self.query_1("""
        SELECT gi.description, gi.visibility, gi.creator_id,
               gi.create_date, gi.expire_date, en.entity_name
        FROM [:table schema=cerebrum name=group_info] gi
        LEFT OUTER JOIN
             [:table schema=cerebrum name=entity_name] en
        ON
          gi.group_id = en.entity_id AND
          en.value_domain = :domain
        WHERE
          gi.group_id=:g_id""",
                      {'g_id': group_id,
                       'domain': int(self.const.group_namespace)})
        try:
            del self.__in_db
        except AttributeError:
            pass
        self.__in_db = True
        self.__updated = []
    # end find

    def find_by_name(self, name, domain=None):
        """Connect object to group having ``name`` in ``domain``."""
        if domain is None:
            domain = self.const.group_namespace
        EntityName.find_by_name(self, name, domain)


    def add_member(self, member_id):
        """Add L{member_id} to this group.

        @type member_id: int
        @param member_id:
          Member (id) to add to this group. This must be an entity
          (i.e. registered in entity_info).
        """

        # First, locate the member's type (it's silly to require the client
        # code to supply it, even though it costs one lookup extra in the
        # database).
        member_type = self.query_1("""
            SELECT entity_type
            FROM [:table schema=cerebrum name=entity_info]
            WHERE entity_id = :member_id""", {"member_id": member_id})

        # Then insert the data into the table. 
        self.execute("""
        INSERT INTO [:table schema=cerebrum name=group_member]
          (group_id, member_type, member_id)
        VALUES (:g_id, :m_type, :m_id)""",
                     {'g_id': self.entity_id,
                      'm_type': int(member_type),
                      'm_id': member_id})
        self._db.log_change(member_id, self.const.group_add, self.entity_id)
    # end add_member


    def has_member(self, member_id):
        """Check whether L{member_id} is a member of this group.

        @type member_id: int
        @param member_id:
          Member (id) to check for membership.

        @rtype: L{db_row} instance or False
        @return:
          A db_row with the membership in question (from group_member) when a
          suitable membership exists; False otherwise.
        """

        # IVR 2008-06-27 TBD: Perhaps, express this in terms of search_members?
        where = ["group_id = :g_id", "member_id = :m_id"]
        binds = {'g_id': self.entity_id, 'm_id': member_id}
        try:
            return self.query_1("""
            SELECT group_id, member_type, member_id
            FROM [:table schema=cerebrum name=group_member]
            WHERE """ + " AND ".join(where), binds)
        except Errors.NotFoundError:
            return False
    # end has_member


    def remove_member(self, member_id):
        """Remove L{member_id}'s membership from this group.

        @type member_id: int
        @param member_id:
          Member (id) to remove from this group.
        """
        
        self.execute("""
        DELETE FROM [:table schema=cerebrum name=group_member]
        WHERE
          group_id=:g_id AND
          member_id=:m_id""", {'g_id': self.entity_id,
                               'm_id': member_id})
        self._db.log_change(member_id, self.clconst.group_rem, self.entity_id)
    # end remove_member
    

    def search(self, group_id=None,
               member_id=None, indirect_members=False,
               spread=None, name=None, description=None,
               filter_expired=True):
        """Search for groups satisfying various filters.

        Search **for groups** where the results are filtered by a number of
        criteria. There are many filters that can be specified; the result
        returned by this method satisfies all of the filters. Not all of the
        filters are compatible (check the documentation)

        If a filter is None, it means that it will not be applied. Calling
        this method without any arguments will return all non-expired groups
        registered in group_info.

        @type group_id: int or sequence thereof or None.
        @param group_id:
          Group ids to look for. This is the most specific filter that can be
          given. With this filter, only the groups matching the specified
          id(s) will be returned.

          This filter cannot be combined with L{member_id}.

        @type member_id: int or sequence thereof or None.
        @param member_id:
          The resulting group list will be filtered by membership - only
          groups that have members specified by member_id will be returned. If
          member_id is a sequence, then a group g1 is returned if any of the
          ids in the sequence are a member of g1.

          This filter cannot be combined with L{group_id}.

        @type indirect_members: bool
        @param indirect_members:
          This parameter controls how the L{member_id} filter is applied. When
          False, only groups where L{member_id} is a/are direct member(s) will
          be returned. When True, the membership of L{member_id} does not have
          to be direct; if group g2 is a member of group g1, and member_id m1
          is a member of g2, specifying indirect_members=True will return g1
          as well as g2. Be careful, for some situations this can drastically
          increase the result size.

          This filter makes sense only when L{member_id} is set.

        @type spread: int or SpreadCode or sequence thereof or None.
        @param spread:
          Filter the resulting group list by spread. I.e. only groups with
          specified spread(s) will be returned.
          
        @type name: basestring
        @param name:
          Filter the resulting group list by name. The name may contain SQL
          wildcard characters.

        @type description: basestring
        @param description:
          Filter the resulting group list by group description. The
          description may contain SQL wildcard characters.

        @type filter_expired: bool
        @param filter_expired:
          Filter the resulting group list by expiration date. If set, do NOT
          return groups that have expired (i.e. have group_info.expire_date in
          the past relative to the call time).

        @rtype: generator (yielding db-rows with group information)
        @return:
          A generator that yields successive db-rows matching all of the
          specified filters. Regardless of the filters, any given group_id is
          guaranteed to occur at most once in the result. The keys available
          in db_rows are the content of the group_info table and group's name
          (if it does not exist, None is assigned to the 'name' key).
        """

        # Sanity check: if indirect members is specified, then at least we
        # need one id to go on.
        if indirect_members:
            assert member_id is not None
            if isinstance(member_id, (list, tuple, set)):
                assert member_id

        # Sanity check: it is probably a bad idea to allow specifying both.
        assert not (member_id and group_id)
        
        def search_transitive_closure(member_id):
            """Return all groups where member_id is/are indirect member(s).

            @type member_id: int or sequence thereof.
            @param member_id:
              We are looking for groups where L{member_id} is/are indirect
              member(s).

            @rtype: set (of group_ids (ints))
            @result:
              Set of group_ids where member_id is/are indirect members.
            """

            result = set()
            if not isinstance(member_id, (tuple, set, list)):
                member_id = (member_id,)

            # workset contains ids of the entities that are members. in each
            # iteration we are looking for direct parents of whatever is in
            # workset.
            workset = set([int(x) for x in member_id])
            while workset:
                tmp = workset
                workset = set()
                for row in self.search(member_id=tmp,
                                       indirect_members=False,
                                       # We need to be *least* restrictive
                                       # here. Final filtering will take care
                                       # of 'expiredness'.
                                       filter_expired=False):
                    group_id = int(row["group_id"])
                    if group_id in result:
                        continue
                    result.add(group_id)
                    if group_id not in workset:
                        workset.add(group_id)

            return result
        # end search_transitive_closure

        select = """SELECT DISTINCT gi.group_id AS group_id,
                                    en.entity_name AS name,
                                    gi.description AS description,
                                    gi.visibility AS visibility,
                                    gi.creator_id AS creator_id,
                                    gi.create_date AS create_date,
                                    gi.expire_date AS expire_date
                 """
        tables = ["""[:table schema=cerebrum name=group_info] gi
                     LEFT OUTER JOIN 
                         [:table schema=cerebrum name=entity_name] en
                     ON 
                        en.entity_id = gi.group_id AND
                        en.value_domain = :vdomain
                  """,]
        where = list()
        binds = {"vdomain": int(self.const.group_namespace)}

        #
        # group_id filter
        if group_id is not None:
            where.append(argument_to_sql(group_id, "gi.group_id", binds, int))

        #
        # member_id filters (all of them)
        if member_id is not None:
            if indirect_members:
                # NB! This can be a very large group set.
                group_ids = search_transitive_closure(member_id)
                where.append(argument_to_sql(group_ids, "gi.group_id", binds, int))
            else:
                tables.append("[:table schema=cerebrum name=group_member] gm")
                where.append("(gi.group_id = gm.group_id)")
                where.append(argument_to_sql(member_id, "gm.member_id",
                                             binds, int))

        # 
        # spread filter 
        if spread is not None:
            tables.append("[:table schema=cerebrum name=entity_spread] es")
            where.append("(gi.group_id = es.entity_id)")
            where.append(argument_to_sql(spread, "es.spread", binds, int))

        #
        # name filter
        if name is not None:
            name = prepare_string(name)
            where.append("(LOWER(en.entity_name) LIKE :name)")
            binds["name"] = name

        # description filter
        if description is not None:
            description = prepare_string(description)
            where.append("(LOWER(gi.description) LIKE :description)")
            binds["description"] = description

        #
        # expired filter
        if filter_expired:
            where.append("(gi.expire_date IS NULL OR gi.expire_date > [:now])")

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        query_str = "%s FROM %s %s" % (select, ", ".join(tables), where_str)
        # IVR 2008-07-09 Originally the idea was to use a generator to avoid
        # caching all rows in memory. Unfortunately, setting fetchall=False
        # causes an ungodly amount of sql statement reparsing, which leads to
        # an abysmal perfomance penalty. 
        return self.query(query_str, binds, fetchall=True)
    # end search


    def search_members(self, group_id=None,
                       member_id=None, member_type=None, 
                       indirect_members=False,
                       member_spread=None,
                       member_filter_expired=True):
        """Search for group *MEMBERS* satisfying certain criteria.

        This method is a complement of L{search}. While L{search} returns
        *group* information, L{search_members} returns member and membership
        information. Despite the similarity in filters, the methods have
        different objectives.

        If a filter is None, it means that it will not be applied. Calling
        this method without any argument will return all non-expired members
        of groups (i.e. a huge chunk of the group_member table). Since
        group_member is one of the largest tables, do not do that, unless you
        have a good reason.

        All filters except for L{group_id} are applied to members, rather than
        groups containing members.

        The db-rows eventually returned by this method contain at least these
        keys: group_id, group_name, member_type, member_id. There may be other
        keys as well.

        @type group_id: int or a sequence thereof or None.
        @param group_id:
          Group ids to look for. Given a group_id, only memberships in the
          specified groups will be returned. This is useful for answering
          questions like 'give a list of all members of group <bla>'. See also
          L{indirect_members}.

        @type member_id: int or a sequence thereof or None.
        @param member_id:
          The result membership list will be filtered by member_ids - only the
          specified member_ids will be listed. This is useful for answering
          questions like 'give a list of memberships held by <entity_id>'. See
          also L{indirect_members}.

        @type member_type:
          int or an EntityType constant or a sequence thereof or None.
        @param member_type:
          The resulting membership list be filtered by member type - only the
          member entities of the specified type will be returned. This is
          useful for answering questions like 'give me a list of *group*
          members of group <bla>'.
          
        @type indirect_members: bool
        @param indirect_members:
          This parameter controls how 'deep' a search is performed. If True,
          we recursively expand *all* group_ids matching the rest of the
          filters.

          This filter can and must be combined either with L{group_id} or with
          L{member_id} (but not both).

          When combined with L{group_id}, the search means 'return all
          membership entries where members are direct AND indirect members of the
          specified group_id(s)'.

          When combined with L{member_id}, the search means 'return all
          membership entries where the specified members are direct AND
          indirect members'

          When False, only direct memberships are considered for all filters.

        @type member_spread: int or SpreadCode or sequence thereof or None.
        @param member_spread:
          Filter the resulting membership list by spread. I.e. only members
          with specified spread(s) will be returned.

        @type member_filter_expired: bool
        @param member_filter_expired:
          Filter the resulting membership list by expiration date. If set, do
          NOT return any rows where members have expired (i.e. have
          expire_date in the past relative to the call time).

        @rtype: generator (yielding db-rows with membership information)
        @return:
          A generator that yields successive db-rows (from group_member)
          matching all of the specified filters. These keys are available in
          each of the db_rows:
            - group_id
            - group_name
            - member_type
            - member_id
            - expire_date
            
          There *may* be other keys, but the caller cannot rely on that; nor
          can the caller assume that any other key will not be revoked at any
          time. expire_date may be None, the rest is always set.
          
          Note that if L{indirect_members} is specified, the answer may
          contain member_ids that were NOT part of the initial filters. The
          client code invoking search_members() this way should be prepared
          for such an eventuality.

          Note that if L{indirect_members} is specified, the answers may
          contain duplicate member_id keys. The client code interested in
          unique member_ids must filter the result set.
        """

        # first of all, a help function to help us look for recursive
        # memberships...
        def search_transitive_closure(start_id_set, searcher, field):
            """Collect the transitive closure of L{ids} by using the search
            strategy specified by L{searcher}.

            L{searcher} is simply a tailored self.search()-call with
            indirect_members=False.

            L{field} is the key to extract from db-rows returned by the
            L{searcher}. Occasionally we need group_id and other times
            member_id. These are the two permissible values.
            """
            result = set()
            if isinstance(start_id_set, (tuple, set, list)):
                workset = start_id_set.copy()
            else:
                workset = set((start_id_set,))

            while workset:
                new_set = set([x[field] for x in searcher(workset)])
                result.update(workset)
                workset = new_set.difference(result)

            return result
        # end search_transitive_closure

        # ... then a slight sanity check. We cannot allow a combination of
        # group and member id filters combined with indirect_members (what
        # kind of meaning can be attached to specifying all three?)
        if indirect_members:
            assert not (group_id and member_id), "Illegal API usage"
            assert group_id or member_id, "Illegal API usage"

        # ... and finally, let's generate the SQL statements for all the
        # filters.

        # IVR 2008-06-12 FIXME: Unfortunately, expire_date tests are not
        # exactly pretty, to put it mildly. There are 2 tables, and we want to
        # outer join on their union. *That* is hopeless (performancewise), so
        # we take the outer joins in turn. It is not exactly pretty either,
        # but at least it is feasible.
        #
        # Once the EntityExpire module is merged in and in production, all
        # this junk can be simplified. Before modifying the expressions, make
        # sure that the the queries actually work on multiple backends.
        select = ["tmp1.group_id AS group_id",
                  "tmp1.entity_name AS group_name",
                  "tmp1.member_type AS member_type",
                  "tmp1.member_id AS member_id",
                  "tmp1.expire1 as expire1",
                  "gi.expire_date as expire2",
                  "NULL as expire_date"]

        # We always grab the expiration dates, but we filter on them ONLY if
        # member_filter_expired is set.
        tables = [""" ( SELECT gm.*,
                           en.entity_name as entity_name,
                           ai.expire_date as expire1
                       FROM [:table schema=cerebrum name=group_member] gm
                       LEFT OUTER JOIN 
                          [:table schema=cerebrum name=entity_name] en
                       ON 
                          (en.entity_id = gm.group_id AND
                           en.value_domain = :vdomain)
                       LEFT OUTER JOIN 
                             [:table schema=cerebrum name=account_info] ai
                       ON ai.account_id = gm.member_id
                  ) AS tmp1
                  LEFT OUTER JOIN
                     [:table schema=cerebrum name=group_info] gi
                  ON gi.group_id = tmp1.member_id
                  """,]

        binds = {"vdomain": int(self.const.group_namespace)}
        where = list()

        if group_id is not None:
            if indirect_members:
                # expand group_id to include all direct and indirect *group*
                # members of the initial set of group ids. This way we get
                # *all* indirect non-group members
                group_id = search_transitive_closure(group_id,
                              lambda ids: self.search_members(group_id=ids,
                                 indirect_members=False,
                                 member_type=self.const.entity_group,
                                 member_filter_expired=False),
                              "member_id")
                indirect_members = False

            where.append(argument_to_sql(group_id, "tmp1.group_id", binds, int))

        if member_id is not None:
            if indirect_members:
                # expand member_id to include all direct and indirect *parent*
                # groups of the initial set of member ids. This way, we reach
                # *all* parent groups starting from a given set of direct
                # members. 
                member_id = search_transitive_closure(member_id,
                               lambda ids: self.search(member_id=ids,
                                  indirect_members=False,
                                  filter_expired=False),
                               "group_id")
                indirect_members = False

            where.append(argument_to_sql(member_id, "tmp1.member_id", binds, int))

        if member_type is not None:
            where.append(argument_to_sql(member_type, "tmp1.member_type",
                                         binds, int))

        if member_spread is not None:
            tables.append("""JOIN [:table schema=cerebrum name=entity_spread] es
                               ON tmp1.member_id = es.entity_id
                                  AND %s""" %
                          argument_to_sql(member_spread, "es.spread", binds, int))
            
        if member_filter_expired:
            where.append("""(tmp1.expire1 IS NULL OR tmp1.expire1 > [:now]) AND
                            (gi.expire_date IS NULL OR gi.expire_date > [:now])
                         """)

        where_str = ""
        if where:
            where_str = "WHERE " + " AND ".join(where)

        query_str = "SELECT DISTINCT %s FROM %s %s" % (", ".join(select),
                                                       " ".join(tables),
                                                       where_str)
        for entry in self.query(query_str, binds):
            # IVR 2008-07-01 FIXME: We do NOT want to expose expire ugliness
            # to the clients. They can all assume that 'expire_date' exists
            # and is set appropriately (None or a date)
            if entry["expire1"] is not None:
                entry["expire_date"] = entry["expire1"]
            elif entry["expire2"] is not None:
                entry["expire_date"] = entry["expire2"]
        
            yield entry
    # end search_members


# end class Group
