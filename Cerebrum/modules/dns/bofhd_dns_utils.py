# -*- coding: iso-8859-1 -*-

import cereconf

from Cerebrum.Utils import Factory
from Cerebrum.modules.dns.HostInfo import HostInfo
#from Cerebrum.modules.dns. import 
#from Cerebrum.modules.dns import EntityNote
from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import IntegrityHelper
from Cerebrum.modules.dns import Utils
from Cerebrum.modules import dns
from Cerebrum import Errors
from Cerebrum import Database
from Cerebrum.modules.bofhd.errors import CerebrumError

class DnsBofhdUtils(object):
    # A number of utility methods used by
    # bofhd_dns_cmds.BofhdExtension.

    # TODO: We should try to put most of the business-logic in this
    # class and not BofhdExtension.  That would make it easier for
    # non-jbofh clients to communicate with dns.  This is a long-term
    # goal, however, and it has not been determined how to approach
    # the problem.
    

    def __init__(self, server, default_zone):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        # TBD: This pre-allocating may interfere with multi-threaded bofhd
        self._arecord = ARecord.ARecord(self.db)
        self._host = HostInfo.HostInfo(self.db)
        self._dns_owner = DnsOwner.DnsOwner(self.db)
        self._ip_number = IPNumber.IPNumber(self.db)
        self._cname = CNameRecord.CNameRecord(self.db)
        self._validator = IntegrityHelper.Validator(server.db, default_zone)
        self._update_helper = IntegrityHelper.Updater(server.db)
        self._mx_set = DnsOwner.MXSet(self.db)
        self.default_zone = default_zone
        self._find = Utils.Find(server.db, default_zone)

    def ip_rename(self, name_type, old_id, new_id):
        """Performs an ip-rename by directly updating dns_owner or
        ip_number.  new_id cannot already exist."""

        if name_type == dns.IP_NUMBER:
            old_ref = self._find.find_target_by_parsing(old_id, dns.IP_NUMBER)
            self._ip_number.clear()
            try:
                self._ip_number.find_by_ip(new_id)
                raise CerebrumError("New IP in use")
            except Errors.NotFoundError:
                pass
            self._ip_number.clear()
            self._ip_number.find(old_ref)
            self._ip_number.a_ip = new_id
            self._ip_number.write_db()
        else:
            old_ref = self._find.find_target_by_parsing(old_id, dns.DNS_OWNER)
            new_id = self._validator.qualify_hostname(new_id)
            # Check if the name is in use, or is illegal
            self._validator.dns_reg_owner_ok(new_id, dns.CNAME_OWNER)
            self._dns_owner.clear()
            self._dns_owner.find(old_ref)
            self._dns_owner.name = new_id
            self._dns_owner.write_db()

    def ip_free(self, name_type, id, force):
        if name_type == dns.IP_NUMBER:
            ip_id = self._find.find_target_by_parsing(id, dns.IP_NUMBER)
            self._ip_number.clear()
            self._ip_number.find(ip_id)
            try:
                self._ip_number.delete()
            except Database.DatabaseError, m:
                raise CerebrumError, "Database violation: %s" % m
        else:
            owner_id = self._find.find_target_by_parsing(
                id, dns.DNS_OWNER)

            refs = self._validator.get_referers(dns_owner_id=owner_id)
            if not force and (
                refs.count(dns.A_RECORD) > 1 or
                dns.GENERAL_DNS_RECORD in refs):
                raise CerebrumError(
                    "Multiple records would be deleted, must force")
            try:
                self._update_helper.full_remove_dns_owner(owner_id)
            except Database.DatabaseError, m:
                raise CerebrumError, "Database violation: %s" % m

            #raise NotImplementedError

    #
    # host, cname, entity-note
    #

    def alloc_host(self, name, hinfo, mx_set, comment, contact):
        name = self._validator.qualify_hostname(name)
        dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
            name, dns.HOST_INFO)

        self._dns_owner.clear()
        self._dns_owner.find(dns_owner_ref)
        self._dns_owner.mx_set_id = mx_set
        self._dns_owner.write_db()
        
        self._host.clear()
        self._host.populate(dns_owner_ref, hinfo)
        self._host.write_db()
        if comment:
            self._host.add_entity_note(self.const.note_type_comment, comment)
        if contact:
            self._host.add_entity_note(self.const.note_type_contact, contact)

    def alloc_cname(self, cname_name, target_name, force):
        cname_name = self._validator.qualify_hostname(cname_name)
        dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
            cname_name, dns.CNAME_OWNER)
        dns_owner_ref = self.alloc_dns_owner(cname_name)
        try:
            target_ref = self._find.find_target_by_parsing(
                target_name, dns.DNS_OWNER)
        except CerebrumError:
            if not force:
                raise CerebrumError, "Target does not exist, must force"
            target_ref = self.alloc_dns_owner(target_name)
        
        self._cname.clear()
        self._cname.populate(dns_owner_ref, target_ref)
        self._cname.write_db()
        return self._cname.entity_id

    def alter_entity_note(self, owner_id, note_type, dta):
        obj_ref, obj_id = self._find.find_target_type(owner_id)
        if not dta:
            obj_ref.delete_entity_note(note_type)
            return "removed"

        try:
            obj_ref.get_entity_note(note_type)
        except Errors.NotFoundError:
            obj_ref.add_entity_note(note_type, dta)
            return "added"
        obj_ref.update_entity_note(note_type, dta)
        return "updated"

    #
    # IP-numbers
    #

    def alloc_ip(self, a_ip, force=False):
        """Allocates an IP-number.  force must be true to use IPs in a
        reserved range"""

        self._ip_number.clear()
        if not force:
            # TODO: Check if IP is in reserved range
            pass
        self._ip_number.populate(a_ip)
        self._ip_number.write_db()
        return self._ip_number.ip_number_id

    #
    # dns-owners, general_dns_records and mx-sets, srv_records
    #
    
    def alloc_dns_owner(self, name, mx_set=None):
        self._dns_owner.clear()
        if not name.endswith(self.default_zone.postfix):
            zone = self.const.other_zone
        else:
            zone = self.default_zone
        self._dns_owner.populate(zone, name, mx_set_id=mx_set)
        self._dns_owner.write_db()
        return self._dns_owner.entity_id

    def alter_general_dns_record(self, owner_id, ttl_type, dta, ttl=None):
        self._dns_owner.clear()
        self._dns_owner.find(owner_id)
        if not dta:
            self._dns_owner.delete_general_dns_record(self._dns_owner.entity_id, ttl_type)
            return "removed"
        try:
            self._dns_owner.get_general_dns_record(self._dns_owner.entity_id, ttl_type)
        except Errors.NotFoundError:
            self._dns_owner.add_general_dns_record(
                self._dns_owner.entity_id, ttl_type, ttl, dta)
            return "added"
        self._dns_owner.update_general_dns_record(
            self._dns_owner.entity_id, ttl_type, ttl, dta)
        return "updated"

    def alter_srv_record(self, operation, service_name, pri,
                         weight, port, target, ttl=None):
        service_name = self._validator.qualify_hostname(service_name)
        # TBD: should we assert that target is of a given type?
        self._dns_owner.clear()
        try:
            self._dns_owner.find_by_name(service_name)
            #TBD: raise error if operation==add depending on type of existing data?
            if operation == 'del':
                self._dns_owner.delete_srv_record(
                    self._dns_owner.entity_id, pri, weight, port,
                    target)
        except Errors.NotFoundError:
            if operation == 'add':
                self.alloc_dns_owner(self, service_name)

        if operation == 'add':
            self._dns_owner.add_srv_record(
                self._dns_owner.entity_id, pri, weight, port, ttl,
                target)

    def mx_set_add(self, mx_set, priority, target_id, ttl=None):
        if ttl:
            ttl = int(ttl)
        else:
            ttl = None
        priority = int(priority)
        self._mx_set.clear()
        try:
            self._mx_set.find_by_name(mx_set)
        except Errors.NotFoundError:
            self._mx_set.populate(mx_set)
            self._mx_set.write_db()
        self._mx_set.add_mx_set_member(ttl, priority, target_id)

    def mx_set_del(self, mx_set, target_id):
        self._mx_set.clear()
        try:
            self._mx_set.find_by_name(mx_set)
        except Errors.NotFoundError:
            raise CerebrumError, "Cannot find mx-set %s" % mx_set
        self._mx_set.del_mx_set_member(target_id)

        # If set is empty, remove it
        if not self._mx_set.list_mx_sets(mx_set_id=self._mx_set.mx_set_id):
            self._mx_set.delete()


    def set_ttl(self, owner_id, ttl):
        """Set TTL entries for this dns_owner"""

        # TODO: Currently we do this by updating the TTL in all
        # tables.  It has been decided to move ttl-information into
        # dns_owner.  However, we will not do this until after we have
        # gone into production to avoid a huge diff when comparing
        # autogenerated zone files to the original ones.
        
        dns_owner = DnsOwner.DnsOwner(self.db)
        dns_owner.find(owner_id)

        arecord = ARecord.ARecord(self.db)
        for row in arecord.list_ext(dns_owner_id=owner_id):
            arecord.clear()
            arecord.find(row['a_record_id'])
            arecord.ttl=ttl
            arecord.write_db()

        host = HostInfo.HostInfo(self.db)
        try:
            host.find_by_dns_owner_id(owner_id)
        except Errors.NotFoundError:
            pass
        else:
            host.ttl = ttl
            host.write_db()

        for row in dns_owner.list_dns_records(dns_owner_id=owner_id):
            dns_owner.update_dns_record(owner_id, row['field_type'],
                                        ttl, row['data'])

        mx_set = DnsOwner.MXSet(self.db)
        for row in mx_set.list_mx_sets(target_id=owner_id):
            mx_set.clear()
            mx_set.find(row['mx_set_id'])
            mx_set.update_mx_set_member(ttl, row['pri'], row['target_id'])
        cname = CNameRecord.CNameRecord(self.db)
        for row in cname.list_ext(cname_owner=owner_id):
            cname.clear()
            cname.find(row['cname_id'])
            cname.ttl = ttl
            cname.write_db()

        for row in dns_owner.list_srv_records(owner_id=owner_id):
            dns_owner.update_srv_record(owner_id, row['pri'], row['weight'],
                                        row['port'], ttl,
                                        row['target_owner_id'])


    #
    # A-Records, reverse-map
    #

    def _alloc_arecord(self, owner_id, ip_id):
        self._arecord.clear()
        self._arecord.populate(owner_id, ip_id)
        self._arecord.write_db()
        return self._arecord.entity_id

    def alloc_arecord(self, host_name, subnet, ip, force):
        host_name = self._validator.qualify_hostname(host_name)
        # Check for existing record with same name
        dns_owner_ref, same_type = self._validator.dns_reg_owner_ok(
            host_name, dns.A_RECORD)
        if dns_owner_ref and same_type and not force:
            raise CerebrumError, "name already in use, must force"

        # Check or get free IP
        if not ip:
            ip = self._find.find_free_ip(subnet)[0]
            ip_ref = None
        else:
            ip_ref = self._find.find_ip(ip)
            if ip_ref and not force:
                raise CerebrumError, "IP already in use, must force"

        # Register dns_owner and/or ip_number
        if not ip_ref:
            ip_ref = self.alloc_ip(ip, force=force)
        if not dns_owner_ref:
            dns_owner_ref = self.alloc_dns_owner(host_name)
        self._alloc_arecord(dns_owner_ref, ip_ref)
        return ip

    def remove_arecord(self, a_record_id):
        self._update_helper.remove_arecord(a_record_id)

    def register_revmap_override(self, ip_host_id, dest_host, force):
        # TODO: clear up empty dest_host
        self._ip_number.clear()
        self._ip_number.find(ip_host_id)
        if not dest_host:
            self._update_helper.update_reverse_override(ip_host_id)
            return "deleted"
        self._dns_owner.clear()
        try:
            self._dns_owner.find_by_name(dest_host)
        except Errors.NotFoundError:
            if not force:
                raise CerebrumError, "Target does not exist, must force"
            self._dns_owner.populate(dest_host)
            self._dns_owner.write_db()
        if self._ip_number.list_override(
            ip_number_id=self._ip_number.ip_number_id):
            self._update_helper.update_reverse_override(
                self._ip_number.ip_number_id, self._dns_owner.entity_id)
            return "updated"
        else:
            self._ip_number.add_reverse_override(
                self._ip_number.ip_number_id, self._dns_owner.entity_id)
            return "added"
