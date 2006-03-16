# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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
import time

from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uio.access_FS import FS
from Cerebrum import Database
from Cerebrum.extlib import xmlprinter
from Cerebrum import Person
from Cerebrum import Errors

# TODO: This file should not have UiO hardcoded data in it
SYDRadmins = ['kaj000', 'stig']
DMLadmins = ['kaj000', 'stig']
AllAdmins = SYDRadmins + DMLadmins
host_config = {
    'uitfronter.fronter.no': { 'DBinst': 'DLOPROD.uio.no',
                       'admins': AllAdmins,
                       'export': ['FS', 'All_users'],
                       'spread': 'spread_uit_fronter'
                       },
    }

#class AccessFronter(object):
#    def __init__(self, db):
#        self.db = db

#    def ListUserInfo(self):
#        return self.db.query("""
#SELECT username, password, firstname, lastname, email
#FROM persontbl2 p
#WHERE username IS NOT NULL AND
#      importid IS NOT NULL AND
#      EXISTS (SELECT 'x' FROM memberstbl m WHERE m.personid = p.id)""")
    
#    def ListGroupInfo(self):
#        return self.db.query("""
#SELECT c.importid, c.title, c.allowsflag, p.importid AS parent_importid
#FROM structuregrouptbl c, structuregrouptbl p
#WHERE c.parent = p.id AND
#      c.importid IS NOT NULL
#UNION
#SELECT importid, title, allowsflag, importid
#FROM structuregrouptbl
#WHERE parent <= 0 AND
#      importid IS NOT NULL""")

#    def GetGroupMembers(self, gid):
#        return self.db.query("""
#SELECT p.username
#FROM persontbl2 p, memberstbl m
#WHERE m.groupid = :gid AND
#      m.personid = p.id AND
#      p.importid IS NOT NULL""", {'gid': gid})
#
#    def ListAllGroupMembers(self):
#        return self.db.query("""
#SELECT g.importid, p.username
#FROM persontbl2 p, structuregrouptbl g, memberstbl m
#WHERE g.importid IS NOT NULL AND
#      g.id = m.groupid AND
#      p.id = m.personid AND
#      p.importid IS NOT NULL""")
#
#    def ListGroupsACL(self):
#        return self.db.query("""
#SELECT s.importid AS structid, g.importid AS groupid, a.group_access, a.room_access
#FROM structuregrouptbl s, structuregrouptbl g, structureacl a
#WHERE s.importid IS NOT NULL AND
#      s.id = a.structid AND
#      g.id = a.groupid AND
#      g.importid IS NOT NULL""")

#    def ListRoomInfo(self):
#        return self.db.query("""
#SELECT r.importid AS room, r.title, s.importid AS structid, r.profile
#FROM projecttbl2 r, structuregrouptbl s
#WHERE r.structureid = s.id AND
#      r.importid IS NOT NULL""")
#
#    def ListRoomsACL(self):
#        return self.db.query("""
#SELECT r.importid AS roomid, g.importid AS groupid, a.read_access, a.write_access,
#       a.delete_access, a.change_access
#FROM projecttbl2 r, structuregrouptbl g, acl a
#WHERE r.importid IS NOT NULL AND
#      r.id = a.prjid AND
#      g.id = a.groupid AND
#      g.importid IS NOT NULL""")

#    def GetProfileId(self, title):
#        try:
#            return self.db.query_1("""
#            SELECT id FROM ProfileTbl WHERE title=:title""", {'title': title})
#        except Errors.NotFoundError:
#            # Bruk "Vanlig prosjektmal" fra masterdata.
#            return 10

