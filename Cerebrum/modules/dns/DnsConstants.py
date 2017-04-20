# coding: utf-8
#
# Copyright 2005-2017 University of Oslo, Norway
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
""" Constant types and common constants for the DNS module. """

from Cerebrum import Constants
from Cerebrum.modules.CLConstants import _ChangeTypeCode
from Cerebrum.modules.EntityTrait import _EntityTraitCode


class _FieldTypeCode(Constants._CerebrumCode):
    "Mappings stored in the field_type_code table"
    _lookup_table = '[:table schema=cerebrum name=dns_field_type_code]'


class _DnsZoneCode(Constants._CerebrumCode):
    _lookup_table = '[:table schema=cerebrum name=dns_zone]'

    _lookup_code_column = 'zone_id'
    _lookup_str_column = 'name'
    _lookup_desc_column = 'postfix'

    def _get_name(self):
        return self.str
    name = property(_get_name, None, None, "the name")

    def _get_zone_id(self):
        return int(self)
    zone_id = property(_get_zone_id, None, None, "the zone_id")

    def _get_postfix(self):
        if not hasattr(self, '_postfix'):
            self._postfix = self.description
        return self._postfix
    postfix = property(_get_postfix, None, None, "the postfix")


class Constants(Constants.Constants):
    """ Common DNS module constants. """

    #
    # DNS Entities
    #
    entity_dns_cname = Constants._EntityTypeCode(
        'cname',
        'cname - see table "cerebrum.cname_info" and friends.')
    entity_dns_host = Constants._EntityTypeCode(
        # name-clash with existing entity_type
        'dns_host',
        'dns_host - see table "cerebrum.dns_host_info" and friends.')
    entity_dns_a_record = Constants._EntityTypeCode(
        'a_record',
        'a_record - see table "cerebrum.a_record_info" and friends.')
    entity_dns_aaaa_record = Constants._EntityTypeCode(
        'aaaa_record',
        'aaaa_record - see table "cerebrum.aaaa_record_info" and friends.')
    entity_dns_owner = Constants._EntityTypeCode(
        'dns_owner',
        'dns_owner - see table "cerebrum.dns_owner" and friends.')
    entity_dns_ip_number = Constants._EntityTypeCode(
        'dns_ip_number',
        'dns_ip_number - see table "cerebrum.dns_ip_number" and friends.')
    entity_dns_ipv6_number = Constants._EntityTypeCode(
        'dns_ipv6_number',
        'dns_ipv6_number - see table "cerebrum.dns_ipv6_number" and friends.')
    entity_dns_subnet = Constants._EntityTypeCode(
        'dns_subnet',
        'dns_subnet - see table "cerebrum.dns_subnet" and friends.')
    entity_dns_ipv6_subnet = Constants._EntityTypeCode(
        'dns_ipv6_subnet',
        'dns_ipv6_subnet - see table "cerebrum.dns_ipv6_subnet" and friends.')

    #
    # Namespace for DNS names
    #
    dns_owner_namespace = Constants._ValueDomainCode(
        'dns_owner_ns',
        'Domain for dns_owners')

    #
    # NIS host group?
    #
    spread_uio_machine_netgroup = Constants._SpreadCode(
        'NIS_mng@uio',
        Constants.Constants.entity_group,
        'Machine netgroup in NIS domain "uio"')

    field_type_txt = _FieldTypeCode(
        'TXT',
        'TXT Record')

    #
    # Traits
    #
    trait_dns_contact = _EntityTraitCode(
        'dns_contact',
        entity_dns_owner,
        """Contact information (e-mail address) for the host.""")
    trait_dns_comment = _EntityTraitCode(
        'dns_comment',
        entity_dns_owner,
        """A freeform comment about the host.""")

    #
    # Default DNS zone
    #
    other_zone = _DnsZoneCode("other", None)

    #
    # ChangeLog constants
    #
    a_record_add = _ChangeTypeCode(
        'host',
        'a_rec_add',
        'add a-record %(subject)s -> %(dest)s')
    a_record_del = _ChangeTypeCode(
        'host',
        'a_rec_del',
        'del a-record %(subject)s -> %(dest)s')
    a_record_update = _ChangeTypeCode(
        'host',
        'a_rec_upd',
        'update a-record %(subject)s -> %(dest)s')
    aaaa_record_add = _ChangeTypeCode(
        'host',
        'aaaa_rec_add',
        'add aaaa-record %(subject)s -> %(dest)s')
    aaaa_record_del = _ChangeTypeCode(
        'host',
        'aaaa_rec_del',
        'del aaaa-record %(subject)s -> %(dest)s')
    aaaa_record_update = _ChangeTypeCode(
        'host',
        'aaaa_rec_upd',
        'update aaaa-record %(subject)s -> %(dest)s')
    cname_add = _ChangeTypeCode(
        'host',
        'cname_add',
        'add cname %(subject)s -> %(dest)s')
    cname_del = _ChangeTypeCode(
        'host',
        'cname_del',
        'del cname %(subject)s -> %(dest)s')
    cname_update = _ChangeTypeCode(
        'host',
        'cname_upd',
        'update cname %(subject)s -> %(dest)s')
    dns_owner_add = _ChangeTypeCode(
        'host',
        'dns_owner_add',
        'add dns-owner %(subject)s')
    dns_owner_update = _ChangeTypeCode(
        'host',
        'dns_owner_upd',
        'update dns-owner %(subject)s')
    dns_owner_del = _ChangeTypeCode(
        'host',
        'dns_owner_del',
        'del dns-owner %(subject)s')
    general_dns_record_add = _ChangeTypeCode(
        'host',
        'gen_dns_rec_add',
        'add record for %(subject)s',
        ('%(int:field_type)s=%(string:data)s',))
    general_dns_record_del = _ChangeTypeCode(
        'host',
        'gen_dns_rec_del',
        'del record for %(subject)s',
        ('type=%(int:field_type)s',))
    general_dns_record_update = _ChangeTypeCode(
        'host',
        'gen_dns_rec_upd',
        'update record for %(subject)s',
        ('%(int:field_type)s=%(string:data)s',))
    host_info_add = _ChangeTypeCode(
        'host',
        'host_info_add',
        'add %(subject)s',
        ('hinfo=%(string:hinfo)s',))
    host_info_update = _ChangeTypeCode(
        'host',
        'host_info_upd',
        'update %(subject)s',
        ('hinfo=%(string:hinfo)s',))
    host_info_del = _ChangeTypeCode(
        'host',
        'host_info_del',
        'del %(subject)s')
    ip_number_add = _ChangeTypeCode(
        'host',
        'ip_number_add',
        'add %(subject)s',
        ('a_ip=%(string:a_ip)s',))
    ip_number_update = _ChangeTypeCode(
        'host',
        'ip_number_upd',
        'update %(subject)s',
        ('a_ip=%(string:a_ip)s',))
    ip_number_del = _ChangeTypeCode(
        'host',
        'ip_number_del',
        'del %(subject)s')
    ipv6_number_add = _ChangeTypeCode(
        'host',
        'ipv6_number_add',
        'add %(subject)s',
        ('aaaaaaa_ip=%(string:aaaa_ip)s',))
    ipv6_number_update = _ChangeTypeCode(
        'host',
        'ipv6_number_upd',
        'update %(subject)s',
        ('aaaaaaa_ip=%(string:aaaa_ip)s',))
    ipv6_number_del = _ChangeTypeCode(
        'host',
        'ipv6_number_del',
        'del %(subject)s')
    mac_adr_set = _ChangeTypeCode(
        'host',
        'mac_adr_set',
        'set %(subject)s',
        ('mac_adr=%(string:mac_adr)s',))
    rev_override_add = _ChangeTypeCode(
        'host',
        'rev_ovr_add',
        'add rev-override %(subject)s -> %(dest)s')
    rev_override_del = _ChangeTypeCode(
        'host',
        'rev_ovr_del',
        'del rev-override for %(subject)s')
    rev_override_update = _ChangeTypeCode(
        'host',
        'rev_ovr_upd',
        'update rev-override %(subject)s -> %(dest)s')
    subnet_create = _ChangeTypeCode(
        'subnet',
        'subnet_create',
        'create subnet %(subject)s')
    subnet_mod = _ChangeTypeCode(
        'subnet',
        'subnet_mod',
        'modify subnet %(subject)s')
    subnet_delete = _ChangeTypeCode(
        'subnet',
        'subnet_delete',
        'delete subnet %(subject)s')
    subnet6_create = _ChangeTypeCode(
        'subnet',
        'subnet6_create',
        'create IPv6 subnet %(subject)s')
    subnet6_mod = _ChangeTypeCode(
        'subnet',
        'subnet6_mod',
        'modify IPv6 subnet %(subject)s')
    subnet6_delete = _ChangeTypeCode(
        'subnet',
        'subnet6_delete',
        'delete IPv6 subnet %(subject)s')
    srv_record_add = _ChangeTypeCode(
        'host',
        'srv_rec_add',
        'add srv-record %(subject)s -> %(dest)s')
    srv_record_del = _ChangeTypeCode(
        'host',
        'srv_rec_del',
        'del srv-record %(subject)s -> %(dest)s')

    FieldTypeCode = _FieldTypeCode
    DnsZone = _DnsZoneCode
