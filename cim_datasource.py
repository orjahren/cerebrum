#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2015 University of Oslo, Norway
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

# import phonenumbers
# from Cerebrum.Utils import Factory
# from Cerebrum.Errors import NotFoundError

import cerebrum_path
import cereconf

from Cerebrum.modules.cim.datasource import CIMDataSource

class CIMDataSourceUit(CIMDataSource):
    """
    This class provides a UiT-specific extension to the CIMDataSource class.
    """

    # distribution list names (building names)
    AB              = 'Arktisk biologi'
    ADM             = 'Administrasjonsbygget'
    ALTA            = 'Alta'
    BARDUFOSS       = 'Bardufoss'
    BRELIA          = 'Breiviklia'
    DRIFTS          = 'Driftssentralen'
    FARM            = 'Farmasibygget'
    FPARK           = 'Forskningsparken'
    HAMMERFEST      = 'Hammerfest'
    HARSTAD         = 'Harstad'
    HAVBRUKSST      = 'Havbruksstasjonen'
    HHT             = 'Handelshøgskolen'
    HOLT            = 'Holt'
    HYPERBOREUM     = 'Hyperboreum'
    KIRKENES        = 'Kirkenes'
    KRV_33          = 'Musikkonservatoriet'
    KUNSTAKADEMIET  = 'Kunstakademiet'
    MAALSELV        = 'Målselv'
    MH              = 'MH-bygget'
    MODULBYGG       = 'Modulbygget'
    MV_110          = 'Mellomvegen 110'
    NARVIK          = 'Narvik'
    NATURF          = 'Naturfagbygget'
    NFH             = 'NFH'
    NLYSTH          = 'Nedre lysthus'
    NOFIMA          = 'Nofimabygget'
    POLARMUSEET     = 'Polarmuseet'
    REALF           = 'Realfagsbygget'
    RKBU            = 'RKBU'
    # SKFELT          = 'Skibotn feltstasjon'
    STAKKEVV        = 'Stakkevollvegen 23'
    SVALBARD        = 'Svalbard'
    SVHUM           = 'HSL-bygget'
    TANN            = 'Tann-bygget'
    TEKNOBYGGET     = 'Teknologibygget'
    TEO_H1          = 'Teorifagbygget hus 1'
    TEO_H2          = 'Teorifagbygget hus 2'
    TEO_H3          = 'Teorifagbygget hus 3'
    TEO_H4          = 'Teorifagbygget hus 4'
    TEO_H5          = 'Teorifagbygget hus 5'
    TEO_H6          = 'Teorifagbygget hus 6'
    TMU             = 'Tromsø museum'
    TMU_BOTANISK    = 'Tromsø museum Kvaløyvegen 30'
    TMU_KVV_156     = 'Tromsø museum Kvaløyvegen 156'
    UB              = 'Universitetsbiblioteket'
    UNN             = 'UNN'
    VITENSENTERET   = 'Vitensenteret'
    AASGAARD        = 'Åsgård'
    OLYSTH          = 'Øvre lysthus'
    IKKE_PLASSERT   = 'Ikke plassert'

    # mapping from location names etc to distribution list names
    loc2distlist = {
                    'arktisk biologi'                   : AB,
                    'aab'                               : AB,
                    'ab'                                : AB,
                    'administrasjonsbygget'             : ADM,
                    'adm'                               : ADM,
                    'alta'                              : ALTA,
                    'bardufoss'                         : BARDUFOSS,
                    'breiviklia'                        : BRELIA,
                    'brelia'                            : BRELIA,
                    'driftssentralen'                   : DRIFTS,
                    'drifts'                            : DRIFTS,
                    'farmasibygget'                     : FARM,
                    'farmasi'                           : FARM,
                    'farm'                              : FARM,
                    'forskningsparken'                  : FPARK,
                    'fpark'                             : FPARK,
                    'hammerfest'                        : HAMMERFEST,
                    'harstad'                           : HARSTAD,
                    'havbruksstasjonen i tromsø'        : HAVBRUKSST,
                    'havbruksstasjonen'                 : HAVBRUKSST,
                    'havbruksst'                        : HAVBRUKSST,
                    'handelshøgskolen'                  : HHT,
                    'handelshøyskolen'                  : HHT,
                    'hht'                               : HHT,
                    'breivang'                          : HHT,
                    'holt'                              : HOLT,
                    'hyperboreum'                       : HYPERBOREUM,
                    'kirkenes'                          : KIRKENES,
                    'krognessveien'                     : KRV_33,
                    'musikkonservatoriet'               : KRV_33,
                    'krognessvegen'                     : KRV_33,
                    'krognessveien'                     : KRV_33,
                    'krognessvn'                        : KRV_33,
                    'krognessvn.33'                     : KRV_33,
                    'krognesvegen'                      : KRV_33,
                    'krv.33'                            : KRV_33,
                    'kunstakademiet'                    : KUNSTAKADEMIET,
                    'mack'                              : KUNSTAKADEMIET,
                    'mack-bygget'                       : KUNSTAKADEMIET,
                    'mack bygget'                       : KUNSTAKADEMIET,
                    'grønnegata'                        : KUNSTAKADEMIET,
                    'grønnegata 1'                      : KUNSTAKADEMIET,
                    'målselv'                           : MAALSELV,
                    'mh-bygget'                         : MH,
                    'mh'                                : MH,
                    'medisin og helsefag'               : MH,
                    'medisin og helsefagbygget'         : MH,
                    'mellomvegen 110'                   : MV_110,
                    'mv.110'                            : MV_110,
                    'modulbygg'                         : MODULBYGG,
                    'modulbygget'                       : MODULBYGG,
                    'modul'                             : MODULBYGG,
                    'narvik'                            : NARVIK,
                    'naturfagbygget'                    : NATURF,
                    'naturf'                            : NATURF,
                    'norges fiskerihøgskole'            : NFH,
                    'nfh'                               : NFH,
                    'nedre lysthus'                     : NLYSTH,
                    'nlysth'                            : NLYSTH,
                    'nofimabygget'                      : NOFIMA,
                    'nofima'                            : NOFIMA,
                    'polarmuseet'                       : POLARMUSEET,
                    'realfagbygget'                     : REALF,
                    'realfagsbygget'                    : REALF,
                    'realf'                             : REALF,
                    'rkbu'                              : RKBU,
                    'gimlevegen 78'                     : RKBU,
                    'stakkevollvegen 23'                : STAKKEVV,
                    'stakkevv'                          : STAKKEVV,
                    'svalbard'                          : SVALBARD,
                    'svhum'                             : SVHUM,
                    'svfak'                             : SVHUM,
                    'humfak'                            : SVHUM,
                    'sv'                                : SVHUM,
                    'hum'                               : SVHUM,
                    'tann-bygget'                       : TANN,
                    'tannbygget'                        : TANN,
                    'tann'                              : TANN,
                    'teknologibygget'                   : TEKNOBYGGET,
                    'teknobygget'                       : TEKNOBYGGET,
                    'tek'                               : TEKNOBYGGET,
                    'teorifagbygget hus 1'              : TEO_H1,
                    'teo-h1'                            : TEO_H1,
                    'teo h1'                            : TEO_H1,
                    'teorifagbygget hus 2'              : TEO_H2,
                    'teo-h2'                            : TEO_H2,
                    'teo h2'                            : TEO_H2,
                    'teorifagbygget hus 3'              : TEO_H3,
                    'teo-h3'                            : TEO_H3,
                    'teo h3'                            : TEO_H3,
                    'teorifagbygget hus 4'              : TEO_H4,
                    'teo-h4'                            : TEO_H4,
                    'teo h4'                            : TEO_H4,
                    'teorifagbygget hus 5'              : TEO_H5,
                    'teo-h5'                            : TEO_H5,
                    'teo h5'                            : TEO_H5,
                    'teorifagbygget hus 6'              : TEO_H6,
                    'teo-h6'                            : TEO_H6,
                    'teo h6'                            : TEO_H6,
                    'tromsø museum'                     : TMU,
                    'tmu'                               : TMU,
                    'tmu botanisk'                      : TMU_BOTANISK,
                    'tromsø museum botanisk avd.'       : TMU_BOTANISK,
                    'kvaløyvegen 30'                    : TMU_BOTANISK,
                    'kvaløyvn. 156'                     : TMU_KVV_156,
                    'kvaløyvegen 156'                   : TMU_KVV_156,
                    'universitetsbiblioteket'           : UB,
                    'ub'                                : UB,
                    'universitetssykehuset nord norge'  : UNN,
                    'unn'                               : UNN,
                    'vitensenteret'                     : VITENSENTERET,
                    'øvre lysthus'                      : OLYSTH,
                    'Øvre lysthus'                      : OLYSTH,
                    'ølysth'                            : OLYSTH,
                    'Ølysth'                            : OLYSTH,
                    'åsgård'                            : AASGAARD,
                    'Åsgård'                            : AASGAARD
                    } 
                    # Note: words that begin with norwegian letters must be present with both
                    # upper- and lowercase first letter

