# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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

import cherrypy
import string

from gettext import gettext as _
from lib.Main import Main
from lib.utils import queue_message, redirect_object, commit
from lib.utils import object_link, transaction_decorator, commit_url
from lib.utils import rollback_url, legal_date
from lib.WorkList import remember_link
from lib.Search import SearchHandler, setup_searcher
from lib.templates.GroupSearchTemplate import GroupSearchTemplate
from lib.templates.GroupViewTemplate import GroupViewTemplate
from lib.templates.GroupEditTemplate import GroupEditTemplate
from lib.templates.GroupCreateTemplate import GroupCreateTemplate


def search(transaction, **vargs):
    """Search for groups and displays results and/or searchform."""
    page = Main()
    page.title = _("Group")
    page.setFocus("group/search")
    page.add_jscript("search.js")
    page.add_jscript("groupsearch.js")

    template = GroupSearchTemplate()
    template.title = _('group(s)')   
    handler = SearchHandler('group', template.form)
    handler.args = (
        'name', 'description', 'spread', 'gid', 'gid_end', 'gid_option'
    )
    handler.headers = (
        ('Group name', 'name'), ('Description', 'description'), ('Actions', '')
    )

    def search_method(values, offset, orderby, orderby_dir):
        name, description, spread, gid, gid_end, gid_option = values
        
        search = transaction.get_group_searcher()
        setup_searcher([search], orderby, orderby_dir, offset)
        
        if name:
            search.set_name_like(name)
        if description:
            search.set_description_like(description)
        if gid:
            if gid_option == "exact":
                search.set_posix_gid(int(gid))
            elif gid_option == "above":
                search.set_posix_gid_more_than(int(gid))
            elif gid_option == "below":
                search.set_posix_gid_less_than(int(gid))
            elif gid_option == "range":
                search.set_posix_gid_more_than(int(gid))
                if gid_end:
                    search.set_posix_gid_less_than(int(gid_end))
                
        if spread:
            group_type = transaction.get_entity_type('group')

            searcher = transaction.get_entity_spread_searcher()
            searcher.set_entity_type(group_type)

            spreadsearcher = transaction.get_spread_searcher()
            spreadsearcher.set_entity_type(group_type)
            spreadsearcher.set_name_like(spread) 
            
            searcher.add_join('spread', spreadsearcher, '')
            search.add_intersection('', searcher, 'entity')

        return search.search()

    def row(elm):
        edit = object_link(elm, text='edit', method='edit', _class='action')
        remb = remember_link(elm, _class='action')
        return object_link(elm), elm.get_description(), str(edit)+str(remb)

    groups = handler.search(search_method, **vargs)
    result = handler.get_result(groups, row)
    page.content = lambda: result

    return page
search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    """Creates a page with the view of the group with the given by."""
    group = transaction.get_group(int(id))
    page = Main()
    page.title = _('Group %s') % group.get_name()
    page.setFocus('group/view', id)
    page.add_jscript("/yui/autocomplete.js")
    page.add_jscript("search.js")
    content = GroupViewTemplate().view(transaction, group)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True
    
def add_member(transaction, id, name, type, operation):
    group = transaction.get_group(int(id))
    
    try:
        op = transaction.get_group_member_operation_type(operation)
    except:
        queue_message(_("Invalid operation '%s'.") % operation, True)
        redirect_object(group)
        return
    
    search = transaction.get_entity_name_searcher()
    search.set_name(name)
    search.set_value_domain(transaction.get_value_domain(type + '_names'))
    try:
        entity_name, = search.search()
    except ValueError, e:
        queue_message(_("Could not find %s %s") % (type, name), True)
        redirect_object(group)
        return
    
    entity = entity_name.get_entity()
    group.add_member(entity, op)
    
    msg = _("%s added as a member to group.") % object_link(entity)
    commit(transaction, group, msg=msg)
add_member = transaction_decorator(add_member)
add_member.exposed = True

def remove_member(transaction, groupid, memberid, operation):
    group = transaction.get_group(int(groupid))
    member = transaction.get_entity(int(memberid))
    operation = transaction.get_group_member_operation_type(operation)

    group_member = transaction.get_group_member(group, operation, member, member.get_type())
    group.remove_member(group_member)

    msg = _("%s removed from group.") % object_link(member)
    commit(transaction, group, msg=msg)
