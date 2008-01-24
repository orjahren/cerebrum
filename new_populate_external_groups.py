#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

"""<Documentation goes here.>"""

from __future__ import generators

import sys
import os
import locale
import getopt
import time

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules import Email
from Cerebrum.modules.no import access_FS
from Cerebrum.modules.no.uit.access_FS import person_xml_parser
from Cerebrum.modules.no.uit.access_FS import student_undakt_xml_parser
from Cerebrum.modules.no.uit.access_FS import undakt_xml_parser

# Define default file locations
dumpdir = os.path.join(cereconf.DUMPDIR,"FS")
default_person_file =   'person.xml'
default_role_file = 'roles.xml'
default_undvenh_file = 'underv_enhet.xml'
default_undenh_student_file = 'student_undenh.xml'
default_studieprogram_file = 'studieprog.xml'
default_undakt_file = 'undakt.xml'
default_undakt_student_file = 'student_undakt.xml'

# Define all global variables, to avoid pychecker warnings.
db = logger = fnr2account_id = const = None


###
### Struktur FS-grupper i Cerebrum
###
#
# 0  Supergruppe for alle grupper automatisk avledet fra FS
#      internal:DOMAIN:fs:{supergroup}
#      Eks "internal:uit.no:fs:{supergroup}"
#    1  Gruppering av alle undervisningsenhet-relaterte grupper ved en
#       institusjon
#         internal:DOMAIN:fs:INSTITUSJONSNR:undenh
#         Eks "internal:uit.no:fs:201:undenh"
#       2  Gruppering av alle undervisningsenhet-grupper i et semester
#            internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:TERMINKODE
#            Eks "internal:uit.no:fs:201:undenh:2004:v�r"
#          3  Gruppering av alle grupper knyttet til en bestemt und.enhet
#               internal:DOMAIN:fs:INSTITUSJONSNR:undenh:ARSTALL:
#                 TERMINKODE:EMNEKODE:VERSJONSKODE:TERMINNR
#               Eks "internal:uit.no:fs:201:undenh:2004:v�r:be-102:g:1"
#             4  Gruppe med studenter som tar und.enhet
#                  Eks "internal:uit.no:fs:201:undenh:2004:v�r:be-102:g:1:
#                       student"
#             4  Gruppe med forelesere som gir und.enhet
#                  Eks "internal:uit.no:fs:201:undenh:2004:v�r:be-102:g:1:
#                       foreleser"
#             4  Gruppe med studieledere knyttet til en und.enhet
#                  Eks "internal:uit.no:fs:201:undenh:2004:v�r:be-102:g:1:
#                       studieleder"
#             4  Gruppe med undervisningsaktiviteter knyttet til en und.enhet
#                  Eks "internal:uit.no:fs:201:undenh:2004:v�r:fil-0700:1:1:
#                       undakt:2-1"
#    1  Gruppering av alle grupper relatert til studieprogram ved en
#       institusjon
#         internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram
#         Eks "internal:uit.no:fs:201:studieprogram"
#       2  Gruppering av alle grupper knyttet til et bestemt studieprogram
#            internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:STUDIEPROGRAMKODE
#            Eks "internal:uit.no:fs:201:studieprogram:tekn.eksp"
#          3  Gruppering av alle studiekull-grupper for et studieprogram
#               internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                 STUDIEPROGRAMKODE:studiekull
#               Eks "internal:uit.no:fs:201:studieprogram:tekn.eksp:studiekull"
#             4  Gruppe med alle studenter i et kull
#                  internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                    STUDIEPROGRAMKODE:studiekull:ARSTALL_KULL:
#                    TERMINKODE_KULL:student
#                  Eks "internal:uit.no:fs:201:studieprogram:tekn.eksp:
#                       studiekull:2004:v�r:student"
#          3  Gruppering av alle personrolle-grupper for et studieprogram
#               internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                 STUDIEPROGRAMKODE:rolle
#               Eks "internal:uit.no:fs:201:studieprogram:tekn.eksp:rolle"
#             4  Gruppe med alle studieledere knyttet til et studieprogram
#                  internal:DOMAIN:fs:INSTITUSJONSNR:studieprogram:
#                    STUDIEPROGRAMKODE:rolle:studieleder
#                  Eks "internal:uit.no:fs:201:studieprogram:tekn.eksp:
#                       rolle:studieleder"
#    1  Gruppering av alle grupper relatert til EVU
#         Eks "internal:DOMAIN:fs:INSTITUSJONSNR:evu"
#       2  Gruppering av alle grupper knyttet til et bestemt EVU-kurs
#            Eks "internal:DOMAIN:fs:INSTITUSJONSNR:evu:94035B:2005 v�r"
#          3  Gruppe med kursdeltakere p� et bestemt EVU-kurs
#               Eks "internal:DOMAIN:fs:INSTITUSJONSNR:evu:94035B:2005 v�r:
#                    kursdeltakere"
#          3  Gruppe med forelesere p� et bestemt EVU-kurs
#               Eks "internal:DOMAIN:fs:INSTITUSJONSNR:evu:94035B:2005 v�r:
#                    forelesere"
#

