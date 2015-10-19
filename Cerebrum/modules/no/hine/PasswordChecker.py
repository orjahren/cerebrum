#!/usr/bin/env python
# encoding: latin-1
#
# Copyright 2003-2015 University of Oslo, Norway
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

import cerebrum_path
import cereconf

from Cerebrum.modules.pwcheck.common import PasswordNotGoodEnough
from Cerebrum.modules.pwcheck.phrase import CheckPassphraseMixin


class HiNePasswordCheckerMixin(CheckPassphraseMixin):

    _passphrase_min_words = 2
    _passphrase_min_word_length = 2
    _passphrase_min_words_error_fmt = ("For f� ord i passordet (minst %d"
                                       "ord p� %d tegn")

    _passphrase_min_length = 15
    _passphrase_min_length_error_fmt = ("Passord m� ha minst %d tegn")

    _passphrase_max_length = None
    _passphrase_max_length_error_fmt = "%r"

    def password_good_enough(self, passphrase):
        """Perform a number of checks on a password to see if it is good
        enough.

        HiNe has the following rules:

        - Characters in the passphrase are either letters or whitespace.
        - The automatically generated password has a minimum of 15
          characters and 2 words (one space)
        - The user supplied passwords have a minimum of 15
          characters. There is no maximum (well, there is in the db
          schema, but this is irrelevant in the passwordchecker).
        """
        for char in passphrase:
            if not (char.isalpha() or char in '������ '):
                raise PasswordNotGoodEnough(
                    "Vennligst ikke bruk andre tegn enn bokstaver og blank.")

        super(HiNePasswordCheckerMixin, self).password_good_enough(passphrase)
        # Super checks length and words
