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

import re
import os
import sys
import time
import xml.sax

from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum.Utils import Factory
from Cerebrum.extlib import sets

class HiAFS(FS):
    """FS klassen definerer et sett med metoder som kan benyttes for �
    hente ut informasjon om personer og OU-er fra FS. De fleste
    metodene returnerer en tuple med kolonnenavn fulgt av en tuple med
    dbrows."""

################################################################
#       Studenter                                              #
################################################################

    def GetTilbud(self, institusjonsnr=0):
	"""Hent data om studenter med tilbud til opptak p�
	et studieprogram ved H�gskolen i Agder. """
	qry = """
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.etternavn, p.fornavn, 
      p.adrlin1_hjemsted, p.adrlin2_hjemsted,
      p.postnr_hjemsted, p.adrlin3_hjemsted, p.adresseland_hjemsted,
      p.sprakkode_malform, osp.studieprogramkode, p.kjonn,
      p.status_reserv_nettpubl
FROM fs.soknadsalternativ sa, fs.person p, fs.opptakstudieprogram osp,
     fs.studieprogram sp
WHERE p.fodselsdato=sa.fodselsdato AND
      p.personnr=sa.personnr AND
      sa.institusjonsnr='%s' AND 
      sa.tilbudstatkode IN ('I', 'S') AND
      sa.studietypenr = osp.studietypenr AND
      osp.studieprogramkode = sp.studieprogramkode
      AND %s
      """ % (institusjonsnr, self.is_alive())
        return (self._get_cols(qry),self.db.query(qry))

