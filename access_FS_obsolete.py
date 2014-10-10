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

class UiTFS(FS):
    """FS klassen definerer et sett med metoder som kan benyttes for �
    hente ut informasjon om personer og OU-er fra FS. De fleste
    metodene returnerer en tuple med kolonnenavn fulgt av en tuple med
    dbrows. """
    def __init__(self, db):
        self.db = db
        t = time.localtime()[0:2]
        if t[1] <= 6:
            self.sem = 'V'
        else:
            self.sem = 'H'
        self.year = t[0]
        self.YY = str(t[0])[2:]

    

    # TODO: Belongs in a separate file, and should consider using row description
    def _get_cols(self, sql):
        sql = sql[:sql.upper().find("FROM")+4]
        m = re.compile(r'^\s*SELECT\s*(DISTINCT)?(.*)FROM', re.DOTALL | re.IGNORECASE).match(sql)
        if m == None:
            raise InternalError, "Unreconginzable SQL!"

        # Simple SQL-parser. Read TODO above.
        #  Problem: Some statements in a SELECT ... are not colomn-names
        #  Ad.hoc solution: "TO_CHAR(e.dato_til,'YYYY-MM-DD')" becomes
        #                   "to_char_e_dato_til_YYYY-MM-DD_"
        #  Supports '... AS foo'
        ret = []
        tmp = ""
        lpar = rpar = 0
        patt = re.compile("^.*\s+AS\s+\"?([a-zA-Z0-9_]+)\"?\s*", re.IGNORECASE)
        for cols in m.group(2).split(","):
            cols = re.sub('\'', '', cols)
            cols = cols.strip()
            chars = list(cols)
            for c in chars:
                if c == '(': lpar+=1
                elif c == ')': rpar+=1
            if lpar == rpar:
                if tmp:
                    tmp = tmp + "," + cols
                else:
                    tmp = cols
                lpar = rpar = 0
                mobj = patt.match(tmp)
                if mobj:
                    ret.append(mobj.group(1))
                else:
                    ret.append(re.sub('[(),]', '_', tmp))
                tmp = ""
            else:
                if tmp:
                    tmp = tmp + "," + cols
                else:
                    tmp = cols

        return ret
        
################################################################
#       Studenter                                              #
################################################################


# P�virkes ikke av endringene ved overgang til FS 5.0
# 20081007 - RMI000 - Added cutoff for tilbud older than 30 days
#                     sa.dato_opprettet > (sysdate - 30)
    def GetTilbud(self, institusjonsnr=0):
	"""Hent data om studenter med tilbud til opptak p�
	et studieprogram ved uit� som har takket ja
        til tilbudet. """
	qry = """
SELECT DISTINCT
      p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
      p.adrlin1_hjemsted, p.adrlin2_hjemsted,
      p.postnr_hjemsted, p.adrlin3_hjemsted, p.adresseland_hjemsted,
      p.sprakkode_malform, osp.studieprogramkode, p.kjonn,
      p.status_reserv_nettpubl, p.telefonnr_mobil
FROM fs.soknadsalternativ sa, fs.person p, fs.opptakstudieprogramtermin osp,
fs.studieprogram sp
WHERE p.fodselsdato=sa.fodselsdato AND
      p.personnr=sa.personnr AND
      sa.institusjonsnr='%s' AND
      sa.dato_opprettet > (sysdate - 30) AND
      sa.tilbudstatkode IN ('I', 'S') AND
      sa.svarstatkode_svar_pa_tilbud='J' AND
      sa.studietypenr = osp.studietypenr AND
      osp.studieprogramkode = sp.studieprogramkode
      AND %s
      """ % (institusjonsnr, self.is_alive())
        return (self._get_cols(qry),self.db.query(qry))


    # def GetAktive(self):
# 	""" Hent opplysninger om studenter definert som aktive 
# 	ved UiT. En aktiv student er enten med i et aktivt kull og
#         har et gyldig studierett eller har en forekomst i registerkort 
#         for innev�rende semester og har en gyldig studierett"""

# 	qry = """

# SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
#        s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
#        s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
#        p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
#        p.adresseland_hjemsted, p.status_reserv_nettpubl,
#        p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
#        sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
#        sps.arstall_kull, p.kjonn, p.status_dod, p.telefonnr_mobil
# FROM fs.kull k, fs.studieprogramstudent sps, fs.person p, fs.student s
# WHERE p.fodselsdato = sps.fodselsdato AND
#       p.personnr = sps.personnr AND
#       p.fodselsdato = s.fodselsdato AND
#       p.personnr = s.personnr AND
#       %s AND
#       k.studieprogramkode = sps.studieprogramkode AND
#       k.terminkode = sps.terminkode_kull AND
#       k.arstall = sps.arstall_kull AND
#       NVL(k.status_aktiv,'J') = 'J' AND
#       NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE
# UNION
# SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
#        s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
#        s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
#        p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
#        p.adresseland_hjemsted, p.status_reserv_nettpubl,
#        p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
#        sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
#        sps.arstall_kull, p.kjonn, p.status_dod, p.telefonnr_mobil
# FROM fs.registerkort r, fs.studieprogramstudent sps, fs.person p, fs.student s
# WHERE p.fodselsdato = sps.fodselsdato AND
#       p.personnr = sps.personnr AND
#       p.fodselsdato = s.fodselsdato AND
#       p.personnr = s.personnr AND
#       %s AND
#       p.fodselsdato = r.fodselsdato AND
#       p.personnr = r.personnr AND
#       NVL(sps.dato_studierett_gyldig_til,SYSDATE)>= SYSDATE AND
#       %s """ % (self.is_alive(), self.is_alive(), self.get_termin_aar(only_current=1))
#         return (self._get_cols(qry),self.db.query(qry))
    def GetAktive(self):
        """Hent personer med opptak til et studieprogram ved
        institusjonen og som enten har v�rt registrert siste �ret
        eller opptak efter 2003-01-01.  Henter ikke de som har
        fremtidig opptak.  Disse kommer med 14 dager f�r dato for
        tildelt opptak.  Alle disse skal ha affiliation med status
        kode 'opptak' til stedskoden sp.faknr_studieansv +
        sp.instituttnr_studieansv + sp.gruppenr_studieansv"""

        qry = """
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
        s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
        s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
        p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
        p.adresseland_hjemsted, p.status_reserv_nettpubl, 
        p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
        sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
        sps.arstall_kull, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps
        WHERE  p.fodselsdato=s.fodselsdato AND
        p.personnr=s.personnr AND
        p.fodselsdato=sps.fodselsdato AND
        p.personnr=sps.personnr AND
        NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
        sps.status_privatist = 'N' AND
        sps.dato_studierett_tildelt < SYSDATE + 14 AND
        ((sps.dato_studierett_gyldig_til != NULL) OR (sps.dato_studierett_tildelt >= to_date('2003-01-01', 'yyyy-mm-dd')))
        """
        # UIT: Added (sps.dato_studierett_gyldig_til != NULL) OR.  // in the above query
        qry += """ UNION
        SELECT DISTINCT s.fodselsdato, s.personnr, p.etternavn, p.fornavn,
        s.adrlin1_semadr,s.adrlin2_semadr, s.postnr_semadr,
        s.adrlin3_semadr, s.adresseland_semadr, p.adrlin1_hjemsted,
        p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
        p.adresseland_hjemsted, p.status_reserv_nettpubl,
        p.sprakkode_malform, sps.studieprogramkode, sps.studieretningkode,
        sps.studierettstatkode, sps.studentstatkode, sps.terminkode_kull,
        sps.arstall_kull, p.kjonn, p.status_dod
        FROM fs.student s, fs.person p, fs.studieprogramstudent sps, fs.registerkort r
        WHERE  p.fodselsdato=s.fodselsdato AND
        p.personnr=s.personnr AND
        p.fodselsdato=sps.fodselsdato AND
        p.personnr=sps.personnr AND
        p.fodselsdato=r.fodselsdato AND
        p.personnr=r.personnr AND
        NVL(sps.dato_studierett_gyldig_til,SYSDATE) >= sysdate AND
        sps.status_privatist = 'N' AND
        r.arstall >= (%s -1)
        """% (self.year)
        return (self._get_cols(qry), self.db.query(qry))

    def GetPrivatist(self):
	"""Her henter vi informasjon om privatister ved UiT
	Som privatist regnes alle studenter med en forekomst i
	FS.STUDIEPROGRAMSTUDENT der dato_studierett_gyldig_til
        er st�rre eller lik dagens dato og studierettstatuskode
        er PRIVATIST eller status_privatist er satt til 'J'"""
	qry = """
SELECT DISTINCT
    p.fodselsdato, p.personnr, p.etternavn,
    p.fornavn, p.kjonn, s.adrlin1_semadr,
    s.adrlin2_semadr, s.postnr_semadr, s.adrlin3_semadr,
    s.adresseland_semadr, p.adrlin1_hjemsted,
    p.sprakkode_malform,sps.studieprogramkode,
    sps.studieretningkode, sps.status_privatist, 
    s.studentnr_tildelt, p.telefonnr_mobil
FROM fs.student s, fs.person p, fs.studieprogramstudent sps
WHERE p.fodselsdato = s.fodselsdato AND
    p.personnr = s.personnr AND
    p.fodselsdato = sps.fodselsdato AND
    p.personnr = sps.personnr AND
    (sps.studierettstatkode = 'PRIVATIST' OR
    sps.status_privatist = 'J') AND
    sps.dato_studierett_gyldig_til >= sysdate """
        return (self._get_cols(qry), self.db.query(qry))

    def GetDeltaker(self):
        """Hent info om personer som er ekte EVU-studenter ved
        UiT, dvs. er registrert i EVU-modulen i tabellen
        fs.deltaker,  Henter alle som er knyttet til kurs som
        tidligst ble avsluttet for 30 dager siden."""
        qry = """
SELECT DISTINCT
       p.fodselsdato, p.personnr, p.etternavn, p.fornavn,
       d.adrlin1_job, d.adrlin2_job, d.postnr_job,
       d.adrlin3_job, d.adresseland_job, d.adrlin1_hjem,
       d.adrlin2_hjem, d.postnr_hjem, d.adrlin3_hjem,
       d.adresseland_hjem, p.adrlin1_hjemsted, p.status_reserv_nettpubl,
       p.adrlin2_hjemsted, p.postnr_hjemsted, p.adrlin3_hjemsted,
       p.adresseland_hjemsted, d.deltakernr, d.emailadresse,
       k.etterutdkurskode, e.studieprogramkode,
       e.faknr_adm_ansvar, e.instituttnr_adm_ansvar,
       e.gruppenr_adm_ansvar, p.kjonn, p.status_dod,
       p.telefonnr_mobil
FROM fs.deltaker d, fs.person p, fs.kursdeltakelse k,
     fs.etterutdkurs e
WHERE p.fodselsdato=d.fodselsdato AND
      p.personnr=d.personnr AND
      d.deltakernr=k.deltakernr AND
      e.etterutdkurskode=k.etterutdkurskode AND
      NVL(e.status_kontotildeling,'J')='J' AND
      k.kurstidsangivelsekode = e.kurstidsangivelsekode AND
      NVL(e.dato_til, SYSDATE) >= SYSDATE - 30"""
        return (self._get_cols(qry), self.db.query(qry))

    def GetFnrEndringer(self):
        """Hent informasjon om alle registrerte f�dselsnummerendringer"""
        qry = """
SELECT fodselsdato_naverende, personnr_naverende,
       fodselsdato_tidligere, personnr_tidligere,
       TO_CHAR(dato_foretatt, 'YYYY-MM-DD HH24:MI:SS') AS dato_foretatt
FROM fs.fnr_endring
ORDER BY dato_foretatt"""
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
       status_utgatt, NVL(status_eksport_lms,'N') as status_eksport_lms
       FROM fs.studieprogram
       WHERE status_utgatt = 'N'"""
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
# UIT: for � populere forelesere i emnerom:  fjernet "aktivitetkode," mellom versjonskode og terminkode i query under

# By bto001, 2006-11-30
# La til 180 i dato_fra for � tillate at l�rere kommer inn i rom 180 dager f�r de starter undervinsninger
# La til 180 i dato_til for � tillate at l�rere blir i rom 180 dager fra de har sluttet undervisningen
        qry = """
