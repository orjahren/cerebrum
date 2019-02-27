#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2002-2019 University of Oslo, Norway
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

"""Script for gathering data from FS and put it into XML files for further
processing by other scripts.

"""
from __future__ import unicode_literals
from __future__ import print_function

import os
import sys
import getopt
import logging

import cereconf

import Cerebrum.logutils
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.atomicfile import SimilarSizeWriter
from Cerebrum.utils.atomicfile import FileChangeTooBigError
from Cerebrum.modules.no.access_FS import make_fs
from Cerebrum.modules.fs.import_from_FS import ImportFromFs, set_filepath

XML_ENCODING = 'utf-8'

logger = logging.getLogger(__name__)
xml = XMLHelper(encoding=XML_ENCODING)


def usage():
    print("""Usage: %(filename)s [options]

    %(doc)s

    Settings:
    --datadir: Override the directory where all files should be put.
               Default: see cereconf.FS_DATA_DIR

               Note that the datadir can be overriden by the file path
               options, if these are absolute paths.
    --studprog-file: Override studprog xml filename.
                     Default: studieprogrammer.xml
    --personinfo-file: Override person xml filename.
                       Default: person.xml.
    --roleinfo-file: Override role xml filename.
                     Default: roles.xml.
    --emneinfo-file: Override emne info xml filename.
                     Default: emner.xml.
    --fnr-update-file: Override fnr-update xml filename.
                       Default: fnr_update.xml.
    --netpubl-file: Override netpublication filename.
                    Default: nettpublisering.xml.
    --ou-file: Override ou xml filename.
               Default: ou.xml.
    --misc-func: Name of extra function in access_FS to call. Will be called
                 at the next given --misc-file.
    --misc-file: Name of output file for previous set misc-func and misc-tag
                 arguments. Note that a relative filename could be used for
                 putting it into the set datadir.
    --misc-tag: Tag to use in the next given --misc-file argument.
    --topics-file: Override topics xml filename.
                   Default: topics.xml.
    --pre-course-file: Name of output file for pre course information.
                       Default: pre_course.xml.
    --regkort-file: Override regkort xml filename.
                    Default: regkort.xml.
    --betalt-papir-file: Override betalt-papir xml filename.
                         Default: betalt_papir.xml.
    --edu-file: Override edu-info xml filename.
                Default edu_info.xml.
    --db-user: connect with given database username
    --db-service: connect to given database

    Action:
    -p: Generate person xml file
    -s: Generate studprog xml file
    -r: Generate role xml file
    -e: Generate emne info xml file
    -f: Generate fnr_update xml file
    -o: Generate ou xml file
    -n: Generate netpublication reservation xml file
    -t: Generate topics xml file
    -b: Generate betalt-papir xml file
    -R: Generate regkort xml file
    -d: Gemerate edu info xml file
    -P: Generate a pre-course xml file
    """ % {'filename': os.path.basename(sys.argv[0]),
           'doc': __doc__})


