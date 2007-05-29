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

import Cerebrum.modules.Email
import Cerebrum.Database
import Cerebrum.Errors

from CerebrumClass import CerebrumClass, CerebrumDbAttr
from SpineLib.DatabaseClass import DatabaseAttr, DatabaseClass
from SpineLib import SpineExceptions
from SpineLib.Date import Date

from Entity import Entity
from Types import PersonAffiliationType
from EmailTypes import EmailDomainCategory, EmailTargetType, EmailServerType
from Host import Host
from Account import Account
from Person import Person
from PersonAffiliation import PersonAffiliation
from Commands import Commands

from SpineLib import Registry
registry = Registry.get_registry()

Commands.register_extention("email")

__all__ = ['EmailDomain', 'EmailDomainCategorization', 'EmailTarget', 'EmailAddress']

table = 'email_domain'
class EmailDomain(DatabaseClass):
    """
    This class represents an e-mail domain, i.e. the part after the @ in an e-mail address.
    A domain is a simple object with an ID, a name and a description.

    E-mail domains are mostly used in association with e-mail addresses, or as
    the default for some kind of person affiliation.  For cleanliness, e-mail
    domains can also be categorized.

    \\see EmailAddress
    \\see PersonAffiliation
    \\see EmailDomainCategory
    \\see EmailDomainCategorization
    """
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('name', table, str, write=True),
        DatabaseAttr('description', table, str, write=True),
    )
    db_attr_aliases = {
        table : {
            'id' : 'domain_id',
            'name' : 'domain',
        }
    }

    def delete(self):
        self._delete_from_db()
    delete.signature = None
    delete.signature_write = True

registry.register_class(EmailDomain)

def create_email_domain(self, name, description):
    """
    This function creates a new e-mail domain with the given name and description.

    \\param name The name of the new domain
    \\param description A description of the new domain

    \\return A new EmailDomain object
    """
    obj = Cerebrum.modules.Email.EmailDomain(self.get_database())
    obj.populate(name, description)
    try:
        obj.write_db()
    except Cerebrum.Database.OperationalError:
        raise SpineExceptions.AlreadyExistsError('A domain with the specified name already exists.')
    return EmailDomain(self.get_database(), obj.email_domain_id)

create_email_domain.signature = EmailDomain
create_email_domain.signature_write = True
create_email_domain.signature_args = [str, str]
create_email_domain.signature_exceptions = [SpineExceptions.AlreadyExistsError]
Commands.create_email_domain = create_email_domain

def get_email_domain_by_name(self, name):
    s = registry.EmailDomainSearcher(self.get_database())
    s.set_name(name)
    domains=s.search()
    if len(domains) == 0:
        raise SpineExceptions.NotFoundError('There is no email domain %s' % name)
    elif len(domains) > 1:
        raise SpineExceptions.TooManyMatchesError('There are several email domains with the name %s' % name)
    return domains[0]
get_email_domain_by_name.signature = EmailDomain
get_email_domain_by_name.signature_args = [str]
get_email_domain_by_name.signature_exceptions = [SpineExceptions.NotFoundError, SpineExceptions.TooManyMatchesError]
Commands.get_email_domain_by_name = get_email_domain_by_name

table = 'email_domain_category'
class EmailDomainCategorization(DatabaseClass):
    """
    This class represents a categorization for an e-mail domain, i.e. the link
    between a category and a domain. You don't need to use this class, as there
    are convenient wrappers in both EmailDomain and EmailDomainCategory which
    fetch you their categories or their domains, respectively. Still, you may
    use it if you insist. ;)

    \\see EmailDomain
    \\see EmailDomainCategory
    """
    primary = (
        DatabaseAttr('domain', table, EmailDomain),
        DatabaseAttr('category', table, EmailDomainCategory),
    )
    db_attr_aliases = {
        table : {
            'domain' : 'domain_id',
        }
    }

    def get_auth_entity(self):
        return self.get_domain()
    get_auth_entity.signature = Entity

registry.register_class(EmailDomainCategorization)

def get_email_domains_by_category(self, category):
    """
    Gets all email domains that are members of a given category.

    \\param category The EmailDomainCategory for which you want to retrieve the members
    \\return A list of EmailDomain objects

    \\see EmailDomain
    \\see EmailDomainCategory
    \\see EmailDomainCategorization
    """
    s = registry.EmailDomainCategorizationSearcher(self.get_database())
    s.set_category(category)
    return [i.get_domain() for i in s.search()]

