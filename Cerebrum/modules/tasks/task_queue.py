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
""" Database access to task queue.  """
import logging

import six

import Cerebrum.Errors
from Cerebrum.DatabaseAccessor import DatabaseAccessor
from Cerebrum.Utils import argument_to_sql, NotSet
from Cerebrum.utils import json

from .task_models import db_row_to_task

# Task ordering in query results
DEFAULT_ORDER = ('queue', 'nbf', 'iat')

# Fields and field order in task query results
DEFAULT_FIELDS = ('queue', 'key', 'iat', 'nbf', 'attempts',
                  'reason', 'payload')


logger = logging.getLogger(__name__)


def _select(queues=None, keys=None, iat_before=None, iat_after=None,
            nbf_before=None, nbf_after=None, min_attempts=None,
            max_attempts=None):
    """
    Generate clauses and binds for task_queue queries.

    Example:

        >>> _select(queues='foo', keys=('123', 'abc'))
        (
            ['queue = :queue', 'key in (:key1, :key2)'],
            {'queue': 'foo', 'key1': '123', 'key2': 'abc'},
        )

    :param queues: only include results for these queue names
    :param keys: only include results for these keys
    :param iat_before: only include results with an iat before this value
    :param iat_after: only include results with an iat after this value
    :param nbf_before: only include results with a nbf before this value
    :param nbf_after: only include results with a nbf after this value
    :param min_attempts: only include results with at least min_attempts
    :param max_attempts: only include results with less than max_attempts

    :rtype: tuple(list, dict)
    :returns:
        Returns a list of conditions, and a dict of query params.

    """
    clauses = []
    binds = {}

    #
    # value selects
    #
    if queues:
        clauses.append(
            argument_to_sql(queues, 'queue', binds, six.text_type))
    if keys:
        clauses.append(
            argument_to_sql(keys, 'key', binds, six.text_type))

    #
    # range selects
    #
    if iat_before and iat_after and iat_before < iat_after:
        # a date can never be *both* before <t> *and* after that same
        # <t>+<delta>
        raise ValueError("iat_after: cannot be after iat_before"
                         " (%s < iat < %s)" % (iat_after, iat_before))

    if iat_after is not None:
        clauses.append("iat > :iat_a")
        binds['iat_a'] = iat_after
    if iat_before is not None:
        clauses.append("iat < :iat_b")
        binds['iat_b'] = iat_before

    if nbf_before and nbf_after and nbf_before < nbf_after:
        # a date can never be *both* before <t> *and* after that same
        # <t>+<delta>
        raise ValueError("nbf_after: cannot be after nbf_before"
                         " (%s < nbf < %s)" % (nbf_after, nbf_before))

    if nbf_after is not None:
        clauses.append("nbf > :nbf_a")
        binds['nbf_a'] = nbf_after
    if nbf_before is not None:
        clauses.append("nbf < :nbf_b")
        binds['nbf_b'] = nbf_before

    if min_attempts is not None and max_attempts is not None:
        if min_attempts > max_attempts:
            raise ValueError("max_attempts: cannot be less than min_attempts"
                             " (%s <= attempts < %s)" % (min_attempts,
                                                         max_attempts))

    if min_attempts is not None:
        clauses.append("attempts >= :min")
        binds['min'] = int(min_attempts)
    if max_attempts is not None:
        clauses.append("attempts < :max")
        binds['max'] = int(max_attempts)

    return clauses, binds


def sql_search(db, fetchall=True, **selects):
    """
    Search for tasks in queues.

    See py:func:`._select` for search params.

    :param fetchall: see ``Cerebrum.database.Database.query``

    :returns: matching item rows.
    """
    query = """
      SELECT {fields}
      FROM [:table schema=cerebrum name=task_queue]
      {where}
      ORDER BY {order}
    """
    clauses, binds = _select(**selects)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    return db.query(
        query.format(
            fields=', '.join(DEFAULT_FIELDS),
            where=where,
            order=', '.join(DEFAULT_ORDER),
        ),
        binds,
        fetchall=fetchall)