SELECT DISTINCT
   pr.fodselsdato, pr.personnr, pr.rollenr, pr.rollekode, pr.dato_fra, pr.dato_til,
   pr.institusjonsnr, pr.faknr, pr.gruppenr, pr.studieprogramkode, pr.emnekode, 
   pr.versjonskode, pr.terminkode, pr.arstall, pr.terminnr,
   pr.etterutdkurskode, pr.kurstidsangivelsekode, CASE WHEN ua.undpartilopenr is NULL THEN NULL ELSE pr.aktivitetkode END as aktivitetkode
FROM fs.personrolle pr
LEFT OUTER JOIN
   fs.undaktivitet ua
ON (pr.institusjonsnr = ua.institusjonsnr AND 
    pr.emnekode = ua.emnekode AND 
    pr.versjonskode = ua.versjonskode AND 
    pr.terminkode = ua.terminkode AND 
    pr.arstall = ua.arstall AND 
    pr.terminnr = ua.terminnr AND 
    pr.aktivitetkode = ua.aktivitetkode)
WHERE dato_fra < SYSDATE + 180 AND
    NVL(dato_til,SYSDATE) >= sysdate - 180"""
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
FROM fs.emne e, fs.undervisningsenhet r, fs.undaktivitet u
WHERE r.emnekode = e.emnekode AND
      u.emnekode = r.emnekode AND
      r.versjonskode = e.versjonskode AND
      """
        # uit. added the following data to the above query:
        # fs.undaktivitet u
        # u.emnekode = r.emnekode AND
        
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
from fs.studieprogramstudent 
WHERE
  studieprogramkode = :studprogkode AND
  st.dato_studierett_gyldig_til >= SYSDATE""" 
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
   arstall_und_forste, terminkode_und_siste, arstall_und_siste, arstall_eks_siste
FROM fs.emne """
        return (self._get_cols(qry),self.db.query(qry))


