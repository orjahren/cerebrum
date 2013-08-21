#!/usr/bin/env python
# -*- encoding: latin-1 -*-
#
# Copyright 2010 University of Oslo, Norway
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

"""This module defines various constants for the voip module.
"""

import cerebrum_path
import cereconf

from Cerebrum import Constants
from Cerebrum.Constants import _EntityTypeCode as EntityTypeCode
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.Constants import _AuthoritativeSystemCode
from Cerebrum.modules.EntityTrait import _EntityTraitCode





class _VoipServiceTypeCode(_CerebrumCode):
    """Different types of non-personal phone locations (voip_service)."""

    _lookup_table = '[:table schema=cerebrum name=voip_service_type_code]'
# end _VoipServiceTypeCode


class _VoipClientTypeCode(_CerebrumCode):
    """Different types of clients -- soft- and hardphones."""
    
    _lookup_table = '[:table schema=cerebrum name=voip_client_type_code]'
# end _VoipClientTypeCode


class _VoipClientInfoCode(_CerebrumCode):
    """Client models in voip -- i.e. a specific phone model string (Foo 123).
    """

    _lookup_table = '[:table schema=cerebrum name=voip_client_info_code]'
# end _VoipClientInfoCode





class VoipConstants(Constants.Constants):
    VoipClientTypeCode = _VoipClientTypeCode
    VoipClientInfoCode = _VoipClientInfoCode
    VoipServiceTypeCode = _VoipServiceTypeCode

    ########################################################################
    # generic voip stuff
    system_voip = _AuthoritativeSystemCode('VOIP', 'Data from voip')

    ########################################################################
    # voip-service
    entity_voip_service = EntityTypeCode(
        "voip_service",
        "voipService - see module mod_voip.sql and friends"
        )

    voip_service_lab = VoipServiceTypeCode(
        "voip_service_lab",
        "lab",
        )

    voip_service_moterom = VoipServiceTypeCode(
        "voip_service_m�terom",
        "m�terom",
        )

    voip_service_resepsjon = VoipServiceTypeCode(
        "voip_service_resepsjon",
        "resepsjon",
        )

    voip_service_forening = VoipServiceTypeCode(
        "voip_service_forening",
        "forening",
        )

    voip_service_teknisk = VoipServiceTypeCode(
        "voip_service_teknisk",
        "teknisk",
        )

    voip_service_fellesnummer = VoipServiceTypeCode(
        "voip_service_fellesnummer",
        "fellesnummer",
        )

    voip_service_porttelefon = VoipServiceTypeCode(
        "voip_service_porttelefon",
        "porttelefon",
        )

    voip_service_fax = VoipServiceTypeCode(
        "voip_service_fax",
        "fax",
        )

    voip_service_ledig_arbeidsplass = VoipServiceTypeCode(
        "voip_service_ledig_arbeidsplass",
        "ledig arbeidsplass",
        )

    voip_service_heis = VoipServiceTypeCode(
        "voip_service_heis",
        "heis",
        )

    voip_service_svarapparat = VoipServiceTypeCode(
        "voip_service_svarapparat",
        "svarapparat",
    )

    voip_service_upersonlig_kontor = VoipServiceTypeCode(
        "voip_service_upersonlig_kontor",
        "upersonlig kontor",
    )

    voip_service_video = VoipServiceTypeCode(
        "voip_service_video",
        "videoenhet",
    )
    
    ########################################################################
    # voip-client
    entity_voip_client = EntityTypeCode(
        'voip_client',
        'voipClient - see module mod_voip.sql and friends'
        )

    voip_client_type_softphone = VoipClientTypeCode(
        'voip_softphone',
        'softphone voip client (e.g. a laptop with software)'
        )

    voip_client_type_hardphone = VoipClientTypeCode(
        'voip_hardphone',
        'hardphone voip client (e.g. a physical device)'
        )

    # This is client info for softphones (there is no specific hardware
    # apparatus model to register here)
    voip_client_info_softphone = VoipClientInfoCode(
        "softphone",
        "softphone client"
        )

    voip_client_ip330 = VoipClientInfoCode(
        "001001",
        "Polycom IP330"
        )

    voip_client_ip331 = VoipClientInfoCode(
        "001002",
        "Polycom IP331"
        )

    voip_client_ip550 = VoipClientInfoCode(
        "001003",
        "Polycom IP550"
        )

    voip_client_ip650 = VoipClientInfoCode(
        "001004",
        "Polycom IP650"
        )

    voip_client_ip670 = VoipClientInfoCode(
        "001005",
        "Polycom IP670"
        )

    voip_client_vvx310 = VoipClientInfoCode(
        "001006",
        "Polycom VVX310"
        )

    voip_client_spa504g = VoipClientInfoCode(
        "002001",
        "Cisco SPA-504G"
        )
    
    voip_client_spa508g = VoipClientInfoCode(
        "002002",
        "Cisco SPA-508G"
        )

    voip_client_spa509g = VoipClientInfoCode(
        "002003",
        "Cisco SPA-509G"
        )

    voip_client_spa525g = VoipClientInfoCode(
        "002004",
        "Cisco SPA-525G"
        )

    voip_client_spa514g = VoipClientInfoCode(
        "002005",
        "Cisco SPA-514G"
        )

    voip_client_spa112 = VoipClientInfoCode(
        "002006",
        "Cisco SPA-112"
        )

    voip_client_spa232d = VoipClientInfoCode(
        "002007",
        "Cisco SPA-232D"
        )

    voip_client_pap2t = VoipClientInfoCode(
        "002008",
        "Linksys PAP2T"
    )

    voip_client_sx20 = VoipClientInfoCode(
        "004001",
        "Cisco SX-20"
    )

    voip_client_c40 = VoipClientInfoCode(
        "004002",
        "Cisco C40"
    )

    voip_client_c60 = VoipClientInfoCode(
        "004003",
        "Cisco C60"
    )

    voip_client_c90 = VoipClientInfoCode(
        "004004",
        "Cisco C90"
    )

    ########################################################################
    # voip-address
    entity_voip_address = EntityTypeCode(
        'voip_address',
        'voipAddress - see module mod_voip.sql and friends'
        )

    contact_voip_extension = Constants.Constants.ContactInfo(
        'EXTENSION',
        'Extension number for voip (full and suffix)'
        )
# end VoipAddressConstants
