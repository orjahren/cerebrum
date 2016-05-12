#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

"""
Module used by publisher to convert 'raw' events into exportable messages.

General idea: The event publisher creates a dict containing the message.
Then the filter_message is called with the required arguments.

If filter_message returns some value that is boolean true, it is used as the
message, otherwise it is discarded.
"""

from collections import OrderedDict
from Cerebrum.Utils import Factory
import re

"""
General fixes:
categories:
    ac_type -> ?
    ad_attr -> ad_attribute
    disk -> ?
    disk_quota -> ?
    dlgroup -> distribution_group
    e_account -> account
    e_group -> group
    email_address -> email
    email_forward -> email
    email_primary_address -> email
    email_quota -> email
    email_scan -> email
    email_sfilter -> email
    email_tfilter -> email
    email_vacation -> email
    entity_addr -> address
    entity_cinfo -> contact_info
    entity_name -> ident?
    entity_note -> note
    guest -> wlan_account
    homedir -> ?
    ou -> orgunit
    posix -> account, group
    quarantine -> ?
    spread -> ?
    trait -> ?

    tidy change types:
        use verbs
        * add
        * remove
        * set
        * unset
        * update

"""


def filter_message(msg, subject, dest, change_type, db):
    """Filter a message, converting the data on the way.

    :param msg: Message object
    :type msg: dict

    :param subject: Subject
    :type subject: Entity

    :param dest: Object/destination
    :type dest: Entity or None

    :param db: Database
    :type db: Database

    :param change_type: ChangeType
    :type change_type: Code ChangeType
    """
    category, change = msg['category'], msg['change']
    for key in _dispatch.keys():
        if re.match('^%s$' % key,
                    '%s:%s' % (category, change) if change else category):
            msg = _dispatch.get(key)(
                msg, subject, dest, change_type, db)
    return msg


# Holds the mapping of names, as registred by dispatch().
def _identity(msg, *args):
    return msg
_dispatch = OrderedDict()


def dispatch(cat, change=None):
    """Wrapper registers transform-functions to change-types."""
    def _fix(fn):
        _dispatch['%s:%s' % (cat, change) if change else '%s:.*' % cat] = fn
        return fn
    return _fix


def _stringify_code(msg, field, code_converter):
    """Convert a code to a string.

    :type msg: dict
    :param msg: The message to convert
    :type field: basestring
    :param field: The key whose value we'll convert.
    :type code_converter: _CerebrumCode
    :param code_converter: The converter to use for the code.
    """
    if msg.get('data', {}).get(field):
        msg['data'][field] = str(code_converter(msg['data'][field]))


def _rename_key(msg, field, new_field):
    """Rename a key in the metadata.

    :type msg: dict
    :param msg: The message to convert
    :type field: basestring
    :param field: The key whose key we'll change.
    :type new_key: basestring
    :param new_key: The key we'll change to
    """
    if msg.get('data', {}).get(field):
        msg['data'][new_field] = msg['data'][field]
        del msg['data'][field]


# Fix change, category and meta_object_type for all events (cleaning up
# existing cruft).
@dispatch('.*_.*')
def fix_cat_for_entities(msg, *args):
    if '_' in msg['category']:
        (msg['category'], msg['meta_object_type']) = msg['category'].split(
            '_', 1)
    return msg


@dispatch('.*', '.*_.*')
def fix_change_for_all(msg, *args):
    if '_' in msg['change']:
        (msg['meta_object_type'], msg['change']) = msg['change'].rsplit('_', 1)
    return msg

"""

    # Account changes

    account_create = _ChangeTypeCode(
        'e_account', 'create', 'created %(subject)s')
    account_delete = _ChangeTypeCode(
        'e_account', 'delete', 'deleted %(subject)s')
    account_mod = _ChangeTypeCode(
        'e_account', 'mod', 'modified %(subject)s',
        ("new owner=%(entity:owner_id)s",
         "new expire_date=%(date:expire_date)s"))
    account_password = _ChangeTypeCode(
        'e_account', 'password', 'new password for %(subject)s')
    account_password_token = _ChangeTypeCode(
        'e_account', 'passwordtoken', 'password token sent for %(subject)s',
        ('phone_to=%(string:phone_to)s',))
    account_destroy = _ChangeTypeCode(
        'e_account', 'destroy', 'destroyed %(subject)s')
    # TODO: account_move is obsolete, remove it
    account_move = _ChangeTypeCode(
        'e_account', 'move', '%(subject)s moved',
        ('from=%(string:old_host)s:%(string:old_disk)s,'
            + 'to=%(string:new_host)s:%(string:new_disk)s,',))



    account_home_updated = _ChangeTypeCode(
        'e_account', 'home_update', 'home updated for %(subject)s',
        ('old=%(homedir:old_homedir_id)s',
         'old_home=%(string:old_home)s',
         'old_disk_id=%(disk:old_disk_id)s',
         'spread=%(spread_code:spread)s'))
    account_home_added = _ChangeTypeCode(
        'e_account', 'home_added', 'home added for %(subject)s',
        ('spread=%(spread_code:spread)s', 'home=%(string:home)s'))
    account_home_removed = _ChangeTypeCode(
        'e_account', 'home_removed', 'home removed for %(subject)s',
        ('spread=%(spread_code:spread)s', 'home=%(string:home)s'))
"""


