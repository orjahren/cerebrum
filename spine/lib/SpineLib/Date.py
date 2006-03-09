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

import mx.DateTime

from Builder import Builder, Attribute
import SpineExceptions

import Registry
registry = Registry.get_registry()

__all__ = ['Date']

class Date(Builder):
    slots = (
        Attribute('format', str, write=True),
    )

    def __init__(self, value, *args, **vargs):
        super(Date, self).__init__(*args, **vargs)
        self._value = value

    def get_primary_key(self):
        return (self._value, )

    for i in ('year', 'month', 'day', 'hour', 'minute', 'second'):
        exec 'def get_%s(self):\n return self._value.%s\nget_%s.signature = int' % (i, i, i)
    def get_unix(self):
        return int(self._value.ticks())
    get_unix.signature = int

    def strftime(self, formatstr):
        return self._value.strftime(formatstr)

    strftime.signature = str
    strftime.signature_args = [str]

    def to_string(self):
        format = getattr(self, self.get_attr('format').get_name_private(), None)
        if format is None:
            return str(self._value)
        else:
            return self.strftime(format)

    to_string.signature = str

registry.register_class(Date)

# arch-tag: 57d51c14-a6c9-4913-a011-1f7222ad79b5
