#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2013 University of Oslo, Norway
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
"""Account mixin for the TSD project.

Accounts in TSD needs to be controlled. The most important issue is that one
account is only allowed to be a part of one single project, which is why we
should refuse account_types from different OUs for a single account.

"""

import base64
import re

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Account
from Cerebrum import Errors
from Cerebrum.modules import EntityTrait
from Cerebrum.modules.no.uio.DiskQuota import DiskQuota
from Cerebrum.modules.bofhd.utils import BofhdRequests
from Cerebrum.modules import dns
from Cerebrum.Utils import pgp_encrypt, Factory

from Cerebrum.modules.tsd import TSDUtils

class AccountTSDMixin(Account.Account):
    """Account mixin class for TSD specific behaviour.

    Accounts should only be part of a single project (OU), and should for
    instance have defined a One Time Password (OTP) key for two-factor
    authentication.

    """

    # TODO: create and deactive - do they need to be subclassed?

    @property
    def has_autofreeze_quarantine(self):
        """
        has_autofreeze_quarantine-property - getter

        :rtype: bool
        :return: Return True if the account has autofreeze quarantine(s),
            otherwise - False
        """
        return bool(
            self.get_entity_quarantine(
                qtype=self.const.quarantine_auto_frozen))

    @property
    def autofreeze_quarantine_start(self):
        """
        autofreeze_quarantine_start-property - getter

        :rtype: mx.DateTime or None
        :return: Return the start_date of the autofreeze quarantine
            (Note: None will be returned in a case of no autofreeze-quarantines
            for the Account. Hence mx.DateTime return value is a proof that
            the Account has at least one autofreeze-quarantine, while return
            value None is not a proof of the opposite
        """
        auto_frozen_quarantines = self.get_entity_quarantine(
            qtype=self.const.quarantine_auto_frozen)
        if auto_frozen_quarantines:
            return auto_frozen_quarantines[0]['start_date']
        return None

    def remove_autofreeze_quarantine(self):
        """A wrapper method that removes autofreeze quarantine
        from the account. It is equivalent to:
        self.delete_entity_quarantine(const.quarantine_auto_frozen)
        """
        self.delete_entity_quarantine(self.const.quarantine_auto_frozen)

    def add_autofreeze_quarantine(self, *args, **kwargs):
        """A wrapper method that adds autofreeze quarantine
        to the account. It is equivalent to:
        self.add_entity_quarantine(const.quarantine_auto_frozen, *args, **kw)
        """
        self.add_entity_quarantine(self.const.quarantine_auto_frozen,
                                   *args,
                                   **kwargs)

    def set_account_type(self, ou_id, affiliation, priority=None):
        """Subclass setting of the account_type.

        Since OUs are treated as separate projects in TSD, we need to add some
        protection to them. An account should only be allowed to be part of a
        single OU, no others, to avoid mixing different projects' data.

        """
        if affiliation == self.const.affiliation_project:
            for row in self.list_accounts_by_type(account_id=self.entity_id,
                                affiliation=self.const.affiliation_project,
                                # We want the deleted ones too, as the account
                                # could have previously been part of a project:
                                filter_expired=False):
                if row['ou_id'] != ou_id:
                    raise Errors.CerebrumError('Account already part of other '
                                               'project OUs')
        return self.__super.set_account_type(ou_id, affiliation, priority)

    def get_tsd_project_id(self):
        """Helper method for getting the ou_id for the account's project.

        @rtype: int
        @return:
            The entity_id for the TSD project the account is affiliated with.

        @raise NotFoundError:
            If the account is not affiliated with any project.

        @raise Exception:
            If the account has more than one project affiliation, which is not
            allowed in TSD, or if the account is not affiliated with any
            project.

        """
        rows = self.list_accounts_by_type(
                    account_id=self.entity_id,
                    affiliation=self.const.affiliation_project)
        assert len(rows) < 2, "Account affiliated with more than one project"
        for row in rows:
            return row['ou_id']
        raise Errors.NotFoundError('Account not affiliated with any project')

    def get_username_without_project(self, username=None):
        """Helper method for fetching the username without the project prefix.

        This was originally not needed, but due to changes in the requirements
        we unfortunately need to a downstripped username from time to time.

        If the format of the project prefix changes in the future, we need to
        expand this method later.

        @type username: str
        @param username:
            A username with a project prefix. If not given, we expect that
            L{self.account_name} is available.

        @rtype: str
        @return:
            The username without the project prefix.

        @raise Exception:
            If the username does not have the format of project accounts.

        """
        if username is None:
            username = self.account_name
        # Users that not fullfill the project format
        if '-' not in username:
            raise Exception("User is not a project account: %s" % username)
        return username[4:]

    def _generate_otpkey(self, length=192):
        """Return a randomly generated OTP key of the given length.

        @type length: int
        @param length:
            The number of bits that should be generated. Note that the number is
            rounded upwards to be contained in a full byte (8 bits).

        @rtype: str
        @return:
            The OTP key, formed as a string of the hexadecimal values. Each
            hexadecimal value represent 8 bits.

        """
        # Round upwards to nearest full byte by adding 7 to the number of bits.
        # This makes sure that it's always rounded upwards if not modulo 0 to 8.
        bytes = (length + 7) / 8
        ret = ''
        f = open('/dev/urandom', 'rb')
        # f.read _could_ return less than what is needed, so need to make sure
        # that we have enough data, in case the read should stop:
        while len(ret) < bytes:
            ret += f.read(bytes - len(ret))
        f.close()
        return ret

    def regenerate_otpkey(self, tokentype=None):
        """Create a new OTP key for the account.

        Note that we do not store the OTP key in Cerebrum. We only pass it on to
        the Gateway, so it's only stored one place. Other requirements could
        change this in the future.

        The OTP type, e.g. hotp or totp, is retrieved from the person's trait.

        @type tokentype: str
        @param tokentype:
            What token type the OTP should become, e.g. 'totp' or 'hotp'. Note
            that it could also be translated by L{cereconf.OTP_MAPPING_TYPES} if
            it matches a value there.

            If this parameter is None, the person's default OTP type will be
            used, or 'totp' by default if no value is set for the person.

        @rtype: string
        @return:
            The full URI of otpauth, as defined in cereconf.OTP_URI_FORMAT,
            filled with the proper data. The format should follow
            https://code.google.com/p/google-authenticator/wiki/KeyUriFormat

        """
        # Generate a new key:
        secret = base64.b32encode(self._generate_otpkey(
                                    getattr(cereconf, 'OTP_KEY_LENGTH', 160)))
        # Get the tokentype
        if not tokentype:
            tokentype = 'totp'
            if self.owner_type == self.const.entity_person:
                pe = Factory.get('Person')(self._db)
                pe.find(self.owner_id)
                typetrait = pe.get_trait(self.const.trait_otp_device)
                if typetrait:
                    tokentype = typetrait['strval']

        # A mapping from e.g. Nettskjema's smartphone_yes -> topt:
        mapping = getattr(cereconf, 'OTP_MAPPING_TYPES', {})
        try:
            tokentype = mapping[tokentype]
        except KeyError:
            raise Errors.CerebrumError('Invalid tokentype: %s' % tokentype)
        return cereconf.OTP_URI_FORMAT % {
                'secret': secret,
                'user': '%s@%s' % (self.account_name,
                                   cereconf.INSTITUTION_DOMAIN_NAME),
                'type': tokentype,
                }

    def illegal_name(self, name):
        """TSD's checks on what is a legal username.

        This checks both project accounts and system accounts, so the project
        prefix is not checked.

        """
        tmp = super(AccountTSDMixin, self).illegal_name(name)
        if tmp:
            return tmp
        if len(name) > getattr(cereconf, 'USERNAME_MAX_LENGTH', 12):
            return "too long (%s)" % name
        if re.search("^[^A-Za-z]", name):
            return "must start with a character (%s)" % name
        if re.search("[^A-Za-z0-9\-_]", name):
            return "contains illegal characters (%s)" % name
        return False

    def is_approved(self):
        """Return if the user is approved for a TSD project or not.

        The approval is in two levels: First, the TSD project (OU) must be
        approved, then the account must not be quarantined.

        :rtype: bool
        :return: True i

        """
        # Check user quarantine:
        if self.get_entity_quarantine(qtype=self.const.quarantine_not_approved,
                                      only_active=True):
            return False
        # Check if OU is approved:
        try:
            projectid = self.get_tsd_project_id()
        except Errors.NotFoundError:
            # Not affiliated with any project, therefore not approved
            return False
        ou = Factory.get('OU')(self._db)
        ou.clear()
        ou.find(projectid)
        return ou.is_approved()

    def suggest_unames(self,
                       domain,
                       fname,
                       lname,
                       maxlen=8,
                       suffix="",
                       prefix=""):
        """
        N.B. This is a legacy method ported from Crebrum/Account.py
        The `prefix` argument is now deprecated

        Returns a tuple with 15 (unused) username suggestions based
        on the person's first and last name.

        domain: value domain code
        fname:  first name (and any middle names)
        lname:  last name
        maxlen: maximum length of a username (incl. the suffix)
        suffix: string to append to every generated username
        prefix: string to add to every generated username (deprecated)
        """
        goal = 15       # We may return more than this
        maxlen -= len(suffix)
        maxlen -= len(prefix)
        assert maxlen > 0, "maxlen - prefix - suffix = no characters left"
        potuname = ()

        lastname = self.simplify_name(lname, alt=1)
        if lastname == "":
            raise ValueError(
                "Must supply last name, got '%s', '%s'" % (fname, lname))

        fname = self.simplify_name(fname, alt=1)
        lname = lastname

        if fname == "":
            # This is a person with no first name.  We "fool" the
            # algorithm below by switching the names around.  This
            # will always lead to suggesting names with numerals added
            # to the end since there are only 8 possible usernames for
            # a name of length 8 or more.  (assuming maxlen=8)
            fname = lname
            lname = ""

        # We ignore hyphens in the last name, but extract the
        # initials from the first name(s).
        lname = lname.replace('-', '').replace(' ', '')
        initials = [n[0] for n in re.split(r'[ -]', fname)]

        # firstinit is set to the initials of the first two names if
        # the person has three or more first names, so firstinit and
        # initial never overlap.
        firstinit = ""
        initial = None
        if len(initials) >= 3:
            firstinit = "".join(initials[:2])
        # initial is taken from the last first name.
        if len(initials) > 1:
            initial = initials[-1]

        # Now remove all hyphens and keep just the first name.  People
        # called "Geir-Ove Johnsen Hansen" generally prefer "geirove"
        # to just "geir".

        fname = fname.replace('-', '').split(" ")[0][0:maxlen]

        # For people with many (more than three) names, we prefer to
        # use all initials.
        # Example:  Geir-Ove Johnsen Hansen
        #           ffff fff i       llllll
        # Here, firstinit is "GO" and initial is "J".
        #
        # gohansen gojhanse gohanse gojhanse ... goh gojh
        # ssllllll ssilllll sslllll ssilllll     ssl ssil
        #
        # ("ss" means firstinit, "i" means initial, "l" means last name)

        if len(firstinit) > 1:
            llen = min(len(lname), maxlen - len(firstinit))
            for j in range(llen, 0, -1):
                un = prefix + firstinit + lname[0:j] + suffix
                if self.validate_new_uname(domain, un):
                    potuname += (un, )

                if initial and len(firstinit) + 1 + j <= maxlen:
                    un = prefix + firstinit + initial + lname[0:j] + suffix
                    if self.validate_new_uname(domain, un):
                        potuname += (un, )

                if len(potuname) >= goal:
                    break

        # Now try different substrings from first and last name.
        #
        # geiroveh,
        # fffffffl
        # geirovjh geirovh geirovha,
        # ffffffil ffffffl ffffffll
        # geirojh geiroh geirojha geiroha geirohan,
        # fffffil fffffl fffffill fffffll ffffflll
        # geirjh geirh geirjha geirha geirjhan geirhan geirhans
        # ffffil ffffl ffffill ffffll ffffilll fffflll ffffllll
        # ...
        # gjh gh gjha gha gjhan ghan ... gjhansen ghansen
        # fil fl fill fll filll flll     fillllll fllllll

        flen = min(len(fname), maxlen - 1)
        for i in range(flen, 0, -1):
            llim = min(len(lname), maxlen - i)
            for j in range(1, llim + 1):
                if initial:
                    # Is there room for an initial?
                    if j < llim:
                        un = prefix + \
                            fname[0:i] + initial + lname[0:j] + suffix
                        if self.validate_new_uname(domain, un):
                            potuname += (un, )
                un = prefix + fname[0:i] + lname[0:j] + suffix
                if self.validate_new_uname(domain, un):
                    potuname += (un, )
            if len(potuname) >= goal:
                break

        # Try prefixes of the first name with nothing added.  This is
        # the only rule which generates usernames for persons with no
        # _first_ name.
        #
        # geirove, geirov, geiro, geir, gei, ge

        flen = min(len(fname), maxlen)
        for i in range(flen, 1, -1):
            un = prefix + fname[0:i] + suffix
            if self.validate_new_uname(domain, un):
                potuname += (un, )
            if len(potuname) >= goal:
                break

        # Absolutely last ditch effort:  geirov1, geirov2 etc.
        i = 1
        prefix = (fname + lname)[:maxlen - 2]

        while len(potuname) < goal and i < 100:
            un = prefix + str(i) + suffix
            i += 1
            if self.validate_new_uname(domain, un):
                potuname += (un, )
        return potuname
