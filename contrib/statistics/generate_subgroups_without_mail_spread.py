#!/usr/bin/env python
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
Generate HTML or CSV report of filegroups containing subgroups
without filegroup-spread
"""

import argparse
import logging
import sys
from time import time as now

from jinja2 import Environment
from six import text_type

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.utils.csvutils as _csvutils
from Cerebrum.Utils import Factory
from Cerebrum.utils.argutils import codec_type

logger = logging.getLogger(__name__)

template = u"""
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="Content-Type"
          content="text/html; charset={{ encoding | default('utf-8') }}">
    <title>Filegroups containing subgroups without fg-spread</title>
    <style type="text/css">
      /* <![CDATA[ */
      h1 {
        margin: 1em .8em 1em .8em;
        font-size: 1.4em;
      }
      h2 {
        margin: 1.5em 1em 1em 1em;
        font-size: 1em;
      }
      table, h1 {
        margin-top: 2em;
      }
      table {
        border-collapse: collapse;
        width: 100%;
        text-align: left;
      }
      table thead {
        border-bottom: solid gray 1px;
      }
      table th, table td {
        padding: .5em 1em;
        width: 10%;
      }
      .meta {
        color: gray;
        text-align: right;
      }
      /* ]] >*/
    </style>
  </head>
  <body>
    <h1>Filegroups containing subgroups without fg-spread</h1>
    <p class="meta">
      {{ num_fgroups }} filegroups containing subgroups without fg-spread
    </p>

    {% for group in groups | groupby('filegroup') |
    sort(attribute='grouper') %}

    <table>
      <thead>
        <tr>
          <th>Filegroup</th>
          <th>Subgroups without fg-spread</th>
          <th>Members in subgroup</th>
        </tr>
      </thead>

    {% for item in group.list | sort(attribute='filegroup') %}
      <tr>
        <td>
        {% if loop.changed(group) %}
          {{ group.list[0].filegroup }}
        {% endif %}
        </td>
        <td>{{ item.subgroup }}</td>
        <td>{{ item.members_in_sub }}</td>
      </tr>
    {% endfor %}
    </table>
    {% endfor %}
  </body>
</html>
""".strip()


def find_subgroups_without_mail_spread(db, filter_expired_groups=False):
    """Extract filegroups containing subgroups without fg-spread.

    :type db: Cerebrum.CLDatabase.CLDatabase
    :param db: Database to search for groups

    :type filter_expired_groups: bool
    :param filter_expired_groups: Filter out groups that are expired

    :rtype: generator
    :return:
        Generator yielding dicts with filegroup, subgroup and
        number of members in subgroup
    """
    gr = Factory.get('Group')(db)
    co = Factory.get('Constants')(db)

    result = db.query(
        """
        SELECT group_id, member_id
        FROM [:table schema=cerebrum name=group_member] filegroup
        WHERE
            filegroup.member_type= :group_type
            AND
            filegroup.group_id IN
                (SELECT entity_spread.entity_id
                FROM [:table schema=cerebrum name=entity_spread] entity_spread
                WHERE
                    entity_spread.spread= :ifi_fg_spread OR
                    entity_spread.spread= :uio_fg_spread OR
                    entity_spread.spread= :hpc_fg_spread)
            AND
            NOT filegroup.member_id IN
                (SELECT entity_spread.entity_id
                FROM [:table schema=cerebrum name=entity_spread] entity_spread
                WHERE
                    entity_spread.spread= :ifi_fg_spread OR
                    entity_spread.spread= :uio_fg_spread OR
                    entity_spread.spread= :hpc_fg_spread)
        """,
        {
            'ifi_fg_spread': co.spread_ifi_nis_fg,
            'uio_fg_spread': co.spread_uio_nis_fg,
            'hpc_fg_spread': co.spread_hpc_nis_fg,
            'group_type': co.entity_group,
        })

    for row in result:
        filegroup = gr.search(group_id=row['group_id'],
                              filter_expired=filter_expired_groups)
        subgroup = gr.search(group_id=row['member_id'],
                             filter_expired=filter_expired_groups)
        members_in_sub = len(gr.search_members(
                              group_id=row['member_id'],
                              member_filter_expired=filter_expired_groups))

        # When filtering expired groups, gr.search returns empty list
        if len(filegroup) == 0 or len(subgroup) == 0:
            continue

        groups = {
            'filegroup': text_type(filegroup[0][1]),
            'subgroup': text_type(subgroup[0][1]),
            'members_in_sub': text_type(members_in_sub),
        }
        yield groups


def generate_csv_report(file, codec, groups, num_fgroups):
    output = codec.streamwriter(file)
    output.write('Number of filegroups: {}\n'.format(num_fgroups))
    output.write('Filegroups,')
    output.write('Subgroups,')
    output.write('Members in subgroup\n')

    fields = ['filegroup', 'subgroup', 'members_in_sub']
    writer = _csvutils.UnicodeDictWriter(output, fields)
    writer.writerows(groups)


def generate_html_report(file, codec, groups, num_fgroups):
    output = codec.streamwriter(file)
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    report = env.from_string(template)
    output.write(
        report.render({
            'encoding': codec.name,
            'groups': groups,
            'num_fgroups': text_type(num_fgroups),
        }))
    output.write('\n')


DEFAULT_ENCODING = 'utf-8'


def main(inargs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '-f', '--file',
        metavar='FILE',
        type=argparse.FileType('w'),
        default='-',
        help='output file for html report, defaults to stdout')
    parser.add_argument(
        '-e', '--encoding',
        dest='codec',
        default=DEFAULT_ENCODING,
        type=codec_type,
        help="output file encoding, defaults to %(default)s")
    parser.add_argument(
        '--csv',
        metavar='FILE',
        type=argparse.FileType('w'),
        default=None,
        help='output file for csv report, if wanted')
    parser.add_argument(
        '--filter-expired',
        action='store_true',
        dest='filter',
        help='do not include expired groups in report'
    )
    Cerebrum.logutils.options.install_subparser(parser)
    args = parser.parse_args(inargs)
    Cerebrum.logutils.autoconf('cronjob', args)

    logger.info('Reporting filegroups containing subgroups without fg-spread')

    start = now()
    db = Factory.get('Database')()
    groups = list(find_subgroups_without_mail_spread(db, args.filter))
    num_fgroups = len(set(g['filegroup'] for g in groups))
    generate_html_report(args.file, args.codec, groups, num_fgroups)

    args.file.flush()
    if args.file is not sys.stdout:
        args.file.close()
    logger.info('HTML report written to %s', args.file.name)

    if args.csv:
        generate_csv_report(args.csv, args.codec, sorted(groups), num_fgroups)
        args.csv.flush()
        if args.csv is not sys.stdout:
            args.csv.close()
        logger.info('CSV report written to %s', args.csv.name)

    logger.info('Report generated in %.2fs', now() - start)
    logger.info('Done with script %s', parser.prog)


if __name__ == '__main__':
    main()
