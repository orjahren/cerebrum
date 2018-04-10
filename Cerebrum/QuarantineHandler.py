#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2018 University of Oslo, Norway
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

"""This module decides how a quaratine should take effect by matching
rules in cereconf.QUARANTINE_RULES with the quarantines that an entity
is reported to have.  This is done by providing methods that can be
queried for the requested operation.

The format of cereconf.QUARANTINE_RULES is
  { <quarantine_code_str>: [ {
         'lock': <0|1>,  'shell': <shell>, ....,
         'spread': spread_code|[spread_codes]
         'sort_num': unique_number
       } ] }

I.e, a dict where the quarantine name is the key, and the value is a
list of dicts.  (If only one dict is required, it can be used as the
value on its own.)

The 'spread' attribute in the inner dict is optional.  If set, the
quarantine rule will only apply when the quarantine handler has been
initialised to include this spread (or spreads, if the value is a
list).  The dict with spread name '*' or without a spread key holds
the default values.

When evaluating the quarantine behaviour, e.g. 'shell', the dicts for
the spreads (which are specified when initialising the
QuarantineHandler object) are matched in order until one which
specifies 'shell' is found.  The order is the integer value of the
quarantine code which is essentially random.  A specific order can be
set using the 'sort_num' key, if so, all dicts must contain a unique
'sort_num' value.  If the handler was initialised with an empty list
of spreads, only the default values will be used.
"""

import six

import cereconf
from Cerebrum import Entity
from Cerebrum.Utils import Factory
from collections import defaultdict

const = Factory.get("Constants")


class QuarantineHandler(object):
    qc2rules = {}
    _explicit_sort = False

    def __init__(self, database, quarantines, spreads=None):
        """Constructs a QuarantineHandler.  quarantines should point
        to the quarantines that the user currently has.  Spreads is
        optional, and points to an optional list of spreads limiting
        the places where the QuarantineHandler will have effect.
        """
        if len(self.qc2rules) == 0:
            # Initial setup only done once.
            #
            # Converting strings to Constants and build:
            #
            # self.qc2rules = {'qc': {'spread_code': {settings} } }
            used_sort_nums = []
            for code, rules in cereconf.QUARANTINE_RULES.items():
                qc_rules = {}
                self.qc2rules[int(const.Quarantine(code))] = qc_rules
                if isinstance(rules, dict):
                    rules = (rules,)
                for r in rules:
                    settings = r.copy()
                    used_sort_nums.append(settings.get('sort_num', None))
                    if 'spread' in settings:
                        tmp_spreads = settings['spread']
                        del(settings['spread'])
                    else:
                        tmp_spreads = ('*',)
                    if isinstance(tmp_spreads, six.text_type):
                        tmp_spreads = (tmp_spreads,)
                    for c in tmp_spreads:
                        if c != '*':
                            c = int(const.Spread(c))
                        qc_rules[c] = settings
            # sort_num must be unique if used
            orig_len = len(used_sort_nums)
            used_sort_nums = dict([(t, None) for t in used_sort_nums
                                   if t is not None]).keys()
            if len(used_sort_nums) != 0 and orig_len != len(used_sort_nums):
                raise ValueError("sort_num in QUARANTINE_RULES illegal")
            if used_sort_nums:
                QuarantineHandler._explicit_sort = True
        if quarantines is None:
            quarantines = []
        self.quarantines = quarantines
        if spreads is None:
            spreads = []
        self.spreads = [int(s) for s in spreads]
        # Append the '*' spread last to do the check against settings
        # for this spread last.
        self.spreads.append('*')

    def _get_matches(self):
        ret = []
        for q in self.quarantines:
            try:
                spread2settings = self.qc2rules[int(q)]
            except KeyError:
                continue
            # Note that for each spread, we only extract the first
            # matching setting.  Otherwise it would not be possible to
            # have a quarantine that did not lock the account for a
            # specific spread.
            for spread in self.spreads:
                if spread in spread2settings:
                    ret.append((spread2settings[spread], int(q)))
                    break
        if self._explicit_sort:
            ret.sort(lambda a, b: a[0]['sort_num'] - b[0]['sort_num'])
        else:
            ret.sort(lambda a, b: a[1] - b[1])
        return [s[0] for s in ret]

    def get_shell(self):
        for m in self._get_matches():
            shell = m.get('shell', None)
            if shell is not None:
                return shell
        return None

    def should_skip(self):
        for m in self._get_matches():
            if m.get('skip', False):
                return True
        return False

    def is_locked(self):
        """The account should be known, but the account locked"""
        for m in self._get_matches():
            if m.get('lock', False):
                return True
        return False

    @staticmethod
    def check_entity_quarantines(db, entity_id, spreads=None):
        """Utility method that returns an initiated QuarantineHandler
        for a given entity_id"""
        eq = Entity.EntityQuarantine(db)
        eq.find(entity_id)
        return QuarantineHandler(
            db, [int(row['quarantine_type'])
                 for row in eq.get_entity_quarantine(only_active=True)],
            spreads)

    @staticmethod
    def get_locked_entities(db, entity_types=None, only_active=True,
                            entity_ids=None, ignore_quarantine_types=None):
        """Utility method that the returns the entity-id of all locked accounts.

        :param db: A database object
        :param entity_types: Entity types to filter on
        :param only_active: Only return locked and active quarantines
        :param entity_ids: Spesific entity-ids to check
        :param ignore_quarantine_types: Quarantines to ignore"""
        cache = defaultdict(list)
        eq = Entity.EntityQuarantine(db)
        for row in eq.list_entity_quarantines(
                entity_types=entity_types,
                only_active=only_active,
                entity_ids=entity_ids,
                ignore_quarantine_types=ignore_quarantine_types):
            cache[row['entity_id']].append(
                row['quarantine_type'])

        def is_locked(key):
            return QuarantineHandler(db, cache.get(key)).is_locked()
        return set(filter(is_locked, cache.keys()))


