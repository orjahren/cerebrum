# -*- coding: utf-8 -*-
#
# Copyright 2020 University of Oslo, Norway
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
Mapper for DFØ-SAP.
"""
from __future__ import unicode_literals

import re
import collections
import logging

import six

from Cerebrum.modules.hr_import import mapper as _base
from Cerebrum.modules.hr_import.models import (HRPerson,
                                               HRTitle,
                                               HRAffiliation,
                                               HRExternalID,
                                               HRContactInfo)
from Cerebrum.modules.no.dfo.utils import assert_list, parse_date

logger = logging.getLogger(__name__)

IGNORE_FNR_REGEX = re.compile(r'(.+00[12]00$|00000000000)')
REQUIRED_ID_TYPE = ('NO_BIRTHNO', 'PASSNR')


def translate_keys(d, mapping):
    """
    Filter and translate keys of a dict-like mapping.

    :param d: A dict-like object to translate
    :param mapping: A dict-like key translation table

    :rtype: dict
    :returns: A modified copy of ``d``.

    >>> translate_keys({'a': 1, 'b': 2, 'c': 3}, {'a': 'A', 'b': 'B'})
    {'A': 1, 'B': 2}
    """
    return {mapping[k]: v for k, v in d.items() if k in mapping}


def filter_elements(d):
    """
    Filter out empty keys and valies from a dict.

    :param d: A dict-like object to filter

    :rtype: dict
    :returns: A modified copy of ``d``.

    >>> filter_elements({'a': None, 'b': 0, 'c': False, '': 3, 'x': 'y'})
    {'x': 'y'}
    """
    return {k: v for k, v in d.items() if k and v}


def get_main_assignment(person_data, assignment_data):
    """Extract data about a person's main assignment from ``assignment_data``

    :param dict person_data: Person data from DFØ-SAP
    :param dict assignment_data: Assignment data from DFØ-SAP
    """
    main_assignment_id = person_data.get('stillingId')
    if not main_assignment_id:
        return None
    return assignment_data[main_assignment_id]


def get_additional_assignment(person_data, assignment_id):
    """Extract data about an additional assignment from ``person_data``

    :type person_data: dict
    :param person_data: Data from SAP
    :type assignment_id: int
    """
    for assignment in assert_list(person_data.get('tilleggsstilling')):
        if assignment['stillingId'] == assignment_id:
            return assignment
    return None


class MapperConfig(_base.MapperConfig):
    pass


class EmployeeMapper(_base.AbstractMapper):
    """A simple employee mapper class"""

    @classmethod
    def parse_affiliations(cls, person_data, assignment_data):
        """
        Parse data from SAP and return affiliations

        :rtype: set(HRAffiliation)
        """
        affiliations = set()
        category_2_status = {
            50001597: 'tekadm',
            50001598: 'tekadm',
            50001599: 'vitenskapelig'
        }
        role_mapping = {
            # TODO:
            #  It says that "medarbeiderundergruppe" is supposed to be int in
            #  the API-doc.
            ('9', '90'): 'assosiert_person',
            ('9', '93'): 'emeritus',
            ('9', '94'): 'ekst_partner',
            ('9', '95'): 'gjesteforsker',
        }

        # TODO:
        #  Rewrite this once orgreg is ready.
        for assignment_id, assignment in assignment_data.items():
            affiliation = 'ANSATT'
            stillingskats = assert_list(assignment.get('stillingskat', []))
            if len(stillingskats) == 0:
                logger.warning('ignoring assignment=%s, no stillingskat',
                               assignment_id)
                continue

            stillingskat_id = stillingskats[0].get('stillingskatId')
            status = category_2_status.get(stillingskat_id)
            is_main_assignment = assignment_id == person_data.get('stillingId')

            if is_main_assignment:
                precedence = (50, 50)
                start_date = parse_date(person_data.get('startdato'),
                                        allow_empty=True)
                end_date = parse_date(person_data['sluttdato'])

                # If the person has one of the MG/MUG combinations present in
                # role_mapping, then the main assignment should instead be
                # interpreted as a TILKNYTTET affiliation.
                group = person_data.get('medarbeidergruppe')
                sub_group = person_data.get('medarbeiderundergruppe')
                role = role_mapping.get((group, sub_group))
                if role:
                    status = role
                    affiliation = 'TILKNYTTET'

                if not status:
                    # extra log message for main aff (to log mg/mug)
                    logger.warning('unknown main assignment=%s '
                                   '(stillingskatId=%r, mg=%r, mug=%r)',
                                   assignment_id, stillingskat_id, group,
                                   sub_group)
            else:
                precedence = None
                additional_assignment = get_additional_assignment(
                    person_data,
                    assignment_id
                )
                start_date = parse_date(additional_assignment.get('startdato'),
                                        allow_empty=True)
                end_date = parse_date(additional_assignment.get('sluttdato'),
                                      allow_empty=True)

            if not status:
                logger.warning('ignoring assignment=%s, '
                               'no matching aff (stillingskatId=%r)',
                               assignment_id, stillingskat_id)
                continue

            ou_id = assignment.get('organisasjonId')
            if ou_id is None:
                logger.warning(
                    'ignoring assignment=%s, missing organisasjonId',
                    assignment_id)
                continue

            affiliations.add(
                HRAffiliation(**{
                    'ou_id': format(ou_id, 'd'),
                    'affiliation': affiliation,
                    'status': status,
                    'precedence': precedence,
                    'start_date': start_date,
                    'end_date': end_date
                })
            )

        logger.info('mapped %d assignments to %d affiliations: %r',
                    len(assignment_data), len(affiliations), affiliations)
        return affiliations

    @classmethod
    def parse_contacts(cls, person_data):
        """
        Parse data from SAP and return contact information.

        :type person_data: dict
        :param person_data: Data from DFØ-SAP

        :rtype: set(HRContactInfo)
        """
        # TODO: Do we have the correct mapping?
        key_map = collections.OrderedDict([
            ('tjenestetelefon', 'PHONE'),
            # ('privatTelefonnummer', ?),
            # ('telefonnummer', 'PRIVMOBVISIBLE'),
            ('mobilnummer', 'MOBILE'),
            ('mobilPrivat', 'PRIVATEMOBILE'),
            # ('privatTlfUtland', ?),
        ])

        numbers_to_add = filter_elements(translate_keys(person_data, key_map))
        numbers_to_add = sorted(
            [(k, v) for k, v in numbers_to_add.items()],
            key=lambda (k, v): key_map.values().index(k))
        numbers = set()
        for pref, (key, value) in enumerate(numbers_to_add):
            numbers.add(HRContactInfo(contact_type=key,
                                      contact_pref=pref,
                                      contact_value=value))
        logger.info('found %d contacts: %r', len(numbers), numbers)
        return numbers

    @classmethod
    def parse_external_ids(cls, person_id, person_data):
        """
        Parse data from DFØ-SAP and return external ids (i.e. passnr).

        :rtype: set(HRExternalID)
        """
        external_ids = set()
        external_ids.add(
            HRExternalID(id_type='DFO_PID',
                         external_id=six.text_type(person_id))
        )

        # TODO:
        #  Also handle "eksternIdent", "brukerident" and "dfoBrukerident"?
        fnr = person_data.get('fnr')
        if fnr:
            fnr_str = str(fnr)
            if re.search(IGNORE_FNR_REGEX, fnr_str):
                logger.info('Invalid FNR: %s, ignoring..', fnr_str)
            else:
                external_ids.add(
                    HRExternalID(id_type='NO_BIRTHNO',
                                 external_id=fnr_str)
                )

        dfo_2_cerebrum = {
            '02': (
                'PASSNR',
                (lambda d: '{}-{}'.format(d['idLand'][:2], d['idNr'])),
            ),
            # TODO: Are there other id-types?
        }

        for external_id in assert_list(person_data.get('annenId')):
            if external_id['idType'] not in dfo_2_cerebrum:
                continue
            id_type, id_format = dfo_2_cerebrum[external_id['idType']]
            id_value = id_format(external_id)
            external_ids.add(HRExternalID(id_type=id_type,
                                          external_id=id_value))
        logger.info('found %d ids: %r',
                    len(external_ids), external_ids)
        return external_ids

    @classmethod
    def parse_titles(cls, main_assignment):
        """
        Parse data from DFØ-SAP and return person titles.

        :rtype: set(HRTitle)
        """
        titles = set()

        # We only want the title of the main assignment
        if not main_assignment:
            return titles

        name = main_assignment.get('stillingstittel')
        if not name:
            return titles

        titles.add(
            HRTitle(name_variant='WORKTITLE',
                    name_language='nb',
                    name=name)
        )
        logger.info('found %d titles: %r', len(titles), titles)
        return titles

    @staticmethod
    def create_hr_person(obj):
        person_id = obj['id']
        person_data = obj['employee']

        return HRPerson(
            hr_id=person_id,
            first_name=person_data.get('fornavn'),
            last_name=person_data.get('etternavn'),
            birth_date=parse_date(person_data.get('fdato'), allow_empty=True),
            gender=person_data.get('kjonn'),
        )

    def update_hr_person(self, hr_person, obj):
        person_data = obj['employee']
        assignment_data = obj['assignments']

        main_assignment = get_main_assignment(person_data, assignment_data)
        hr_person.external_ids = self.parse_external_ids(hr_person.hr_id,
                                                         person_data)
        if not any(id_ in REQUIRED_ID_TYPE for id_ in hr_person.external_ids):
            raise Exception('None of required id types %s present: %s' % (
                REQUIRED_ID_TYPE,
                hr_person.external_ids))
        hr_person.contact_infos = self.parse_contacts(person_data)
        hr_person.titles = self.parse_titles(main_assignment)
        hr_person.affiliations = self.parse_affiliations(person_data,
                                                         assignment_data)

    def translate(self, reference, obj):
        """
        Populate a HRPerson object with data fetched from SAP

        :type reference: str
        :type obj: RemoteObject
        :rtype: HRPerson
        """
        hr_person = self.create_hr_person(obj)
        self.update_hr_person(hr_person, obj)
        return hr_person

    def is_active(self, hr_object, is_active=None):
        return hr_object.has_active_affiliations(start_grace=self.start_grace,
                                                 end_grace=self.end_grace)