###
### Struktur SAP-grupper i Cerebrum
###
#
# 0  Supergruppe for alle grupper automatisk avledet fra SAP
#      internal:DOMAIN:sap:{supergroup}
#      Eks "internal:uit.no:sap:{supergroup}"
#    1  Gruppering av alle fakultets-baserte grupper
#         internal:DOMAIN:sap:fakultet
#         Eks "internal:uit.no:sap:fakultet"
#       2  Gruppering av alle grupper knyttet til et bestemt fakultet
#            internal:DOMAIN:sap:fakultet:INSTITUSJONSNR:STEDKODE
#            Eks "internal:uit.no:sap:fakultet:201:010000"
#          3  Gruppe med alle ansatte p� fakultet
#            internal:DOMAIN:sap:fakultet:INSTITUSJONSNR:STEDKODE:ansatt
#            Eks "internal:uit.no:sap:fakultet:201:010000:ansatt"

def safe_join(elements, sep=' '):
    """As string.join(), but ensures `sep` is not part of any element."""
    for i in range(len(elements)):
        if elements[i].find(sep) <> -1:
            raise ValueError, \
                  "Join separator %r found in element #%d (%r)" % (
                sep, i, elements[i])
    return sep.join(elements)

def get_account(name):
    ac = Factory.get('Account')(db)
    ac.find_by_name(name)
    return ac

def get_group(id):
    gr = Factory.get('Group')(db)
    if isinstance(id, str):
        gr.find_by_name(id)
    else:
        gr.find(id)
    return gr

def destroy_group(group_id, max_recurse):
    if max_recurse is None:
        logger.fatal("destroy_group(%r) vil ikke slette permanent gruppe.",
                     group_id)
        #return
        sys.exit(1)
    gr = get_group(group_id)
    logger.debug("destroy_group(%s/%d, %d) [After get_group]",
                 gr.group_name, gr.entity_id, max_recurse)
    if max_recurse < 0:
        logger.fatal("destroy_group(%s): Recursion too deep", gr.group_name)
        sys.exit(3)
        
    # If this group is a member of other groups, remove those
    # memberships.
    for r in gr.list_groups_with_entity(gr.entity_id):
        parent = get_group(r['group_id'])
        logger.debug("removing %s from group %s",
                     gr.group_name, parent.group_name)
        parent.remove_member(gr.entity_id, r['operation'])

    # If a e-mail target is of type multi and has this group as its
    # destination, delete the e-mail target and any associated
    # addresses.  There can only be one target per group.
    et = Email.EmailTarget(db)
    try:
        et.find_by_email_target_attrs(target_type = const.email_target_multi,
                                      entity_id = gr.entity_id)
    except Errors.NotFoundError:
        pass
    else:
        logger.debug("found email target referencing %s", gr.group_name)
        ea = Email.EmailAddress(db)
        for r in et.get_addresses():
            ea.clear()
            ea.find(r['address_id'])
            logger.debug("deleting address %s@%s",
                         r['local_part'], r['domain'])
            ea.delete()
        et.delete()
    # Fetch group's members
    u, i, d = gr.list_members(member_type=const.entity_group)
    logger.debug("destroy_group() subgroups: %r", u)
    # Remove any spreads the group has
    for row in gr.get_spread():
        gr.delete_spread(row['spread'])
    # Delete the parent group (which implicitly removes all membership
    # entries representing direct members of the parent group)
    gr.delete()
    # Destroy any subgroups (down to level max_recurse).  This needs
    # to be done after the parent group has been deleted, in order for
    # the subgroups not to be members of the parent anymore.
    for subg in u:
        destroy_group(subg[1], max_recurse - 1)


