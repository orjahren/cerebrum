#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2003-2016 University of Oslo, Norway
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
""" This module contains simple password checks.

The CheckSimpleMixin class is an adoption of the old PasswordChecker class, and
used to check simple password constraints.

HISTORY
-------
This module was moved from Cerebrum.modules.PasswordChecker. For the old
structure of the dictionary checks, please see:

> commit 9a01d8b6ac93513a57ac8d6393de842939582f51
> Mon Jul 20 14:12:55 2015 +0200

"""

import re
import operator

from Cerebrum.Errors import NotFoundError
from Cerebrum.Utils import Factory

from .checker import pwchecker, PasswordChecker, l33t_speak


# TODO: Should we really disallow characters from passwords?
@pwchecker('space_or_null')
class CheckSpaceOrNull(PasswordChecker):
    """ Check for space or null in password string. """

    def __init__(self):
        self._requirement = _(
            'Must not contain a space or the special null character.')
        self._password_illegal_chars = {
            '\0': _('Password cannot contain the null character.'),
            ' ': _('Password cannot contain space.'), }

    def check_password(self, password, account=None):
        """ Check that only valid characters are allowed. """
        errors = []

        for char, err in self._password_illegal_chars.iteritems():
            if char in password:
                errors.append(err)

        return errors


# TODO: Should we really disallow characters from passwords?
@pwchecker('8bit_characters')
class CheckEightBitChars(PasswordChecker):
    """ Check for 8-bit characters in password string. """

    def __init__(self):
        self._requirement = _(u'Must not contain 8-bit characters (e.g. æøå).')

    def check_password(self, password, account=None):
        """ Check that only valid characters are allowed. """
        if re.search(r'[\200-\376]', password):
            return [_(u'Password cannot contain 8-bit characters (e.g. æøå).')]


@pwchecker('length')
class CheckLengthMixin(PasswordChecker):
    """ Check for minimum and maximum password length. """

    def __init__(self, min_length=8, max_length=None):
        self.min_length = min_length
        self.max_length = max_length

        if not max_length:
            self._requirement = _(
                'Must be at least {min_length} characters.').format(
                    min_length=min_length)
        else:
            self._requirement = _(
                'Must be at least {min_length} and at most '
                '{max_length} characters.').format(min_length=min_length,
                                                   max_length=max_length)

    def check_password(self, password, account=None):
        """Check the length of the password.

        The password must be at least _password_min_length long and at most
        _password_max_length long.

        """
        if (self.min_length is not None and
                len(password.strip()) < self.min_length):
            return [
                _('Password must be at least {min_length} '
                  'characters long.').format(min_length=self.min_length)]

        if (self.max_length is not None and
                len(password) > self.max_length):
            return [
                _('Password must be at most {max_length} characters '
                  'long.').format(max_length=self.max_length)]


@pwchecker('multiple_character_sets')
class CheckMultipleCharacterSets(PasswordChecker):
    """ Adds a entropy check to password checker. """

    def __init__(self):
        self._requirement = _('Something')

    def check_password(self, password, account=None):
        """ Check that a password use multiple character sets.

        The password must contain characters from at least three
        of the following sets:

          - lowecase
          - uppercase
          - digit
          - special char

        """

        # TODO: Write proper regex, so that we don't have to truncate the
        # password
        first_eight = password[0:8]

        good_try = variation = 0
        if re.search(r'[a-z]', first_eight):
            variation += 1
        if re.search(r'[A-Z][^A-Z]{7}', first_eight):
            # The only upper case character in the first 8 characters is in
            # position 1
            good_try += 1
        if re.search(r'[A-Z]', first_eight[1:8]):
            # Contains at least 1 upper case char in pos 1-8.
            variation += 1
        if re.search(r'[^0-9]{7}[0-9]', first_eight):
            # Only number (in the first eight chars), is the last char
            good_try += 1
        if re.search(r'[0-9]', first_eight[0:7]):
            # contains a number in the first 7 chars
            variation += 1
        if re.search(r'[A-Za-z0-9]{7}[^A-Za-z0-9]', first_eight):
            # Only non-alnum and non-digit is the last one.
            good_try += 1
        if re.search(r'[^A-Za-z0-9]', password[0:7]):
            # Must contain a non-alnum and non-digit char
            variation += 1

        if variation < 3:
            if good_try:
                return [
                    _("A password that only contains one uppercase letter,"
                      " must not have this as the first character."
                      " If the first 8 characters only contains one number or"
                      " special character, this must not be in position 8.")]
            else:
                return [
                    _("The first eight characters of the password must contain"
                      " characters from at least three of the four following"
                      " character groups: Uppercase letters, lowercase"
                      " letters, numbers and special characters.")]


