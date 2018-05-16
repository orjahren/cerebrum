# -*- coding: iso-8859-1 -*-
# Copyright 2002-2018 University of Oslo, Norway
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
import types

from Cerebrum import database, Errors
from Cerebrum.modules.no import fodselsnr


class LT(object):
    """
    Methods for fetching person, OU and some other information from LT.

    Each methods returns a sequence of db_rows.

    """

    def __init__(self, db):
        self.db = db

    def GetSteder(self):
        "Henter informasjon om alle ikke-nedlagte steder"
        qry = """
        SELECT
          sk.fakultetnr, sk.instituttnr, sk.gruppenr,
          sk.forkstednavn,
          NVL(sk.stednavnfullt, sk.stednavn) as stednavn,
          sk.akronym, sk.stedkortnavn_bokmal, sk.stedkortnavn_nynorsk,
          sk.stedkortnavn_engelsk, sk.stedlangnavn_bokmal,
          sk.stedlangnavn_nynorsk, sk.stedlangnavn_engelsk,
          sk.fakultetnr_for_org_sted, sk.instituttnr_for_org_sted,
          sk.gruppenr_for_org_sted, sk.opprettetmerke_for_oppf_i_kat,
          sk.telefonnr, sk.innvalgnr, sk.linjenr,
          sk.stedpostboks,
          sk.adrtypekode_besok_adr, sk.adresselinje1_besok_adr,
                                    sk.adresselinje2_besok_adr,
          sk.poststednr_besok_adr, sk.poststednavn_besok_adr,
                                   sk.landnavn_besok_adr,
          sk.adrtypekode_intern_adr, sk.adresselinje1_intern_adr,
                                     sk.adresselinje2_intern_adr,
          sk.poststednr_intern_adr, sk.poststednavn_intern_adr,
                                    sk.landnavn_intern_adr,
          sk.adrtypekode_alternativ_adr, sk.adresselinje1_alternativ_adr,
          sk.adresselinje2_alternativ_adr, sk.poststednr_alternativ_adr,
          sk.poststednavn_alternativ_adr, sk.landnavn_alternativ_adr,
          TO_CHAR(sk.dato_opprettet, 'YYYYMMDD') as dato_opprettet,
          TO_CHAR(sk.dato_nedlagt, 'YYYYMMDD') as dato_nedlagt,
          skk.konvtilverdi as nsd_kode
        FROM
          lt.sted sk, lt.stedkodekonv skk 
        WHERE
          sk.fakultetnr = skk.fakultetnr (+) AND
          sk.instituttnr = skk.instituttnr (+) AND
          sk.gruppenr = skk.gruppenr (+) AND
          'DBH' = skk.KONVTYPEKODE (+) AND
          NVL(sk.dato_nedlagt,SYSDATE) >= ADD_MONTHS(SYSDATE, -12)
        ORDER BY
          sk.fakultetnr, sk.instituttnr, sk.gruppenr
        """

        return self.db.query(qry)
    # end GetSteder
    


    def GetStedKomm(self, fak, inst, gr):
        "Henter kontaktinformasjon for et sted"
        qry = """
        SELECT
          kommtypekode, tlfpreftegn, telefonnr, kommnrverdi
        FROM
          lt.stedkomm
        WHERE
          fakultetnr=:fak AND
          instituttnr=:inst AND
          gruppenr=:gr AND
          kommtypekode IN ('EKSTRA TLF', 'FAX', 'FAXUTLAND', 'TLF', 'TLFUTL',
                           'EPOST', 'URL')
        ORDER BY
          tlfpreftegn
        """

        return self.db.query(qry, {'fak': fak, 'inst': inst, 'gr': gr}) 
    # end GetStedKomm
    
    

    def GetTilsettinger(self):
        "Henter alle tilsetninger med dato_til frem i tid"
        qry = """
        SELECT
          DISTINCT t.fodtdag, t.fodtmnd, t.fodtar,
                   t.personnr, t.fakultetnr_utgift, t.instituttnr_utgift,
                   t.gruppenr_utgift,
                   NVL(t.stillingkodenr_beregnet_sist,
                       s.stillingkodenr) as stillingkodenr_beregnet_sist,
                   t.prosent_tilsetting,
                   TO_CHAR(t.dato_fra, 'YYYYMMDD') as dato_fra,
                   TO_CHAR(t.dato_til, 'YYYYMMDD') as dato_til,
                   t.tilsnr
        FROM
          lt.tilsetting t, lt.stilling s
        WHERE
          NVL(dato_til, SYSDATE) >= ADD_MONTHS(SYSDATE, -12) AND
          t.stilnr = s.stilnr
        """

        return self.db.query(qry)
    # end GetTilsettinger
    
    

    def GetTitler(self):
        """
        Hent informasjon om stillingskoder, kronologisk sortert.
        """

        qry = """
        SELECT
          stillingkodenr, tittel, univstkatkode
        FROM
          lt.stillingskode
        ORDER BY
          dato_fra
        """

        return self.db.query(qry)
    # end GetTitler



    def GetLonnsPosteringer(self, tid):
        """
        Hent person og sted informasjon for alle l�nnsposteringer med
        relevante bel�pskoder foretatt etter TID.
        """

        qry = """
        SELECT
          belopskodenr
        FROM
          lt.belkodespesielle
        WHERE
          belkodeomradekode='LT35UREG'
        """
        koder = [str(k['belopskodenr']) for k in self.db.query(qry)]

        qry = ("""
               SELECT
                 TO_CHAR(dato_oppgjor, 'YYYYMMDD') as dato_oppgjor,
                 p.fodtdag, p.fodtmnd, p.fodtar, p.personnr,
                 fakultetnr_kontering, instituttnr_kontering, gruppenr_kontering
               FROM
                 lt.lonnspostering p, lt.delpostering d
               WHERE
                 p.posteringsnr=d.posteringsnr AND
                 p.aarnr_termin=d.aarnr AND p.mndnr_termin=d.mndnr AND
                 p.fodtdag=d.fodtdag AND p.fodtmnd=d.fodtmnd AND
                 p.fodtar=d.fodtar AND p.personnr=d.personnr AND
                 dato_oppgjor > TO_DATE(%s, 'YYYYMMDD') AND
                 d.belopskodenr IN (""" % tid +", ".join(koder)+")") 

        return self.db.query(qry)
    # end GetLonnsPosteringer

    

    def GetGjester(self):
        "Hent informasjon om gjester"

        qry = """
        SELECT
          fodtdag, fodtmnd, fodtar, personnr,
          fakultetnr, instituttnr, gruppenr, gjestetypekode,
          TO_CHAR(dato_fra, 'YYYYMMDD') as dato_fra,
          TO_CHAR(dato_til, 'YYYYMMDD') as dato_til
        FROM
          lt.gjest
        WHERE
          NVL(dato_til, SYSDATE) >= SYSDATE - 14
        """

        return self.db.query(qry)
    # end GetGjester

    

    def GetPersonRoller(self, fodtdag, fodtmnd, fodtar, personnr):
        "Hent informasjon om hvilke roller en person har"

        qry = """
        SELECT
          fakultetnr, instituttnr, gruppenr, ansvarsrollekode,
          TO_CHAR(dato_fra, 'YYYYMMDD') as dato_fra,
          TO_CHAR(dato_til, 'YYYYMMDD') as dato_til
        FROM
          lt.personrolle
        WHERE
          fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND
          personnr=:personnr AND
          dato_fra <= SYSDATE AND
          NVL(dato_til, SYSDATE + 1) > SYSDATE
        """

        return self.db.query(qry, locals())
    # end GetPersonRoller

    
        
    def GetPersonInfo(self, fodtdag, fodtmnd, fodtar, personnr):
        "Hent informasjon om en bestemt person"

        qry = """
        SELECT
          fornavn, etternavn, navn, adrtypekode_privatadresse,
          adresselinje1_privatadresse, adresselinje2_privatadresse,
          poststednr_privatadresse, poststednavn_privatadresse,
          landnavn_privatadresse, telefonnr_privattelefon, tittel_personlig,
          fakultetnr_for_lonnsslip, instituttnr_for_lonnsslip,
          gruppenr_for_lonnsslip
        FROM
          lt.person
        WHERE
          fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND
          personnr=:personnr
        """

        return self.db.query(qry, locals()) 
    # end GetPersonInfo

    

    def GetArbTelefon(self, fodtdag, fodtmnd, fodtar, personnr):
        "Hent en persons telefon-nr"

        qry = """
        SELECT
          telefonnr, innvalgnr, linjenr, tlfpreftegn
        FROM
          lt.arbstedtelefon
        WHERE
          fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND
          personnr=:personnr
        ORDER BY
          tlfpreftegn
        """

        return self.db.query(qry, locals())
    # end GetArbTelefon
    


    def GetPersKomm(self, fodtdag, fodtmnd, fodtar, personnr):
        "Hent kontakt informasjon for en person"
        
        qry = """
        SELECT
          kommtypekode, kommnrverdi, telefonnr, tlfpreftegn
        FROM
          lt.perskomm
        WHERE
          fodtdag=:fodtdag AND fodtmnd=:fodtmnd AND fodtar=:fodtar AND
          personnr=:personnr
        ORDER BY
          tlfpreftegn
        """

        return self.db.query(qry, locals())
    # end GetPersKomm

    

    def GetHovedkategorier(self):
        "Hent hovedkategorier (VIT for vitenskapelig ansatt o.l.)"
        
        qry = """
        SELECT
          univstkatkode, hovedkatkode
        FROM
          lt.univstkategori
        """

        return self.db.query(qry)
    # end GetHovedkategorier

    

    def _GetAllPersonsKommType(self, kommtype):

        if kommtype not in ('UREG-EMAIL', 'UREG-USER'):
            raise ValueError, "Bad kommtype: %s" % kommtype
        # fi

        query = """
        SELECT
          fodtdag, fodtmnd, fodtar, personnr, kommnrverdi, tlfpreftegn
        FROM
          lt.perskomm
        WHERE kommtypekode = :kommtype AND tlfpreftegn = 'A'
        ORDER BY fodtdag, fodtmnd, fodtar, personnr, tlfpreftegn
        """

        return self.db.query(query, {'kommtype': kommtype})
    # end _GetAllPersonsKommType



    def GetAllPersons(self):

        query = """
        SELECT
          fodtdag, fodtmnd, fodtar, personnr
        FROM
          lt.person
        ORDER BY fodtdag, fodtmnd, fodtar, personnr
        """

        return self.db.query(query)
    # end GetAllPersons



    def GetReservasjoner(self):
        """
        Finn reservasjoner i LT.
        """

        qry = """
        SELECT
          fodtdag, fodtmnd, fodtar, personnr, katalogkode, felttypekode, 
          resnivakode
        FROM lt.reservasjon
        ORDER BY fodtdag, fodtmnd, fodtar, personnr
        """

        return self.db.query(qry)
    # end GetReservasjoner

    
    
    def GetAllPersonsUregEmail(self):
        return self._GetAllPersonsKommType('UREG-EMAIL')
    # end GetAllPersonsUregEmail

    

    def GetAllPersonsUregUser(self):
        return self._GetAllPersonsKommType('UREG-USER')
    # end GetAllPersonsUregUser

    

    def _DeleteKommtypeVerdi(self, fnr, kommtypekode, kommnrverdi):
        dag, maned, aar, personnr = fodselsnr.del_fnr_4(fnr)

        query = """
        DELETE
          lt.perskomm
        WHERE
          Fodtdag=:dag AND
          Fodtmnd=:maned AND
          Fodtar=:aar AND
          Personnr=:personnr AND
          Kommtypekode=:kommtypekode AND
          kommnrverdi=:kommverdi AND
          tlfpreftegn = 'A'
        """

        return self.db.execute(query, {'dag': dag,
                                       'maned': maned,
                                       'aar': aar,
                                       'personnr': personnr,
                                       'kommtypekode': kommtypekode,
                                       'kommverdi': kommnrverdi}) 
    # end _DeleteKommtypeVerdi
    
    
        
    def DeletePriUser(self, fnr, uname):
        return self._DeleteKommtypeVerdi(fnr, 'UREG-USER', uname)
    # end DeletePriUser

    

    def DeletePriMailAddr(self, fnr, email):
        return self._DeleteKommtypeVerdi(fnr, 'UREG-EMAIL', email)
    # end DeletePriMailAddr

    

    def _UpdateKommtypeVerdi(self, fnr, kommtypekode, kommnrverdi):
        dag, maned, aar, personnr = fodselsnr.del_fnr_4(fnr)

        query = """
        UPDATE lt.perskomm
        SET
          kommnrverdi = :kommnrverdi
        WHERE
          FODTDAG = :fodtdag AND
          FODTMND = :fodtmnd AND
          FODTAR = :fodtar AND
          PERSONNR = :personnr AND
          TLFPREFTEGN = 'A' AND 
          KOMMTYPEKODE = :kommtypekode
        """

        return self.db.execute(query, {'fodtdag': dag,
                                       'fodtmnd': maned,
                                       'fodtar': aar,
                                       'personnr': personnr,
                                       'kommtypekode': kommtypekode,
                                       'kommnrverdi': kommnrverdi})
    # end _AddKommtypeVerdi

    

    def UpdatePriMailAddr(self, fnr, email):
        return self._UpdateKommtypeVerdi(fnr, 'UREG-EMAIL', email)
    # end WritePriMailAddr

    

    def UpdatePriUser(self, fnr, uname):
        return self._UpdateKommtypeVerdi(fnr, 'UREG-USER', uname)
    # end WritePriUser



    def _InsertKommtypeVerdi(self, fnr, kommtypekode, kommnrverdi):
        dag, maned, aar, personnr = fodselsnr.del_fnr_4(fnr)

        query = """
        INSERT INTO
          lt.perskomm(FODTDAG, FODTMND, FODTAR, PERSONNR,
                      KOMMTYPEKODE, KOMMNRVERDI, TLFPREFTEGN)
        VALUES
          (:dag, :mnd, :aar, :personnr, :kommtypekode, :kommnrverdi, 'A')
        """

        return self.db.execute(query, {"dag" : dag,
                                       "mnd" : maned,
                                       "aar" : aar,
                                       "personnr" : personnr,
                                       "kommtypekode" : kommtypekode,
                                       "kommnrverdi"  : kommnrverdi})
    # end _InsertKommtypeVerdi



    def InsertPriMailAddr(self, fnr, email):
        return self._InsertKommtypeVerdi(fnr, "UREG-EMAIL", email)
    # end InsertPriMailAddr



    def InsertPriUser(self, fnr, uname):
        return self._InsertKommtypeVerdi(fnr, 'UREG-USER', uname)
    # end InsertPriUser



    def get_column_names(self, argument):
        """
        Extract all names from a query result located in ARGUMENT.

        Occasionally we need to fish out column names for an SQL
        result. This function returns such names in order respecting things
        such as '<expr> as foo' (yielding column name 'foo').

        (Actually, the client code _could_ use db_row's methods objects
        directly, but this would be make things difficult, should we chose
        too change the meaning of column name).

        Caveat: if ARGUMENT is an empty list, we will not have any column
        names at all. That is the disadvantage of using db_rows rather than
        munging SQL directly.
        """

        if (type(argument) is types.ListType or
            type(argument) is types.TupleType):
            if not argument:
                return ()
            # fi

            db_row = argument[0]
        else:
            db_row = argument
        # fi

        return list(db_row.keys())
    # end get_column_names
    


    def list_dbfg_usernames(self, fetchall = False):
        """
        Get all usernames and return them as a sequence of db_rows.
        """

        query = """
        SELECT
          username as username
        FROM
          all_users
        """

        return self.db.query(query, fetchall = fetchall)
    # end list_usernames



    def list_dba_usernames(self, fetchall = False):
        """
        Get all usernames for internal statistics.
        """

        query = """
        SELECT
           lower(username) as username
        FROM
           dba_users
        WHERE
           default_tablespace = 'USERS' and account_status != 'LOCKED'
        """

        return self.db.query(query, fetchall = fetchall)
    # end list_dba_usernames



    def GetPermisjoner(self):
        """
        Returns current leaves of absence (permisjoner) for all individuals
        in LT.
        """
        query = """
        SELECT
          fodtdag, fodtmnd, fodtar, personnr, tilsnr,
          TO_CHAR(dato_fra, 'YYYYMMDD') as dato_fra,
          TO_CHAR(dato_til, 'YYYYMMDD') as dato_til,
          permarsakkode,
          prosent_permisjon,
          lonstatuskode
        FROM   lt.permisjon
        WHERE  dato_fra <= SYSDATE AND
               dato_til >= SYSDATE
        """
        
        return self.db.query(query, locals()) 
    # end GetPermisjoner



    def GetFnrEndringer(self):
        """
        Returns changes in the Norwegian social security numbers
        (f�dselsnumre) registered in LT.
        """

        query = """
        SELECT 
          Fodtdag_kom_fra, Fodtmnd_kom_fra, Fodtar_kom_fra, Personnr_kom_fra,
          Fodtdag_ble_til, Fodtmnd_ble_til, Fodtar_ble_til, Personnr_ble_til,
          TO_CHAR(Dato_endret, 'YYYY-MM-DD HH24:MI:SS') AS Dato_endret
        FROM
          lt.personhenvisning
        ORDER BY
          Dato_endret
        """

        return self.db.query(query)
    # end GetFnrEndringer
# end class LT