# Eiscat? -> HOVEDBYGNING -> is "Hovedbygning" enough to place a person?

    def room_to_dist_list(self, room_info):
        """
        TODO: describe this method
        """
        dist_list = None

        # # test
        # print 'room_info:', room_info

        lower = room_info.lower().strip()
        fixed = lower.decode('iso-8859-1').encode('utf-8')

        split = fixed.split(' ')
        if split[0] in self.loc2distlist.keys():
            dist_list = self.loc2distlist[split[0]]

        if dist_list == None and '_' in fixed:
            split = fixed.split('_')
            if split[0] in self.loc2distlist.keys():
                dist_list = self.loc2distlist[split[0]]

        return dist_list

    def building_to_dist_list(self, building_info):
        """
        TODO: describe this method
        """
        dist_list = None

        # # test
        # print 'building_info:', building_info

        lower = building_info.lower().strip()
        fixed = lower.decode('iso-8859-1').encode('utf-8')

        if fixed in self.loc2distlist.keys():
            dist_list = self.loc2distlist[fixed]

        if dist_list == None and '/' in lower:
            # don't use 'fixed' for this!
            split = lower.split('/')
            for s in split:
                res = self.building_to_dist_list(s)
                if res != None:
                    if dist_list == None:
                        dist_list = res
                    elif res not in dist_list:
                        dist_list += ',' + res

        if dist_list == None and ' ' in fixed:
            split = fixed.split(' ')
            if split[0] in self.loc2distlist.keys():
                dist_list = self.loc2distlist[split[0]]

        if dist_list == None and '.' in fixed:
            split = fixed.split('.')
            if split[0] in self.loc2distlist.keys():
                dist_list = self.loc2distlist[split[0]]

        return dist_list

    def add_to_dist_lists(self, dist_lists, to_add):
        split = to_add.split(',')
        for s in split:
            if s not in dist_lists:
                if len(dist_lists) == 0:
                    dist_lists = s
                else:
                    dist_lists += ',' + s
        return dist_lists