@pwchecker('character_sequence')
class CheckCharacterSequence(PasswordChecker):
    """ Check for sequences of related chars. """

    def __init__(self, char_seq_length=3):
        self._requirement = _(
            'Must not contain sequences of closely related characters.')
        self.char_seq_length = char_seq_length

    def check_password(self, password, account=None):
        """ Check for sequences of closely related characters. """
        errors = []

        if isinstance(password, str):
            try:
                password = unicode(password, 'UTF-8')
            except UnicodeDecodeError:
                password = unicode(password, 'ISO-8859-1')
        passwd = password.lower()
        ordpw = map(ord, passwd)

        def find_adjacent_runs(seq):
            def fun(tot, elt):
                if tot and tot[-1][0] == elt:
                    tot[-1][1] += 1
                else:
                    tot.append([elt, 1])
                return tot
            return reduce(fun, seq, [])

        # A sequence of closely related ASCII characters.
        for diff, num in find_adjacent_runs(
                map(operator.sub, ordpw[1:], ordpw[:-1])):
            if diff in (-1, 1) and num >= self.char_seq_length:
                errors.append(_('Password cannot contain characters in '
                                'alpabetical or numerical order'))
                break

        # TODO: 'kbd' should probably try a number of typical layouts.
        # Rows may be of different lengths, but the same symbol CANNOT occur
        # more than once.
        keyboard_rows = (u"qwertyuiop[]",
                         u"qwertyuiopå",  # norwegian
                         u"asdfghjkl;'",
                         u"asdfghjkløæ",  # norwegian
                         u"zxcvbnm,./",
                         u"zxcvbnm,.-",   # norwegian
                         u"!@#$%^&*()_+|~",
                         u"§!\"#$%&/()=?",
                         u"-1234567890=\`",
                         u"å,.pyfgcrl'",  # dvorak
                         u"å;:pyfgcrl'",  # dvorak
                         u"aoeuidhtns-<",  # dvorak
                         u"øæqjkxbmwvz",  # dvorak
                         )

        for row in keyboard_rows:
            mapper = dict([(key, val+1) for val, key in enumerate(row)])
            pw = [mapper.get(x, -1) for x in passwd]
            runs = find_adjacent_runs(map(operator.sub, pw[1:], pw[:-1]))
            for diff, num in runs:
                if diff in (-1, 1) and num >= self.char_seq_length:
                    errors.append(_(
                        'Password cannot contain neighbouring keyboard keys'))
                    break
        return errors


@pwchecker('repeated_pattern')
class CheckRepeatedPattern(PasswordChecker):
    """ Check for repeated patterns in password. """

    def __init__(self):
        self._requirement = _(
            'Must not contain repeated sequences of characters.')

    def check_password(self, password, account=None):
        """ Check for repeated sequences in the first eight chars. """

        # TODO: Clean up this check, and get rid of the trunc
        first_eight = password[0:8]
        repeat_err = [
            _('Password cannot contain repeated sequences of characters.')]

        # Repeated patterns: ababab, abcabc, abcdabcd
        if (re.search(r'^(..)\1\1', first_eight) or
                re.search(r'^(...)\1', first_eight) or
                re.search(r'^(....)\1', first_eight)):
            return repeat_err

        # Reversed patterns: abccba abcddcba
        if (re.search(r'^(.)(.)(.)\3\2\1', first_eight) or
                re.search(r'^(.)(.)(.)(.)\4\3\2\1', first_eight)):
            return repeat_err


