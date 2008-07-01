#!/usr/bin/env python
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

#
# This script reads data exported from our HR system PAGA.
# It is a simple CSV file.
#

import getopt
import sys
import os
import mx.DateTime

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum.Utils import Factory, AtomicFileWriter
from Cerebrum.extlib import xmlprinter

from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError

progname = __file__.split("/")[-1]
__doc__="""Usage: %s [options]
    Parse datafile from PAGA. 

    options:
    -o | --out_file   : alternative xml file to store data in
    -p | --paga-file  : file to read from
    -h | --help       : show this
    --logger-name     : name of logger to use
    --logger-level    : loglevel to use
    
    """ % progname




#Define defaults
TODAY=mx.DateTime.today().strftime("%Y-%m-%d")
CHARSEP=';'
dumpdir_employees = os.path.join(cereconf.DUMPDIR, "employees")
dumpdir_paga = os.path.join(cereconf.DUMPDIR, "paga")
default_employee_file = 'paga_persons_%s.xml' % (TODAY,)
default_paga_file = 'uit_paga_%s.csv' % (TODAY,)

# some common vars
db = Factory.get('Database')()
logger = Factory.get_logger("cronjob")

# define field positions in PAGA csv-data
# First line in PAGA csv file contains field names. Use them.
KEY_AKSJONKODE='A.kode'
KEY_AKSJONDATO='A.dato'
KEY_ANSATTNR='Ansattnr'
KEY_AV='Av'
KEY_BRUKERNAVN= 'Brukernavn'
KEY_DBHKAT='DBH stillingskategori'
KEY_DATOFRA='F.l�nnsdag'
KEY_DATOTIL='S.l�nnsdag'
KEY_EPOST='E-postadresse'
KEY_ETTERNAVN='Etternavn'
KEY_FNR='F�dselsnummer'
KEY_FORNAVN= 'Fornavn'
KEY_HOVEDARBFORH='HovedAF'
KEY_KOSTNADSTED='K.sted'
KEY_NR='Nr'
KEY_ORGSTED='Org.nr.'
KEY_PERMISJONKODE='P.kode'
KEY_STANDEL='St.andel'
KEY_STILLKODE='St. kode'
KEY_TITTEL='St.bet'
KEY_TJFORH='Tj.forh.'
KEY_UNIKAT='Univkat'
KEY_UITKAT='UITkat'

def parse_paga_csv(pagafile):
    import csv
    persons=dict()
    tilsettinger=dict()
    permisjoner=dict()
    dupes=list()
    for detail in csv.DictReader(open(pagafile,'r'),delimiter=CHARSEP):
        ssn=detail[KEY_FNR]        
        
        # some checks
        if detail[KEY_PERMISJONKODE]!='0':
            logger.warn("Dropping detail for %s, P.Kode=%s" % \
                (ssn,detail[KEY_PERMISJONKODE]))
            permisjoner[ssn]=detail[KEY_PERMISJONKODE]
            continue
        elif detail[KEY_AKSJONKODE]:
            logger.warn("Detail contains A.Kode for %s, A.Kode=%s" % \
                (ssn,detail[KEY_AKSJONKODE]))
        
        person_data={
            'ansattnr': detail[KEY_ANSATTNR],
            'fornavn': detail[KEY_FORNAVN],
            'etternavn': detail[KEY_ETTERNAVN],
            'brukernavn': detail[KEY_BRUKERNAVN],
            'epost': detail[KEY_EPOST],
            'brukernavn': detail[KEY_BRUKERNAVN], 
        }
        tilskey="%s:%s"  % (detail[KEY_NR], detail[KEY_AV])
        tils_data={
            'stillingskode': detail[KEY_STILLKODE],
            'tittel':detail[KEY_TITTEL],
            'stillingsandel': detail[KEY_STANDEL],
            'kategori': detail[KEY_UITKAT],
            'hovedkategori': detail[KEY_UNIKAT],
            'forhold': detail[KEY_TJFORH],            
            'dato_fra':detail[KEY_DATOFRA],
            'dato_til':detail[KEY_DATOTIL],
            'dbh_kat':detail[KEY_DBHKAT],
            'hovedarbeidsforhold':detail[KEY_HOVEDARBFORH],
        }
        stedkode=detail[KEY_ORGSTED]
        # check if stedkode should be mapped to something else
        query="""
        SELECT new_ou_id 
        FROM [:table schema=cerebrum name=ou_history]
        where old_ou_id=:stedkode
        """ 
        #query="select new_ou_id from ou_history where old_ou_id='%s'"% stedkode
        try:
            new_sko=db.query_1(query,{'stedkode':stedkode})
        except Errors.TooManyRowsError:
            logger.error("stedkode %s repeated in ou_history" % stedkode)
        except Errors.NotFoundError:
            pass
        else:            
            logger.warn("Stedkode %s for person %s remapped to %s" % \
                (stedkode, ssn, new_sko))
            stedkode = "%s" % new_sko

        if persons.get(ssn,None):
            dupes.append(ssn)
        else:
            persons[ssn]=person_data

        #logger.debug('Person %s' % person_data)
        #tilsettinger we have seen before
        current=tilsettinger.get(ssn,dict())
        if not current:
            # sted not seen before, insert
            tilsettinger[ssn]={stedkode: tils_data}
        else:
            tmp=current.get(stedkode)
            if tmp:
                logger.warn("Several tilsettiger to same place for %s" % (ssn))
                #several tilsettinger to same place. Decide which to keep.
                # TODO: We can use standel or nr/av  fields. Which? 
                # Use st.andel for now
                if tils_data['stillingsandel']>tmp.get(tils_data['stillingsandel']):
                    logger.info("New aff at same place, upgraded for %s" % (ssn))
                    tilsettinger[ssn][stedkode]=tils_data
            else:
                logger.info("adding tilsetting for %s" % (ssn))
                tilsettinger[ssn][stedkode]=tils_data
                
    return persons,tilsettinger,permisjoner

