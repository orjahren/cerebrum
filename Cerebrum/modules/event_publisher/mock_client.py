#!/usr/bin/env python
# encoding: utf-8
#
# Copyright 2015 University of Oslo, Norway
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

"""Mock client usable with the EventPublisher.

Messages and operations (i.e. publish and commit) are logged."""

from Cerebrum.Utils import Factory


class MockClient(object):
    def __init__(self, config):
        self.logger = Factory.get_logger("cronjob")

    def publish(self, routing_key, message):
        self.logger.info("Publishing: routing_key={} message={}".format(
            routing_key, message))

    def rollback(self):
        self.logger.info("Rolling back")

    def commit(self):
        self.logger.info("Commiting")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, trace):
        return
