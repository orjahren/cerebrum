# -*- coding: iso-8859-1 -*-

# Copyright 2005 University of Oslo, Norway
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

import sets
from gettext import gettext as _
from Cereweb.Main import Main
from Cereweb.utils import url, queue_message, redirect, redirect_object
from Cereweb.utils import transaction_decorator, object_link
from Cereweb.WorkList import remember_link
from Cereweb.templates.EmailDomain import EmailDomain
from Cereweb.templates.EmailTarget import EmailTarget
from Cereweb.SpineIDL.Errors import NotFoundError



def index(req):
    # Could also let people search by email address etc
    return redirect(req, url('emaildomain/list'))

def view(req, transaction, id):
    target = transaction.get_email_target(int(id))
    page = Main(req)
    page.title = _("Email target") 
    try:
        primary = target.get_primary_address()
    except NotFoundError:
        pass    
    else:
        page.title += " " + primary.full_address()    
    page.setFocus("email/target/view", id)
    template = EmailTarget()

    if not target.get_addresses() and target.get_entity():
        #FIXME: Should use Cerebrum methods to suggest email address    
        suggestion = target.get_entity().get_name()
    else:
        suggestion = ""   
    
    content = template.view_target(transaction, target, suggestion)
    page.content = lambda: content
    return page
view = transaction_decorator(view)


def edit(req, transaction, id):
    target = transaction.get_email_target(int(id))
    page = Main(req)
    page.title = _("Email target") 
    try:
        primary = target.get_primary_address()
    except NotFoundError:
        pass    
    else:
        page.title += " " + primary.full_address()    
    page.setFocus("email/target/edit", id)
    template = EmailTarget()
    content = template.edit_target(transaction, target)
    page.content = lambda: content
    return page
    
    
edit = transaction_decorator(edit)

def create(req, transaction, target_type, entity=None):
    target_type = transaction.get_email_target_type(target_type)    
    cmd = transaction.get_commands()
    target = cmd.create_email_target(target_type)
    msg = _("Created email target of type %s") % target_type.get_name()
    queue_message(req, msg)
    if entity:
        entity = transaction.get_entity(int(entity))
        target.set_entity(entity) 
        if entity.get_type().get_name() == "account" and entity.is_posix():
            target.set_using(entity)
        queue_message(req, _("Set target entity to %s") % object_link(entity))
    redirect_object(req, target, "edit")
    transaction.commit() 
create = transaction_decorator(create)

def save(req, transaction, id, target_type, using=None, alias=""):
    target_type = transaction.get_email_target_type(target_type)    
    cmd = transaction.get_commands()
    target = transaction.get_email_target(int(id))
    if target.get_type() != target_type:
        target.set_type(target_type)
    old_using = target.get_using()
    if old_using is not None:
        old_using = old_using.get_name()
    if old_using != using:
        if using is not None:
            cmd = transaction.get_commands()
            using = cmd.get_account_by_name(using)
        target.set_using(using)
    if target.get_alias() != alias:
        target.set_alias(alias)    
    redirect_object(req, target)
    transaction.commit() 
     
save = transaction_decorator(save)

def delete(req, transaction, id):
    target = transaction.get_email_target(int(id))
    entity = target.get_entity()
    if entity:
        redirect_object(req, entity)
    else:
        redirect(req, url('/'))
    target.delete()
    msg = _("Deleted email target")
    transaction.commit()
    queue_message(req, msg)
    
delete = transaction_decorator(delete)


def add_address(req, transaction, local_part, domain, target):
    target = transaction.get_email_target(int(target))
    domain = transaction.get_email_domain(int(domain))
    cmd = transaction.get_commands()
    addr = cmd.create_email_address(local_part, domain, target)
    queue_message(req, _("Added email address %s") % addr.full_address())

    if len(target.get_addresses()) == 1:
        # First address    
        addr.set_as_primary()
        queue_message(req, _("Set %s as primary address of target") % addr.full_address())
    
    redirect_object(req, target)
    transaction.commit()
    
add_address = transaction_decorator(add_address)    


def set_primary(req, transaction, id, address=None):
    target = transaction.get_email_target(int(id))
    if address:
        address = transaction.get_email_address(int(address))
    # else: set to none, ie. unset primary    
    target.set_primary_address(address)    
    if address is None:
        queue_message(req, _("Unset primary email address"))
    else:    
        queue_message(req, _("Set %s as primary email address") % address.full_address())
    redirect_object(req, target)
    transaction.commit()
set_primary = transaction_decorator(set_primary)        

def remove_address(req, transaction, id, address):
    target = transaction.get_email_target(int(id))
    address = transaction.get_email_address(int(address))
    msg = _("Removed address %s") % address.full_address()
    address.delete()
    redirect_object(req, target)
    transaction.commit()
    queue_message(req, msg)
remove_address = transaction_decorator(remove_address)

# arch-tag: 53b597b2-0472-11da-9196-788d6ec686ec