class group_tree(object):

    # Dersom destroy_group() kalles med max_recurse == None, aborterer
    # programmet.
    max_recurse = None

    # De fleste automatisk opprettede gruppene skal ikke ha noen
    # spread.
    spreads = ()

    def __init__(self):
        self.subnodes = {}
        self.users = {}

    def name_prefix(self):
        prefix = ()
        parent = getattr(self, 'parent', None)
        if parent is not None:
            prefix += parent.name_prefix()
        prefix += getattr(self, '_prefix', ())
        return prefix

    def name(self):
        name_elements = self.name_prefix()
        name_elements += getattr(self, '_name', ())
        return safe_join(name_elements, ':').lower()

    def description(self):
        pass

    def list_matches(self, gtype, data, category):
        if self.users:
            raise RuntimeError, \
                  "list_matches() not overriden for user-containing group."
        for subg in self.subnodes.itervalues():
            #logger.debug("subg = %s" % subg.values())
            #logger.debug("subg: %s" % subg.name())
            for match in subg.list_matches(gtype, data, category):
                #logger.debug("match")
                yield match
    def list_matches_1(self, *args, **kws):
        ret = [x for x in self.list_matches(*args, **kws)]
        if len(ret) == 1:
            return ret
        elif len(ret) == 0:
            # I praksis viser det seg at mange "aktive" studenter har
            # registreringer p� utg�tte studieprogrammer o.l., slik at
            # list_matches returnerer 0 grupper.  Den situasjonen er
            # det lite dette scriptet kan gj�re med, og det b�r derfor
            # ikke f�re til noen ERROR-loggmelding.
            logger.debug("Ikke gyldig kull eller studieprog: args=%r", args)
            #import pprint
            #pprint.pprint(self.subnodes)
            #sys.exit(1)
            return () 
        logger.error("Matchet for mange: self=%r, args=%r, kws=%r, ret=%r",
                     self, args, kws, ret)
        return ()

    def sync(self):
        logger.debug("Start: group_tree.sync(), name = %s", self.name())
        db_group = self.maybe_create()
        sub_ids = {}
        if self.users:
            # Gruppa inneholder minst en person, og skal dermed
            # populeres med *kun* prim�rbrukermedlemmer.  Bygg opp
            # oversikt over prim�rkonto-id'er i 'sub_ids'.
            for fnr in self.users.iterkeys():
                a_ids = fnr2account_id.get(fnr)
                if a_ids is not None:
                    primary_account_id = int(a_ids[0])
                    sub_ids[primary_account_id] = const.entity_account
                else:
                    logger.warn("Fant ingen bruker for fnr=%r (XML = %r)",
                                fnr, self.users[fnr])
        else:
            # Gruppa har ikke noen personmedlemmer, og skal dermed
            # populeres med *kun* evt. subgruppemedlemmer.  Vi s�rger
            # for at alle subgrupper synkroniseres f�rst (rekursivt),
            # og samler samtidig inn entity_id'ene deres i 'sub_ids'.
            for subg in self.subnodes:
                sub_ids[int(subg.sync())] = const.entity_group
        # I 'sub_ids' har vi n� en oversikt over hvilke entity_id'er
        # som skal bli gruppens medlemmer.  Foreta n�dvendige inn- og
        # utmeldinger.
        membership_ops = (const.group_memberop_union,
                          const.group_memberop_intersection,
                          const.group_memberop_difference)
        for members_with_op, op in zip(db_group.list_members(),
                                       membership_ops):
            for member_type, member_id in members_with_op:
                member_id = int(member_id)
                if member_id in sub_ids:
                    del sub_ids[member_id]
                else:
                    db_group.remove_member(member_id, op)
                    if member_type == const.entity_group:
                        destroy_group(member_id, self.max_recurse)
        for member_id in sub_ids.iterkeys():
            db_group.add_member(member_id, sub_ids[member_id],
                                const.group_memberop_union)
        # Synkroniser gruppens spreads med lista angitt i
        # self.spreads.
        want_spreads = {}
        for s in self.spreads:
            want_spreads[int(s)] = 1
        for row in db_group.get_spread():
            spread = int(row['spread'])
            if spread in want_spreads:
                del want_spreads[spread]
            else:
                db_group.delete_spread(spread)
        for new_spread in want_spreads.iterkeys():
            db_group.add_spread(new_spread)
        logger.debug("Ferdig: group_tree.sync(), name = %s", self.name())
        return db_group.entity_id

    def maybe_create(self):
        
        try:
            return get_group(self.name())
        except Errors.NotFoundError:
            gr = Factory.get('Group')(db)
            gr.populate(self.group_creator(),
                        const.group_visibility_internal,
                        self.name(),
                        description=self.description())
            gr.write_db()
            return gr

    def group_creator(self):
        acc = get_account(cereconf.INITIAL_ACCOUNTNAME)
        return acc.entity_id

    def __eq__(self, other):
        if type(other) is type(self):
            return (self.name() == other.name())
        return False

    def __ne__(self, other):
        return (not self.__eq__(other))

    def __hash__(self):
        return hash(self.name())


class fs_supergroup(group_tree):

    max_recurse = None

    def __init__(self):
        super(fs_supergroup, self).__init__()
        self._prefix = ('internal', cereconf.INSTITUTION_DOMAIN_NAME, 'fs')
        self._name = ('{supergroup}',)

    def description(self):
        return "Supergruppe for alle FS-avledede grupper ved %s" % (
            cereconf.INSTITUTION_DOMAIN_NAME,)

    def add(self, gtype, attrs):
        if gtype == 'undenh':
            subg = fs_undenh_1(self, attrs)
        elif gtype == 'studieprogram':
            subg = fs_stprog_1(self, attrs)
        elif gtype == 'evu':
            subg = fs_evu_1(self, attrs)
        else:
            raise ValueError, "Ukjent gruppe i hierarkiet: %r" % (gtype,)
        children = self.subnodes
        # TBD: Make fs_{undenh,stprog}_N into singleton classes?
        if children.has_key(subg):
            subg = children[subg]
        else:
            children[subg] = subg
        subg.add(attrs)


class fs_undenh_group(group_tree):

    def __init__(self, parent):
        super(fs_undenh_group, self).__init__()
        self.parent = parent
        self.child_class = None

    def add(self, ue):
        new_child = self.child_class(self, ue)
        children = self.subnodes
        if new_child in children:
            new_child = children[new_child]
        else:
            children[new_child] = new_child
        new_child.add(ue)


