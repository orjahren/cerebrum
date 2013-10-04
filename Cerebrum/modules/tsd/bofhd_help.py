# -*- coding: iso-8859-1 -*-
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
"""Help text for bofhd in the TSD project."""

from Cerebrum.modules.bofhd.bofhd_core_help import group_help
from Cerebrum.modules.bofhd.bofhd_core_help import command_help
from Cerebrum.modules.bofhd.bofhd_core_help import arg_help

# Add instance specific help text:

group_help['project'] = 'Project related commands'

# The texts in command_help are automatically line-wrapped, and should
# not contain \n
command_help['user'].update({
    'user_approve':
        'Activate a user in the systems, after checking',
    'user_generate_otpkey':
        'Regenerate a One Time Password (OTP) key for an account',
    'user_set_password':
        'Set a password for a user',
})
command_help['group'].update({
    'group_add_member':
        'Add a member to a group',
    'group_remove_member':
        'Remove a member from a group',
})
command_help.setdefault('subnet', {}).update({
    'subnet_list':
        'List all subnets',
})
command_help['project'] = {
    'project_approve':
        'Approve a project with the given name',
    'project_reject':
        'Reject a project with the given name',
    'project_create':
        'Create a new project manually',
    'project_freeze':
        'Add a BofhdRequest for freezing a project',
    'project_unfreeze':
        'Thaw a project',
    'project_info':
        'Show information about a given project',
    'project_list':
        'List all projects according to given filter',
    'project_set_enddate':
        'Reset the end date for a project',
    'project_terminate':
        'Terminate a project by removing all data',
    'project_unapproved':
        'List all projects that has not been approved or rejected yet',
}

arg_help.update({
    'project_id':
        ['projectID', 'Project ID',
         'The project ID, normally on the form pXX, where XX goes from 01 to 99'],
    'project_name':
        ['projectname', 'Project name',
         'Short, unique name of the project, around 6 digits'],
    'project_longname':
        ['longname', "Project's full name",
         'The full, long name of the project'],
    'project_shortname':
        ['shortname', "Project's short name",
         'The short, descriptive name of the project'],
    'project_start_date':
        ['startdate', "Project's start date",
         'The day the project should be activated'],
    'project_end_date':
        ['enddate', "Project's end date",
         'The day the project should be ended and frozen'],
    'project_statusfilter':
        ['filter', 'Filter on project status',
                   'Not implemented yet'],
    'entity_type':
        ['entity_type', 'Entity type',
         'Possible values:\n - group\n - account\n - project'],
    'person_search_type':
        ['search_type', 'Enter person search type',
         """Possible values:
  - 'fnr'
  - 'name'
  - 'date' of birth, on format YYYY-MM-DD
  - 'stedkode' - Use project-ID"""],
})
