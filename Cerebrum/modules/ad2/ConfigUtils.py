# -*- coding: utf-8 -*-
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
"""Default Cerebrum settings for Active Directory and the AD synchronisations.

Overrides should go in a local, instance specific file named:

    adconf.py

Each setting should be well commented in this file, to inform developers and
sysadmin about the usage and consequences of the setting.

TODO: Should the check for valid config be here, or in the sync instead?

"""

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory

# Note that the constants object is not instantiated, as we only need type
# checking in here.
const = Factory.get('Constants')

class ConfigError(Exception):
    """Exception for configuration errors."""
    pass

class AttrConfig(object):
    """Configuration settings for an AD attribute.

    This class, and its subclasses, is used to specify what a given attribute
    should contain of information. The configuration is then used by the AD sync
    to feed the given attribute with the values from db that matches these
    criterias.

    """
    def __init__(self, default=None, transform=None, spreads=None,
            source_systems=None):
        """Setting the basic, most used config variables.

        @type default: mixed
        @param default:
            The default value to set for the attribute if no other value is
            found, based on other criterias, e.g. in the subclasses. Note that
            if this is a string, it is able to use some of the basic variables
            for the entities, like entity_name, entity_id, ad_id and ou.

        @type transform: function
        @param transform:
            A function, e.g. a lambda, that should process the given value
            before sending it to AD. This could for instance be used to strip
            whitespace, or lowercase strings. For instance:

                lambda x: x[1:].lower()

            though this specific example could be simplified:

                string.lower

        @type spreads: SpreadCode or sequence thereof
        @param spreads:
            If set, defines what spreads the user must have for the value to be
            set. Entitites without the spread would get an empty (blank) value.
            Note that spreads were originally meant to control what systems
            information should get spread to - here we use it for modifying what
            information goes over to a system, which is wrong use of the spread
            definition. Use therefore with care.

        @type source_systems: AuthoritativeSystemCode or sequence thereof
        @param source_systems:
            One or more of the given source systems to retrieve the information
            from, in prioritised order. If None is set, the attribute would be
            given from any source system (TODO: need a default order for such).

        # TODO: Should attributes behave differently when multiple values are
        # accepted? For instance with the contact types.

        """
        self.default = default
        if transform:
            self.transform = transform
        self.source_systems = self._prepare_constants(source_systems,
                const.AuthoritativeSystem)
        self.spreads = self._prepare_constants(spreads, const.Spread)

    def _prepare_constants(self, input, const_class):
        """Prepare and validate given constant(s).

        @type input: Cerebrum constant or sequence thereof or None
        @param input: The constants that should be used.

        @type const_class: CerebrumCode class or sequence thereof
        @param const_class: The class that the given constant(s) must be
            instances of to be valid. If a sequence is given, the constants must
            be an instance of one of the classes.

        @rtype: sequence of Cerebrum constants
        @return: Return the given input, but makes sure that it is iterable.

        """
        if input:
            if not isinstance(input, (list, tuple, set)):
                input = (input,)
            for i in input:
                if not isinstance(i, const_class):
                    raise ConfigError('Not a %s: %s (%r)' % (const_class, i, i))
        return input

class ContactAttr(AttrConfig):
    """Configuration for an attribute containing contact info.

    This is used for attributes that should contain data that is stored as
    contact info in Cerebrum. 

    Note that the contact information consist of different elements:

        - contact_value
        - contact_alias
        - contact_pref
        - description

    """
    def __init__(self, contact_types, *args, **kwargs):
        """Initiate a contact info variable.

        @type contact_types: str or sequence thereof
        @param contact_types: One or more of the contact types to use, in
            priority, i.e. the first contact type is used if it exists for an
            entity, otherwise the next one. The contact types are identified by
            their L{code_str}.

        """
        super(ContactAttr, self).__init__(*args, **kwargs)
        self.contact_types = self._prepare_constants(contact_types,
                const.ContactInfo)

class NameAttr(AttrConfig):
    """Configuration for attributes that should contain a name.

    This is not the same as entity_name. There are another name table in
    Cerebrum that contains names in different variant, and with different
    languages. Also, persons have their own table - this is used for accounts.

    Since this configuration class both accepts entity names and person names,
    it behaves a bit differently for the entity_types.

    """
    def __init__(self, name_variants, languages=None, *args, **kwargs):
        """Initiate a name attribute.

        @type name_variants: PersonName (constant) or sequence thereof
        @param name_variants: The defined name variants to retrieve.

        @type languages: LanguageCode or sequence thereof
        @param languages: If set, it specifies that only names in these
            languages should be used.

        """
        super(NameAttr, self).__init__(*args, **kwargs)
        self.name_variants = self._prepare_constants(name_variants,
                (const.EntityNameCode, const.PersonName))
        self.languages = self._prepare_constants(languages, const.LanguageCode)

class AddressAttr(AttrConfig):
    """Config for attributes with addresses, or parts of an address.

    """
    def __init__(self, address_types, *args, **kwargs):
        """Initiate an address attribute.

        Note that each address is a dict and not a string. You therefore need to
        use L{transform} to set the proper variable(s) you would like. Each
        address consists of the elements:
        
                - address_text
                - p_o_box
                - postal_number
                - city
                - country

        Example on a transform callable::

            lambda adr: adr['postal_number']

        which would for instance return::
        
            0360

        You could also combine elements::

            def adrformat(adr)
                if adr['p_o_box']:
                    return u'%s, %s' % (adr['address_text'], adr['p_o_box'])
                return adr['address_text']

        which could return::

            "Problemveien 1"
            "Problemveien 1, Postboks 120"

        Note that the element "country" is a reference to a Country code::

            lambda adr: co.Country(adr['country']).country

        which would give::

            "Sweden"

        @type address_types: AddressCode or sequence thereof
        @param address_types: What addresses to fetch and use, in prioritised
            order. The first available for an entity is used.

        """
        super(AddressAttr, self).__init__(*args, **kwargs)
        self.address_types = self._prepare_constants(address_types,
                const.Address)

class ExternalIdAttr(AttrConfig):
    """Config for attributes using external IDs.

    """
    def __init__(self, id_types, *args, **kwargs):
        """Initiate a config for given external IDs.

        @type id_types: EntityExternalIdCode or sequence thereof
        @param id_types: What external ID types to use, in prioritized order.

        """
        super(ExternalIdAttr, self).__init__(*args, **kwargs)
        self.id_types = self._prepare_constants(id_types,
                const.EntityExternalId)

class TraitAttr(AttrConfig):
    """Config for attributes retrieved from traits.

    """
    def __init__(self, traitcodes, *args, **kwargs):
        """Initiate a config for given traits.

        Note that each trait is a dict that contains different elements, like
        strval and numval, and must therefore be wrapped e.g. through
        L{transform}.

        This might be expanded later, if more criterias are needed.

        @type traitcodes: EntityTraitCode or sequence thereof
        @param traitcodes: What trait types to use, in prioritised order.

        """
        super(TraitAttr, self).__init__(*args, **kwargs)
        self.traitcodes = self._prepare_constants(traitcodes, const.EntityTrait)