class ImportFromFsUio(ImportFromFs):
    def __init__(self, opts, fs):
        super(ImportFromFsUio, self).__init__(opts, fs)
        self.topics_file = "topics.xml"
        self.regkort_file = "regkort.xml"
        self.betalt_papir_file = "betalt_papir.xml"
        self.edu_file = "edu_info.xml"
        self.pre_course_file = "pre_course.xml"

        # Parse arguments
        for o, val in opts:
            if o in ('--topics-file',):
                self.topics_file = val
            elif o in ('--regkort-file',):
                self.regkort_file = val
            elif o in ('--betalt-papir-file',):
                self.betalt_papir_file = val
            elif o in ('--edu-file',):
                self.edu_file = val
            elif o in ('--pre-course-file',):
                self.pre_course_file = val

    def write_person_info(self):
        """Lager fil med informasjon om alle personer registrert i FS som
        vi muligens også ønsker å ha med i Cerebrum.  En person kan
        forekomme flere ganger i filen."""

        # TBD: Burde vi cache alle data, slik at vi i stedet kan lage en
        # fil der all informasjon om en person er samlet under en egen
        # <person> tag?

        logger.info("Writing person info to '%s'", self.person_file)
        f = SimilarSizeWriter(self.person_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")

        # Aktive studenter
        cols, students = self._ext_cols(self.fs.student.list_aktiv())
        for s in students:
            f.write(
                xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'aktiv') + "\n")

        # Eksamensmeldinger
        cols, students = self._ext_cols(
            self.fs.student.list_eksamensmeldinger())
        for s in students:
            f.write(
                xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'eksamen') + "\n")

        # EVU students
        # En del EVU studenter vil være gitt av søket over
        cols, students = self._ext_cols(self.fs.evu.list())
        for e in students:
            f.write(
                xml.xmlify_dbrow(e, xml.conv_colnames(cols), 'evu') + "\n")

        # Privatister, privatistopptak til studieprogram eller emne-privatist
        cols, students = self._ext_cols(self.fs.student.list_privatist())
        for s in students:
            self.fix_float(s)
            f.write(
                xml.xmlify_dbrow(
                    s, xml.conv_colnames(cols),
                    'privatist_studieprogram') + "\n")
        cols, students = self._ext_cols(self.fs.student.list_privatist_emne())
        for s in students:
            f.write(
                xml.xmlify_dbrow(
                    s, xml.conv_colnames(cols), 'privatist_emne') + "\n")

        # Drgradsstudenter med opptak
        cols, drstudents = self._ext_cols(self.fs.student.list_drgrad())
        for d in drstudents:
            f.write(
                xml.xmlify_dbrow(d, xml.conv_colnames(cols), 'drgrad') + "\n")

        # Fagpersoner
        cols, fagpersoner = self._ext_cols(
            self.fs.undervisning.list_fagperson_semester())
        for p in fagpersoner:
            f.write(
                xml.xmlify_dbrow(
                    p, xml.conv_colnames(cols), 'fagperson') + "\n")

        # Studenter med opptak, privatister (=opptak i studiepgraommet
        # privatist) og Alumni
        cols, students = self._ext_cols(self.fs.student.list())
        for s in students:
            # The Oracle driver thinks the result of a union of ints is float
            self.fix_float(s)
            f.write(
                xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'opptak') + "\n")

        # Aktive emnestudenter
        cols, students = self._ext_cols(self.fs.student.list_aktiv_emnestud())
        for s in students:
            f.write(
                xml.xmlify_dbrow(
                    s, xml.conv_colnames(cols), 'emnestud') + "\n")

        # Semester-registrering
        cols, students = self._ext_cols(self.fs.student.list_semreg())
        for s in students:
            f.write(
                xml.xmlify_dbrow(s, xml.conv_colnames(cols), 'regkort') + "\n")

        # Studenter i permisjon (ogs� dekket av GetStudinfOpptak)
        cols, permstud = self._ext_cols(self.fs.student.list_permisjon())
        for p in permstud:
            f.write(
                xml.xmlify_dbrow(
                    p, xml.conv_colnames(cols), 'permisjon') + "\n")

        #
        # STA har bestemt at personer med tilbud ikke skal ha tilgang til noen
        # IT-tjenester inntil videre. Derfor slutter vi på nåværende tidspunkt
        # å hente ut informasjon om disse. Ettersom det er usikkert om dette
        # vil endre seg igjen i nær fremtid lar vi koden ligge for nå.
        #
        # # Personer som har fått tilbud
        # cols, tilbudstud = self._ext_cols(fs.student.list_tilbud())
        # for t in tilbudstud:
        #     f.write(
        #         xml.xmlify_dbrow(
        #             t, xml.conv_colnames(cols), 'tilbud') + "\n")

        f.write("</data>\n")
        f.close()

    def write_ou_info(self):
        """Lager fil med informasjon om alle OU-er"""
        logger.info("Writing OU info to '%s'", self.ou_file)
        f = SimilarSizeWriter(self.ou_file, mode='w', encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, ouer = self._ext_cols(
            self.fs.info.list_ou(cereconf.DEFAULT_INSTITUSJONSNR))
        for o in ouer:
            sted = {}
            for fs_col, xml_attr in (
                    ('faknr', 'fakultetnr'),
                    ('instituttnr', 'instituttnr'),
                    ('gruppenr', 'gruppenr'),
                    ('stedakronym', 'akronym'),
                    ('stedakronym', 'forkstednavn'),
                    ('stednavn_bokmal', 'stednavn'),
                    ('faknr_org_under', 'fakultetnr_for_org_sted'),
                    ('instituttnr_org_under', 'instituttnr_for_org_sted'),
                    ('gruppenr_org_under', 'gruppenr_for_org_sted'),
                    ('adrlin1', 'adresselinje1_intern_adr'),
                    ('adrlin2', 'adresselinje2_intern_adr'),
                    ('postnr', 'poststednr_intern_adr'),
                    ('adrlin1_besok', 'adresselinje1_besok_adr'),
                    ('adrlin2_besok', 'adresselinje2_besok_adr'),
                    ('postnr_besok', 'poststednr_besok_adr')):
                if o[fs_col] is not None:
                    sted[xml_attr] = xml.escape_xml_attr(o[fs_col])
            komm = []
            for fs_col, typekode in (
                    ('telefonnr', 'EKSTRA TLF'),
                    ('faxnr', 'FAX'),
            ):
                if o[fs_col]:  # Skip NULLs and empty strings
                    komm.append(
                        {'kommtypekode': xml.escape_xml_attr(typekode),
                         'kommnrverdi': xml.escape_xml_attr(o[fs_col])})
            # TODO: Kolonnene 'url' og 'bibsysbeststedkode' hentes ut fra
            # FS, men tas ikke med i outputen herfra.
            f.write('<sted ' +
                    ' '.join(["%s=%s" % item for item in sted.items()]) +
                    '>\n')
            for k in komm:
                f.write('<komm ' +
                        ' '.join(["%s=%s" % item for item in k.items()]) +
                        ' />\n')
            f.write('</sted>\n')
        f.write("</data>\n")
        f.close()

    def write_topic_info(self):
        """Lager fil med informasjon om alle XXX"""
        # TODO: Denne filen blir endret med det nye opplegget :-(
        logger.info("Writing topic info to '%s'", self.topics_file)
        f = SimilarSizeWriter(self.topics_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, topics = self._ext_cols(self.fs.student.list_eksamensmeldinger())
        for t in topics:
            # The Oracle driver thinks the result of a union of ints is float
            self.fix_float(t)
            f.write(
                xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'topic') + "\n")
        f.write("</data>\n")
        f.close()

    def write_forkurs_info(self):
        from mx.DateTime import now
        logger.info("Writing pre-course file to '%s'", self.pre_course_file)
        f = SimilarSizeWriter(self.pre_course_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        cols, course_attendants = self._ext_cols(self.fs.forkurs.list())
        f.write(xml.xml_hdr + "<data>\n")
        for a in course_attendants:
            f.write(
                '<regkort fodselsdato="{}" personnr="{}" dato_endring="{}" '
                'dato_opprettet="{}"/>\n'.format(a['fodselsdato'],
                                                 a['personnr'],
                                                 str(now()),
                                                 str(now())))
            f.write('<emnestud fodselsdato="{}" personnr="{}" etternavn="{}" '
                    'fornavn="{}" adrlin2_semadr="" postnr_semadr="" '
                    'adrlin3_semadr="" adrlin2_hjemsted="" postnr_hjemsted="" '
                    'adrlin3_hjemsted="" sprakkode_malform="NYNORSK" '
                    'kjonn="X" studentnr_tildelt="{}" emnekode="FORGLU" '
                    'versjonskode="1" terminkode="VÅR" arstall="2016" '
                    'telefonlandnr_mobil="{}" telefonnr_mobil="{}"/>\n'.format(
                        a['fodselsdato'],
                        a['personnr'],
                        a['etternavn'],
                        a['fornavn'],
                        a['studentnr_tildelt'],
                        a['telefonlandnr'],
                        a['telefonnr']
                    ))
        f.write("</data>\n")
        f.close()

    def write_edu_info(self):
        """Lager en fil med undervisningsinformasjonen til alle studenter.

        For hver student, lister vi opp alle tilknytningene til undenh, undakt,
        evu, kursakt og kull.

        Hovedproblemet i denne metoden er at vi må bygge en enorm dict med all
        undervisningsinformasjon. Denne dicten bruker mye minne.

        Advarsel: vi gjør ingen konsistenssjekk på at undervisningselementer
        nevnt i outfile vil faktisk finnes i andre filer genererert av dette
        skriptet. Mao. det er fullt mulig at en student S er registrert ved
        undakt U1, samtidig som U1 ikke er nevnt i undervisningsaktiveter.xml.

        fs.undervisning.list_studenter_alle_kull()      <- kull deltagelse
        fs.undervisning.list_studenter_alle_undenh()    <- undenh deltagelse
        fs.undervisning.list_studenter_alle_undakt()    <- undakt deltagelse
        fs.evu.list_studenter_alle_kursakt()            <- kursakt deltagelse
        fs.evu.list()                                   <- evu deltagelse
        """
        logger.info("Writing edu info to '%s'", self.edu_file)
        f = SimilarSizeWriter(self.edu_file, mode='w', encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")

        for triple in (
                ("kull", None,
                 self.fs.undervisning.list_studenter_alle_kull),
                ("undenh", None,
                 self.fs.undervisning.list_studenter_alle_undenh),
                ("undakt", None,
                 self.fs.undervisning.list_studenter_alle_undakt),
                ("evu", ("fodselsdato",
                         "personnr",
                         "etterutdkurskode",
                         "kurstidsangivelsekode"),
                 self.fs.evu.list),
                ("kursakt", None, self.fs.evu.list_studenter_alle_kursakt)):
            kind, fields, selector = triple
            logger.debug("Processing %s entries", kind)
            for row in selector():
                if fields is None:
                    tmp_row = row
                    keys = row.keys()
                else:
                    tmp_row = dict((f, row[f]) for f in fields)
                    keys = fields

                f.write(xml.xmlify_dbrow(tmp_row, keys, kind) + '\n')

        f.write("</data>\n")
        f.close()

    def write_regkort_info(self):
        """Lager fil med informasjon om semesterregistreringer for
        inneværende semester"""
        logger.info("Writing regkort info to '%s'", self.regkort_file)
        f = SimilarSizeWriter(self.regkort_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, regkort = self._ext_cols(self.fs.student.list_semreg())
        for r in regkort:
            f.write(
                xml.xmlify_dbrow(r, xml.conv_colnames(cols), 'regkort') + "\n")
        f.write("</data>\n")
        f.close()

    def write_betalt_papir_info(self):
        """Lager fil med informasjon om alle som enten har fritak fra å
        betale kopiavgift eller har betalt kopiavgiften"""

        logger.info("Writing betaltpapir info to '%s'", self.betalt_papir_file)
        f = SimilarSizeWriter(self.betalt_papir_file, mode='w',
                              encoding=XML_ENCODING)
        f.max_pct_change = 50
        f.write(xml.xml_hdr + "<data>\n")
        cols, dta = self._ext_cols(
            self.fs.betaling.list_kopiavgift_data(
                kun_fritak=False, semreg=True))
        for t in dta:
            self.fix_float(t)
            f.write(
                xml.xmlify_dbrow(t, xml.conv_colnames(cols), 'betalt') + "\n")
        f.write("</data>\n")
        f.close()


def main():
    Cerebrum.logutils.autoconf('cronjob')
    logger.info("Starting import from FS")
    try:
        opts, args = getopt.getopt(sys.argv[1:], "psrefontbRdP",
                                   ["datadir=",
                                    "personinfo-file=",
                                    "studprog-file=",
                                    "roleinfo-file=",
                                    "emneinfo-file=",
                                    "fnr-update-file=",
                                    "netpubl-file=",
                                    "ou-file=",
                                    "misc-func=",
                                    "misc-file=",
                                    "misc-tag=",
                                    "topics-file=",
                                    "betalt-papir-file=",
                                    "regkort-file=",
                                    "edu-file=",
                                    "pre-course-file=",
                                    "db-user=",
                                    "db-service="
                                    ])
    except getopt.GetoptError as error:
        print(error)
        usage()
        sys.exit(2)

    db_user = None
    db_service = None
    for o, val in opts:
        if o in ('--db-user',):
            db_user = val
        elif o in ('--db-service',):
            db_service = val

    fs = make_fs(user=db_user, database=db_service)
    fsimporter = ImportFromFsUio(opts, fs)

    misc_tag = None
    misc_func = None
    for o, val in opts:
        try:
            if o in ('-p',):
                fsimporter.write_person_info()
            elif o in ('-s',):
                fsimporter.write_studprog_info()
            elif o in ('-r',):
                fsimporter.write_role_info()
            elif o in ('-e',):
                fsimporter.write_emne_info()
            elif o in ('-f',):
                fsimporter.write_fnrupdate_info()
            elif o in ('-o',):
                fsimporter.write_ou_info()
            elif o in ('-n',):
                fsimporter.write_netpubl_info()
            elif o in ('-t',):
                fsimporter.write_topic_info()
            elif o in ('-b',):
                fsimporter.write_betalt_papir_info()
            elif o in ('-R',):
                fsimporter.write_regkort_info()
            elif o in ('-d',):
                fsimporter.write_edu_info()
            elif o in ('-P',):
                fsimporter.write_forkurs_info()
            # We want misc-* to be able to produce multiple file in one
            # script-run
            elif o in ('--misc-func',):
                misc_func = val
            elif o in ('--misc-tag',):
                misc_tag = val
            elif o in ('--misc-file',):
                fsimporter.misc_file = set_filepath(fsimporter.datadir, val)
                fsimporter.write_misc_info(misc_tag, misc_func)
        except FileChangeTooBigError as msg:
            logger.error("Manual intervention required: %s", msg)
    logger.info("Done with import from FS")


if __name__ == '__main__':
    main()
