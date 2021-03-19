#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2021 University of Oslo, Norway
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
""" search and display queued events. """
from __future__ import print_function

import argparse
import datetime
import logging
from functools import partial

import Cerebrum.logutils
import Cerebrum.logutils.options
from Cerebrum.Utils import Factory
from Cerebrum.utils.date import parse_date, parse_datetime
from Cerebrum.utils.date_compat import get_datetime_tz
from Cerebrum.modules.tasks.task_queue import sql_search

logger = logging.getLogger(__name__)


def to_str(value):
    if value is None:
        return ''
    if isinstance(value, datetime.date):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, dict):
        return repr(value)
    return str(value)


def limit_str(s, max_length):
    return s if len(s) <= max_length else s[:max_length-3] + '...'


class Formatter(object):

    default_field_size = 20

    field_size = {
        'queue': 15,
        'key': 10,
        'attempts': 8,
    }

    field_sep = '  '

    def __init__(self, fields):
        self.fields = tuple(fields)

    def get_size(self, field):
        return self.field_size.get(field, self.default_field_size)

    def format_cell(self, field, value):
        size = self.get_size(field)
        return format(limit_str(to_str(value), size),
                      '<' + str(self.get_size(field)))

    def format_header(self):
        return self.field_sep.join(self.format_cell(f, f)
                                   for f in self.fields)

    def format_sep(self):
        return self.field_sep.join(self.format_cell(f, '-' * self.get_size(f))
                                   for f in self.fields)

    def format_row(self, data):
        return self.field_sep.join(self.format_cell(f, data[f])
                                   for f in self.fields)


def dt_type(value):
    for parse in (parse_datetime, parse_date):
        try:
            return get_datetime_tz(parse(value))
        except ValueError:
            pass

    raise ValueError('invalid date/datetime: ' + repr(value))


parser = argparse.ArgumentParser(
    description='Search and show items on task queue',
)


search_args = parser.add_argument_group(
    'Search',
)
search_args.add_argument(
    '--queue',
    dest='queues',
    action='append',
    help='include items in queue %(metavar)s',
    metavar='<name>',
)
search_args.add_argument(
    '--key',
    dest='keys',
    action='append',
    help='only include items with key %(metavar)s',
    metavar='<key>',
)
iat_before_arg = search_args.add_argument(
    '--issued-before',
    dest='iat_before',
    type=dt_type,
    help='only include items with iat < %(metavar)s',
    metavar='<when>',
)
iat_after_arg = search_args.add_argument(
    '--issued-after',
    dest='iat_after',
    type=dt_type,
    help='only include items with iat > %(metavar)s',
    metavar='<when>',
)
nbf_before_arg = search_args.add_argument(
    '--nbf',
    dest='nbf_before',
    type=dt_type,
    help='only include items with nbf < %(metavar)s',
    metavar='<when>',
)
search_args.add_argument(
    '--min-attempts',
    dest='min_attempts',
    type=int,
    help='only include items attempts <= %(metavar)s',
    metavar='<n>',
)
search_args.add_argument(
    '--max-attempts',
    dest='max_attempts',
    type=int,
    help='only include items attempts > %(metavar)s',
    metavar='<n>',
)

display_args = parser.add_argument_group(
    'Display',
    'Show non-default task information',
)
display_args.add_argument(
    '-i', '--show-iat',
    action='store_true',
    help='include iat (issued at) in output',
)
display_args.add_argument(
    '-r', '--show-reason',
    action='store_true',
    help='include reason in output',
)
display_args.add_argument(
    '-p', '--show-payload',
    action='store_true',
    help='include payload in output',
)

log_sub = Cerebrum.logutils.options.install_subparser(parser)
log_sub.set_defaults(**{
    Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'WARNING',
})


def main(inargs=None):
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('console', args)

    logger.info('Start %s', parser.prog)
    logger.debug('args: %r', args)

    db = Factory.get('Database')()

    search = partial(sql_search, db)

    params = {}
    if args.queues:
        params['queues'] = args.queues
    if args.queues:
        params['keys'] = args.keys
    if args.iat_before:
        params['iat_before'] = args.iat_before
    if args.iat_after:
        params['iat_after'] = args.iat_after
    if args.nbf_before:
        params['nbf_before'] = args.nbf_before
    if args.min_attempts is not None:
        params['min_attempts'] = args.min_attempts
    if args.max_attempts is not None:
        params['max_attempts'] = args.max_attempts

    fields = ['queue', 'key', 'nbf', 'attempts']
    if args.show_iat:
        fields.append('iat')
    if args.show_reason:
        fields.append('reason')
    if args.show_payload:
        fields.append('payload')

    formatter = Formatter(fields)

    print(formatter.format_header())
    print(formatter.format_sep())

    for row in search(**params):
        print(formatter.format_row(row))

    logger.info('Done %s', parser.prog)


if __name__ == '__main__':
    main()