# if someone has more than one entry in entity_contact_info with same contact_type (550 or 558):
#   use contact_pref to decide which to use, or add to both dist groups? 
#   => will add to both for now...

    def create_dist_lists(self, person_id):
        """
        TODO: describe this method
        """
        dist_lists = ""

        self.pe.clear()
        self.pe.find(person_id)
        rooms = self.pe.get_contact_info(type=550)
        buildings = self.pe.get_contact_info(type=558)

        for r in rooms:
            room_dist_list = self.room_to_dist_list(r['contact_value'])
            if room_dist_list == None:
                self.logger.info("CIMDataSourceUit: Unrecognized room info, %s, for person_id %s" 
                                  % (r['contact_value'], person_id))
            else:
                # # test
                # print "room_dist_list:", room_dist_list

                dist_lists = self.add_to_dist_lists(dist_lists, room_dist_list)

        for b in buildings:
            building_dist_list = self.building_to_dist_list(b['contact_value'])
            if building_dist_list == None:
                self.logger.info("CIMDataSourceUit: Unrecognized building info, %s, for person_id %s" 
                                  % (b['contact_value'], person_id))
            else:
                # # test
                # print "building_dist_list:", building_dist_list

                dist_lists = self.add_to_dist_lists(dist_lists, building_dist_list)

        if dist_lists == "":
            # Information about ROOM@UIT and BYGG@UIT could not be used to place person in dist_lists
            dist_lists = self.IKKE_PLASSERT

        return dist_lists

# forts her...
    # Run test with all persons that have cim_person spread...
    #   ->  check results...

    # need to do more to handle upper/lowercase comparison of words that contain norwegian letters

    def get_person_data(self, person_id):
        """
        Builds a dict according to the CIM-WS schema, using info stored in
        Cerebrum's database about the given person.

        :param int person_id: The person's entity_id in Cerebrum
        :return: A dict with person data, with entries adhering to the
                 CIM-WS-schema.
        :rtype: dict
        """
        # TODO: move 'CIM_SYSTEM_LOOKUP_ORDER' to cereconf
        CIM_SYSTEM_LOOKUP_ORDER = ['system_paga', 'system_fs', 'system_x']

        orig_auth_system = self.authoritative_system
        person = None

        # get data about person using CIM_SYSTEM_LOOKUP_ORDER to determine source_system to use
        for sys in CIM_SYSTEM_LOOKUP_ORDER:
            source_system = getattr(self.co, sys)
            self.authoritative_system = source_system

            try:
                person = super(CIMDataSourceUit, self).get_person_data(person_id)
            except IndexError:
                person = None

            if person != None:
                # TODO later: ?? do I need to check result? e.g. ou stuff for students and sysX persons...
                break

            # Doing things like this might be a problem when we add students:
            # What if a person is a student, but has a (small) part-time job at UiT?
            # person would get cim_spread because of the student-status, but
            # PAGA would be used as source_system...
            # 
            # example of special case to consider:
            # krs025 (Kristin Solberg): student, but also has ansatt and tilknyttet affiliations (from FS and SysX)
            #                           ansatt and tilknyttet at IKM, student at HSL

        # set authoritative_system back to what it was at beginning of method
        self.authoritative_system = orig_auth_system

        if person != None:
            person['dist_list'] = self.create_dist_lists(person_id)

        return person