# Datagrunnlaget hos HiA er ikke ryddet ferdig, derfor skal vi ikke bruke dette
# s�ket forel�pig. Lar det st� i tilfelle siden vi kan f� bruk for 
# den i fremtiden.

    def GetOpptak(self):
	"""Hent inn data om alle studenter med opptak til
	et studieprogram ved HiA (studierett)."""
        qry = """
SELECT DISTINCT 
      p.fodselsdato, p.personnr, p.etternavn, 
      p.fornavn, p.kjonn, s.adrlin1_semadr,
      s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr, 
      s.adresseland_semadr, p.adrlin1_hjemsted,
      p.sprakkode_malform,st.studieprogramkode, 
      st.studieretningkode, st.studierettstatkode,
      s.studentnr_tildelt
FROM  fs.student s, fs.person p, fs.studierett st
WHERE p.fodselsdato = s.fodselsdato AND
      p.personnr = s. personnr AND
      p.fodselsdato = st.fodselsdato AND
      p.personnr = st.personnr AND
      NVL(st.dato_gyldig_til,SYSDATE) >= sysdate 
      AND %s 
      """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry))

    def GetAktive(self):
	""" Hent opplysninger om alle aktive studenter. En
	aktiv student er definert som en student p� et aktivt 
	kull som i tillegg har en forekomst i tabellen 
	fs.registerkort for innev�rende semester. For � f� helt riktige 
	data her burde man ogs� sjekke at studierett er gyldig, men
	det ser ut til at HiA da mister noe data. Etterhvert (n�r opprydingen
	i FSHIA er gjort) b�r man legge inn setningen
	NVL(st.dato_gyldig_til,SYSDATE) >= sysdate i begge delene av s�ket."""
	qry = """
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.etternavn, p.fornavn, 
      p.kjonn, s.adrlin1_semadr,
      s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
      s.adresseland_semadr, p.adrlin1_hjemsted,
      p.adrlin2_hjemsted, p.postnr_hjemsted, 
      p.adrlin3_hjemsted, p.adresseland_hjemsted,
      nk.studieprogramkode, nk.studieretningkode, 
      nk.kullkode, nk.klassekode, s.studentnr_tildelt
FROM  fs.person p, fs.student s, fs.naverende_klasse nk, 
      fs.registerkort r, fs.studierett st
WHERE p.fodselsdato = s.fodselsdato AND
      p.personnr = s.personnr AND
      p.fodselsdato = nk.fodselsdato AND
      p.personnr = nk.personnr AND
      nk.fodselsdato = st.fodselsdato AND
      nk.personnr = st.personnr AND
      nk.studieprogramkode = st.studieprogramkode AND
      st.studierettstatkode NOT IN ('PRIVATIST','EVU') AND
      %s AND
      p.fodselsdato = r.fodselsdato AND
      p.personnr = r.personnr AND
      %s """ % (self.is_alive(),self.get_termin_aar(only_current=1))
        qry += """ UNION
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.etternavn, p.fornavn, 
      p.kjonn, s.adrlin1_semadr,
      s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
      s.adresseland_semadr, p.adrlin1_hjemsted,
      p.adrlin2_hjemsted, p.postnr_hjemsted, 
      p.adrlin3_hjemsted, p.adresseland_hjemsted,
      nk.studieprogramkode, nk.studieretningkode, 
      nk.kullkode, nk.klassekode, s.studentnr_tildelt
FROM  fs.person p, fs.student s, fs.naverende_klasse nk, 
      fs.studiekull sk, fs.studierett st
WHERE p.fodselsdato = s.fodselsdato AND
      p.personnr = s.personnr AND
      p.fodselsdato = nk.fodselsdato AND
      p.personnr = nk.personnr AND
      nk.fodselsdato = st.fodselsdato AND
      nk.personnr = st.personnr AND
      nk.studieprogramkode = st.studieprogramkode AND
      st.studierettstatkode NOT IN ('PRIVATIST','EVU') AND
      %s AND
      nk.kullkode = sk.kullkode AND
      nk.studieprogramkode = sk.studieprogramkode AND
      sk.status_aktiv = 'J' """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry))

    def GetPrivatist(self):
	"""Her henter vi informasjon om privatister ved HiA"""
	qry = """
SELECT DISTINCT
     p.fodselsdato, p.personnr, p.etternavn,
     p.fornavn, p.kjonn, s.adrlin1_semadr,
     s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
     s.adresseland_semadr, p.adrlin1_hjemsted,
     p.sprakkode_malform,st.studieprogramkode,
     st.studieretningkode, st.status_privatist, 
     s.studentnr_tildelt
FROM fs.student s, fs.person p, fs.studierett st
WHERE p.fodselsdato = s.fodselsdato AND
      p.personnr = s. personnr AND
      p.fodselsdato = st.fodselsdato AND
      p.personnr = st.personnr AND
      (st.studierettstatkode = 'PRIVATIST' OR
       st.status_privatist = 'J') AND
      NVL(st.dato_gyldig_til,SYSDATE) >= sysdate """
        return (self._get_cols(qry), self.db.query(qry))
      

    def GetAlleMedEvuStudierett(self):
	""" Opplysninger om EVU-studenter ved HiA."""
	qry = """
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.etternavn,
      p.fornavn, p.kjonn, s.adrlin1_semadr,
      s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
      s.adresseland_semadr, p.adrlin1_hjemsted,
      p.adrlin2_hjemsted, p.postnr_hjemsted, 
      p.adrlin3_hjemsted, p.adresseland_hjemsted,
      s.studentnr_tildelt, st.studieretningkode, 
      st.studieprogramkode
FROM  fs.student s, fs.person p, fs.studierett st, fs.studieprogram sp
WHERE p.fodselsdato = s.fodselsdato AND
      p.personnr = s. personnr AND
      p.fodselsdato = st.fodselsdato AND
      p.personnr = st.personnr AND
      st.studierettstatkode = 'EVU' AND
      NVL(st.dato_gyldig_til,SYSDATE) >= sysdate 
      AND %s
      """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry))

    def GetEkteEvu(self):
        qry = """
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
      p.kjonn, d.adrlin1_hjem, d.adrlin2_hjem, d.postnr_hjem,
      d.adrlin3_hjem, d.adresseland_hjem, d.adrlin1_job, 
      d.adrlin2_job, d.postnr_job, d.adrlin3_job, d.adresseland_job,
      d.deltakernr, d.emailadresse,
      k.etterutdkurskode, e.studieprogramkode,
      e.faknr_adm_ansvar, e.instituttnr_adm_ansvar,
      e.gruppenr_adm_ansvar
FROM  fs.deltaker d, fs.person p, fs.kursdeltakelse k,
      fs.etterutdkurs e
WHERE p.fodselsdato=d.fodselsdato AND
      p.personnr=d.personnr AND
      d.deltakernr=k.deltakernr AND
      e.etterutdkurskode=k.etterutdkurskode AND
      NVL(e.status_nettbasert_und,'J')='J' AND
      k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
      e.dato_til > SYSDATE - 180 
      AND %s
      """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry))

