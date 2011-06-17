#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2011 University of Oslo, Norway
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

# Messages used by the Individuation Server
messages = {
    'error_unknown':     {'en': u'An unknown error occured',
                          'no': u'En ukjent feil oppstod'},
    'person_notfound':   {'en': u'Could not find a person by given data, please try again. Please note that you will ' + 
                                u'not be able to use this service if you are reserved from being published on UiO\'s ' +
                                u'web pages.',
                          'no': (u'Kunne ikke finne personen ut fra oppgitte data, vennligst prøv igjen. Merk at du ' + 
                                 u'ikke kan bruke denne tjenesten om du har reservert deg fra å bli publisert på UiO ' +
                                 u'sine nettsider.')},
    'person_miss_info':  {'en': u'Not all your information is available. Please contact your HR department or student office.',
                          'no': u'Ikke all din informasjon er tilgjengelig. Vennligst ta kontakt med din personalavdeling eller studentkontor.'},
    'account_blocked':   {'en': u'This account is inactive. Please contact your local IT.',
                          'no': u'Denne brukerkontoen er ikke aktiv. Vennligst ta kontakt med din lokale IT-avdeling.'},
    'account_reserved':  {'en': u'You are reserved from using this service. Please contact your local IT.',
                          'no': u'Du er reservert fra å bruke denne tjenesten. Vennligst ta kontakt med din lokale IT-avdeling.'},
    'account_self_reserved':  {'en': u'You have reserved yourself from using this service. Please contact your local IT.',
                          'no': u'Du har reservert deg fra å bruke denne tjenesten. Vennligst ta kontakt med din lokale IT-avdeling.'},
    'token_notsent':     {'en': u'Could not send one time password to phone',
                          'no': u'Kunne ikke sende engangspassord til telefonen'},
    'toomanyattempts':   {'en': u'Too many attempts. You have temporarily been blocked from this service',
                          'no': u'For mange forsøk. Du er midlertidig utestengt fra denne tjenesten'},
    'toomanyattempts_check': {'en': u'Too many attempts, one time password got invalid',
                          'no': u'For mange forsøk, engangspassordet er blitt gjort ugyldig'},
    'timeout_check':     {'en': u'Timeout, one time password got invalid',
                          'no': u'Tidsavbrudd, engangspassord ble gjort ugyldig'},
    'fresh_phonenumber': {'en': u'Phone number recently changed, not yet available',
                          'no': u'Telefonnummer er nylig blitt byttet, er ikke tilgjengelig enda'},
    'password_invalid':  {'en': u'Bad password: %s',
                          'no': u'Ugyldig passord: %s'},
}