@dispatch('e_account')
def account(msg, *args):
    """
    Change e_account to account
    """
    msg['category'] = 'account'
    return msg


@dispatch('e_account', 'password')
def account_password(msg, *args):
    """Remove actual password"""
    del msg['data']['password']
    return msg


@dispatch('e_account', 'password_token')
def password_token(*args):
    return None


@dispatch('e_account', 'create')
def account_create(msg, *args):
    """account create (by write_db)
    attributes other than _auth_info, _acc_affect_auth_types, password
    """
    # TODO: Fix docstring
    return msg


@dispatch('e_account', 'mod')
def account_mod(msg, *kws):
    """account mod (by write_db)
    attributes that have been changed
    """
    return msg


@dispatch('spread')
def spread(msg, *args):
    msg['category'] = 'context'
    return msg

"""
    account_type_add = _ChangeTypeCode(
        'ac_type', 'add', 'ac_type add for account %(subject)s',
        ('ou=%(ou:ou_id)s, aff=%(affiliation:affiliation)s,
        pri=%(int:priority)s',))
    account_type_mod = _ChangeTypeCode(
        'ac_type', 'mod', 'ac_type mod for account %(subject)s',
        ('old_pri=%(int:old_pri)s, old_pri=%(int:new_pri)s',))
    account_type_del = _ChangeTypeCode(
        'ac_type', 'del', 'ac_type del for account %(subject)s',
        ('ou=%(ou:ou_id)s, aff=%(affiliation:affiliation)s',))

"""


def _ou(msg, db):
    ou = msg['data'].get('ou_id')
    if ou:
        o = Factory.get("OU")(db)
        o.find(ou)
        msg['data']['ou'] = str(o)


@dispatch('ac_type')
def account_type(msg, *args):
    msg['category'] = 'account_type'
    _ou(msg, args[-1])
    return msg

"""
    # AccountHomedir changes

    homedir_remove = _ChangeTypeCode(
        'homedir', 'del', 'homedir del for account %(subject)s',
        ('id=%(int:homedir_id)s',))
    homedir_add = _ChangeTypeCode(
        'homedir', 'add', 'homedir add for account %(subject)s',
        ('id=%(int:homedir_id)s', 'home=%(string:home)s'))
    homedir_update = _ChangeTypeCode(
        'homedir', 'update', 'homedir update for account %(subject)s',
        ('id=%(int:homedir_id)s',
         'home=%(string:home)s', 'status=%(home_status:status)s'))

    # Disk changes

    disk_add = _ChangeTypeCode('disk', 'add', 'new disk %(subject)s')
    disk_mod = _ChangeTypeCode('disk', 'mod', 'update disk %(subject)s')
    disk_del = _ChangeTypeCode('disk', 'del', "delete disk %(subject)s")

    # Host changes

    host_add = _ChangeTypeCode('host', 'add', 'new host %(subject)s')
    host_mod = _ChangeTypeCode('host', 'mod', 'update host %(subject)s')
    host_del = _ChangeTypeCode('host', 'del', 'del host %(subject)s')

    # OU changes

    ou_create = _ChangeTypeCode(
        'ou', 'create', 'created OU %(subject)s')
    ou_mod = _ChangeTypeCode(
        'ou', 'mod', 'modified OU %(subject)s')
    ou_unset_parent = _ChangeTypeCode(
        'ou', 'unset_parent', 'parent for %(subject)s unset',
        ('perspective=%(int:perspective)s',))
    ou_set_parent = _ChangeTypeCode(
        'ou', 'set_parent', 'parent for %(subject)s set to %(dest)s',
        ('perspective=%(int:perspective)s',))
    ou_del = _ChangeTypeCode(
        'ou', 'del', 'deleted OU %(subject)s')

"""


# suppress entity, the usually follow something else
@dispatch('entity')
def entity(*args):
    return None


# change entity_name to identifier, as this is easier understood
# (not conflicting with other names)
# TODO: map to account, group, etc?
@dispatch('entity_name')
def entity_name(msg, *args):
    msg['meta_object_type'] = 'identifier'
    co = Factory.get('Constants')(args[-1])
    _stringify_code(msg, 'name_variant', co.EntityNameCode)
    _stringify_code(msg, 'name_language', co.LanguageCode)
    return msg