@pwchecker('username')
class CheckUsername(PasswordChecker):
    """ Check for use of the username in the password. """

    def __init__(self):
        self._requirement = _(
            'Must not contain your username, even in reverse.')

    def check_password(self, password, account=None):
        """ Does the password contain the username? """
        if account is None:
            return

        uname = getattr(account, 'account_name', None)
        if uname is None:
            return

        # password cannot contain the username
        if uname.lower() in password.lower():
            return [_('Password cannot contain your username')]

        # password cannot contain the username reversed
        if uname[::-1].lower() in password.lower():
            return [_('Password cannot contain your username in reverse')]


@pwchecker('owner_name')
class CheckOwnerNameMixin(PasswordChecker):
    """ Check for use of the account owners name in the password. """

    def __init__(self, name_seq_len=5):
        self.name_seq_len = name_seq_len
        self._requirement = _('Must not contain {name_seq_len} or more characters from your name.').format(name_seq_len=name_seq_len)

    def check_password(self, password, account=None):
        if account is None:
            return
        if not hasattr(self, 'owner_id'):
            return

        if isinstance(password, str):
            try:
                password = unicode(password, 'UTF-8')
            except:
                password = unicode(password, 'ISO-8859-1')

        self._check_human_owner(account.owner_id, password, self.name_seq_len)

    def _check_human_owner(self, owner_id, password, seqlen):
        """Check if password is a variation of the owner's name."""
        # TODO: Should we not check the name of other owner types as well?
        #       E.g.: owner=group:foobarbaz, password=fooBARbaz

        # First, do we have a human owner at all?
        person = Factory.get("Person")(self._db)
        const = Factory.get("Constants")(self._db)
        try:
            person.find(owner_id)
        except NotFoundError:
            return
        # Which name to use? Let's grab the first full name we find
        # TODO: Why not check _ALL_ the names? What if there are multiple
        # `name_full' names, but they are different between source systems?
        for row in person.get_all_names():
            if row["name_variant"] == const.name_full:
                name = row["name"]
                break
        else:
            return
        self._match_password_to_name(name, password, seqlen)

    def _match_password_to_name(self, name, password, seqlen):
        """Check whether password 'matches' (in a sense) name."""

        def make_match(name_chunks, pwd_chunks):
            # For each subsequent name part, check if that name part starts
            # with a the leftover password. In case there is a match, shorten
            # leftover password (that's what pwd_index is for).

            # How many overlapping characters we have found so far.
            matching_length = 0
            for name in name_chunks:
                for pwd in pwd_chunks:
                    if name.startswith(pwd):
                        matching_length += len(pwd)

            return matching_length
        # Now, we have a name, 'Schnappi von Krokodil'. What password
        # variations are compared against such a name? We want to trap
        # variations like S*Krokodil, Sv-Krokodil, Schnappi-Krok and the like;
        # i.e. we want to force people NOT to use some trivial version of
        # their name.
        name = unicode(name.lower(), 'latin-1')
        password = password.lower()
        name_chunks = [x for x in name.split() if len(x) > 0]
        pwd_chunks = [x for x in re.split(r"[^a-z]+", password) if len(x) > 0]
        pwd_l33t_chunks = [x for x in re.split(
            r"[^a-z]+",
            password.translate(unicode(l33t_speak, 'ISO-8859-1')))
            if len(x) > 0]

        # Now, matching_length counts the number of password alpha characters
        # that overlap with the name. Let's say that if more than half the
        # password is, in fact, a match => the password is a copy of the name.
        if (make_match(name_chunks, pwd_chunks) >= seqlen or
                make_match(name_chunks, pwd_l33t_chunks) >= seqlen):
            return [_('Password cannot contain your name.')]

        # Join all possible sequences of length
        def all_chunks(x):
            tmp = u''.join(x)
            if len(tmp) > seqlen:
                for i in range(len(tmp) - seqlen):
                    yield tmp[i:i+seqlen]
            else:
                yield tmp

        all_pw_chunks = set(all_chunks(password.split()))
        for name in all_chunks(name_chunks):
            if name in all_pw_chunks:
                return [_('Password cannot contain {seqlen} characters from '
                          'your name').format(seqlen=seqlen)]