get_email_domains_by_category.signature = [EmailDomain]
get_email_domains_by_category.signature_args = [EmailDomainCategory]
Commands.get_email_domains_by_category = get_email_domains_by_category

def get_categories(self):
    """
    Returns a list of all categories this domain is a member of.
    
    \\return A list of categories the domain is a member of
    \\see EmailDomainCategory
    \\see EmailDomainCategorization
    """
    s = registry.EmailDomainCategorizationSearcher(self.get_database())
    s.set_domain(self)
    return [i.get_category() for i in s.search()]

get_categories.signature = [EmailDomainCategory]
EmailDomain.get_categories = get_categories

def add_to_category(self, category):
    """
    Adds this domain to the given category.

    \\param category The category to which you want to add this domain.
    \\see EmailDomainCategory
    \\see EmailDomainCategorization
    """
    if category in self.get_categories():
        raise SpineExceptions.ValueError('This domain is already a member of the given category.')
    obj = Cerebrum.modules.Email.EmailDomain(self.get_database())
    obj.find(self.get_id())
    obj.add_category(category.get_id())
    obj.write_db()

add_to_category.signature = None
add_to_category.signature_write = True
add_to_category.signature_args = [EmailDomainCategory]
EmailDomain.add_to_category = add_to_category


def remove_from_category(self, category):
    """
    Removes this domain from the given category.

    \\param category The category from which you want to remove this domain.
    \\see EmailDomainCategory
    \\see EmailDomainCategorization
    """
    if category not in self.get_categories():
        raise SpineExceptions.ValueError('This domain is not a member of the given category.')
    obj = Cerebrum.modules.Email.EmailDomain(self.get_database())
    obj.find(self.get_id())
    obj.remove_category(category.get_id())
    obj.write_db()

remove_from_category.signature = None
remove_from_category.signature_write = True
remove_from_category.signature_args = [EmailDomainCategory]
EmailDomain.remove_from_category = remove_from_category

def get_domains(self):
    """
    Fetch all domains in this category.
    \\return A list of all EmailDomain objects in the category.
    \\see EmailDomain
    \\see EmailDomainCategorization
    """
    s = registry.EmailDomainCategorizationSearcher(self.get_database())
    s.set_category(self)
    return [i.get_domain() for i in s.search()]


get_domains.signature = [EmailDomain]
EmailDomainCategory.get_domains = get_domains

table = 'email_server'
attrs = [
    DatabaseAttr('email_server_type', table, EmailServerType, write=True, optional=True)
    ]
for attr in attrs:
    Host.register_attribute(attr)
Host.db_attr_aliases[table] = {'id': 'server_id',
                               'email_server_type': 'server_type'}
# Since we change the attributes of host, we need to make host rebuild it's methods.
Host.build_methods()

def promote_email_server(self, type):
    obj = self._get_cerebrum_obj()
    email_server = Cerebrum.modules.Email.EmailServer(self.get_database())
    email_server.populate(type.get_id(), parent=obj)
    email_server.write_db()
promote_email_server.signature = None
promote_email_server.signature_args = [EmailServerType]
promote_email_server.signature_write = True

def demote_email_server(self):
    raise NotImplementedError
demote_email_server.signature = None
demote_email_server.signature_args = []
demote_email_server.signature_write = True
Host.register_methods([promote_email_server, demote_email_server])

