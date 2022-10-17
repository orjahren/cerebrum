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
DFØ-SAP datasource for HR imports.
"""
from __future__ import unicode_literals

import json
import logging

import six

from Cerebrum.modules.hr_import.datasource import (
    AbstractDatasource,
    DatasourceInvalid,
    RemoteObject,
)
from Cerebrum.utils import date as date_utils
from Cerebrum.utils.date_compat import get_datetime_tz

logger = logging.getLogger(__name__)


def normalize_id(dfo_id):
    """ Get a normalized employee object id. """
    return six.text_type(int(dfo_id))


def assert_list(value):
    """
    Assert that value is a list.

    Usage: ``some_key = assert_list(dfo_object.get('someKey'))``
    """
    # This is a hacky way to fix the broken DFØ API
    # Some items in the API are specified to be a list, but lists of length 1
    # are unwrapped, and empty lists are simply not present.
    if not value:
        return []

    if not isinstance(value, list):
        value = [value]
    return [x for x in value if x is not None]


def parse_dfo_date(value, allow_empty=True):
    """ Get a date object from a DFO date value. """
    if value:
        return date_utils.parse_date(value)
    elif allow_empty:
        return None
    else:
        raise ValueError('No date: %r' % (value,))


def _get_id(d):
    """ parse 'id' field from message dict. """
    if 'id' not in d:
        raise DatasourceInvalid("missing 'id' field: %r" % (d,))
    return d['id']


def _get_uri(d):
    """ parse 'uri' field from message dict. """
    if 'uri' not in d:
        raise DatasourceInvalid("missing 'uri' field: %r" % (d,))
    return d['uri']


def _get_nbf(d):
    """ parse 'gyldigEtter' (nbf) field from message dict. """
    obj_nbf = d.get('gyldigEtter')
    if not obj_nbf:
        return None
    try:
        return get_datetime_tz(parse_dfo_date(obj_nbf))
    except Exception as e:
        raise DatasourceInvalid("invalid 'gyldigEtter' field: %s (%r, %r)"
                                % (e, obj_nbf, d))


def parse_message(msg_text):
    """ Parse DFØ-SAP message.

    :param str msg_text: json encoded message

    :rtype: dict
    :return:
        Returns a dict with message fields:

        - id (str): object id
        - uri (str): object type
        - nbf (datetime): not before (or None if not given)
    """
    try:
        msg_data = json.loads(msg_text)
    except Exception as e:
        raise DatasourceInvalid('invalid message format: %s (%r)' %
                                (e, msg_text))

    return {
        'id': _get_id(msg_data),
        'uri': _get_uri(msg_data),
        'nbf': _get_nbf(msg_data),
    }


class Employee(RemoteObject):
    pass


class Assignment(RemoteObject):
    pass


class Person(RemoteObject):
    pass


def parse_employee(employee_d):
    """ Sanitize and normalize assignment data """
    # TODO: Filter out unused fields, normalize the rest
    result = dict(employee_d)
    result.update({
        'startdato': parse_dfo_date(employee_d['startdato'], allow_empty=True),
        'sluttdato': parse_dfo_date(employee_d['sluttdato']),
        'tilleggsstilling': [],
    })
    for amnt in assert_list(employee_d.get('tilleggsstilling')):
        result['tilleggsstilling'].append({
            'stillingId': amnt['stillingId'],
            'startdato': parse_dfo_date(amnt['startdato'], allow_empty=True),
            'sluttdato': parse_dfo_date(amnt['sluttdato'], allow_empty=True),
        })
    return result


def parse_assignment(assignment_d):
    """
    Sanitize and normalize assignment data.
    """
    # TODO: remove unused fields
    result = {
        'id': assignment_d['id'],
        'organisasjonId': assignment_d['organisasjonId'],
        'stillingskode': assignment_d['stillingskode'],
        'stillingsnavn': assignment_d['stillingsnavn'],
        'stillingstittel': assignment_d['stillingstittel'],
        'yrkeskode': assignment_d['yrkeskode'],
        'yrkeskodetekst': assignment_d['yrkeskodetekst'],
        'category': [],
    }
    for cat_d in assert_list(assignment_d.get('stillingskat')):
        result['category'].append(cat_d['stillingskatId'])

    employees = {}
    for mem_d in assert_list(assignment_d.get('innehaver')):
        if mem_d['innehaverAnsattnr'] not in employees:
            employees[mem_d['innehaverAnsattnr']] = []
        employees[mem_d['innehaverAnsattnr']].append((
            parse_dfo_date(mem_d.get('innehaverStartdato'), allow_empty=True),
            parse_dfo_date(mem_d.get('innehaverSluttdato'), allow_empty=True),
        ))

    result['employees'] = employees
    return result


def _unpack_list_item(value):
    if not value:
        raise ValueError("empty list")
    value = assert_list(value)
    if len(value) != 1:
        raise ValueError("invalid number of objects: " + str(len(value)))
    return value[0]


class EmployeeDatasource(AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from message body """
        return parse_message(event.body)['id']

    def _get_employee(self, employee_id):
        raw = self.client.get_employee(employee_id)
        try:
            raw = _unpack_list_item(raw)
        except ValueError as e:
            logger.warning('no result for employee-id %s (%s)',
                           repr(employee_id), str(e))
            return {}

        result = parse_employee(raw)
        return result

    def _get_assignment(self, employee_id, assignment_id):
        raw = self.client.get_stilling(assignment_id)
        try:
            raw = _unpack_list_item(raw)
        except ValueError as e:
            logger.warning('no result for assignment-id %s (%s)',
                           repr(assignment_id), str(e))
            return {}
        return parse_assignment(raw)

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        employee_id = reference
        employee_data = self._get_employee(employee_id)

        employee = {
            'id': normalize_id(reference),
            'employee': {},
            'assignments': {},
        }
        if employee_data:
            employee['employee'] = Person('dfo-sap', reference, employee_data)
            assignment_ids = {employee_data['stillingId']}

            for secondary_assignment in employee_data['tilleggsstilling']:
                assignment_ids.add(secondary_assignment['stillingId'])

            for assignment_id in assignment_ids:
                assignment = self._get_assignment(employee_id, assignment_id)

                if assignment:
                    employee['assignments'][assignment_id] = (
                        Assignment('dfo-sap', assignment_id, assignment)
                    )
                else:
                    raise DatasourceInvalid('No assignment_id=%r found' %
                                            (assignment_id,))

        return Employee('dfo-sap', reference, employee)


class AssignmentDatasource(AbstractDatasource):

    def __init__(self, client):
        self.client = client

    def get_reference(self, event):
        """ Extract reference from message body """
        return parse_message(event.body)['id']

    def _get_assignment(self, assignment_id):
        raw = self.client.get_stilling(assignment_id)
        try:
            raw = _unpack_list_item(raw)
        except ValueError as e:
            logger.warning('no result for assignment-id %s (%s)',
                           repr(assignment_id), str(e))
            return {}
        return parse_assignment(raw)

    def get_object(self, reference):
        """ Fetch data from sap (employee data, assignments, roles). """
        assignment = self._get_assignment(reference)
        if not assignment:
            raise DatasourceInvalid('No assignment_id=%r found' %
                                    (reference,))
        return Assignment('dfo-sap', reference, assignment)