class FronterUtils(object):
    def UE2KursID(type, *rest):
        """Lag ureg2000-spesifikk "kurs-ID" av prim�rn�kkelen til en
        undervisningsenhet eller et EVU-kurs.  Denne kurs-IDen forblir
        uforandret s� lenge kurset p�g�r; den endres alts� ikke b�r man
        f.eks. kommer til et nytt semester.

        F�rste argument angir hvilken type FS-entitet de resterende
        argumentene stammer fra; enten 'KURS' (for undervisningsenhet) eller
        'EVU' (for EVU-kurs)."""
        type = type.lower()
        if type != 'kurs':
            raise ValueError, "ERROR: Ukjent kurstype <%s> (%s)" % (type, rest)

        # Vi vet her at $type er 'KURS', og vet dermed ogs� hvilke
        # elementer som er med i @rest:
        if len(rest) != 6:
            raise ValueError, "ERROR: Undervisningsenheter skal identifiseres av 6 "+\
                  "felter, ikke <%s>" % ">, <".join(rest)

        instnr, emnekode, versjon, termk, aar, termnr = rest
        termnr = int(termnr)
        aar = int(aar)
        tmp_termk = re.sub('[^a-zA-Z0-9]', '_', termk).lower()
        # Finn $termk og $aar for ($termnr - 1) semestere siden:
        if (tmp_termk == 'h_st'):
            if (termnr % 2) == 1:
                termk = 'h�st'
            else:
                termk = 'v�r'
            aar -= int((termnr - 1) / 2)
        elif tmp_termk == 'v_r':
            if (termnr % 2) == 1:
                termk = 'v�r'
            else:
                termk = 'h�st'
            aar -= int(termnr / 2)
        else:
            # Vi krysser fingrene og h�per at det aldri vil benyttes andre
            # verdier for $termk enn 'v�r' og 'h�st', da det i s� fall vil
            # bli vanskelig � vite hvilket semester det var "for 2
            # semestere siden".
            raise ValueError, "ERROR: Unknown terminkode <%s> for emnekode <%s>." % (
                termk, emnekode)

        # $termnr er ikke del av den returnerte strengen.  Vi har benyttet
        # $termnr for � beregne $termk og $aar ved $termnr == 1; det er
        # alts� implisitt i kurs-IDen at $termnr er lik 1 (og dermed
        # un�dvendig � ta med).
        ret = "%s:%s:%s:%s:%s:%s" % (type, instnr, emnekode, versjon, termk, aar)
        return ret.lower()
    UE2KursID = staticmethod(UE2KursID)

class Fronter(object):
    STATUS_ADD = 1
    STATUS_UPDATE = 2
    STATUS_DELETE = 3

    ROLE_READ = '01'
    ROLE_WRITE = '02'
    ROLE_DELETE = '03'
    ROLE_CHANGE = '07'

    EMNE_PREFIX = 'KURS'
    #EVU_PREFIX = 'EVU'

    def __init__(self, db, const, logger=None):
        self.db = db
        self.const = const
        self.logger = logger
        for k in ('DBinst', 'admins', 'export'):
           setattr(self, k, host_config[fronterHost][k])
        self.plain_users = host_config[fronterHost].get('plain_users', ())
        self.spread = host_config[fronterHost].get('spread', None)
        self.supergroups = self.GetSuperGroupnames()
        self.logger.debug("Fronter: len(self.supergroups)=%i" % len(self.supergroups))
        #fronter_db = Database.connect(user='fronter',
        #                              service=self.DBinst,
        #                              DB_driver='Oracle')
        #self._accessFronter = AccessFronter(fronter_db)
        self.kurs2navn = {}
        self.kurs2enhet = {}
        self.enhet2sko = {}
        self.enhet2akt = {}
        self.emne_versjon = {}
        self.emne_termnr = {}

    def GetSuperGroupnames(self):
        if 'FS' in self.export:
            group = Factory.get("Group")(self.db)
            ret = []
            for e in group.list_all_with_spread(int(getattr(self.const,
                                                            self.spread))):
                group.clear()
                group.find(e['entity_id'])
                ret.append(group.group_name)
            return ret
        elif 'FS_all' in self.export:
            # Ser ikke ut til � v�re i bruk.
            raise ValueError, "didn't think this was in use"
            # [ Skulle egentlig ha returnert alle grupper som er
            #   direktemedlemmer under
            #   INTERNAL_PREFIX}uio.no:fs:{supergroup} ]
        else:
            # Ingen synkronisering av FS-emner; returner tom liste.
            return ()

    def _date_sort(self, x, y):
        """Sort by year, then by semester"""
        if(x[0] != y[0]):
            return cmp(x[0], y[0])
        return cmp(y[1][0], x[1][0])

    def read_kurs_data(self):
        #
        # @supergroups inneholder n� navnet p� de gruppene fra niv� 2 i
        # hierarkiet av FS-avledede grupper som er markert for eksport til
        # CF-instansen vi n� bygger eksport-XML til:
        #
        # Niv� 0: Supergruppe, brukes for � samle alle FS-avledede grupper.
        # Niv� 1: Emnekode-grupper eller EVU-kurs-grupper, subgrupper av
        #         supergruppa p� niv� 0.
        # Niv� 2: KursID-grupper, brukes til � legge inn eksport av et
        #         gitt kurs til ClassFronter.
        # Niv� 3: Grupper for l�rere/studenter p� hver av det spesifiserte
        #         kursets aktiviteter etc.
        #
        kurs = {}
        for group in self.supergroups:
            # Om man stripper vekk de tre f�rste elementene av $group (dvs
            # "({u2k-internal}):uio.no:fs"), vil man sitte igjen med en
            # "kurs-ID", f.eks.
            #
            #   kurs:185:jurprig:1:v�r:2001
            #   kurs:185:diavhf:1:h�st:2001
            #   evu:14-latkfu:2001-2002
            #
            # Med utgangspunkt i disse kurs-IDene kan man bestemme hvilke
            # n�v�rende (og evt. fremtidige) undervisningsenheter (med
            # tilh�rende und.aktiviteter) og EVU-kurs (med tilh�rende
            # EVU-aktiviteter) som skal taes med i eksporten.
            #
            kurs_id = ":".join(group.split(':')[3:]).lower()
            kurs[kurs_id] = 1

        #
        # Vi har n� skaffet oss oversikt over hvilke Kurs-IDer som skal
        # eksporteres, og kan benytte dette til � plukke ut data om de
        # aktuelle undervisningsenhetene/EVU-kursene (og tilh�rende
        # aktiviteter) fra ymse dumpfiler.
        #
        #for enhet in self._fs.GetUndervEnhetAll()[1]:
	#M� byttes ut med XML-parser mot underv_enhet (current og next)
	for enhet in parser_call(file): 
            id_seq = (self.EMNE_PREFIX, enhet['institusjonsnr'],
                      enhet['emnekode'], enhet['versjonskode'],
                      enhet['terminkode'], enhet['arstall'],
                      enhet['terminnr'])
            kurs_id = FronterUtils.UE2KursID(*id_seq)

            if kurs.has_key(kurs_id):
                # Alle kurs-IDer som stammer fra undervisningsenheter
                # prefikses med EMNE_PREFIX + ':'.
                enhet_id = ":".join([str(x) for x in id_seq])