def sql_delete(db, **kwargs):
    """
    Delete tasks from the queue.

    See py:func:`._select` for search params.

    :param limit: upper limit of deleted items

    :returns: deleted item rows.
    """
    stmt = """
      DELETE FROM [:table schema=cerebrum name=task_queue]
      WHERE (queue, key) in (
          SELECT queue, key
          FROM [:table schema=cerebrum name=task_queue]
          {where}
          ORDER BY {order}
          {limit}
      )
      RETURNING {fields}
    """
    if kwargs.get('limit') is not None:
        limit = 'LIMIT {}'.format(int(kwargs.pop('limit')))
    else:
        limit = ''

    clauses, binds = _select(**kwargs)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    return db.query(
        stmt.format(
            where=where,
            order=', '.join(DEFAULT_ORDER),
            fields=', '.join(DEFAULT_FIELDS),
            limit=limit,
        ),
        binds,
        fetchall=True)


def sql_pop(db, queue, key):
    """
    Pop a given key from a given queue.

    :returns: the popped item row

    :raises NotFoundError: if no matching item exists.
    """
    rows = list(sql_delete(db, queues=six.text_type(queue),
                           keys=six.text_type(key)))
    if len(rows) < 1:
        raise Cerebrum.Errors.NotFoundError(
            'task_queue pop: no items in queue %r with key %r' %
            (queue, key))

    if len(rows) > 1:
        raise Cerebrum.Errors.TooManyRowsError(
            'task_queue get: multiple items in queue %r with key %r!' %
            (queue, key))

    logger.debug('popped task %s/%s', rows[0]['queue'], rows[0]['key'])

    return rows[0]


def sql_pop_next(db, queues=None, nbf=None, max_attempts=None):
    """
    Pop next item from queue.

    :returns: the popped item row

    :raises NotFoundError: if no matching item exists.
    """
    rows = list(sql_delete(db, queues=queues, nbf_before=nbf,
                           max_attempts=max_attempts, limit=1))
    if len(rows) < 1:
        raise Cerebrum.Errors.NotFoundError(
            'task_queue pop: no items in %s (nbf: %s, max_attempts: %s)'
            % (queues, nbf, max_attempts))

    if len(rows) > 1:
        raise Cerebrum.Errors.TooManyRowsError(
            'task_queue pop: removed multiple items!')

    logger.debug('popped task %s/%s', rows[0]['queue'], rows[0]['key'])
    return rows[0]


def sql_get(db, queue, key):
    """
    Get item from queue.

    :raises NotFoundError: if no matching item exists.
    """
    rows = list(sql_search(db, queues=six.text_type(queue),
                           keys=six.text_type(key), fetchall=True))
    if len(rows) < 1:
        raise Cerebrum.Errors.NotFoundError(
            'task_queue get: no items in queue %r with key %r' %
            (queue, key))

    if len(rows) > 1:
        raise Cerebrum.Errors.TooManyRowsError(
            'task_queue get: multiple items in queue %r with key %r!' %
            (queue, key))

    return rows[0]


def _sql_insert(db, queue, key, iat=None, nbf=None, attempts=None, reason=None,
                payload=None):
    """ Insert a new task into a queue.  """
    binds = {
        'queue': six.text_type(queue),
        'key': six.text_type(key),
    }

    if iat:
        # we really shouldn't ever need to set the iat
        binds['iat'] = iat
    if nbf:
        binds['nbf'] = nbf
    if attempts:
        binds['attempts'] = int(attempts)
    if reason:
        binds['reason'] = reason
    if payload:
        binds['payload'] = json.dumps(dict(payload))

    stmt = """
      INSERT INTO [:table schema=cerebrum name=task_queue]
        ({cols})
      VALUES
        ({binds})
      RETURNING {fields}
    """.format(
        cols=', '.join(sorted(binds)),
        binds=', '.join(':' + col for col in sorted(binds)),
        fields=', '.join(DEFAULT_FIELDS),
    )
    return db.query_1(stmt, binds)


def _sql_update(db, queue, key, iat=NotSet, nbf=NotSet, attempts=NotSet,
                reason=NotSet, payload=NotSet):
    """ Update an existing task in a queue. """
    binds = {
        'queue': six.text_type(queue),
        'key': six.text_type(key),
    }
    update = {}

    if iat is not NotSet:
        update['iat'] = iat
    if nbf is not NotSet:
        update['nbf'] = nbf
    if attempts is not NotSet:
        update['attempts'] = int(attempts)
    if reason is not NotSet:
        # reason is nullable, i.e. we *should* update with a None-value
        update['reason'] = reason
    if payload is not NotSet:
        if payload is None:
            update['payload'] = payload
        else:
            update['payload'] = json.dumps(dict(payload))

    binds.update(update)

    stmt = """
      UPDATE [:table schema=cerebrum name=task_queue]
      SET
        {changes}
      WHERE
        queue = :queue AND key = :key
      RETURNING {fields}
    """.format(
        changes=', '.join('{0} = :{0}'.format(k) for k in sorted(update)),
        fields=', '.join(DEFAULT_FIELDS),
    )
    return db.query_1(stmt, binds)