@dispatch('entity_cinfo')
def entity_cinfo(msg, *args):
    """Convert address type and source constants."""
    msg['meta_object_type'] = 'contact_info'
    co = Factory.get('Constants')(args[-1])
    _stringify_code(msg, 'type', co.ContactInfo)
    _stringify_code(msg, 'src', co.AuthoritativeSystem)
    return msg


@dispatch('entity_addr')
def entity_addr(msg, *args):
    msg['meta_object_type'] = 'address'
    return msg


@dispatch('entity_note')
def entity_note(msg, *args):
    # TODO: Should we get the actual note, and send it?
    return msg


@dispatch('entity', 'ext_id.*')
def entity_external_id(msg, *args):
    msg['meta_object_type'] = 'external-id'
    co = Factory.get('Constants')(args[-1])
    _stringify_code(msg, 'src', co.AuthoritativeSystem)
    _stringify_code(msg, 'id_type', co.EntityExternalId)
    return msg


@dispatch('person')
def person(msg, subject, dest, change_type, db):
    return msg


@dispatch('person', 'name_.*')
def person_name_ops(msg, *args):
    co = Factory.get('Constants')(args[-1])
    _stringify_code(msg, 'name_variant', co.PersonName)
    _stringify_code(msg, 'src', co.AuthoritativeSystem)
    return msg


@dispatch('person', 'aff_(add|mod|del)')
def person_affiliation_ops(msg, *args):
    msg['meta_object_type'] = 'affiliation'
    return msg


@dispatch('person', 'aff_src.*')
def person_affiliation_source_ops(msg, *args):
    msg['meta_object_type'] = 'affiliation-source'
    return msg


@dispatch('quarantine')
def quarantine(msg, *args):
    # TODO: What should we call quarantines?
    co = Factory.get('Constants')(args[-1])
    _stringify_code(msg, 'q_type', co.Quarantine)
    _rename_key(msg, 'q_type', 'type')
    return msg

# TODO: What to translate to?

"""
    # TBD: Is it correct to have posix_demote in this module?

    posix_demote = _ChangeTypeCode(
        'posix', 'demote', 'demote posix %(subject)s',
        ('uid=%(int:uid)s, gid=%(int:gid)s',))
    posix_group_demote = _ChangeTypeCode(
        'posix', 'group-demote', 'group demote posix %(subject)s',
        ('gid=%(int:gid)s',))
    posix_promote = _ChangeTypeCode(
        'posix', 'promote', 'promote posix %(subject)s',
        ('uid=%(int:uid)s, gid=%(int:gid)s',))
    posix_group_promote = _ChangeTypeCode(
        'posix', 'group-promote', 'group promote posix %(subject)s',
        ('gid=%(int:gid)s',))

    # Guest functionality

    guest_create = _ChangeTypeCode(
        'guest', 'create', 'created guest %(dest)s',
        ('mobile=%(string:mobile)s, name=%(string:name)s,
        owner_id=%(string:owner)s',))


    # AD functionality
    ad_attr_add = CLConstants._ChangeTypeCode(
        'ad_attr', 'add', 'added AD-attribute for %(subject)s',
        ('spread=%(string:spread)s, attr=%(string:attr)s,
        value=%(string:value)s',))

    ad_attr_del = CLConstants._ChangeTypeCode(
        'ad_attr', 'del', 'removed AD-attribute for %(subject)s',
        ('spread=%(string:spread)s, attr=%(string:attr)s',))


"""


"""
   # Group changes

    group_add = _ChangeTypeCode(
        'e_group', 'add', 'added %(subject)s to %(dest)s')
    group_rem = _ChangeTypeCode(
        'e_group', 'rem', 'removed %(subject)s from %(dest)s')
    group_create = _ChangeTypeCode(
        'e_group', 'create', 'created %(subject)s')
    group_mod = _ChangeTypeCode(
        'e_group', 'mod', 'modified %(subject)s')
    group_destroy = _ChangeTypeCode(
        'e_group', 'destroy', 'destroyed %(subject)s')
"""


@dispatch('e_group')
def group(msg, *rest):
    msg['category'] = 'group'
    del msg['meta_object_type']
    return msg


@dispatch('entity_name')
def group_name(msg, *args):
    if msg.get('subjecttype') == 'group' and msg.get('data').get('domain'):
        del msg['data']['domain']
    return msg


@dispatch('ad_attr')
def ad_attr(msg, *rest):
    msg['category'] = 'ad_attribute'
    return msg


@dispatch('dlgroup')
def dlgroup(msg, *rest):
    """distribution group roomlist"""
    msg['category'] = 'distribution_group'
    return msg
