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

from Cerebrum.modules.no.uio.access_FS import FS

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
        return self.db.query(qry)

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
      st.studieretningkode, st.studierettstatkode
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
	fs.registerkort for innev�rende semester."""
	qry = """
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.etternavn, p.fornavn, 
      p.kjonn, s.adrlin1_semadr,
      s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
      s.adresseland_semadr, p.adrlin1_hjemsted,
      p.adrlin2_hjemsted, p.postnr_hjemsted, 
      p.adrlin3_hjemsted, p.adresseland_hjemsted,
      nk.studieprogramkode, nk.studieretningkode, 
      nk.kullkode, nk.klassekode
FROM  fs.person p, fs.student s, fs.naverende_klasse nk, 
      fs.studiekull sk, fs.registerkort r
WHERE p.fodselsdato = s.fodselsdato AND
      p.personnr = s.personnr AND
      p.fodselsdato = nk.fodselsdato AND
      p.personnr = nk.personnr AND
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
      nk.kullkode, nk.klassekode
FROM  fs.person p, fs.student s, fs.naverende_klasse nk, 
      fs.studiekull sk
WHERE p.fodselsdato = s.fodselsdato AND
      p.personnr = s.personnr AND
      p.fodselsdato = nk.fodselsdato AND
      p.personnr = nk.personnr AND
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
     st.studieretningkode, st.status_privatist
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
      st.studieretningkode, st.studieprogramkode
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
        informasjon om utd_plan og eier samt studieprogkode"""
        qry = """
SELECT studieprogramkode, studieprognavn, studienivakode,
       status_utdplan, institusjonsnr_studieansv,
       faknr_studieansv, instituttnr_studieansv, gruppenr_studieansv, 
FROM fs.studieprogram
WHERE status_utgatt = 'N' """
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
   versjonskode, aktivitetkode, terminnr, etterutdkurskode, 
   kurstidsangivelsekode
FROM fs.personrolle 
WHERE dato_fra < SYSDATE AND
      NVL(dato_til,SYSDATE) >= sysdate AND
      institusjonsnr = %s""" %  institusjonsnr
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
  r.terminnr, r.terminkode, r.arstall
FROM fs.emne e, fs.undervisningsenhet r
WHERE r.emnekode = e.emnekode AND
      r.versjonskode = e.versjonskode AND
      """ 
        if (sem=="current"):
	    qry +="""%s""" % self.get_termin_aar(only_current=1)
        else: 
	    qry +="""%s""" % self.get_next_termin_aar()
	return (self._get_cols(qry), self.db.query(qry))
	
   
    def GetEmnerUndervNaa(self):
	"""Hent data om emner som har undervisning dette semesteret.
	Skal brukes til � opprette rom (p� emneniv�) i ClassFronter. 
	Bruker fs.emne og fs.undervisninsenhet. Henter emnekode, 
	versjonskode, terminkode, �rstall og terminnummer, samt 
	emnets navn og forkortet navn. Forel�pig hentes data for
	n�v�rende semester, det er mulig at man vil �nske � utvide 
	dette til � omfatte flere semestre. Dumpes til fil p� 
	/cerebrum/dumps/FS/aktive_emner.xml"""
	qry = """
SELECT DISTINCT
   r.emnekode, e.emnenavnfork, r.versjonskode, r.terminnr, 
   r.terminkode, r.arstall
FROM fs.emne e, fs.undervisningsenhet r
WHERE r.emnekode = e.emnekode AND
      r.versjonskode = e.versjonskode AND
      %s """ % self.get_termin_aar(only_current=1)
        return (self._get_cols(qry),self.db.query(qry))

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
# �vrige metoder (ikke i bruk)
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
	yr, mon, md  = t = time.localtime()[0:3]
	if mon <= 6:
	    next = "(r.terminkode LIKE 'H_ST' AND r.arstall=%s)\n" % yr
	else:
	    next = "(r.terminkode LIKE 'V_R' AND r.arstall=%s)\n" % (yr + 1)
	return next

    def get_termin_aar(self, only_current=0):
        yr, mon, md = t = time.localtime()[0:3]
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