#		self.logger.debug("read_kurs_data: enhet_id=%s" % enhet_id)
                self.kurs2enhet.setdefault(kurs_id, []).append(enhet_id)
                multi_id = ":".join([str(x) for x in(
                    enhet['institusjonsnr'], enhet['emnekode'],
                    enhet['terminkode'], enhet['arstall'])])
                self.emne_versjon.setdefault(
                    multi_id, {})["v%s" % enhet['versjonskode']] = 1
                self.emne_termnr.setdefault(
                    multi_id, {})[enhet['terminnr']] = 1
                full_sko = "%02d%02d%02d" % (enhet['faknr_kontroll'],
                                             enhet['instituttnr_kontroll'],
                                             enhet['gruppenr_kontroll'])
                #if full_sko in ("150030",):
                #    # Spesialbehandling av UNIK; til tross for at
                #    # dette stedkode-messig bare er en gruppe, skal de
                #    # ha en egen korridor.
                #    self.enhet2sko[enhet_id] = full_sko
                #else:
		self.enhet2sko[enhet_id] = "%02d%02d00" % (
                        enhet['faknr_kontroll'],
                        enhet['instituttnr_kontroll'])
                self.kurs2navn.setdefault(kurs_id, []).append(
                    [enhet['arstall'], enhet['terminkode'],
                     enhet['emnenavn_bokmal']])

        for kurs_id in self.kurs2navn.keys():
            navn_sorted = self.kurs2navn[kurs_id][:]
            navn_sorted.sort(self._date_sort)
            # Bruk navnet fra den eldste enheten; dette navnet vil enten
            # v�re fra innev�rende eller et fremtidig semester
            # pga. utplukket som finnes i dumpfila.
            self.kurs2navn[kurs_id] = navn_sorted[0][2]

        #for akt in self._fs.list_undervisningsaktiviteter():
        #    id_seq = (self.EMNE_PREFIX, akt['institusjonsnr'],
        #              akt['emnekode'], akt['versjonskode'],
        #              akt['terminkode'], akt['arstall'],
        #              akt['terminnr'])

