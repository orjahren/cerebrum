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
""" Show tasks on the greg import queues. """
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
import argparse
import logging

import Cerebrum.logutils
import Cerebrum.logutils.options
import Cerebrum.Errors
from Cerebrum.Utils import Factory
from Cerebrum.database.ctx import db_context
from Cerebrum.modules.greg.tasks import GregImportTasks
from Cerebrum.modules.tasks.formatting import TaskFormatter
from Cerebrum.modules.tasks.task_queue import sql_search

logger = logging.getLogger(__name__)


def main(inargs=None):
    parser = argparse.ArgumentParser(
        description='Show queued greg-person import tasks',
        epilog="For more complex queries, use contrib/tasks/search-tasks.py",
    )
    parser.add_argument(
        '-l', '--limit',
        type=int,
        default=None,
        help='only show the first %(metavar)s tasks',
        metavar='<n>',
    )

    log_subparser = Cerebrum.logutils.options.install_subparser(parser)
    log_subparser.set_defaults(**{
        Cerebrum.logutils.options.OPTION_LOGGER_LEVEL: 'WARNING',
    })
    args = parser.parse_args(inargs)

    Cerebrum.logutils.autoconf('console', args)

    logger.info("Starting %s", parser.prog)
    logger.debug("args: %r", args)

    queue = GregImportTasks.queue

    format_table = TaskFormatter(('queue', 'sub', 'key', 'nbf', 'attempts'))

    with db_context(Factory.get('Database')(), dryrun=True) as db:
        items = sql_search(db, queues=queue, limit=args.limit)
        for row in format_table(items, header=True):
            print(row)


if __name__ == '__main__':
    main()