remove_member = transaction_decorator(remove_member)
remove_member.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a person."""
    group = transaction.get_group(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(group)
    page.setFocus("group/edit", id)

    edit = GroupEditTemplate()
    content = edit.editGroup(transaction, group)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def create(name="", expire="", description=""):
    """Creates a page with the form for creating a group."""
    page = Main()
    page.title = _("Group")
    page.setFocus("group/create")
    
    content = GroupCreateTemplate().form(name, expire, description)
    page.content = lambda :content
    return page
create.exposed = True

def save(transaction, id, name, expire="",
         description="", visi="", gid=None, submit=None):
    """Save the changes to the server."""
    group = transaction.get_group(int(id))
    c = transaction.get_commands()
    
    if submit == 'Cancel':
        redirect_object(group)
        return
    
    if expire:
        expire = c.strptime(expire, "%Y-%m-%d")
    else:
        if group.get_expire_date():
            expire = c.get_date_none()
            group.set_expire_date(expire)

    if gid is not None and group.is_posix():
        group.set_posix_gid(int(gid))

    if visi:
        visibility = transaction.get_group_visibility_type(visi)
        group.set_visibility(visibility)

    group.set_name(name)
    group.set_description(description)
    
    commit(transaction, group, msg=_("Group successfully updated."))
save = transaction_decorator(save)
save.exposed = True

def make(transaction, name, expire="", description=""):
    """Performs the creation towards the server."""
    msg=''
    if name:
        if len(name) < 3:
            msg=_("Group-name is too short( min. 3 characters).")
        elif len(name) > 8:
            msg=_("Group-name is too long(max. 8 characters).")
    else:
        msg=_("Group-name is empty.")
    if not msg and expire:
        if not legal_date( expire ):
            msg=_("Expire-date is not a legal date.")
    if not msg:
        commands = transaction.get_commands()
        group = commands.create_group(name)

        if expire:
            expire = commands.strptime(expire, "%Y-%m-%d")
            group.set_expire_date(expire)

        if description:
            group.set_description(description)
    
        commit(transaction, group, msg=_("Group successfully created."))
    else:
        rollback_url('/group/create', msg, err=True)
make = transaction_decorator(make)
make.exposed = True

def posix_promote(transaction, id):
    group = transaction.get_group(int(id))
    group.promote_posix()
    msg = _("Group successfully promoted to posix.")
    commit(transaction, group, msg=msg)
posix_promote = transaction_decorator(posix_promote)
posix_promote.exposed = True

def posix_demote(transaction, id):
    group = transaction.get_group(int(id))
    group.demote_posix()
    msg = _("Group successfully demoted from posix.")
    commit(transaction, group, msg=msg)
posix_demote = transaction_decorator(posix_demote)
posix_demote.exposed = True

def delete(transaction, id):
    """Delete the group from the server."""
    group = transaction.get_group(int(id))
    msg = _("Group '%s' successfully deleted.") % group.get_name()
    group.delete()
    commit_url(transaction, 'index', msg=msg)
delete = transaction_decorator(delete)
delete.exposed = True

def join_group(transaction, entity, name, operation):
    """Join entity into group with name 'group'."""
    entity = transaction.get_entity(int(entity))
    operation = transaction.get_group_member_operation_type(operation)

    # find the group by name.
    searcher = transaction.get_entity_name_searcher()
    searcher.set_name(name)
    searcher.set_value_domain(transaction.get_value_domain('group_names'))
    try:
        group, = searcher.search()
        group = group.get_entity()
        assert group.get_type().get_name() == 'group'
    except:
        msg = _("Group '%s' not found") % name
        queue_message(msg, True, object_link(entity))
        redirect_object(entity)
        return

    group.add_member(entity, operation)

    msg = _('Joined group %s successfully') % name
    commit(transaction, entity, msg=msg)
join_group = transaction_decorator(join_group)
join_group.exposed = True

# arch-tag: d14543c1-a7d9-4c46-8938-c22c94278c34