#	    #self.logger.debug("read_kurs_data_getundaktivitet: %s, %s, %s, %s, %s, %s, %s" % (self.EMNE_PREFIX,akt['institusjonsnr'],akt['emnekode'],akt['versjonskode'],akt['terminkode'],akt['arstall'],akt['terminnr']))

            #kurs_id = FronterUtils.UE2KursID(*id_seq)
#	    #self.logger.debug("read_kurs_data_getundaktivitet: kurs_id=%s" % kurs_id)
            #if kurs.has_key(kurs_id):
            #    enhet_id = ":".join([str(x) for x in id_seq])
#		self.logger.debug("read_kurs_data: enhet_id=%s" % enhet_id)
		#self.enhet2akt.setdefault(enhet_id, []).append(
                #[akt['aktivitetkode'], akt['aktivitetsnavn']])

        #for evu in self._fs.GetEvuKurs()[1]:
        #    id_seq = (self.EVU_PREFIX, evu['etterutdkurskode'],
        #              evu['kurstidsangivelsekode'])
        #    kurs_id = FronterUtils.UE2KursID(*id_seq)
        #    if kurs.has_key(kurs_id):
                # Alle kurs-IDer som stammer fra EVU-kurs prefikses med "EVU:".
        #        enhet_id = ":".join(id_seq)
        #        self.kurs2enhet.setdefault(kurs_id, []).append(enhet_id)
        #        self.enhet2sko[enhet_id] = "%02d%02d00" % (
        #            evu['faknr_adm_ansvar'],
        #            evu['instituttnr_adm_ansvar'])
        #        # Da et EVU-kurs alltid vil best� av kun en
        #        # "undervisningsenhet", kan vi sette kursnavnet med en
        #        # gang (uten � m�tte sortere slik vi gjorde over for
        #        # "ordentlige" undervisningsenheter).
        #        self.kurs2navn[kurs_id] = evu['etterutdkursnavn']

        #        for akt in self._fs.GetAktivitetEvuKurs(
        #            evu['etterutdkurskode'], evu['kurstidsangivelsekode'])[1]:
        #            self.enhet2akt.setdefault(enhet_id, []).append(
        #                (akt['etterutdkurskode'], akt['aktivitetsnavn']))
        self.logger.debug("read_kurs_data: len(self.kurs2enhet)=%i" % \
                          len(self.kurs2enhet))

    #def get_fronter_users(self):
    #    """Return a dict with info on all users in Fronter"""
    #    users = {}
    #    for user in self._accessFronter.ListUserInfo():
    #        if not user['username']:
    #            print "Undefined Fronter username: <undef> => [%s,%s,%s,%s]" % (
    #                  user['password'], user['firstname'], user['lastname'], user['email'])
    #            continue
    #        if not user['password']:
    #            user['password'] = 'plain:'
    #        users[user['username']] = {'PASSWORD': user['password'] or 'plain:',
    #                                   'GIVEN': user['firstname'] or '',
    #                                   'FAMILY': user['lastname'] or '',
    #                                   'EMAIL': user['email'] or '',
    #                                   'USERACCESS': 0 # Default
    #                                   }

        # Set correct access for these users.
    #    gid2access = {7: 'viewmygroups',
    #                  4: 'allowlogin',
    #                  1: 'administrator'}
    #    # Walk through group ids in descending order (we assume that
    #    # membership in a group with lower group ID should take
    #    # preference).
    #    keys = gid2access.keys()
    #    keys.sort()
    #    keys.reverse()
    #    for gid in keys:
    #        for gm in self._accessFronter.GetGroupMembers(gid):
    #            if users.has_key(gm['username']):
    #                users[gm['username']]['USERACCESS'] = gid2access[gid]
    #    self.logger.debug("get_fronter_users ret %i users" % len(users))
    #    return users

    def pwd(self, p):
        type, pwd = p.split(":")
        type_map = {'md5': 1,
                    'unix': 2,
                    'nt': 3,
                    'plain': 4}
        ret = {'passwordtype': type_map[type]}
        if pwd:
            ret['password'] = pwd
        return ret
    
    def useraccess(self, access):
        # TODO: move to config section
        mapping = {0: 1,                # Not allowed to log in
                   'viewmygroups': 2,   # Normal user
                   'allowlogin': 2,     # Normal user
                   'administrator': 3}  # Admin
        return mapping[access]

    def get_fronter_groups(self):
        # In Fronter, groups and structure shares the same data structures
        # internally.  Thus, both groups and structure are defined by using
        # IMS <GROUP> elements.
        #
        # Additionally, the <GROUP> element is (ab)used for creating "rooms".
        group = {}
        for gi in self._accessFronter.ListGroupInfo():
            id = gi['importid']
            if re.search(r'^STRUCTURE/(Enhet|Studentkorridor):', id):
                #     Hovedkorr. enh:     STRUCTURE/Enhet:<ENHETID>
                #     Undv.korr. enh:     STRUCTURE/Studentkorridor:<ENHETID>
                rest = gi['importid'].split(":")
                corr_type = rest.pop(0)
                if not (rest[0] == self.EMNE_PREFIX or
                        rest[0] == self.EVU_PREFIX):
                    rest.insert(0, self.EMNE_PREFIX)
		id = "%s:%s" % (corr_type, FronterUtils.UE2KursID(*rest))
            group[id] = {'title': gi['title'],
                         'parent': gi['parent_importid'],
                         'allow_room': (int(gi['allowsflag']) & 1),
                         'allow_contact': (int(gi['allowsflag']) & 2),
                         'CFid': gi['importid'],
                         }
        self.logger.debug("get_fronter_groups ret %i groups" % len(group))
        return group

    def get_fronter_rooms(self):
        rooms = {}
        for ri in self._accessFronter.ListRoomInfo():
            rest = ri['room'].split(":")
            room_type = rest.pop(0)
            if not rest[0] in (self.EMNE_PREFIX, self.EVU_PREFIX):
                rest.insert(0, self.EMNE_PREFIX)
            
            if room_type == 'ROOM/Aktivitet':
                aktkode = rest.pop()
                room = ":".join((room_type, FronterUtils.UE2KursID(*rest), aktkode))
            else:
                room = "%s:%s" % (room_type, FronterUtils.UE2KursID(*rest))
            rooms[room] = {'title': ri['title'],
                           'parent': ri['structid'],
                           'profile': ri['profile'],
                           'CFid': ri['room']
                           }
        self.logger.debug("get_fronter_rooms ret %i rooms" % len(rooms))
        return rooms

    def get_fronter_groupmembers(self, current_groups):
        groupmembers = {}
        for m in self._accessFronter.ListAllGroupMembers():
            if current_groups.has_key(m['importid']):
                groupmembers.setdefault(m['importid'], {})[m['username']] = 1
        self.logger.debug("get_fronter_groupmembers ret %i groups" % \
                          len(groupmembers))
        return groupmembers

    def get_fronter_acl(self, current_groups, current_rooms):
        acl = {}
        fix_newgroup = re.compile(r'^uio\.no:fs:')
        for a in self._accessFronter.ListGroupsACL():
            # Any access granted to groups with the old naming scheme
            # should be removed.
            newgroup = a['groupid']
            if re.search(r'^uio\.no:fs:\d', newgroup):
                newgroup = fix_newgroup.sub(
                    'uio.no:fs:%s:' % self.EMNE_PREFIX.lower(), newgroup)

            # Place all access-entries for node `$struct' in one hash (we
            # don't really need to look up all the nodes for which a
            # specific group has rights, so changing the order of the two
            # hash keys would make things harder).
            if (current_groups.has_key(a['structid']) and
                (current_groups.has_key(a['groupid']) or
                 current_groups.has_key(newgroup))):
                acl.setdefault(a['structid'], {})[a['groupid']] = {
                    'gacc': a['group_access'],
                    'racc': a['room_access']}
        for r in self._accessFronter.ListRoomsACL():
            role = ((r['change_access'] and self.ROLE_CHANGE) or
                    (r['delete_access'] and self.ROLE_DELETE) or
                    (r['write_access'] and self.ROLE_WRITE) or
                    (r['read_access'] and self.ROLE_READ))
            newgroup = r['groupid']
            if re.search(r'^uio\.no:fs:\d', newgroup):
                newgroup = fix_newgroup.sub(
                    'uio.no:fs:%s:' % self.EMNE_PREFIX.lower(), newgroup)

            if (current_rooms.has_key(r['roomid']) and
                (current_groups.has_key(r['groupid']) or
                 current_groups.has_key(newgroup))):
                acl.setdefault(r['roomid'], {})[r['groupid']] = {
                    'role': role}
        self.logger.debug("get_fronter_acl ret %i acls" % len(acl))
        return acl