class fs_undenh_1(fs_undenh_group):

    max_recurse = 3

    def __init__(self, parent, ue):
        super(fs_undenh_1, self).__init__(parent)
        self._prefix = (ue['institusjonsnr'], 'undenh')
        self.child_class = fs_undenh_2

    def description(self):
        return ("Supergruppe for alle grupper avledet fra"
                " undervisningsenhetene i %s sin FS" %
                cereconf.INSTITUTION_DOMAIN_NAME)

    def list_matches(self, gtype, data, category):
        if gtype <> 'undenh':
            return ()
        if access_FS.roles_xml_parser.target_key in data:
            target = data[access_FS.roles_xml_parser.target_key]
            if not (len(target) == 1 and target[0] == 'undenh'):
                return ()
        if data.get('institusjonsnr', self._prefix[0]) <> self._prefix[0]:
            return ()
        return super(fs_undenh_1, self).list_matches(gtype, data, category)


class fs_undenh_2(fs_undenh_group):

    max_recurse = 2

    def __init__(self, parent, ue):
        super(fs_undenh_2, self).__init__(parent)
        self._prefix = (ue['arstall'], ue['terminkode'])
        self.child_class = fs_undenh_3

    def description(self):
        return ("Supergruppe for alle %s sine FS-undervisningsenhet-grupper"
                " %s %s" % (cereconf.INSTITUTION_DOMAIN_NAME,
                            self._prefix[1], self._prefix[0]))

    def list_matches(self, gtype, data, category):
        if data.get('arstall', self._prefix[0]) <> self._prefix[0]:
            return ()
        if data.get('terminkode', self._prefix[1]) <> self._prefix[1]:
            return ()
        return super(fs_undenh_2, self).list_matches(gtype, data, category)


class fs_undenh_3(fs_undenh_group):

    ue_versjon = {}
    ue_termin = {}
    max_recurse = 1

    def __init__(self, parent, ue):
        super(fs_undenh_3, self).__init__(parent)
        self._prefix = (ue['emnekode'], ue['versjonskode'], ue['terminnr'])
        multi_id = ":".join([str(x)
                             for x in(ue['institusjonsnr'], ue['emnekode'],
                                      ue['terminkode'], ue['arstall'])])
        self.ue_versjon.setdefault(multi_id, {})[ue['versjonskode']] = 1
        self.ue_termin.setdefault(multi_id, {})[ue['terminnr']] = 1
        self._multi_id = multi_id
        self.spreads = (const.spread_uit_fronter,)

    def multi_suffix(self):
        multi_suffix = []
        multi_id = self._multi_id
        if len(self.ue_versjon.get(multi_id, {})) > 1:
            multi_suffix.append("v%s" % (self._prefix[1],))
        if len(self.ue_termin.get(multi_id, {})) > 1:
            multi_suffix.append("%s. termin" % (self._prefix[2],))
        if multi_suffix:
            return (" " + " ".join(multi_suffix))
        return ""

    def description(self):
        return ("Supergruppe for grupper tilknyttet undervisningsenhet"
                " %s%s" % (self._multi_id, self.multi_suffix()))

    def list_matches(self, gtype, data, category):
        if data.get('emnekode', self._prefix[0]) <> self._prefix[0]:
            return ()
        if data.get('versjonskode', self._prefix[1]) <> self._prefix[1]:
            return ()
        if data.get('terminnr', self._prefix[2]) <> self._prefix[2]:
            return ()
        return super(fs_undenh_3, self).list_matches(gtype, data, category)

    def add(self, ue):
        children = self.subnodes
        #for category in ('student', 'foreleser', 'studieleder'):
        for category in ('student', 'foreleser'):
            gr = fs_undenh_users(self, ue, category)
            if gr in children:
                logger.warn('Undervisningsenhet %r forekommer flere ganger.',
                            ue)
                continue
            children[gr] = gr
        
        if 'aktivitetkode' in ue:
            gr = fs_undakt_users(self, ue, 'undakt')
            if gr in children:
                logger.warn('Undervisningsaktivitet %r forekommer flere ganger.',
                            ue)
            else:
                children[gr] = gr


