#!/usr/bin/env python2.2
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

import cerebrum_path

import re
import os
import sys
import getopt
import cereconf

from Cerebrum.modules.no.uio.access_LT import LT
from Cerebrum import Database,Errors
from Cerebrum.Utils import XMLHelper

def get_sted_info(outfile):
    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")

    cols, steder = LT.GetSteder();
    for s in steder:
        f.write(xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'sted', 0) + "\n")
        cols2, komm = LT.GetStedKomm(s['fakultetnr'], s['instituttnr'], s['gruppenr'])
        for k in komm:
            f.write(xml.xmlify_dbrow(k, xml.conv_colnames(cols2), 'komm') + "\n")
        f.write("</sted>\n")
    f.write("</data>\n")

def get_person_info(outfile):
    """Henter info om alle personer i LT som er av interesse.
    Ettersom opplysningene samles fra flere datakilder, lagres de
    først i en dict persondta"""

    skode2tittel = {}
    for t in LT.GetTitler()[1]:
        skode2tittel[t['stillingkodenr']] = (t['tittel'], t['univstkatkode'])

    kate2hovedkat = {}
    for t in LT.GetHovedkategorier()[1]:
        kate2hovedkat[t['univstkatkode']] = t['hovedkatkode']

    f=open(outfile, 'w')
    f.write(xml.xml_hdr + "<data>\n")
    tilscols, tils = LT.GetTilsettinger()
    persondta = {}
    for t in tils:
        # f.write(xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'tils', 0) + "\n")
        key = '-'.join((str(t['fodtdag']), str(t['fodtmnd']), str(t['fodtar']), str(t['personnr'])))
        if not persondta.has_key(key):
            persondta[key] = {}
        persondta[key]['tils'] = persondta[key].get('tils', []) + [t]

    # $tid er siste entry i lønnsposterings-cache. TODO
    tid = '20020601'
    lonnscols, lonnspost = LT.GetLonnsPosteringer(tid)
    for lp in lonnspost:
        key = '-'.join((str(lp['fodtdag']), str(lp['fodtmnd']), str(lp['fodtar']),
                        str(lp['personnr'])))
        if not persondta.has_key(key):
            persondta[key] = {}
        persondta[key]['bil'] = persondta[key].get('bil', []) + [
            "%02d%02d%02d" % (lp['fakultetnr_kontering'], lp['instituttnr_kontering'],
                              lp['gruppenr_kontering'])]

    for p in persondta.keys():
        fodtdag, fodtmnd, fodtar, personnr = p.split('-')
        picols, pi = LT.GetPersonInfo(fodtdag, fodtmnd, fodtar, personnr)
        f.write(xml.xmlify_dbrow(pi[0],  xml.conv_colnames(picols), 'person', 0,
                              extra_attr={'fodtdag': fodtdag, 'fodtmnd':fodtmnd,
                                          'fodtar':fodtar, 'personnr': personnr}) + "\n")
        tlfcols, tlf = LT.GetTelefon(fodtdag, fodtmnd, fodtar, personnr)
        for t in tlf:
            f.write(xml.xmlify_dbrow(t,  xml.conv_colnames(tlfcols), 'arbtlf') + "\n")

        kcols, komm = LT.GetKomm(fodtdag, fodtmnd, fodtar, personnr)
        for k in komm:
            f.write(xml.xmlify_dbrow(k,  xml.conv_colnames(kcols), 'komm') + "\n")

        for t in persondta[p].get('tils', ()):
            # Unfortunately the oracle driver returns
            # to_char(dato_fra,'yyyymmdd') as key for rows, so we use
            # indexes here :-(
            attr = " ".join(["%s=%s" % (tilscols[i], xml.escape_xml_attr(t[i]))
                             for i in (4,5,6,7,8,9,10,11, )])
            if t['stillingkodenr_beregnet_sist'] is not None:
                sk = skode2tittel[t['stillingkodenr_beregnet_sist']]
                attr += ' hovedkat=%s' % xml.escape_xml_attr(
                    kate2hovedkat[sk[1]])
                attr += ' tittel=%s' % xml.escape_xml_attr(sk[0])
                f.write("<tils "+attr+"/>\n")

        prev = ''
        persondta[p].get('bil', []).sort()
        for t in persondta[p].get('bil', []):
            if t == prev:
                continue
            f.write('<bilag stedkode="%s"' % t + "/>\n")
            prev = t
        f.write("</person>\n")

    f.write("</data>\n")

def usage(exitcode=0):
    print """Usage: -s sid -u uname [options]
    -v | --verbose : turn up verbosity
    -s | --sid sid: sid to connect with
    -u uname: username to connect with
    --sted-file file: filename to write sted info to
    --person-file file: filename to write person info to"""
    sys.exit(exitcode)

def main():
    global LT, xml, verbose

    personfile = None
    stedfile = None
    sid = None
    user = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vs:u:',
                                   ['verbose', 'sid=', 'sted-file=', 'person-file='])
    except getopt.GetoptError:
        usage(1)
    for opt, val in opts:
        if opt in ('-v', '--verbose'):
            pass  # not currently used
        elif opt in ('-s', '--sid'):
            sid = val
        elif opt in ('-u'):
            user = val
        elif opt in ('--sted-file'):
            stedfile = val
        elif opt in ('--person-file'):
            personfile = val
    if user is None or sid is None:
        usage(1)
    db = Database.connect(user=user, service=sid, DB_driver='Oracle')
    LT = LT(db)
    xml = XMLHelper()

    if stedfile is not None:
        get_sted_info(stedfile)
    if personfile is not None:
        get_person_info(personfile)

if __name__ == '__main__':
    main()