class XMLWriter(object):   # TODO: Move to separate file
    # TODO: should produce indented XML for easier readability
    def __init__(self, fname):
        self.gen = xmlprinter.xmlprinter(
            file(fname, 'w'), indent_level=2, data_mode=1,
            #input_encoding='UTF-8')
            input_encoding='ISO-8859-1')

    def startTag(self, tag, attrs={}):
        a = {}
        for k in attrs.keys():   # saxutils don't like integers as values
            a[k] = "%s" % attrs[k]
        self.gen.startElement(tag, a)

    def endTag(self, tag):
        self.gen.endElement(tag)

    def emptyTag(self, tag, attrs={}):
        a = {}
        for k in attrs.keys():   # saxutils don't like integers as values
            a[k] = "%s" % attrs[k]
        self.gen.emptyElement(tag, a)

    def dataElement(self, tag, data, attrs={}):
        self.gen.dataElement(tag, data, attrs)

    def comment(self, data):  # TODO: implement
        self.gen.comment(data)
    
    def startDocument(self, encoding):
        self.gen.startDocument(encoding)

    def endDocument(self):
        self.gen.endDocument()

class FronterXML(object):
    def __init__(self, fname, cf_dir=None, debug_file=None, debug_level=None,
                 fronter=None, include_password=True):
        self.xml = XMLWriter(fname)
        #self.xml.startDocument(encoding='ISO-8859-1')
        self.xml.startDocument(encoding='UTF-8')
        self.rootEl = 'ENTERPRISE'
        self.DataSource = 'NO-FS'
        self.cf_dir = cf_dir
        self.debug_file = debug_file
        self.debug_level = debug_level
        self.fronter = fronter
        self.include_password = include_password
        #self.cf_id = self.fronter.DBinst.split(".")[0]
	self.cf_id = 'uitfronter'

    def start_xml_head(self):
	self.xml.comment("Eksporterer data for UiT")
	self.xml.startTag(self.rootEl)
        self.xml.startTag('PROPERTIES')
        self.xml.dataElement('DATASOURCE', self.DataSource)
        self.xml.dataElement('DATETIME', time.strftime("%Y-%m-%d"))
        self.xml.endTag('PROPERTIES')

    def start_xml_file(self, kurs2enhet):
        self.xml.comment("Eksporterer data om f�lgende emner:\n  " + 
                    "\n  ".join(kurs2enhet.keys()))
        self.xml.startTag(self.rootEl)
        self.xml.startTag('PROPERTIES')
        self.xml.dataElement('DATASOURCE', self.DataSource)
        self.xml.dataElement('TARGET', "ClassFronter/%s@uit.no" % self.cf_id)
        # :TODO: Tell Fronter (again) that they need to define the set of
        # codes for the TYPE element.
        # self.xml.dataElement('TYPE', "REFRESH")
        self.xml.dataElement('DATETIME', time.strftime("%Y-%m-%d"))
        self.xml.startTag('EXTENSION')
        self.xml.emptyTag('DEBUG', {
            'debugdest': 0, # File
            'logpath': self.debug_file,
            'debuglevel': self.debug_level})
        self.xml.emptyTag('DATABASESETTINGS', {
            'database': 0,	# Oracle
            'jdbcfilename': "%s/%s.dat" % (self.cf_dir, self.cf_id)
            })
        self.xml.endTag('EXTENSION')
        self.xml.endTag('PROPERTIES')

    def user_to_XML(self, id, recstatus, data):
        #Uit: temporary setting recstatus=1 for all users
        recstatus = 1
        """Lager XML for en person"""
        self.xml.startTag('PERSON', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == Fronter.STATUS_ADD
            or recstatus == Fronter.STATUS_UPDATE):
            self.xml.startTag('NAME')
            self.xml.dataElement('FN', data['FN'])
            self.xml.startTag('N')
            self.xml.dataElement('FAMILY', data['FAMILY'])
            self.xml.dataElement('GIVEN', data['GIVEN'])
            self.xml.endTag('N')
            self.xml.endTag('NAME')
            self.xml.dataElement('EMAIL', data['EMAIL'])
            self.xml.startTag('EXTENSION')
            if self.include_password:
                #self.xml.emptyTag('PASSWORD',
                #                  {'password': data['PASSWORD_CRYPT'],'passwordtype': data['PASSWORD_TYPE']})
                self.xml.emptyTag('PASSWORD',
                                  {'passwordtype': 'ldap1'})
            self.xml.emptyTag('EMAILCLIENT',
                              {'clienttype': data['EMAILCLIENT']})
            self.xml.emptyTag('USERACCESS', {'accesstype': data['USERACCESS']})
            self.xml.endTag('EXTENSION')
        self.xml.endTag('PERSON')

    def group_to_XML(self, id, recstatus, data):
        # Lager XML for en gruppe
        if recstatus == Fronter.STATUS_DELETE:
            return
        #Uit: temporary setting recstatus=1 for all groups
        recstatus = 1
        self.xml.startTag('GROUP', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == Fronter.STATUS_ADD or
            recstatus == Fronter.STATUS_UPDATE):
            self.xml.startTag('GROUPTYPE')
            self.xml.dataElement('SCHEME', 'FronterStructure1.0')
            allow_room = data.get('allow_room', 0)
            if allow_room:
                allow_room = 1
            allow_contact = data.get('allow_contact', 0)
            if allow_contact:
                allow_contact = 2
            self.xml.emptyTag('TYPEVALUE',
                              {'level': allow_room | allow_contact})
            self.xml.endTag('GROUPTYPE')
            self.xml.startTag('DESCRIPTION')
            if (len(data['title']) > 60):
                self.xml.emptyTag('SHORT')
                self.xml.dataElement('LONG', data['title'])
            else:
                self.xml.dataElement('SHORT', data['title'])
            self.xml.endTag('DESCRIPTION')
            self.xml.startTag('RELATIONSHIP', {'relation': 1})
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', self.DataSource)
            self.xml.dataElement('ID', data['parent'])
            self.xml.endTag('SOURCEDID')
            self.xml.emptyTag('LABEL')
            self.xml.endTag('RELATIONSHIP')
        self.xml.endTag('GROUP')

    def room_to_XML(self, id, recstatus, data):
        # Lager XML for et rom
        #
        # Gamle rom skal aldri slettes automatisk.
        if recstatus == Fronter.STATUS_DELETE:
            return 
        self.xml.startTag('GROUP', {'recstatus': recstatus})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', id)
        self.xml.endTag('SOURCEDID')
        if (recstatus == Fronter.STATUS_ADD or
            recstatus == Fronter.STATUS_UPDATE):
            self.xml.startTag('GROUPTYPE')
            self.xml.dataElement('SCHEME', 'FronterStructure1.0')
            self.xml.emptyTag('TYPEVALUE', {'level': 4})
            self.xml.endTag('GROUPTYPE')
            if (recstatus == Fronter.STATUS_ADD):
                # Romprofil settes kun ved opprettelse av rommet, og vil
                # aldri senere tvinges tilbake til noen bestemt profil.
                self.xml.startTag('GROUPTYPE')
                self.xml.dataElement('SCHEME', 'Roomprofile1.0')
                self.xml.emptyTag('TYPEVALUE', {'level': data['profile']})
                self.xml.endTag('GROUPTYPE')

        self.xml.startTag('DESCRIPTION')
        if (len(data['title']) > 60):
            self.xml.emptyTag('SHORT')
            self.xml.dataElement('LONG', data['title'])
        else:
            self.xml.dataElement('SHORT', data['title'])

        self.xml.endTag('DESCRIPTION')
        self.xml.startTag('RELATIONSHIP', {'relation': 1})
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', data['parent'])
        self.xml.endTag('SOURCEDID')
        self.xml.emptyTag('LABEL')
        self.xml.endTag('RELATIONSHIP')
        self.xml.endTag('GROUP')

    def personmembers_to_XML(self, gid, recstatus, members):
        # lager XML av medlemer
        self.xml.startTag('MEMBERSHIP')
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', gid)
        self.xml.endTag('SOURCEDID')
        for uname in members:
            self.xml.startTag('MEMBER')
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', self.DataSource)
            self.xml.dataElement('ID', uname)
            self.xml.endTag('SOURCEDID')
            self.xml.dataElement('IDTYPE', '1')	# The following member ids are persons.
            self.xml.startTag('ROLE', {'recstatus': recstatus,
                                       'roletype': Fronter.ROLE_READ})
            self.xml.dataElement('STATUS', '1')
            self.xml.startTag('EXTENSION')
            self.xml.emptyTag('MEMBEROF', {'type': 1}) # Member of group, not room.
            self.xml.endTag('EXTENSION')
            self.xml.endTag('ROLE')
            self.xml.endTag('MEMBER')
        self.xml.endTag('MEMBERSHIP')

    def acl_to_XML(self, node, recstatus, groups):
        self.xml.startTag('MEMBERSHIP')
        self.xml.startTag('SOURCEDID')
        self.xml.dataElement('SOURCE', self.DataSource)
        self.xml.dataElement('ID', node)
        self.xml.endTag('SOURCEDID')
        for gname in groups.keys():
            self.xml.startTag('MEMBER')
            self.xml.startTag('SOURCEDID')
            self.xml.dataElement('SOURCE', self.DataSource)
            self.xml.dataElement('ID', gname)
            self.xml.endTag('SOURCEDID')
            self.xml.dataElement('IDTYPE', '2')	# The following member ids are groups.
            acl = groups[gname]
            if acl.has_key('role'):
                self.xml.startTag('ROLE', {'recstatus': recstatus,
                                           'roletype': acl['role']})
                self.xml.dataElement('STATUS', '1')
                self.xml.startTag('EXTENSION')
                self.xml.emptyTag('MEMBEROF', {'type': 2}) # Member of room.
            else:
                self.xml.startTag('ROLE', {'recstatus': recstatus})
                self.xml.dataElement('STATUS', '1')
                self.xml.startTag('EXTENSION')
                self.xml.emptyTag('MEMBEROF', {'type': 1}) # Member of group.
                self.xml.emptyTag('GROUPACCESS',
                                  {'contactAccess': acl['gacc'],
                                   'roomAccess': acl['racc']})
            self.xml.endTag('EXTENSION')
            self.xml.endTag('ROLE')
            self.xml.endTag('MEMBER')
        self.xml.endTag('MEMBERSHIP')

    def end(self):
        self.xml.endTag(self.rootEl)
        self.xml.endDocument()