class fs_undenh_users(fs_undenh_group):

    max_recurse = 0

    def __init__(self, parent, ue, category):
        super(fs_undenh_users, self).__init__(parent)
        self._name = (category,)
        self._emnekode = ue['emnekode']

    def description(self):
        ctg = self._name[0]
        emne = self._emnekode + self.parent.multi_suffix()
        if ctg == 'student':
            return "Studenter p� %s" % (emne,)
        elif ctg == 'foreleser':
            return "Forelesere p� %s" % (emne,)
        #elif ctg == 'studieleder':
        #    return "Studieledere p� %s" % (emne,)
        else:
            raise ValueError, "Ukjent UE-bruker-gruppe: %r" % (ctg,)

    def list_matches(self, gtype, data, category):
        if category == self._name[0]:
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user['fodselsdato']), int(user['personnr']))
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.warn("Bruker %r fors�kt meldt inn i gruppe %r"
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return
        self.users[fnr] = user

class fs_undakt_users(fs_undenh_group):

    def __init__(self, parent, ue, category):        
        super(fs_undakt_users, self).__init__(parent)
        self._aktivitetkode=ue['aktivitetkode']
        self._name=(category,self._aktivitetkode)
        self._emnekode = ue['emnekode']

    def description(self):
        ctg = self._name[0]
        emne = self._emnekode + self.parent.multi_suffix()
        if ctg == 'undakt':
            return "Personer p� %s (%s)" % (emne,self._aktivitetkode)
        else:
            raise ValueError, "Ukjent UA-bruker-gruppe: %r" % (ctg,)

    def list_matches(self, gtype, data, category):
        #logger.debug("undak_users: gtype=%s, data=%s, category=%s, self._name=%s, aktivitetkode=%s" % (gtype,data,category,self._name,self._aktivitetkode))
        if category == self._name[0] and data.get('aktivitetkode', self._aktivitetkode) == self._aktivitetkode:
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user['fodselsdato']), int(user['personnr']))
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.warn("Bruker %r fors�kt meldt inn i gruppe %r"
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return
        self.users[fnr] = user

class fs_stprog_group(group_tree):

    def __init__(self, parent):
        super(fs_stprog_group, self).__init__()
        self.parent = parent
        self.child_class = None

    def add(self, stprog):
        new_child = self.child_class(self, stprog)
        children = self.subnodes
        if new_child in children:
            new_child = children[new_child]
        else:
            children[new_child] = new_child
        new_child.add(stprog)


class fs_stprog_1(fs_stprog_group):

    max_recurse = 3

    def __init__(self, parent, stprog):
        super(fs_stprog_1, self).__init__(parent)
        if (stprog['institusjonsnr_studieansv'] == "4902"):
           logger.critical("SUPERERROR: Got institusjonnr = 4902!")
           sys.exit(1)
        self._prefix = (stprog['institusjonsnr_studieansv'],
                        'studieprogram')
        self.child_class = fs_stprog_2

    def description(self):
        return ("Supergruppe for alle grupper relatert til"
                " studieprogram i %s sin FS" %
                (cereconf.INSTITUTION_DOMAIN_NAME,))

    def list_matches(self, gtype, data, category):
        if gtype <> 'studieprogram':
            return ()
        if access_FS.roles_xml_parser.target_key in data:
            target = data[access_FS.roles_xml_parser.target_key]
            if not (len(target) == 1 and target[0] == 'stprog'):
                return ()
        if data.get('institusjonsnr', self._prefix[0]) <> self._prefix[0]:
            return ()
        return super(fs_stprog_1, self).list_matches(gtype, data, category)


class fs_stprog_2(fs_stprog_group):

    max_recurse = 2

    def __init__(self, parent, stprog):
        super(fs_stprog_2, self).__init__(parent)
        self._prefix = (stprog['studieprogramkode'],)
        # Denne klassen har mer enn en mulig barn-klasse.
        self.child_class = None

    def description(self):
        return ("Supergruppe for alle grupper knyttet til"
                " studieprogrammet %r" % (self._prefix[0],))

    def add(self, stprog):
        # Det skal lages to grener under hver gruppe p� dette niv�et.
        old = self.child_class
        try:
            for child_class in (fs_stprog_3_kull, fs_stprog_3_rolle):
                self.child_class = child_class
                super(fs_stprog_2, self).add(stprog)
        finally:
            self.child_class = old

    def list_matches(self, gtype, data, category):
        if data.get('studieprogramkode', self._prefix[0]) <> self._prefix[0]:
            return ()
        return super(fs_stprog_2, self).list_matches(gtype, data, category)


class fs_stprog_3_kull(fs_stprog_group):

    max_recurse = 1

    def __init__(self, parent, stprog):
        super(fs_stprog_3_kull, self).__init__(parent)
        self._prefix = ('studiekull',)
        self._studieprog = stprog['studieprogramkode']
        self.child_class = fs_stprog_kull_users
        self.spreads = (const.spread_uit_fronter,)

    def description(self):
        return ("Supergruppe for studiekull-grupper knyttet til"
                " studieprogrammet %r" % (self._studieprog,))

    def list_matches(self, gtype, data, category):
        # Denne metoden er litt annerledes enn de andre
        # list_matches()-metodene, da den ogs� gj�r opprettelse av
        # kullkode-spesifikke subgrupper n�r det er n�dvendig.
        ret = []
        for subg in self.subnodes.itervalues():
            ret.extend([m for m in subg.list_matches(gtype, data, category)])
        if (not ret) and (data.has_key('arstall_kull')
                          and data.has_key('terminkode_kull')):
            ret.extend(self.add(data))
        return ret

    def add(self, stprog):
        children = self.subnodes
        ret = []
        for category in ('student',):
            # Fila studieprog.xml inneholder ikke noen angivelse av
            # hvilke studiekull som finnes; den lister bare opp
            # studieprogrammene.
            #
            # Opprettelse av grupper for de enkelte studiekullene
            # utsettes derfor til senere (i.e. ved parsing av
            # person.xml); se metoden list_matches over.
            if (stprog.has_key('arstall_kull')
                and stprog.has_key('terminkode_kull')):
                gr = self.child_class(self, stprog, category)
                if gr in children:
                    logger.warn("Kull %r forekommer flere ganger.", stprog)
                    continue
                children[gr] = gr
                ret.append(gr)
        # TBD: B�r, bl.a. for konsistensens skyld, alle .add()-metoden
        # returnere noe?  Denne .add()-metodens returverdi brukes av
        # .list_matches()-metoden like over.
        return ret


class fs_stprog_kull_users(fs_stprog_group):

    max_recurse = 0

    def __init__(self, parent, stprog, category):
        super(fs_stprog_kull_users, self).__init__(parent)
        self._prefix = (stprog['arstall_kull'], stprog['terminkode_kull'])
        self._studieprog = stprog['studieprogramkode']
        self._name = (category,)

    def description(self):
        category = self._name[0]
        if category == 'student':
            return ("Studenter p� kull %s %s i"
                    " studieprogrammet %r" % (self._prefix[1],
                                              self._prefix[0],
                                              self._studieprog))
        raise ValueError("Ugyldig kategori: %r" % category)

    def list_matches(self, gtype, data, category):
        if (data.get('arstall_kull', self._prefix[0]) == self._prefix[0]
            and data.get('terminkode_kull', self._prefix[1]) == self._prefix[1]
            and category == self._name[0]):
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user['fodselsdato']), int(user['personnr']))
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.warn("Bruker %r fors�kt meldt inn i gruppe %r"
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return
        self.users[fnr] = user


class fs_stprog_3_rolle(fs_stprog_group):

    max_recurse = 1

    def __init__(self, parent, stprog):
        super(fs_stprog_3_rolle, self).__init__(parent)
        self._prefix = ('rolle',)
        self._studieprog = stprog['studieprogramkode']
        self.child_class = fs_stprog_rolle_users
        self.spreads = (const.spread_uit_fronter,)

    def description(self):
        return ("Supergruppe for personrolle-grupper knyttet til"
                " studieprogrammet %r" % (self._studieprog,))

    def add(self, stprog):
        children = self.subnodes
        for category in ('studieleder',):
            gr = self.child_class(self, stprog, category)
            if gr in children:
                logger.warn('Studieprogram %r forekommer flere ganger.',
                            self._studieprog)
                continue
            children[gr] = gr


class fs_stprog_rolle_users(fs_stprog_group):

    max_recurse = 0

    def __init__(self, parent, stprog, category):
        super(fs_stprog_rolle_users, self).__init__(parent)
        self._studieprog = stprog['studieprogramkode']
        self._name = (category,)

    def description(self):
        category = self._name[0]
        if category == 'studieleder':
            return ("Studieledere p� studieprogrammet %r" % self._studieprog)
        raise ValueError("Ugyldig kategori: %r" % category)

    def list_matches(self, gtype, data, category):
        if category == self._name[0]:
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user['fodselsdato']), int(user['personnr']))
        # TBD: Key on account_id (of primary user) instead?
        if fnr in self.users:
            logger.warn("Bruker %r fors�kt meldt inn i gruppe %r"
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return
        self.users[fnr] = user



class fs_evu_1(fs_undenh_group):
    """
    EVU-subtre
    """

    max_recurse = 2

    def __init__(self, parent, evudata):
        super(fs_evu_1, self).__init__(parent)
        self._prefix = (evudata["institusjonsnr_adm_ansvar"], "evu")
        self.child_class = fs_evu_2
    # end __init__


    def description(self):
        return ("Supergruppe for alle grupper avledet fra"
                " EVU-kurs i %s sin FS" %
                cereconf.INSTITUTION_DOMAIN_NAME)
    # end description


    def list_matches(self, gtype, data, category):
        if gtype != "evu":
            return ()
        # fi

        if access_FS.roles_xml_parser.target_key in data:
            target = data[access_FS.roles_xml_parser.target_key]
            if not (len(target) == 1 and target[0] == "evu"):
                return ()
            # fi
        # fi

        if (data.get("institusjonsnr_adm_ansvar", self._prefix[0]) !=
            self._prefix[0]):
            return ()

        return super(fs_evu_1, self).list_matches(gtype, data, category)


class fs_evu_2(fs_undenh_group):
    max_recurse = 1

    def __init__(self, parent, evudata):
        super(fs_evu_2, self).__init__(parent)
        self._prefix = (evudata["etterutdkurskode"],
                        evudata["kurstidsangivelsekode"])
        self.spreads = (const.spread_uit_fronter,)

    def description(self):
        return ("Supergruppe for grupper tilknyttet EVU-kurs %s:%s" %
                (self._prefix[0], self._prefix[1]))

    def list_matches(self, gtype, data, category):
        if data.get("etterutdkurskode", self._prefix[0]) != self._prefix[0]:
            return ()
        if (data.get("kurstidsangivelsekode", self._prefix[1]) !=
            self._prefix[1]):
            return ()
        return super(fs_evu_2, self).list_matches(gtype, data, category)


    def add(self, evudata):
        children = self.subnodes
        for category in ("kursdeltaker", "foreleser"):
            gr = fs_evu_users(self, evudata, category)
            if gr in children:
                logger.warn("EVU-kurs %r forekommer flere ganger.",
                            evudata)
                continue 
            children[gr] = gr


class fs_evu_users(fs_undenh_group):

    max_recurse = 0

    def __init__(self, parent, evudata, category):
        super(fs_evu_users, self).__init__(parent)
        self._name = (category,)

    def description(self):
        category = self._name[0]
        if category == "kursdeltaker":
            return "Kursdeltakere p� %s" % self.parent.name()
        elif category == "foreleser":
            return "Forelesere p� %s" % self.parent.name()
        else:
            raise ValueError, "Ukjent EVU-brukergrupper: %r" % (category,)

    def list_matches(self, gtype, data, category):
        if category == self._name[0]:
            yield self

    def add(self, user):
        fnr = "%06d%05d" % (int(user["fodselsdato"]), int(user["personnr"]))
        if fnr in self.users:
            logger.warn("Bruker %r fors�kt meldt inn i gruppe %r "
                        " flere ganger (XML = %r).",
                        fnr, self.name(), user)
            return
        self.users[fnr] = user



def prefetch_primaryusers():
    logger.debug("Start: prefetch_primaryusers()")
    # TBD: This code is used to get account_id for both students and
    # fagansv.  Should we look at affiliation here?
    account = Factory.get('Account')(db)
    personid2accountid = {}
    for a in account.list_accounts_by_type():
        p_id = int(a['person_id'])
        a_id = int(a['account_id'])
        personid2accountid.setdefault(p_id, []).append(a_id)

    person = Factory.get('Person')(db)
    fnr_source = {}
    for row in person.list_external_ids(id_type=const.externalid_fodselsnr):
        p_id = int(row['entity_id'])
        fnr = row['external_id']
        src_sys = int(row['source_system'])
        #print "LOADED: p_id: %s, fnr: '%s', src_sys: %s" % (row['entity_id'],row['external_id'],row['source_system'])
        if fnr_source.has_key(fnr) and fnr_source[fnr][0] <> p_id:
            # Multiple person_info rows have the same fnr (presumably
            # the different fnrs come from different source systems).
            logger.error("Multiple persons share fnr %s: (%d, %d)",
                         fnr, fnr_source[fnr][0], p_id)
            # Determine which person's fnr registration to use.
            source_weight = {int(const.system_fs): 4,
                             int(const.system_manual): 3,
                             int(const.system_lt): 2} # UIT: orginal -> system_sap
                             #int(const.system_migrate): 1} # UIT: removed migrate
            old_weight = source_weight.get(fnr_source[fnr][1], 0)
            if source_weight.get(src_sys, 0) <= old_weight:
                continue
            # The row we're currently processing should be preferred;
            # if the old row has an entry in fnr2account_id, delete
            # it.
            if fnr2account_id.has_key(fnr):
                #print "deleting fnr=%s"
                del fnr2account_id[fnr]
        fnr_source[fnr] = (p_id, src_sys)
        if personid2accountid.has_key(p_id):
            account_ids = personid2accountid[p_id]
##             for acc in account_ids:
##                 account_id2fnr[acc] = fnr
            #print "adding fnr=%s: %s" % (fnr,account_ids)
            fnr2account_id[fnr] = account_ids
        else:
            pass
            #print "dropping fnr=%s, not in personis2accountid" % (fnr)
    del fnr_source
    #print fnr2account_id
    logger.debug("Ferdig: prefetch_primaryusers()")

def init_globals():
    global db, const, logger, fnr2account_id
    global dump_dir, dryrun, immediate_evu_expire

    # H�ndter upper- og lowercasing av strenger som inneholder norske
    # tegn.
    locale.setlocale(locale.LC_CTYPE, ('en_US', 'iso88591'))

    dump_dir = dumpdir
    dryrun = False
    immediate_evu_expire = False
    logger = Factory.get_logger('cronjob')

    opts, rest = getopt.getopt(sys.argv[1:],
                               "d:rl:",
                               ["dump-dir=", "dryrun",
                                "immediate-evu-expire"])
    for option, value in opts:
        if option in ("-d", "--dump-dir"):
            dump_dir = value
        elif option in ("-r", "--dryrun"):
            dryrun = True
        elif option in ("--immediate-evu-expire",):
            immediate_evu_expire = True

    db = Factory.get("Database")()
    db.cl_init(change_program='pop_extern_grps')
    const = Factory.get("Constants")(db)

    fnr2account_id = {}
    prefetch_primaryusers()

def main():
    init_globals()
    # Opprett objekt for "internal:uit.no:fs:{supergroup}"
    fs_super = fs_supergroup()

    # G� igjennom alle kjente undervisningsenheter; opprett
    # gruppe-objekter for disse.
    #
    # La fs-supergruppe-objektet ta seg av all logikk rundt hvor mange
    # niv�er gruppestrukturen skal ha for undervisningsenhet-grupper,
    # etc.
    def create_UE_helper(el_name, attrs):
        if el_name == 'undenhet':
            fs_super.add('undenh', attrs)

    logger.info("Leser XML-fil: %s", default_undvenh_file)
    access_FS.underv_enhet_xml_parser(
        os.path.join(dump_dir, default_undvenh_file),
        create_UE_helper)

    # Meld studenter inn i undervisningsenhet-gruppene
    def student_UE_helper(el_name, attrs):
        if el_name == 'student':
            for undenh in fs_super.list_matches_1('undenh', attrs,
                                                  'student'):
                undenh.add(attrs)
                
    logger.info("Leser XML-fil: %s", default_undenh_student_file)
    access_FS.student_undenh_xml_parser(
        os.path.join(dump_dir, default_undenh_student_file),
        student_UE_helper)


    # opprett undervisningsaktiviteter
    def create_UA_helper(el_name, attrs):
        if el_name == 'undakt':
            fs_super.add('undenh', attrs)

    logger.info("Leser XML-fil: %s",  default_undakt_file)
    undakt_xml_parser(
        os.path.join(dump_dir, default_undakt_file),
        create_UA_helper)

    # Meld studenter inn i undervisningsaktivitet-gruppene
    def student_UA_helper(el_name, attrs):
        if el_name == 'undakt':
            for undenh in fs_super.list_matches_1('undenh', attrs,
                                                  'undakt'):
                undenh.add(attrs)
                
    logger.info("Leser XML-fil: %s", default_undakt_student_file)
    student_undakt_xml_parser(
        os.path.join(dump_dir, default_undakt_student_file),
        student_UA_helper)


    # G� igjennom alle kjente studieprogrammer; opprett gruppeobjekter
    # for disse.
    def create_studieprog_helper(el_name, attrs):
        if el_name == 'studprog' and attrs.get('status_utgatt') <> 'J':
            fs_super.add('studieprogram', attrs)

    logger.info("Leser XML-fil: %s", default_studieprogram_file)
    access_FS.studieprog_xml_parser(
        os.path.join(dump_dir, default_studieprogram_file),
        create_studieprog_helper)

    # Meld forelesere og studieledere inn i passende
    # undervisningsenhet/EVU-kurs -gruppene
    def rolle_helper(el_name, attrs):
        logger.info("melder forelesere og studieledere inn i grupper: el_name=%s,attrs=%s" % (el_name,attrs))
        if el_name != 'rolle':
            return
        rolle = attrs['rollekode']
        target = attrs[access_FS.roles_xml_parser.target_key]
        if len(target) != 1:
            return
        target = target[0]
        if target in ('undenh', 'stprog'):
            #UIT: endret denne linja: if rolle == 'FORELESER':
            if rolle in ['ANSVLEDER','ASSISTENT','FAGANSVARL','FORELESER',
                         'GRUPPEL�RE','HOVEDL�RER','KONTAKT','L�RER',
                         'SENSOR','VEILEDER']:
                logger.debug("1.rolle_helper: rolle=%s, sjekker list_matches(undenh,attrs,foreleser)" % rolle)

                for ue_foreleser in fs_super.list_matches('undenh', attrs,
                                                          'foreleser'):
                    logger.debug("1.1.adding: %s" % attrs)
                    ue_foreleser.add(attrs)
                #for und_foreleser in fs_super.list_matches('undakt', attrs,'foreleser'):#uit
                #    logger.debug("1.2.adding: %s" % attrs)
                #    und_foreleser.add(attrs) # uit
                    
            if rolle in ['ANSVLEDER',]:
                logger.debug("2.rolle_helper: rolle=%s, sjekker list_matches(undenh,attrs,foreleser)" % rolle)
                #for ue_studieleder in fs_super.list_matches('undenh', attrs,
                #                                            'studieleder'):
                #    logger.debug("2.1 adding: %s" % attrs)
                #    ue_studieleder.add(attrs)
                for stpr_studieleder in fs_super.list_matches('studieprogram',
                                                              attrs,
                                                              'studieleder'):
                    logger.debug("2.2.adding: %s" % attrs)
                    stpr_studieleder.add(attrs)
        elif target in ('evu',):
            logger.info("target=%s" % target)
            if rolle == 'FORELESER':
                logger.info("logger=%s" % rolle)
                # Kan ett element tilh�re flere evukurs?
                for evu_foreleser in fs_super.list_matches('evu', attrs,
                                                           "foreleser"):
                    evu_foreleser.add(attrs)
    
    logger.info("Leser XML-fil: %s", default_role_file)
    access_FS.roles_xml_parser(os.path.join(dump_dir, default_role_file),
                               rolle_helper)
    logger.info("Ferdig med %s", default_role_file)

    # Finn alle studenter 
    def student_studieprog_helper(el_name, attrs):
        if el_name == 'aktiv':
            for stpr in fs_super.list_matches_1('studieprogram', attrs,
                                                'student'):
                stpr.add(attrs)

    logger.info("Leser XML-fil: %s", default_person_file)
    person_xml_parser(
        os.path.join(dump_dir, default_person_file),
        student_studieprog_helper)
    logger.info("Ferdig med XML-fil: %s", default_person_file)

    # Write back all changes to the database
    fs_super.sync()

    if dryrun:
        logger.info("rolling back all changes")
        db.rollback()
    else:
        logger.info("committing all changes")
        db.commit()
    # fi
# end main



def walk_hierarchy(root, indent = 0, print_users = False):
    """
    Display the data structure (tree) from a given node. Useful to get an
    overview over how various nodes are structured/populated. This is used for
    debugging only.
    """
    logger.debug("%snode: %r (%d subnode(s), %d user(s))",
                 ' ' * indent, root.name(), len(root.subnodes),
                 len(root.users))
    if print_users and root.users:
        import pprint
        logger.debug("%susers: %s", ' ' * indent, pprint.pformat(root.users))
    # fi
    
    for n in root.subnodes:
        walk_hierarchy(n, indent + 2)
    # od
# end walk_hierarchy
    




if __name__ == '__main__':
    main()