table = 'email_target'
class EmailTarget(DatabaseClass):
    """
    This class represents an e-mail target. The target is a somewhat abstract
    concept, but can be thought of as 'the something that wants to receive the
    e-mail coming to an e-mail address'. As you can probably guess, targets are
    mostly used in association with e-mail addresses.

    If the target is a POSIX account, the e-mail target must also contain the
    UID. 
    
    The target may also have an alias, but the interpretation of the
    alias string is specific to each target type.

    Some target types allow specifying a Posix UID to use for delivery 
    or execution. The attribute using can be set to a posix enabled
    Account for such cases.

    \\see EmailTargetType
    \\see EmailAddress
    \\see Entity
    """
    primary = (
        DatabaseAttr('id', table, int),
    )

    slots = (
        DatabaseAttr('target_type', table, EmailTargetType, write=True),
        DatabaseAttr('entity', table, Entity, write=True, exceptions=[SpineExceptions.AlreadyExistsError]),
        DatabaseAttr('alias_value', table, str, write=True),
        # FIXME: should be PosixUser
        DatabaseAttr('using_uid', table, Account, write=True),
        DatabaseAttr('server', table, Host, write=True, optional=True),
    )
    db_attr_aliases = {
        table : {
            'id' : 'target_id',
            'entity' : 'entity_id',
            'server': 'server_id',
        },
        'email_target_server': {
            'id': 'target_id',
            'server': 'server_id',
        }
    }

    def get_auth_entity(self):
        return self.get_entity()
    get_auth_entity.signature = Entity

    def get_entity(self):
        """
        Fetch the entity associated with this target (if any).

        \\return The entity associated with the target (an account, a group, or
                 None if no entity is associated with the target).
        """
        obj = Cerebrum.modules.Email.EmailTarget(self.get_database())
        obj.find(self.get_id())
        if obj.email_target_entity_id is None:
            return None
        return registry.Entity(self.get_database(), obj.email_target_entity_id)

    def set_entity(self, entity):
        """
        Set the entity that should be associated with this e-mail target.

        \\param entity The entity that should be associated with this target.
                NOTE: The entity must be either an account, a group or None.

        \\see Account
        \\see Group
        """
        obj = Cerebrum.modules.Email.EmailTarget(self.get_database())
        obj.find(self.get_id())
        if entity is None:
            obj.email_target_entity_id = None
            obj.email_target_entity_type = None
        else:
            obj.email_target_entity_id = entity.get_id()
            obj.email_target_entity_type = entity.get_type().get_id()
        try:
            obj.write_db()
        except Cerebrum.Database.OperationalError:
            raise SpineExceptions.AlreadyExistsError('There already exists a target for the specified entity.')

    def delete_email_target(self):
        obj = Cerebrum.modules.Email.EmailTarget(self.get_database())
        obj.find(self.get_id())
        try:
            obj.delete()
        except Cerebrum.Database.IntegrityError:
            raise SpineExceptions.DeletionError('Constraint violated during deletion. There may be e-mail addresses referring to the target.')

    delete_email_target.signature = None
    delete_email_target.signature_write = True
    delete_email_target.signature_exceptions = [SpineExceptions.DeletionError]

registry.register_class(EmailTarget)

def create_email_target(self, type):
    """
    This method creates a new e-mail target.

    \\param type The type of the target

    \\return A new e-mail target object.

    \\see EmailTarget
    \\see EmailTargetType
    """
    obj = Cerebrum.modules.Email.EmailTarget(self.get_database())
    obj.populate(type.get_id())
    obj.write_db()
    return EmailTarget(self.get_database(), obj.email_target_id)

create_email_target.signature = EmailTarget
create_email_target.signature_write = True
create_email_target.signature_args = [EmailTargetType]
Commands.create_email_target = create_email_target

table = 'email_address'
class EmailAddress(DatabaseClass):
    """
    This class represents an e-mail address. Every e-mail address has a local
    part, a domain, and a target. The local part is essentially the part before
    the @, the domain is the part after the @, and the target is the right side
    in an aliases file.

    In addition, every e-mail address has a creation date, a change timestamp
    and an expiry date, the last of which can be changed.

    \\see EmailDomain
    \\see EmailTarget
    """
    primary = (
        DatabaseAttr('id', table, int),
    )
    slots = (
        DatabaseAttr('local_part', table, str, write=True),
        DatabaseAttr('domain', table, EmailDomain, write=True),
        DatabaseAttr('target', table, EmailTarget, write=True),
        DatabaseAttr('create_date', table, Date),
        # TODO: How do we auto-update change date here?
        DatabaseAttr('change_date', table, Date),
        DatabaseAttr('expire_date', table, Date, write=True),
    )

    db_attr_aliases = {
        table : {
            'id' : 'address_id',
            'domain' : 'domain_id',
            'target' : 'target_id',
        }
    }

    def get_auth_entity(self):
        return self.get_target()
    get_auth_entity.signature = Entity

    def delete(self):
        """
        This method deletes this e-mail address.
        """
        if self.is_primary(): # Defined below PrimaryEmailAddress
            self.unset_as_primary()
        obj = Cerebrum.modules.Email.EmailAddress(self.get_database())
        obj.find(self.get_id())
        obj.delete()
        obj.write_db()

    delete.signature = None
    delete.signature_write = True