##################################################################
# Metoder brukt av bofh
##################################################################

    def GetStudentEksamen(self,fnr,pnr):
	"""Hent alle eksamensmeldinger for en student for n�v�rende
	semester"""
        qry = """
SELECT DISTINCT
   em.emnekode, em.dato_opprettet, em.status_er_kandidat
FROM fs.eksamensmelding em, fs.person p
WHERE em.fodselsdato = :fnr AND
      em.personnr = :pnr AND
      em.fodselsdato = p.fodselsdato AND
      em.personnr = p.personnr AND
      em.arstall >= :year AND
      em.manednr > :mnd - 3
      AND %s
        """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr,
                                                         'pnr': pnr,
                                                         'year': self.year,
                                                         'mnd': self.mndnr}))

    def GetStudentStudierett(self,fnr,pnr):
	"""Hent info om alle studierett en student har eller har hatt"""
        qry = """
SELECT DISTINCT
  sps.studieprogramkode, sps.studierettstatkode, sps.dato_studierett_tildelt,
  sps.dato_studierett_gyldig_til, sps.status_privatist, sps.studentstatkode
FROM fs.studieprogramstudent sps, fs.person p
WHERE sps.fodselsdato=:fnr AND
      sps.personnr=:pnr AND
      p.fodselsdato = sps.fodselsdato AND
      p.personnr = sps.personnr AND
      %s
        """ % self.is_alive()
        return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 
                                                         'pnr': pnr}))

    def GetStudentSemReg(self,fnr,pnr):
        """Hent data om semesterregistrering for student i n�v�rende semester."""
        qry = """
SELECT DISTINCT
  r.regformkode, r.betformkode, r.dato_betaling, r.dato_regform_endret
FROM fs.registerkort r, fs.person p
WHERE r.fodselsdato = :fnr AND
      r.personnr = :pnr AND
      %s AND
      r.fodselsdato = p.fodselsdato AND
      r.personnr = p.personnr AND
      %s
        """ %(self.get_termin_aar(only_current=1),self.is_alive())
	return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 'pnr': pnr}))

    def GetStudentUtdPlan(self,fnr,pnr):
        """Hent opplysninger om utdanningsplan for student"""
        qry = """
SELECT DISTINCT
  utdp.studieprogramkode, utdp.terminkode_bekreft, utdp.arstall_bekreft,
  utdp.dato_bekreftet
FROM fs.studprogstud_planbekreft utdp, fs.person p
WHERE utdp.fodselsdato = :fnr AND
      utdp.personnr = :pnr AND
      utdp.fodselsdato = p.fodselsdato AND
      utdp.personnr = p.personnr AND
      %s
        """ % self.is_alive()
	return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 'pnr': pnr}))

    def GetStudentKull(self, fnr, pnr):
	"""Hent opplysninger om hvilken klasse studenten er en del av og 
	hvilken kull studentens klasse tilh�rer."""
	qry = """
SELECT DISTINCT
  sps.studieprogramkode, sps.terminkode_kull, sps.arstall_kull,
  k.status_aktiv
FROM fs.studieprogramstudent sps, fs.kull k, fs.person p
WHERE sps.fodselsdato = :fnr AND
      sps.personnr = :pnr AND
      p.fodselsdato = sps.fodselsdato AND
      p.personnr = sps.personnr AND
      sps.studieprogramkode = k.studieprogramkode AND
      sps.terminkode_kull = k.terminkode AND
      sps.arstall_kull = k.arstall AND
      %s
      """ % self.is_alive()
	return (self._get_cols(qry), self.db.query(qry, {'fnr': fnr, 'pnr': pnr}))

    def GetEmneIStudProg(self,emne):
	"""Hent alle studieprogrammer et gitt emne kan inng� i."""
	qry = """
SELECT DISTINCT 
  studieprogramkode   
FROM fs.emne_i_studieprogram
WHERE emnekode = :emne
      """ 
        return (self._get_cols(qry), self.db.query(qry, {'emne': emne}))

