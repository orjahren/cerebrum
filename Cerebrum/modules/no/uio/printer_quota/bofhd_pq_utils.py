# -*- coding: utf-8 -*-
# Copyright 2004-2018 University of Oslo, Norway
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

import os
import time

import six

import cereconf

from Cerebrum import Account
from Cerebrum import Constants
from Cerebrum import Errors
from Cerebrum import Person
from Cerebrum.modules.no.uio.printer_quota import PaidPrinterQuotas
from Cerebrum.modules.no.uio.printer_quota import errors


class SimpleLogger(object):
    # Unfortunately we cannot user Factory.get_logger due to the
    # singleton behaviour of cerelog.get_logger().  Once this is
    # fixed, this class can be removed.
    def __init__(self, fname):
        self.stream = open(
            os.path.join(cereconf.AUTOADMIN_LOG_DIR, fname), 'a+')

    def show_msg(self, lvl, msg, *args, **kwargs):
        self.stream.write("%s %s [%i] %s\n" % (
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            lvl, os.getpid(), msg % args))
        self.stream.flush()

    def debug2(self, msg, *args, **kwargs):
        self.show_msg("DEBUG2", msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self.show_msg("DEBUG", msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.show_msg("INFO", msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.show_msg("ERROR", msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        self.show_msg("FATAL", msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.show_msg("CRITICAL", msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.show_msg("WARN", msg, *args, **kwargs)


class BofhdUtils(object):

    def __init__(self, db, const):
        self.db = db
        self.const = const
        self.uname_cache = {}

    def get_pquota_status(self, person_id):
        ppq = PaidPrinterQuotas.PaidPrinterQuotas(self.db)
        try:
            row = ppq.find(person_id)
        except Errors.NotFoundError:
            raise errors.UserHasNoQuota("User has no quota")
        return row

    def get_bdate_and_pnum(self, person_id):
        """Return birth date and person number in the form expected by
        FS.  If the person has no fodselsnr from FS, NotFoundError is
        raised.

        """
        person = Person.Person(self.db)
        person.find(person_id)
        row = person.get_external_id(source_system=self.const.system_fs,
                                     id_type=self.const.externalid_fodselsnr)
        if not row:
            raise errors.NotFoundError("Person has no fnr from FS")
        fnum = row[0]['external_id']
        return int(fnum[:6]), int(fnum[6:])


    def find_pq_person(self, fnr):
        """Returns person_id by doing fnr lookup in the order
        specified by 'betaling for utskrift': spesifikasjon.txt"""
        person = Person.Person(self.db)
        person.clear()
        for ss in (self.const.system_fs, self.const.system_sap,
                   self.const.system_manual):
            try:
                person.find_by_external_id(
                    self.const.externalid_fodselsnr, fnr, source_system=ss)
                return person.entity_id
            except Errors.NotFoundError:
                pass
        raise errors.NotFoundError("No person with fnr=%s" % fnr)

    def _map_person_id(self, id_data):
        """Map <id_type:id> to const.<id_type>, id.  Recognizes
        fødselsnummer without <id_type>.  Also recognizes entity_id"""
        if id_data.isdigit() and len(id_data) >= 10:
            return self.const.externalid_fodselsnr, id_data
        if id_data.find(":") == -1:     # Assume it is an account
            return "account_name", id_data

        id_type, id_data = id_data.split(":", 1)
        if id_type != 'entity_id':
            id_type = self.const.EntityExternalId(id_type)
        if id_type is not None:
            return id_type, id_data
        raise errors.NotFoundError, "Unknown person_id type"

    def find_person(self, id_data, id_type=None):
        """Return person_id matching id_data.  id_data can be an
        account name or an id_type:id string as well as an 11 digit
        fødselsnummer."""

        if not id_type:
            id_type, id_data = self._map_person_id(id_data)

        person = Person.Person(self.db)
        person.clear()
        try:
            if six.text_type(id_type) == 'account_name':
                ac = self.get_account(id_data)
                person.find(ac.owner_id)
            elif isinstance(id_type, Constants._CerebrumCode):
                if int(id_type) == int(self.const.externalid_fodselsnr):
                    return self.find_pq_person(id_data)
                person.find_by_external_id(id_type, id_data)
            elif id_type == 'entity_id':
                person.find(id_data)
            else:
                raise errors.NotFoundError, "Unknown id_type"
        except Errors.NotFoundError:
            raise errors.NotFoundError, "Could not find person with %s=%s" % (
                id_type, id_data)
        except Errors.TooManyRowsError:
            raise errors.NotFoundError, "ID not unique %s=%s" % (id_type, id_data)
        return person.entity_id

    def get_uname(self, entity_id):
        if not self.uname_cache.has_key(entity_id):
            ac = self.get_account(entity_id, id_type='id')
            self.uname_cache[entity_id] = ac.account_name
        return self.uname_cache[entity_id]

    def get_account(self, id_data, id_type=None):
        account = Account.Account(self.db)
        account.clear()
        try:
            if id_type is None:
                if id_data.find(":") != -1:
                    id_type, id_data = id_data.split(":", 1)
                else:
                    id_type = 'name'
            if id_type == 'name':
                account.find_by_name(id_data, self.const.account_namespace)
            elif id_type == 'id':
                account.find(id_data)
            else:
                raise errors.NotFoundError, "unknown id_type: '%s'" % id_type
        except Errors.NotFoundError:
            raise errors.NotFoundError(
                "Could not find Account with %s=%s" % (id_type, id_data))
        return account

