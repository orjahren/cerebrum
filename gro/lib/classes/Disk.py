# -*- coding: iso-8859-1 -*-
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

import Cerebrum.Disk

import Registry
registry = Registry.get_registry()

Entity = registry.Entity
Host = registry.Host

CerebrumAttr = registry.CerebrumAttr
CerebrumEntityAttr = registry.CerebrumEntityAttr

__all__ = ['Disk']

class Disk(Entity):
    slots = Entity.slots + [CerebrumEntityAttr('host', 'Host', Host, 'host_id', write=True),
                            CerebrumAttr('path', 'string', write=True),
                            CerebrumAttr('description', 'string', write=True)]

    cerebrum_class = Cerebrum.Disk.Disk

# arch-tag: 239b4bea-84e4-412d-9158-e1af43362885