def _test():
    # TODO: This should use the unit-testing framework, and use common
    # constants (which we currently don't have for spreads)
    cereconf.QUARANTINE_RULES = {
        'nologin': {'lock': 1, 'shell': 'nologin-shell', 'sort_num': 10},
        'system': [{'lock': 1, 'shell': 'nologin-shell2', 'sort_num': 2},
                   {'spread': 'AD_account', 'shell': 'ad-shell', 'sort_num': 3}]
    }
    from Cerebrum.Utils import Factory
    db = Factory.get('Database')()
    co = Factory.get('Constants')(db)

    # Check with old cereconf syntax
    qh = QuarantineHandler(db, (co.quarantine_nologin,))
    print "nolgin: L=%i, S=%s" % (qh.is_locked(), qh.get_shell())

    # New cereconf syntax, non-spread spesific
    qh = QuarantineHandler(db, (co.quarantine_system,))
    print "system: L=%i, S=%s" % (qh.is_locked(), qh.get_shell())

    # spread-spesific quarantine action, should not be locked
    qh = QuarantineHandler(db, (co.quarantine_system,),
                           spreads=(co.spread_uio_ad_account,))
    print "system & AD: L=%i, S=%s" % (qh.is_locked(), qh.get_shell())

    # spread-specific quarantine action and another quarantine that
    # requires lock
    qh = QuarantineHandler(db, (co.quarantine_system, co.quarantine_nologin),
                           spreads=(co.spread_uio_ad_account,))
    print "system & AD & L: L=%i, S=%s" % (qh.is_locked(), qh.get_shell())

    qh = QuarantineHandler.check_entity_quarantines(db, 67201)
    print "An entity: L=%i, S=%s" % (qh.is_locked(), qh.get_shell())

if __name__ == '__main__':
    _test()