class uitfronter(Person.Person):

    __read_attr__ = ('__in_db', '_extid_source', '_extid_types')

    def clear(self):
        self.__super.clear()
        self.clear_class(uitfronter)
        self.__updated = []
    # end clear


    def list_cf_persons(self):
	"""Increase perfomance to fronter export""" 
	return self.query("""
        SELECT DISTINCT pi.person_id, at.account_id, pei.external_id,
          pn.name, en.entity_name, 
          pn2.name AS fs_l_name, pn3.name AS fs_f_name
        FROM
          [:table schema=cerebrum name=person_info] pi
          JOIN [:table schema=cerebrum name=account_type] at
            ON at.person_id = pi.person_id AND
               at.priority = (
                 SELECT MIN(priority)
                 FROM [:table schema=cerebrum name=account_type] at2
                 WHERE at2.person_id = pi.person_id)
          JOIN  [:table schema=cerebrum name=person_name] pn
            ON pn.person_id = pi.person_id AND
               pn.source_system = [:get_constant name=system_cached] AND
               pn.name_variant = [:get_constant name=name_full]
	  JOIN [:table schema=cerebrum name=entity_name] en
            ON at.account_id = en.entity_id
          JOIN [:table schema=cerebrum name=entity_external_id] pei
            ON pi.person_id = pei.entity_id AND
	  	pei.id_type = [:get_constant name=externalid_fodselsnr]
	  LEFT JOIN [:table schema=cerebrum name=person_name] pn2
            ON pn2.person_id = pi.person_id AND
               pn2.name_variant = [:get_constant name=name_last] AND
	       pn2.source_system = [:get_constant name=system_fs]	
          LEFT JOIN [:table schema=cerebrum name=person_name] pn3
            ON pn3.person_id = pi.person_id AND
               pn3.name_variant = [:get_constant name=name_first] AND
               pn3.source_system = [:get_constant name=system_fs]
	""")

    #Uit: function to figgure out if a person is a student,employee, or other
    #generated by kennethj 290704
    def get_affiliation(self,person_id):
        return self.query("SELECT code_str from person_affiliation_code where code in (select affiliation from person_affiliation where person_id = %s)" % person_id )

    def get_ou(self,person_id):
        #print "select ou_id from person_affiliation where person_id = %s" % person_id
        return self.query("select fakultet,institutt,avdeling from stedkode where ou_id in (select ou_id from person_affiliation where person_id = %s and affiliation=188)" % person_id)

# arch-tag: 87624dc2-b4f2-11da-9bce-cf68781f5bb2
