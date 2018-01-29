# -*- coding: utf-8 -*-
# Copyright 2002, 2003 University of Oslo, Norway
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

"""Cache - memory- and/or time-limited dictionary types.

Cache instances work just like ordinary python dictionaries, with one
exception: They can forget things without you explicitly asking them
to.

Which algorithm to use when deciding which data should be forgotten
first can be specified by passing a sequence of mix-in classes as the
``mixins`` argument of the Cache constructor.

Some of the mix-in classes take additional keyword arguments.  These
can also be given to the Cache ctor, or they can be passed to that
mix-in class's setup() method:


  >>> c = Cache(mixins=[cache_slots], size=50)
  >>> for x in range(100):
  ...     c[x] = chr(x)
  ...
  >>> print len(c)
  50

The setup() method can also be used to change the parameters of a
cache holding data:

  >>> cache_slots.setup(c, size=60)
  >>> c[127] = chr(127)
  >>> print len(c)
  51

"""

import time
from threading import Lock


class Cache(dict):

    """Constructor class for cache instances."""
    def __new__(cls, mixins=(), **kwargs):
        bases = [cache_base]
        bases.extend(mixins)
        bases = tuple(bases)
        cache_class = type('cache', bases, {})
        # Return an instance of the freshly generated type.  Python
        # will call the __init__() method of this instance with the
        # same arguments we received in this __new__() call.
        return dict.__new__(cache_class)


class cache_base(Cache):

    """Minimal base class of 'cache' types."""

    def __init__(self, mixins=(), **kwargs):
        self._lock = Lock()
        dict.__init__(self)
        # if self._lock.acquire is called when we already have the
        # lock, a deadlock occours.  A number of mix-ins for
        # __setitem__ calls __delitem__.  These mixins must set
        # self._dont_lock=True to prevent __delitem__ from trying to
        # aquire the lock.
        self._dont_lock = False
        self.registry = []
        for cls in mixins:
            if hasattr(cls, 'setup'):
                cls.setup(self, **kwargs)

    def __setitem__(self, key, value):
        self._lock.acquire()
        try:
            if not dict.has_key(self, key):
                self.registry.insert(0, key)
            return super(cache_base, self).__setitem__(key, value)
        finally:
            self._lock.release()

    def __delitem__(self, key):
        if not self._dont_lock:
            self._lock.acquire()
        did_lock = not self._dont_lock
        try:
            ret = super(cache_base, self).__delitem__(key)
            self.registry.remove(key)
            return ret
        finally:
            if did_lock:
                self._lock.release()

    def __getitem__(self, key):
        self._lock.acquire()
        try:
            return super(cache_base, self).__getitem__(key)
        finally:
            self._lock.release()

# Invariants:
#  * self.registry must contain a single entry for `key` immediately
#    before and immediately after executing the __setitem__ method of
#    a mixin class.
#  * self.registry must contain a single entry for `key` immediately
#    before and immediately after executing the __delitem__ or
#    __getitem__ methods of a mixin class with a `key` that is present
#    in the cache.


class cache_mru(Cache):

    """Mixin class that gives a cache Most-Recently-Used behaviour."""

    def __getitem__(self, key):
        ret = super(cache_mru, self).__getitem__(key)
        if self.registry[0] != key:
            self.registry.remove(key)
            self.registry.insert(0, key)
        return ret

    def __setitem__(self, key, value):
        ret = super(cache_mru, self).__setitem__(key, value)
        if self.registry[0] != key:
            self.registry.remove(key)
            self.registry.insert(0, key)
        return ret


class cache_slots(Cache):

    """Mixin class that restricts the maximum number of slots in a cache."""

    def setup(self, **kwargs):
        self.size = kwargs.get('size', 100)

    def __setitem__(self, key, value):
        ret = super(cache_slots, self).__setitem__(key, value)
        while len(self.registry) > self.size:
            stale_key = self.registry[-1]
            self._dont_lock = True
            self.__delitem__(stale_key)
            self._dont_lock = False
        return ret


class cache_timeout(Cache):

    """Mixin class that implements a timeout on cached elements."""

    def setup(self, **kwargs):
        import time
        self.timestamps = {}
        self.timeout = kwargs.get('timeout', 60 * 5)

    def __setitem__(self, key, value):
        ret = super(cache_timeout, self).__setitem__(key, value)
        self.timestamps[key] = time.time()
        return ret

    def __delitem__(self, key, **kwargs):
        self._dont_lock = True
        ret = super(cache_timeout, self).__delitem__(key)
        self._dont_lock = False
        del self.timestamps[key]
        return ret

    def __getitem__(self, key):
        val = super(cache_timeout, self).__getitem__(key)
        if time.time() - self.timestamps[key] >= self.timeout:
            self._dont_lock = True
            self.__delitem__(key)
            self._dont_lock = False
            raise KeyError, "Timed out"
        return val


def memoize_function(function, cache_type=Cache, **kwargs):
    """
    Return a wrapper around FUNCTION that caches previously computed
    results. KWARGS is passed to CACHE_TYPE.
    """

    cache = cache_type(**kwargs)

    def memoized(*rest):
        if rest in cache:
            return cache[rest]

        result = function(*rest)
        cache[rest] = result
        return result

    return memoized