################################################################
#	Studieprogrammer				       #
################################################################	

    def GetStudieproginf(self):
        """For hvert definerte studieprogram henter vi 
        informasjon om utd_plan og eier samt studieprogkode. Dumpen fra
	denne (studieprog.xml) skal ogs� brukes i forbindelse med bygging 
	av rom i CF."""
        qry = """
SELECT studieprogramkode, studieprognavn, studienivakode,
       status_utdplan, institusjonsnr_studieansv, 
       faknr_studieansv, instituttnr_studieansv, gruppenr_studieansv,
       status_utgatt
FROM fs.studieprogram"""

# Det er en del studenter p� HiA som har opptak til inaktive studieprogrammer
# derfor m� vi fjerne dette kravet fram til det er ryddet opp i dette
# Kravet burde settes inn permanent siden man bygger felles-rom for studieprogrammer
# i CF p� grunnlag av disse data (det er litt dumt � bygge flere enn n�dvndig
# Vi henter dog status_utgatt, det burde kunne brukes til � skille ut de programmene
# man ikke skal ha rom for.
# WHERE status_utgatt = 'N' """
        return (self._get_cols(qry), self.db.query(qry))


##################################################################
# Studiekull
##################################################################

    def GetAktivStudiekull(self):
	"""Henter informasjon om aktive studiekull."""
	qry = """
SELECT
      studieprogramkode, kullkode, studiekullnavn, 
      klassetrinn_start, terminnr_maks
FROM  fs.studiekull
WHERE status_aktiv = 'J' """
        return (self._get_cols(qry), self.db.query(qry))


##################################################################
# Fronterspesifikke s�k
##################################################################

    def GetAllePersonRoller(self, institusjonsnr=0):
	"""Hent alle personroller registrert i FS. For hver person
	vi plukker ut trenger vi � vite hvilke roller personen innehar,
	i tilknytting til hvilket emne(kode), versjon(skode) for innev�rende 
	og neste semester/termin. I tillegg henter vi dato_fra og dato_til
	da disse angir rollens varighet. """
        qry = """
SELECT DISTINCT
   fodselsdato, personnr, rollenr, rollekode, dato_fra, dato_til,
   institusjonsnr, faknr, gruppenr, studieprogramkode, emnekode, 
   versjonskode, aktivitetkode, terminkode, arstall, terminnr,
   etterutdkurskode, kurstidsangivelsekode
FROM fs.personrolle 
WHERE dato_fra < SYSDATE AND
      NVL(dato_til,SYSDATE) >= sysdate"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetUndervEnhet(self, sem="current"):
	"""Metoden som henter data om undervisningsenheter
	i n�verende (current) eller neste (next) semester. Default
	vil v�re n�v�rende semester. For hver undervisningsenhet 
	henter vi institusjonsnr, emnekode, versjonskode, terminkode + �rstall 
	og terminnr."""
	qry = """
SELECT DISTINCT
  r.institusjonsnr, r.emnekode, r.versjonskode, e.emnenavnfork,
  e.emnenavn_bokmal, e.faknr_kontroll, e.instituttnr_kontroll, 
  e.gruppenr_kontroll, r.terminnr, r.terminkode, r.arstall