##################################################################
## E-post adresser i FS:
##################################################################


    def GetAllPersonsEmail(self, fetchall = False):
        return self.db.query("""
        SELECT fodselsdato, personnr, emailadresse
        FROM fs.person""", fetchall = fetchall)

    def WriteMailAddr(self, fodselsdato, personnr, email):
        self.db.execute("""
        UPDATE fs.person
        SET emailadresse=:email
        WHERE fodselsdato=:fodselsdato AND personnr=:personnr""",
                        {'fodselsdato': fodselsdato,
                         'personnr': personnr,
                         'email': email})

##################################################################
## Brukernavn i FS:
##################################################################

# oppdatere til fs.person
    def GetAllPersonsUname(self, fetchall = False):
        return self.db.query("""
        SELECT fodselsdato, personnr, brukernavn
        FROM fs.personreg""", fetchall = fetchall)
    # end GetAllPersonsUname


    def WriteUname(self, fodselsdato, personnr, uname):
        self.db.execute("""
        UPDATE fs.personreg
        SET brukernavn = :uname
        WHERE fodselsdato = :fodselsdato AND personnr = :personnr""",
                        {'fodselsdato': fodselsdato,
                         'personnr': personnr,
                         'uname': uname})
    # end WriteUname



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
                'rolle': True,
                }

    def endElement(self, name):
        if name == 'rolle':
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
            'aktivitetkode': ['undakt', 'kursakt'],   ## uit la til kursakt fra no/access_fs
            'terminkode': ['undenh', 'undakt'],
            'arstall': ['undenh', 'undakt'],
            'terminnr': ['undenh', 'undakt'],
            'etterutdkurskode': ['evu', 'kursakt'],  # uit la til kursakt fra no/access_fs
            'kurstidsangivelsekode': ['evu','kursakt'], # uit la til kursakt fra no/access_fs
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
            print "VALIDATE_ROLE: %s:%s" % (col,targs)
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
                    #print "VALIDATE_ROLE: snitt mellom % og %s" % (target,targs)
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

        if target is not None:
            target = tuple(target - not_target)
        else:
            # Denne personrollen inneholdt ikke _noen_
            # target-spesifiserende kolonner.
            target = ()
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

