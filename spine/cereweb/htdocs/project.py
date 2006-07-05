# -*- coding: iso-8859-1 -*-

# Copyright 2006 University of Oslo, Norway
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

from gettext import gettext as _
from lib.Main import Main
from lib.utils import commit, commit_url, queue_message, object_link
from lib.utils import transaction_decorator, redirect, redirect_object
from lib.WorkList import remember_link
from lib.Search import get_arg_values, get_form_values, setup_searcher
from lib.templates.SearchResultTemplate import SearchResultTemplate
from lib.templates.ProjectSearchTemplate import ProjectSearchTemplate
# from lib.templates.HostViewTemplate import HostViewTemplate
# from lib.templates.HostEditTemplate import HostEditTemplate
#from lib.templates.HostCreateTemplate import HostCreateTemplate
from lib.templates.ProjectViewTemplate import ProjectViewTemplate
from lib.templates.ProjectEditTemplate import ProjectEditTemplate
#from lib.templates.ProjectCreateTemplate import ProjectCreateTemplate

def search(transaction, offset=0, **vargs):
    """Search for projects and displays result and/or searchform."""
    page = Main()
    page.title = _("Search for project(s)")
    page.setFocus("project/search")
    page.add_jscript("search.js")

    searchform = ProjectSearchTemplate()
    arguments = ['title', 'description', 'science',
                 'orderby', 'orderby_dir']
    values = get_arg_values(arguments, vargs)
    perform_search = len([i for i in values if i != ""])

    if perform_search:
        cherrypy.session['project_ls'] = values
        title, description, science, orderby, orderby_dir = values

        searcher = transaction.get_project_searcher()
        setup_searcher([searcher], orderby, orderby_dir, offset)

        if title:
            searcher.set_title_like(title)

        if description:
            searcher.set_description_like(description)

        projects = searcher.search()

        result = []

        display_hits = cherrypy.session['options'].getint('search', 'display hits')
        for project in projects[:display_hits]:
            edit = object_link(project, text='edit', method='edit', _class='actions')
            remb = remember_link(project, _class='actions')
            sci  = " " #project.get_science().get_name()
            ownr = object_link(project.get_owner())
            result.append((object_link(project), sci, ownr,
                           str(edit) + str(remb)))

        headers = [('Title', 'title'), ('Science', 'science'),
                   ('Owner', 'owner'), ('Actions', '')]

        template = SearchResultTemplate()
        table = template.view(result, headers, arguments, values,
            len(projects), display_hits, offset, searchform, 'search')

        page.content = lambda: table
    else:
        rmb_last = cherrypy.session['options'].getboolean('search', 'remember last')
        if 'project_ls' in cherrypy.session and rmb_last:
            values = cherrypy.session['project_ls']
            searchform.formvalues = get_form_values(arguments, values)
        page.content = searchform.form
    
    return page

search = transaction_decorator(search)
search.exposed = True
index = search

def view(transaction, id):
    """Creates a page with a view of the project given by id."""
    project = transaction.get_project(int(id))
    page = Main()
    page.title = _('Project %s') % project.get_title()
    page.setFocus('project/view', id)
    content = ProjectViewTemplate().view(transaction, project)
    page.content = lambda: content
    return page
view = transaction_decorator(view)
view.exposed = True

def edit(transaction, id):
    """Creates a page with the form for editing a project."""
    project = transaction.get_project(int(id))
    page = Main()
    page.title = _("Edit ") + object_link(project)
    page.setFocus("project/edit", id)

    edit = ProjectEditTemplate()
    content = edit.editProject(project,transaction)
    page.content = lambda: content
    return page
edit = transaction_decorator(edit)
edit.exposed = True

def save(transaction, id, title="", description="", submit=None, **vargs):
    """Saves the information for the project."""
    project = transaction.get_project(int(id))

    if submit == 'Cancel':
        redirect_object(project)

    