FROM fs.emne e, fs.undervisningsenhet r
WHERE r.emnekode = e.emnekode AND
      r.versjonskode = e.versjonskode AND
      """ 
        if (sem=="current"):
	    qry +="""%s""" % self.get_termin_aar(only_current=1)
        else: 
	    qry +="""%s""" % self.get_next_termin_aar()
	return (self._get_cols(qry), self.db.query(qry))

    def GetStudenterUndervEnhet(self, institusjonsnr, emnekode, versjonskode,
				terminnr, terminkode, arstall):
	"""Finn f�dselsnumrene til alle studenter p� et gitt 
	undervisningsenhet. Skal brukes til � generere grupper for
	adgang til CF."""
	qry = """
SELECT DISTINCT
  fodselsdato, personnr
FROM fs.undervisningsmelding
WHERE
  institusjonsnr = :institusjonsnr AND
  emnekode = :emnekode AND
  versjonskode = :versjonskode AND
  terminnr = :terminnr AND
  terminkode = :terminkode AND
  arstall = :arstall"""
        return (self._get_cols(qry),
                self.db.query(qry, {'institusjonsnr': institusjonsnr,
                                    'emnekode': emnekode,
                                    'versjonskode': versjonskode,
                                    'terminnr': terminnr,
                                    'terminkode': terminkode,
                                    'arstall': arstall}
                              ))

    def StudprogAlleStud(self, faknr, studprogkode):
	"""Henter data om alle studenter p� et gitt studieprogram og 
	fakultetet denne tilh�rer. Med alle studenter mener vi her de
	studentene som er med i et aktivt studiekull tilknyttet et 
	studieprogram."""
	qry = """
SELECT DISTINCT
  sp.faknr_studieansv, nk.fodselsdato, nk.personnr, 
  nk.studieprogramkode, nk.kullkode,nk.klassekode
FROM fs.naverende_klasse nk, fs.studieprogram sp, fs.studiekull sk
WHERE sp.faknr_studieansv = :faknr AND
      sp.studieprogramkode = :studprogkode AND
      sp.studieprogramkode = nk.studieprogramkode
      nk.kullkode = sk.kullkode AND
      sk.statusaktiv = 'J'"""
        return (self._get_cols(qry),
                self.db.query(qry, {'faknr': faknr,
                                    'studprogkode': studprogkode}
                              ))

    def AlternativtGetAlleStudStudprog(self, studprogkode):
	"""Finn alle studenter p� et studieprogram.
	Skal brukes for � populere fellesrom i CF. 
	Henter opplysninger om alle studenter som har
	en (hvilken som helt) gyldig studierett til 
	studieprogrammet 'studprogkode'"""
	qry = """
SELECT DISTINCT
  fodselsdato, personnr, studieprogramkode
from fs.studierett 
WHERE
  studieprogramkode = :studprogkode AND
  NVL(st.dato_gyldig_til,SYSDATE) >= sysdate""" 
        return (self._get_cols(qry),
                self.db.query(qry, {'studprogkode': studprogkode}))

##################################################################
# Metoder for OU-er:
##################################################################


    def GetAlleOUer(self, institusjonsnr=0):
        """Hent data om stedskoder registrert i FS. Dumpes til fil
	p� /cerebrum/dumps/FS/ou.xml"""
        qry = """
SELECT DISTINCT
   faknr, instituttnr, gruppenr, stedakronym, stednavn_bokmal,
   faknr_org_under, instituttnr_org_under, gruppenr_org_under,
   adrlin1, adrlin2, postnr, telefonnr, faxnr,
   adrlin1_besok, adrlin2_besok, postnr_besok, url, emailadresse,
   bibsysbeststedkode, stedkode_konv
FROM fs.sted
WHERE institusjonsnr='%s'
	 """ % institusjonsnr
        return (self._get_cols(qry),self.db.query(qry))
        
##################################################################
# �vrige metoder (ikke i bruk enn�)
##################################################################


    def GetAlleEmner(self):
        """Hent informasjon om alle emner i FS. Denne brukes forel�pig 
        ikke til noe som helst men det kan tenkes at vi trenger noen av
        dataene etterhvert s� den beholder vi."""
        qry = """
SELECT DISTINCT
   emnekode, versjonskode, emnenavnfork, institusjonsnr_reglement,
   faknr_reglement, instituttnr_reglement, gruppenr_reglement, 
   studienivakode, emnetypekode, fjernundstatkode, terminkode_und_forste,
   arstall_und_forste, terminkode_und_siste, arstall_und_siste