registry.register_class(EmailAddress)

def find_email_address(self, address):        
    """
    Find an EmailAddress from the full address.
    """
    obj = Cerebrum.modules.Email.EmailAddress(self.get_database())
    try:
        obj.find_by_address(address)
    except Cerebrum.Errors.NotFoundError:
        return
    except ValueError:
        ## FIXME: what error to raise if caller forgot @ ? 
        return
    return EmailAddress(self.get_database(), obj.email_addr_id)

find_email_address.signature = EmailAddress
find_email_address.signature_args = [str]
Commands.find_email_address = find_email_address

def create_email_address(self, local_part, domain, target):
    """
    This function creates a new e-mail address.
    
    \\param local_part The string before the @ in the address
    \\param domain The domain in the address (the part after the @)
    \\param target The target of the address (who/what mail for this address goes to)

    \\return A new e-mail address

    \\see EmailDomain
    \\see EmailTarget
    """
    obj = Cerebrum.modules.Email.EmailAddress(self.get_database())
    obj.populate(local_part, domain.get_id(), target.get_id())
    obj.write_db()
    return EmailAddress(self.get_database(), obj.email_addr_id)

create_email_address.signature = EmailAddress
create_email_address.signature_write = True
create_email_address.signature_args = [str, EmailDomain, EmailTarget]
Commands.create_email_address = create_email_address
  
def full_address(self):
    """
    Return a string version of the email address, ie localpart@domain
    """       
    ## FIXME: Should be in Cerebrum object
    return "%s@%s" % (self.get_local_part(), self.get_domain().get_name())
full_address.signature = str
EmailAddress.full_address = full_address

def get_addresses(self):
    """
    This method gets the addresses of this e-mail target.

    NOTE: Calling this method is equivalent to searching for all EmailAddresses
    with this EmailTarget as their target.

    \\return A list of the addresses associated with this e-mail target.
    \\see EmailAddress
    """
    s = registry.EmailAddressSearcher(self.get_database())
    s.set_target(self)
    return s.search()

get_addresses.signature = [EmailAddress]
EmailTarget.get_addresses = get_addresses

table = 'email_primary_address'
class PrimaryEmailAddress(DatabaseClass):
    """
    This class represents the link between e-mail targets and their primary
    e-mail address.  Every address is associated with a target, but only one of
    them is the primary address for the target. This class represents those
    mappings.

    The primary address for a target can be fetched by using the
    get_primary_address() method in EmailTarget, or by constructing an object
    of this class for the desired target, and calling get_address() on that.

    \\see EmailTarget
    \\see EmailAddress
    """

    primary = (
        DatabaseAttr('target', table, EmailTarget),
    )
    slots = (
        DatabaseAttr('address', table, EmailAddress, write=True),
    )
    db_attr_aliases = {
        table : {
            'target' : 'target_id',
            'address' : 'address_id',
        }
    }

    def get_auth_entity(self):
        return self.get_target()
    get_auth_entity.signature = Entity

registry.register_class(PrimaryEmailAddress)

def get_primary_address(self):
    """
    This method gets the primary address of this e-mail target.

    \\return The primary address for this e-mail target.
    \\see PrimaryEmailAddress
    """
    try:
        return registry.PrimaryEmailAddress(self.get_database(), self).get_address()
    except SpineExceptions.NotFoundError:
        return None

get_primary_address.signature = EmailAddress
get_primary_address.signature_exceptions = [SpineExceptions.NotFoundError]
EmailTarget.get_primary_address = get_primary_address

def set_primary_address(self, address):
    """
    This method sets the primary e-mail address for the target.
    
    \\param address The EmailAddress object to set as the primary address for this target.

    \\see EmailAddress
    \\see PrimaryEmailAddress
    """
    obj = Cerebrum.modules.Email.EmailPrimaryAddressTarget(self.get_database())
    if address is None:
        try:
            obj.find(self.get_id())
        except Cerebrum.Errors.NotFoundError:
            return
        obj.delete()
    else:
        if address.get_target() != self:
            raise SpineExceptions.NotFoundError('The given address does not have this target as its target.')
        try:
            obj.find(self.get_id())
            obj.email_primaddr_id = address.get_id()
        except Cerebrum.Errors.NotFoundError:
            obj.populate(address.get_id(), self.get_id())
    obj.write_db()