class person_xml:

    def __init__(self,out_file):
        self.out_file=out_file


    def create(self,persons,affiliations,permisjoner):
        """ Build a xml that import_lt should process:
        <person tittel_personlig=""
        fornavn=""
        etternavn=""
        fnr=""
        fakultetnr_for_lonnsslip=""
        instituttnr_for_lonnsslip=""
        gruppenr_for_lonnsslip=""
        #adresselinje1_privatadresse=""
        #poststednr_privatadresse=""
        #poststednavn_privatadresse=""
        #uname=""
        >
        <bilag stedkode=""/>
        </person>
        """

        stream = AtomicFileWriter(self.out_file, "w")
        writer = xmlprinter.xmlprinter(stream,
                                       indent_level = 2,
                                       data_mode = True,
                                       input_encoding = "latin1")
        writer.startDocument(encoding = "iso8859-1")
        writer.startElement("data")

        for fnr, person_data in persons.iteritems():
            
            affs = affiliations.get(fnr)
            aff_keys=affs.keys()
            person_data['fnr']=fnr

            temp_tils=list()
            for sted in aff_keys:
                aff = affs.get(sted)
                ## use . instead of , as decimal char.
                st_andel=aff.get('stillingsandel','').replace(',','.')
                if st_andel=='':
                    logger.error("ST.andel for fnr %s er tom",fnr)
                tils_dict = {'hovedkategori' : aff['hovedkategori'],
                             'stillingskode' : aff['stillingskode'],
                             'tittel' : aff['tittel'],
                             'stillingsandel' : st_andel,
                             'fakultetnr_utgift' : sted[0:2],
                             'instituttnr_utgift' : sted[2:4],
                             'gruppenr_utgift' : sted[4:6],
                             'dato_fra' : aff['dato_fra'],
                             'dato_til' : aff['dato_til'],
                             'dbh_kat' : aff['dbh_kat'],
                             'hovedarbeidsforhold': aff['hovedarbeidsforhold'],
                          }
                temp_tils.append(tils_dict)
            writer.startElement("person",person_data)
            for tils in temp_tils:
                writer.emptyElement("tils",tils)
            writer.endElement("person")
        writer.endElement("data")
        writer.endDocument()
        stream.close()


def main():
       
    out_file = os.path.join(dumpdir_employees, default_employee_file)
    paga_file = os.path.join(dumpdir_paga, default_paga_file)
    try:
        opts,args = getopt.getopt(sys.argv[1:],'hp:o:',
            ['paga-file=','out-file=','help'])
    except getopt.GetoptError,m:
        usage(1,m)

    for opt,val in opts:
        if opt in ('-o','--out-file'):
            out_file = val
        if opt in ('-p','--paga-file'):
            paga_file = val
        if opt in ('-h','--help'):
            usage()
    
    pers,tils,perms = parse_paga_csv(paga_file)
    logger.debug("File parsed. Got %d persons" % (len(pers),))
    xml=person_xml(out_file)
    xml.create(pers,tils,perms)
    sys.exit(0)
    
def usage(exit_code=0,msg=None):
    if msg: print msg
    print __doc__
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