def _needs_update(old_row, values):
    for k in ('iat', 'nbf', 'attempts', 'reason', 'payload'):
        if values.get(k, NotSet) is NotSet:
            continue
        if values[k] == old_row[k]:
            continue
        yield k, values[k]


def sql_push(db, queue, key, attempts=NotSet, iat=NotSet, nbf=NotSet,
             reason=NotSet, payload=NotSet,
             ignore_nbf_after=False):
    """
    Insert or update a task.

    On update:
        Only keyword arguments given explicitly will be updated.  If set to the
        default value (NotSet), the field will be ignored.

    On insert:
        Only keyword arguments given explicitly will be set.  If set to the
        default value (NotSet), the field will get a default value.

    :param db:
    :param queue: a queue to push to
    :param key: unique id for this item within the queue

    :param int attempts: number of attempts at processing this item.

    :param datetime.datetime iat: issued at - create time for this item.
    :param datetime.datetime nbf: not before - do not process until this time.
    :param str reason: human readable description of this item.
    :param dict payload: extra data to include in this item

    :param bool ignore_nbf_after:
        if true, we ignore this push when the new item would replace an
        existing item but with a later nbf value.

        This field should be used when we want to keep the item in queue with a
        closer nbf time.
    """

    try:
        prev = sql_get(db, queue, key)
    except Cerebrum.Errors.NotFoundError:
        prev = dict()

    if ignore_nbf_after and prev and nbf and prev['nbf'] < nbf:
        # This is an update, and we want to ignore updates that overwrites an
        # existing item if the new nbf date would add a delay.
        logger.debug('ignoring task %s/%s: already exists with nbf %s < %s',
                     queue, key, prev['nbf'], nbf)
        return None

    values = {
        'iat': iat,
        'nbf': nbf,
        'attempts': attempts,
        'reason': reason,
        'payload': payload,
    }

    if prev:
        to_update = dict(_needs_update(prev, values))
        if to_update:
            # update the given key/value pairs
            logger.debug('updating task %s/%s with %r',
                         queue, key, to_update.keys())
            return _sql_update(db, queue, key, **to_update)
        else:
            # no change
            logger.debug('ignoring task %s/%s: nothing to update',
                         queue, key)
            return None
    else:
        logger.debug('inserting task %s/%s', queue, key)
        return _sql_insert(db, queue, key, **values)


def sql_get_queue_counts(db, **kwargs):
    """
    Get number of queued tasks.

    See py:func:`._select` for filtering params.

    :returns: rows of (queue, count) tuples
    """
    query = """
      SELECT queue, count(*) as num
      FROM [:table schema=cerebrum name=task_queue]
      {where}
      GROUP BY queue
      ORDER BY queue
    """
    clauses, binds = _select(**kwargs)

    if clauses:
        where = ' WHERE ' + ' AND '.join(clauses)
    else:
        where = ''

    return db.query(query.format(where=where), binds, fetchall=True)


class TaskQueue(DatabaseAccessor):
    """ Access the task queue. """

    def find(self, queue, key):
        return db_row_to_task(sql_get(self._db, queue, key))

    def get(self, queue, key):
        try:
            return self.find(queue, key)
        except Cerebrum.Errors.NotFoundError:
            return None

    def pop(self, queue, key):
        return db_row_to_task(sql_pop(self._db, queue, key))

    def pop_next(self, *args, **kwargs):
        return db_row_to_task(sql_pop_next(self._db, *args, **kwargs))

    def search(self, **fields):
        for row in sql_search(self._db, **fields):
            yield db_row_to_task(row)

    def push(self, task, ignore_nbf_after=False):
        kwargs = task.to_dict()
        kwargs['ignore_nbf_after'] = ignore_nbf_after
        row = sql_push(self._db, **kwargs)
        return db_row_to_task(row, allow_empty=True)