set_primary_address.signature = None
set_primary_address.signature_write = True
set_primary_address.signature_args = [EmailAddress]
EmailTarget.set_primary_address = set_primary_address

def set_as_primary(self):
    """
    Set this e-mail address as the primary address of its target. This method
    will silently return even if the address is already the primary address of
    its target.

    \\see EmailTarget
    \\see PrimaryEmailAddress
    """
    if not self.is_primary():
        self.get_target().set_primary_address(self)

set_as_primary.signature = None
EmailAddress.set_as_primary = set_as_primary

def unset_as_primary(self):
    """
    Unset this e-mail address as the primary address of its target. This method
    will silently return even if the address is not the primary address of the
    target.

    \\see EmailTarget
    \\see PrimaryEmailAddress
    """
    if self.is_primary():
        # FIXME: there might be more here like this.
        target = self.get_target()
        target.set_primary_address(None)
        target.save()

unset_as_primary.signature = None
unset_as_primary.signature_write = True
EmailAddress.unset_as_primary = unset_as_primary

def is_primary(self):
    """
    Returns true if this address is the primary address of its target.

    \\see EmailTarget
    \\see PrimaryEmailAddress
    """
    s = registry.PrimaryEmailAddressSearcher(self.get_database())
    s.set_target(self.get_target())
    s.set_address(self)
    assert len(s.search()) <= 1 # There can only be either 0 or 1 primary e-mail address
    return len(s.search()) == 1

is_primary.signature = bool
EmailAddress.is_primary = is_primary

table = 'email_entity_domain'
class EntityEmailDomain(DatabaseClass):
    """
    This is used to map a (default) emaildomain to users in a
    OU/affiliation or possibly directly other entity types.

    You shouldn't need to use this class directly, but rather access
    it through convenience methods in PersonAffiliationType, EmailDomain
    and Person. Of course, you may still use it if you want to.

    \\see Person
    \\see PersonAffiliationType
    \\see EmailDomain
    """
    primary = (
        DatabaseAttr('entity', table, Entity),
        DatabaseAttr('affiliation', table, PersonAffiliationType),
    )
    slots = (
        DatabaseAttr('domain', table, EmailDomain),
    )
    db_attr_aliases = {
        table : {
            'entity' : 'entity_id',
            'domain' : 'domain_id',
        }
    }
    
    def get_auth_entity(self):
        return self.get_entity()
    get_auth_entity.signature = Entity

registry.register_class(EntityEmailDomain)

def get_email_domain(self, affiliation):
    """
    Fetches the e-mail domain for this person under the given affiliation type.
    \\param affiliation The affiliation for which domain should be retrieved.
    \\return The EmailDomain for this entity.

    \\see PersonAffiliationType
    \\see EmailDomain
    """
    return registry.EntityEmailDomain(self.get_database(), self, affiliation).get_domain()

get_email_domain.signature = EmailDomain
get_email_domain.signature_args = [int]
Person.get_email_domain = get_email_domain

def set_email_domain(self, affiliation, domain):
    """
    Sets the e-mail domain for this person under the given affiliation type.

    \\param affiliation The affiliation for which the domain should be set.
    \\param domain The domain to set for the given affiliation.

    \\see PersonAffiliationType
    \\see EmailDomain
    """
    obj = Cerebrum.modules.Email.EntityEmailDomain(self.get_database())
    try:
        if affiliation is None:
            obj.find(self.get_id())
        else:
            obj.find(self.get_id(), affiliation.get_id())
        obj.entity_email_domain_id = domain.get_id()
    except Cerebrum.Errors.NotFoundError:
        obj.populate(self.get_id())
        if affiliation is None:
            obj.populate_email_domain(domain.get_id())
        else:
            obj.populate_email_domain(domain.get_id(), affiliation.get_id())
    obj.write_db()

set_email_domain.signature = EmailDomain
set_email_domain.signature_write = True
set_email_domain.signature_args = [PersonAffiliationType, EmailDomain]
Person.set_email_domain = set_email_domain

def get_persons(self, affiliation):
    """
    Fetches all persons that have this domain associated with them under the given affiliation.
    \\param affiliation The affiliation for which persons should be retrieved.
    \\return The persons associated with the domain.

    \\see PersonAffiliationType
    \\see Person
    """
    s = registry.EntityEmailDomainSearcher(self.get_database())
    s.set_domain(self)
    s.set_affiliation(affiliation)
    return [i.get_entity() for i in s.search()]