FROM fs.emne """
        return (self._get_cols(qry),self.db.query(qry))

##################################################################
# Hjelpemetoder  
##################################################################

    def is_alive(self):
	"""Sjekk om en person er registrert som avd�d i FS"""
	return "NVL(p.status_dod, 'N') = 'N'\n"

    def get_next_termin_aar(self):
	"""en fin metode som henter neste semesters terminkode og �rstal."""
	yr, mon, md = time.localtime()[0:3]
	if mon <= 6:
	    next = "(r.terminkode LIKE 'H_ST' AND r.arstall=%s)\n" % yr
	else:
	    next = "(r.terminkode LIKE 'V_R' AND r.arstall=%s)\n" % (yr + 1)
	return next

    def get_termin_aar(self, only_current=0):
        yr, mon, md = time.localtime()[0:3]
        if mon <= 6:
            # Months January - June == Spring semester
            current = "(r.terminkode LIKE 'V_R' AND r.arstall=%s)\n" % yr;
            if only_current or mon >= 3 or (mon == 2 and md > 15):
                return current
            return "(%s OR (r.terminkode LIKE 'H_ST' AND r.arstall=%d))\n" % (
                current, yr-1)
        # Months July - December == Autumn semester
        current = "(r.terminkode LIKE 'H_ST' AND r.arstall=%d)\n" % yr
        if only_current or mon >= 10 or (mon == 9 and md > 15):
            return current
        return "(%s OR (r.terminkode LIKE 'V_R' AND r.arstall=%d))\n" % (current, yr)


class element_attribute_xml_parser(xml.sax.ContentHandler, object):

    elements = {}
    """A dict containing all valid element names for this parser.

    The dict must have a key for each of the XML element names that
    are valid for this parser.  The corresponding values indicate
    whether or not the parser class should invoke the callback
    function upon encountering such an element.

    Subclasses should override this entire attribute (i.e. subclasses
    should do elements = {key: value, ...}) rather than add more keys
    to the class attribute in their parent class (i.e. subclasses
    should not do elements[key] = value)."""

    def __init__(self, filename, callback, encoding='iso8859-1'):
        self._callback = callback
        self._encoding = encoding
        xml.sax.parse(filename, self)

    def startElement(self, name, attrs):
        if name not in self.elements:
            raise ValueError, \
                  "Unknown XML element: %r" % (name,)
        # Only set self._in_element etc. for interesting elements.
        if self.elements[name]:
            data = {}
            for k, v in attrs.items():
                data[k] = v.encode(self._encoding)
            self._callback(name, data)

class non_nested_xml_parser(element_attribute_xml_parser):

    def __init__(self, filename, callback, encoding='iso8859-1'):
        self._in_element = None
        self._attrs = None
        super(non_nested_xml_parser, self).__init__(
            filename, callback, encoding)

    def startElement(self, name, attrs):
        if name not in self.elements:
            raise ValueError, \
                  "Unknown XML element: %r" % (name,)
        if self._in_element is not None:
            raise RuntimeError, \
                  "Can't deal with nested elements (<%s> before </%s>)." % (
                name, self._in_element)
        # Only set self._in_element etc. for interesting elements.
        if self.elements[name]:
            self._in_element = name
            self._data = {}
            for k, v in attrs.items():
                self._data[k] = v.encode(self._encoding)

    def endElement(self, name):
        if name not in self.elements:
            raise ValueError, \
                  "Unknown XML element: %r" % (name,)
        if self._in_element == name:
            self._callback(name, self._data)
            self._in_element = None

class ou_xml_parser(element_attribute_xml_parser):
    "Parserklasse for ou.xml."

    elements = {'data': False,
                'sted': True,
                'komm': True,
                }

class person_xml_parser(non_nested_xml_parser):
    "Parserklasse for person.xml."

    elements = {'data': False,
                'aktiv': True,
                'tilbud': True,
                'evu': True,
                'privatist_studieprogram': True,
                }

class roles_xml_parser(non_nested_xml_parser):
    "Parserklasse for studieprog.xml."

    elements = {'data': False,
                'role': True,
                }

    def endElement(self, name):
        if name == 'role':
            do_callback = self.validate_role(self._data)
            if not do_callback:
                self._in_element = None
        return super(roles_xml_parser, self).endElement(name)

    def validate_role(self, attrs):
        # Verifiser at rollen _enten_ gjelder en (fullstendig
        # spesifisert) undervisningsenhet _eller_ en und.aktivitet
        # _eller_ et studieprogram, osv. -- og ikke litt av hvert.
        col2target = {
            'fodselsdato': None,
            'personnr': None,
            'rollenr': None,
            'rollekode': None,
            'dato_fra': None,
            'dato_til': None,
            'institusjonsnr': ['sted', 'emne', 'undenh', 'undakt'],
            'faknr': ['sted'],
            'instituttnr': ['sted'],
            'gruppenr': ['sted'],
            'studieprogramkode': ['stprog'],
            'emnekode': ['emne', 'undenh', 'undakt'],
            'versjonskode': ['emne', 'undenh', 'undakt'],
            'aktivitetkode': ['undakt'],
            'terminkode': ['undenh', 'undakt'],
            'arstall': ['undenh', 'undakt'],
            'terminnr': ['undenh', 'undakt'],
            'etterutdkurskode': ['evu'],
            'kurstidsangivelsekode': ['evu'],
            'saksbehinit_opprettet': None,
            'dato_opprettet': None,
            'saksbehinit_endring': None,
            'dato_endring': None,
            'merknadtekst': None,
            }
        logger = Factory.get_logger()
        data = attrs.copy()
        target = None
        not_target = sets.Set()
        possible_targets = sets.Set()
        for col, targs in col2target.iteritems():
            if col in data:
                del data[col]
                if targs is None:
                    continue
                possible_targets = possible_targets.union(targs)
                if target is None:
                    # Har ikke sett noen kolonner som har med
                    # spesifisering av target � gj�re f�r; target
                    # m� v�re en av de angitt i 'targs'.
                    target = sets.Set(targs)
                else:
                    # Target m� v�re i snittet mellom 'targs' og
                    # 'target'.
                    target = target.intersection(targs)
            else:
                if targs is None:
                    continue
                # Kolonnen kan spesifisere target, men er ikke med i
                # denne posteringen; oppdater not_target.
                not_target = not_target.union(targs)

        do_callback = True
        if data:
            # Det fantes kolonner i posteringen som ikke er tatt med i
            # 'col2target'-dicten.
            logger.error("Ukjente kolonner i FS.PERSONROLLE: %r", data)
            do_callback = False

        target = tuple(target - not_target)
        if len(target) <> 1:
            if len(target) > 1:
                logger.error("Personrolle har flertydig angivelse av",
                             " targets, kan v�re: %r (XML = %r).",
                             target, attrs)
                attrs['::rolletarget::'] = target
            else:
                logger.error("Personrolle har ingen tilstrekkelig"
                             " spesifisering av target, inneholder"
                             " elementer fra: %r (XML = %r).",
                             tuple(possible_targets), attrs)
                attrs['::rolletarget::'] = tuple(possible_targets)
            do_callback = False
        else:
            logger.debug("Personrolle OK, target = %r (XML = %r).",
                         target[0], attrs)
            # Target er entydig og tilstrekkelig spesifisert; gj�r
            # dette tilgjengelig for callback.
            attrs['::rolletarget::'] = target
        return do_callback


class studieprog_xml_parser(non_nested_xml_parser):
    "Parserklasse for studieprog.xml."

    elements = {'data': False,
                'studprog': True,
                }

class underv_enhet_xml_parser(non_nested_xml_parser):
    "Parserklasse for underv_enhet.xml."

    elements = {'undervenhet': False,
                'undenhet': True,
                }

class student_undenh_xml_parser(non_nested_xml_parser):
    "Parserklasse for student_undenh.xml."

    elements = {'data': False,
                'student': True
                }