get_persons.signature = [Person]
get_persons.signature_args = [PersonAffiliationType]
EmailDomain.get_persons = get_persons

def aff_get_email_domain(self):
    """
    Returns the e-mail domain for this affiliation.

    \\return The e-mail domain for this affiliation (for this person).
    \\see EmailDomain
    \\see EntityEmailDomain
    """
    return registry.EntityEmailDomain(self.get_database(), self.get_person(), self.get_affiliation()).get_domain()

aff_get_email_domain.signature = EmailDomain
PersonAffiliation.aff_get_email_domain = aff_get_email_domain

def aff_set_email_domain(self, domain):
    """
    Sets the e-mail domain for this affiliation.
    \\param domain The domain to set.

    \\see EmailDomain
    \\see EntityEmailDomain
    """
    obj = Cerebrum.modules.Email.EntityEmailDomain(self.get_database())
    try:
        obj.find(self.get_person().get_id(), self.get_id())
        obj.entity_email_domain_id = domain.get_id()
    except Cerebrum.Errors.NotFoundError:
        obj.populate(self.get_person().get_id())
        obj.populate_email_domain(domain.get_id(), affiliation.get_id())
    obj.write_db()

aff_set_email_domain.signature = None
aff_set_email_domain.signature_write = True
aff_set_email_domain.signature_args = [EmailDomain]
PersonAffiliation.aff_set_email_domain = aff_set_email_domain

table = 'email_forward'
class EmailForward(DatabaseClass):
    primary = (
        DatabaseAttr('target', table, EmailTarget),
        DatabaseAttr('forward_to', table, str),
    )
    slots = (
        DatabaseAttr('enable', table, bool, write=True),
    )
    db_attr_aliases = {
        table : {
            'target' : 'target_id',
        }
    }

    def get_auth_entity(self):
        return self.get_target()
    get_auth_entity.signature = Entity

    #TODO delete()

registry.register_class(EmailForward)

def add_forward(self, forward_to):
    db = self.get_database()
    obj = Cerebrum.modules.Email.EmailForward(db)
    obj.find(self.get_id())
    obj.add_forward(forward_to)
    obj.write_db()
    return EmailForward(db, self, forward_to)
add_forward.signature = EmailForward
add_forward.signature_write = True
add_forward.signature_args = [str]

def remove_forward(self, forward_to):
    db = self.get_database()
    obj = Cerebrum.modules.Email.EmailForward(db)
    obj.find(self.get_id())
    obj.remove_forward(forward_to)
    obj.write_db()
remove_forward.signature = None
remove_forward.signature_write = True
remove_forward.signature_args = [str]

def get_forwards(self):
    s = registry.EmailForwardSearcher(self.get_database())
    s.set_target(self)
    return s.search()
get_forwards.signature = [EmailForward]
get_forwards.signature_args = []

EmailTarget.register_methods([add_forward, remove_forward, get_forwards])

table = 'email_vacation'
class EmailVacation(DatabaseClass):
    primary = (
        DatabaseAttr('target', table, EmailTarget),
        DatabaseAttr('start_date', table, Date),
    )
    slots = (
        DatabaseAttr('vacation_text', table, str, write=True),
        DatabaseAttr('end_date', table, Date, write=True),
        DatabaseAttr('enable', table, bool, write=True),
    )
    db_attr_aliases = {
        table : {
            'target' : 'target_id',
        }
    }

    def get_auth_entity(self):
        return self.get_target()
    get_auth_entity.signature = Entity

registry.register_class(EmailVacation)

def add_vacation(self, start, text, end):
    db = self.get_database()
    obj = Cerebrum.modules.Email.EmailVacation(db)
    obj.find(self.get_id())
    obj.add_vacation(start.strftime('%Y-%m-%d'), text,
                     end.strftime('%Y-%m-%d'))
    obj.write_db()
    return EmailVacation(db, self, start)
add_vacation.signature = EmailVacation
add_vacation.signature_write = True
add_vacation.signature_args = [Date, str, Date]

def get_vacations(self):
    s = registry.EmailVacationSearcher(self.get_database())
    s.set_target(self)
    return s.search()
get_vacations.signature = [EmailVacation]
get_vacations.signature_args = []

EmailTarget.register_methods([add_vacation, get_vacations])


# arch-tag: bd478dc6-f9ef-11d9-905c-b1284ed93a3d
