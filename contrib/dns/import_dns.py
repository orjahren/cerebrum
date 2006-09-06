#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import re
import sys
import getopt
import cereconf

from Cerebrum import Errors
from Cerebrum import Account
from Cerebrum import Group
from Cerebrum.Utils import Factory

from Cerebrum.modules.dns import ARecord
from Cerebrum.modules.dns import CNameRecord
from Cerebrum.modules.dns import DnsOwner
from Cerebrum.modules.dns import HostInfo
from Cerebrum.modules.dns import IPNumber
from Cerebrum.modules.dns import Utils

db = Factory.get('Database')()
db.cl_init(change_program='import_dns')
co = Factory.get('Constants')(db)
sys.argv.extend(["--logger-level", "DEBUG"])
logger = Factory.get_logger("cronjob")
ipnumber = IPNumber.IPNumber(db)
arecord = ARecord.ARecord(db)
cname = CNameRecord.CNameRecord(db)
dnsowner = DnsOwner.DnsOwner(db)
host = HostInfo.HostInfo(db)
mx_set = DnsOwner.MXSet(db)

# logger.setLevel(logger.debug)
header_splitter = r'^; AUTOGENERATED: do not edit below this line'

class Netgroups(object):
    class MergeRestart(Exception): pass

    def __init__(self, fname, default_zone):
        self._fname = fname
        self._default_zone = default_zone
        self._import_netgroups()
        
    def _parse_netgroups(self):
        import pprint
        pp = pprint.PrettyPrinter(indent=4)

        f = file(self._fname)
        r_linecomment = re.compile(r'^\s*#')
        r_blank = re.compile(r'^\s*$')
        r_machine_member = re.compile(r'\(([^\)]+),-,[^\)]*\)')
        netgroups = {}
        for line in f.readlines():
            if r_blank.search(line) or r_linecomment.search(line):
                continue
            parts = line.split()
            main_ng = netgroups[parts[0]] = {'machines': [], 'netgroups': []}
            for p in parts[1:]:
                m = r_machine_member.match(p)
                if m:
                    main_ng['machines'].append(m.group(1))
                else:
                    main_ng['netgroups'].append(p)

        # Try to merge netgroups that had appended digits due to too long
        # lines
        r_digit = re.compile(r'^(.*\D+)(\d+)$')
        non_existent_bases = {}
        merged_netgroups = {}
        while True:
            try:
                order = netgroups.keys()
                order.sort()    # Makes reading the debug-log easier
                for k in order:
                    m = r_digit.match(k)
                    if m:
                        if netgroups.has_key(m.group(1)):
                            print "Merging ", (m.group(1), m.group(2))
                            netgroups[m.group(1)]['machines'].extend(
                                netgroups[k]['machines'])
                            netgroups[m.group(1)]['netgroups'].extend(
                                netgroups[k]['netgroups'])
                            del(netgroups[k])
                            merged_netgroups[k] = True
                            raise Netgroups.MergeRestart()
                        else:
                            # print "base non-existent: ",  (m.group(1), m.group(2))
                            non_existent_bases[m.group(1)] = True
                    else:
                        # print k
                        pass
                break
            except Netgroups.MergeRestart:
                # OK, it could probably be done a better way, but it is
                # late, and I'm tired...
                pass
        for k in netgroups.keys():
            for m in merged_netgroups.keys():
                if m in netgroups[k]['netgroups']:
                    netgroups[k]['netgroups'].remove(m)
        print "Non-existent bases found:", non_existent_bases.keys()
        #pp.pprint(netgroups)
        return netgroups

    def _ng_machine_filter(self, name):
        if len(name.split(".")) > 2:
            return name + "."
        return name + self._default_zone.postfix

    def _import_netgroups(self):
        netgroups = self._parse_netgroups()
        account = Account.Account(db)
        account.find_by_name(cereconf.INITIAL_ACCOUNTNAME)
        creator_id = account.entity_id
        group = Group.Group(db)
        # First define all netgroups
        groupname2id = {}
        for k in netgroups.keys():
            sys.stdout.write('g')
            sys.stdout.flush()
            names = [k]
            names.extend(netgroups[k]['netgroups'])
            for n in names:
                if groupname2id.has_key(n):
                    continue
                group.clear()
                group.populate(creator_id=creator_id,
                               visibility=co.group_visibility_all,
                               name=n, description='machine netgroup %s' % n)
                group.write_db()
                group.add_spread(co.spread_uio_machine_netgroup)
                groupname2id[n] = group.entity_id

        # Then populate members
        dns_owner2id = {}
        for row in dnsowner.list():
            dns_owner2id[row['name']] = int(row['dns_owner_id'])
        for k in groupname2id.keys():
            sys.stdout.write('.')
            sys.stdout.flush()
            # Add group members
            group.clear()
            group.find(groupname2id[k])
            if not netgroups.has_key(k):
                print "Warning, no members for %s" % k
                continue
            for n in netgroups[k]['netgroups']:
                group.add_member(groupname2id[n],
                                 co.entity_group,
                                 co.group_memberop_union)
            # Add machine memebers
            machines = {}
            for n in netgroups[k]['machines']:
                n = self._ng_machine_filter(n)
                machines[n] = True
            for n in machines.keys():
                if not dns_owner2id.has_key(n):
                    print "Warning, unknown member: %s" % n
                    continue
                group.add_member(dns_owner2id[n],
                                 co.entity_dns_owner,
                                 co.group_memberop_union)
        db.commit()

class ForwardMap(object):
    def __init__(self, fname, default_zone, header_end):
        self._a_ip_name_unique = {}
        self._mx_targets = {}
        self._lookup = Lookup(default_zone)
        self._prepare_parse_zone_file(fname, header_end)

    def _prepare_parse_zone_file(self, fname, header_end):
        logger.info("parse_zone_file(%s)" % fname)
        self.f = file(fname)
        while 1:
            line = self.f.readline()
            if not line: break
            if re.search(header_end, line): break

        self.r_linecomment = re.compile('^\s*;')
        self.r_contact = re.compile(';\s*(\S+):\s*contact\s*(\S+)')
        self.r_blank = re.compile(r'^\s*$')
        self.r_comment = re.compile('(.*);(.*)')

    def next_zone_entry(self):
        while 1:
            line = self.f.readline()
            if not line: break
            line = line.rstrip()
            if self.r_blank.search(line):
                continue
            # Line start with ; check for contact-comment
            if self.r_linecomment.search(line):
                m = self.r_contact.match(line)
                if m is not None:
                    logger.debug2("Contact: %s=%s" % (m.group(1), m.group(2)))
                    name = self._lookup.filter_name(m.group(1))
                    return 'contact', name, m.group(2)
                continue
            comment = None
            if self.r_comment.search(line):
                m = self.r_comment.match(line)
                line = m.group(1)
                comment = m.group(2).strip()
            # split line on whitespace
            lparts = line.split()
            ttl = None
            if not line[0].isspace():  # continuation of previous owner
                self.owner = self._lookup.filter_name(lparts[0])
                lparts = lparts[1:]
            if lparts[0].isdigit():   # Check for TTL value
                ttl = lparts[0]
                lparts = lparts[1:]
            if lparts[0] == 'IN':    # Ignore, IN is default in a zone file
                lparts = lparts[1:]
            rectype = lparts[0]       # Get record type
            lparts = lparts[1:]
            logger.debug2("%s: r=%s, ttl=%s" % (line, rectype, ttl))
            if rectype == 'TXT':   # Find quoted part of line
                lparts = [ line[line.find('"')+1:-1], ]
            elif rectype in ('MX', 'CNAME', 'SRV'):
                lparts[-1] = self._lookup.filter_name(lparts[-1])
            return rectype, ttl, lparts, comment

    def process_zone_file(self):
        records = {}
        while True:
            dta = self.next_zone_entry()
            if not dta:
                break
            rectype = dta[0]
            if rectype == 'contact':
                name, dest = dta[1:3]
                records.setdefault(name, {})['contact'] = dest
            elif rectype in ('HINFO', 'MX', 'TXT', 'A', 'CNAME', 'SRV'):
                ttl, lparts, comment = dta[1:4]
                if not records.has_key(self.owner):
                    records[self.owner] = {}
                if comment:
                    if rectype in ('A', 'CNAME'):
                        records[self.owner]['comment'] = comment
                    else:
                        logger.warn("Unexpected comment in %s" % str(dta))
                lparts.insert(0, ttl)
                records[self.owner].setdefault(rectype, []).append(lparts)
            else:
                logger.warn("eh?: %s" % str(dta))
            # logger.debug("'%s' (%s) -> %s" % (line, owner, records[owner]))
            # if len(records) > 500: return records
        self.recs = records

    def _pass_one(self, name, dta):
        if dta.has_key('A'):
            first_id = None
            for a in dta['A']:
                logger.debug("Adding A: %s" % name)
                arecord.clear()
                if not self._a_ip_name_unique.has_key((name, a[1])):
                    self._a_ip_name_unique[(name, a[1])] = 1
                    ip_ref = self._lookup.get_ip(a[1], try_lookup=True)
                    owner_type, owner_id = self._lookup.get_dns_owner(
                        name, _type='a_record', try_lookup=True)
                    arecord.populate(owner_id, ip_ref, ttl=dta['A'][0][0])
                    arecord.write_db()
                else:
                    # "tassenmac01  A       129.240.79.31" fantes 2 ganger i sonefila
                    logger.warn("Duplicate A-record violation: %s->%s" % (name, a[1]))
            if dta.has_key('HINFO'):
                if len(dta['HINFO']) != 1:
                    # we have many of these... don't want to see the warning
                    #logger.warn("Many HINFO? %s -> %s" % (name, str(dta['HINFO'])))
                    pass
                hinfo = self._lookup.get_hinfo(*dta['HINFO'][0][1:3])
                logger.debug2("HINFO %s -> %s" % (dta['HINFO'], hinfo))
                del dta['HINFO']
                owner_type, owner_id = self._lookup.get_dns_owner(
                    name, _type='a_record', make=False)

                host.clear()
                host.populate(owner_id, hinfo, ttl=dta['A'][0][0])
                host.write_db()
            # All existing TXT records are connected to host
            if dta.has_key('TXT'):
                if len(dta['TXT']) > 1:
                    logger.warn("Multiple TXT records for %s" % name)
                ttl, txt_val = dta['TXT'][0]
                owner_type, owner_id = self._lookup.get_dns_owner(name, make=False)
                dnsowner.add_general_dns_record(
                    owner_id, co.field_type_txt, ttl, txt_val)
                if owner_id != host.dns_owner_id:
                    logger.warn("TXT for %s which is not a host (hinfo: %s)" % (
                        name, host.name))
                del dta['TXT']
            del dta['A']

    def _pass_two(self, name, dta):
        # We delay insertion of mx-records because we want the A-record to
        # exist first

        def _sort_mx(mx_records):
            d = {}
            for m in mx_records:
                d[(m[1], m[2])] = m
            ret = d.values()
            ret.sort()
            return ret

        if dta.has_key('MX'):
            mx_records = _sort_mx(dta['MX'])
            if(len(dta['MX']) != len(mx_records)):
                logger.warn("Multiple equal MX records for %s" % name)

            key = "-".join([ str(x) for x in mx_records ])
            if not self._mx_targets.has_key(key):
                mx_name = "%s%i" % (mx_target_prefix, len(self._mx_targets) + 1)
                logger.debug("Creating %s (%s)" % (mx_name, key))
                mx_set.clear()
                mx_set.populate(mx_name)
                mx_set.write_db()
                self._mx_targets[key] = int(mx_set.mx_set_id)
                prev_mx_member = ()
                for ttl, pri, target_name in mx_records:
                    if prev_mx_member == (pri, target_name):
                        logger.warn("Multiple equal MX records for %s" % name)
                        continue
                    prev_mx_member = (pri, target_name)
                    owner_type, owner_id = self._lookup.get_dns_owner(
                        target_name, try_lookup=True)
                    if not isinstance(owner_type, (
                        ARecord.ARecord, CNameRecord.CNameRecord,
                        DnsOwner.DnsOwner)):
                        logger.warn("Unsupported MX target %s" % owner_type)
                        self._mx_targets[key] = None
                        continue
                    mx_set.add_mx_set_member(ttl, pri, owner_id)

            owner_type, owner_id = self._lookup.get_dns_owner(name)
            dnsowner.clear()
            dnsowner.find(owner_id)
            dnsowner.mx_set_id = self._mx_targets[key]
            #logger.debug("TGT: %s for %s, %i" % (self._mx_targets[key], name, owner_ids[1]))
            dnsowner.write_db()
            del dta['MX']

        if dta.has_key('CNAME'):
            if len(dta['CNAME']) > 1:
                logger.warn("Too many CNAME in %s" % str(dta))
            cname_ttl, cname_target = dta['CNAME'][0]
            target_owner_type, target_owner_id = self._lookup.get_dns_owner(
                cname_target, _type='a_record', try_lookup=True)
            cname_owner_type, cname_owner_id = self._lookup.get_dns_owner(
                name, _type='cname_record', try_lookup=True)
            cname.clear()
            cname.populate(cname_owner_id, target_owner_id, cname_ttl)
            cname.write_db()
            logger.debug("Make CNAME for '%s', owner=%i, ety_id=%i" % (
                name, cname_owner_id, cname.entity_id))
            del dta['CNAME']
        if dta.has_key('SRV'):
            owner_type, owner_id = self._lookup.get_dns_owner(name)
            for ttl, pri, weight, port, target_name in dta['SRV']:
                target_owner_type, target_owner_id = self._lookup.get_dns_owner(
                    target_name)
                dnsowner.add_srv_record(owner_id, pri, weight, port,
                                        ttl, target_owner_id)
            del dta['SRV']
        if dta.has_key('contact') or dta.has_key('comment'):
            owner_type, owner_id = self._lookup.get_dns_owner(name)
            if dnsowner.entity_id != owner_id:
                dnsowner.clear()
                dnsowner.find(owner_id)
            if dta.has_key('contact'):
                logger.debug2("ADD contact: %s " % owner_id)
                dnsowner.populate_trait(co.trait_dns_contact,
                                        strval=dta['contact'])
                del dta['contact']
            if dta.has_key('comment'):
                logger.debug2("ADD comment: %s " % owner_id)
                dnsowner.populate_trait(co.trait_dns_comment,
                                        strval=dta['comment'])
                del dta['comment']
            dnsowner.write_db()

    def _change_existing_zone_associations(self):
        """When merging zones, we want to move existing entries from
        the 'other' zone to the new zone """
        
        dz = self._lookup._default_zone 
        for row in dnsowner.list():
            if (row['name'].endswith(dz.postfix) and
                row['zone_id'] != dz.zone_id):
                dnsowner.clear()
                dnsowner.find(row['dns_owner_id'])
                dnsowner.zone = dz
                dnsowner.write_db()

    def records_to_db(self):
        logger.info("records_to_db()")
        for k in self.recs.keys():
            if self.recs[k].has_key('contact') and len(self.recs[k].keys()) == 1:
                logger.warn("Contact for nothing: %s" % k)
                del(self.recs[k])
        self._change_existing_zone_associations()
        order = self.recs.keys()  # Not really needed, but looks nice
        order.sort()
        for pass_num in (1,2):
            # name has been through filter_name()
            for name in order:
                # logger.debug("%s -> %s" % (k, str(r[k])))
                logger.debug("Process %s" % name)
                if pass_num == 1:
                    self._pass_one(name, self.recs[name])
                elif pass_num == 2:
                    logger.debug2("%s -> %s" % (name, str(self.recs[name])))
                    self._pass_two(name, self.recs[name])
                    for y in self.recs[name]:
                        logger.warn("Unexpected rest (for %s): %s" % (
                            name, str(self.recs[name])))
        db.commit()
    #    db.rollback()

class RevMap(object):
    def __init__(self, fname, default_zone):
        self._prepare_parse_revmap(fname)
        self._lookup = Lookup(default_zone)

    def _prepare_parse_revmap(self, fname):
        logger.info("parse_revmap(%s)" % fname)
        self.f = file(fname)
        self.r_linecomment = re.compile('^\s*;')
        self.r_blank = re.compile(r'^\s*$')
        self.r_origin = re.compile(
            r'^\$ORIGIN\s+(\d+\.\d+\.\d+)\.IN-ADDR.arpa.', re.IGNORECASE)
        
    def next_revmap(self):
        in_head=True
        while 1:
            line = self.f.readline()
            if not line: break
            line = line.rstrip()
            if self.r_blank.search(line):
                continue
            if self.r_linecomment.search(line):
                continue
            m = self.r_origin.match(line)
            if m is not None:
                t = m.group(1).split(".")
                t.reverse()
                self.origin = ".".join(t)
                logger.debug2("Origin: %s" % self.origin)
                continue
            lparts = line.split()
            if in_head:
                if lparts[1] == 'PTR':
                    in_head=False
                else:
                    continue
            if len(lparts) != 3:
                logger.warn("huh: %s" % line)
                continue
            if lparts[1] != 'PTR':
                logger.warn("huh: %s" % line)
                continue
            if lparts[2][-1] != '.':
                logger.warn("Bad postfix: %s" % lparts[2])
                continue
            if not lparts[0].isdigit():
                logger.warn("Wierd ptr: %s" % repr(lparts))
                continue
            return "%s.%s" % (self.origin, lparts[0]), lparts[2]
        return None, None
        
    def records_to_revdb(self):
        logger.info("records_to_revdb()")
        fail_warned = {}
        rev = {}
        # Parse revmap, and determine range og IPs
        min_ip = max_ip = None
        while True:
            ip, name = self.next_revmap()
            if not ip:
                break
            rev.setdefault(ip, []).append(name)
            if min_ip is None or Utils.IPCalc.ip_to_long(ip) < min_ip:
                min_ip = Utils.IPCalc.ip_to_long(ip)
            if max_ip is None or Utils.IPCalc.ip_to_long(ip) > max_ip:
                max_ip = Utils.IPCalc.ip_to_long(ip)
        if min_ip is None:
            logger.error("No IP-numbers in file?")
            return
        logger.debug("Min-ip=%s, max-ip=%s" % (
            Utils.IPCalc.long_to_ip(min_ip), Utils.IPCalc.long_to_ip(max_ip)))
        default_revmap = {}
        for row in arecord.list_ext(start=min_ip, stop=max_ip):
            default_revmap.setdefault(row['a_ip'], []).append(
                {'name': row['name'], 'id': row['dns_owner_id']})

        # Handle entries that should not have a reverse-map at all
        for ip in default_revmap.keys():
            if not rev.has_key(ip):
                logger.warn("%s should not have a rev-map" % ip)
                ip_ref = self._lookup.get_ip(ip, try_lookup=True)
                ipnumber.add_reverse_override(ip_ref, None)

        # Remove all entries with normal rev-maps
        for ip in rev.keys():
            if len(rev[ip]) > 1:
                logger.warn("rev file has multiple reverse for %s" % ip)
                # Check if all A -> IP has rev: IP -> A
                rev[ip].sort()
                tmp = [df['name'] for df in default_revmap[ip]]
                tmp.sort()
                if rev[ip] == tmp:
                    del rev[ip]
                continue
            if not default_revmap.has_key(ip):
                logger.warn("rev-map for missing A-record %s (%s)" % (
                    ip, rev[ip]))
                continue
            # Compare to default reversemap
            if len(default_revmap[ip]) > 1:
                logger.debug("multiple A-records for %s" % ip)
                continue
            name = rev[ip][0]
            if default_revmap[ip][0]['name'] != name:
                logger.info("rev-map for %s -> %s while A -> %s" % (
                    ip, default_revmap[ip][0]['name'], name))
                continue
            # Has forward-map=reverse-map, no overide needed
            del rev[ip]

        # De som er igjen i rev setter revmap eskplisitt
        set_rev_map = {}
        for ip in rev.keys():
            ip_ref = self._lookup.get_ip(ip, try_lookup=True)
            for name in rev[ip]:
                owner_type, owner_id = self._lookup.get_dns_owner(
                    name, try_lookup=True)
                ipnumber.add_reverse_override(ip_ref, owner_id)
        db.commit()        

class Hosts(object):
    """Extracts comments from hosts file"""
    def __init__(self, fname, default_zone):
        self._fname = fname
        self._lookup = Lookup(default_zone)

    def update_records(self, recs):
        for name, comment in self.parse_hosts_file().items():
            if not recs.has_key(name):
                logger.warn("comment for unknown host %s" % name)
            else:
                if recs[name].has_key('comment'):
                    recs[name]['comment'] += ' - '+comment
                    logger.warn("comment for %s in zone and hosts file" % name)
                else:
                    recs[name]['comment'] = comment
        
    def parse_hosts_file(self):
        # We are only interested in any comments for the hosts
        # Example: 129.240.2.3     nissen  nissen.uio.no #  ds5000/240
        logger.info("parse_hosts_file(%s)" % self._fname)
        f = file(self._fname)
        ret = {}
        while 1:
            line = f.readline()
            if not line: break
            ip_nr, hostname, rest = line.split("\t",2)
            if rest.find('#') == -1:
                continue
            rest = rest[rest.find('#')+1:]
            rest = rest.strip()
            hostname = self._lookup.filter_name(hostname)
            ret[hostname] = rest
        return ret

class Lookup(object):
    def __init__(self, default_zone):
        self._ip_cache = {}
        self._filter_warned = {}
        self._dns_owners = {}
        self._all_zones = co.fetch_constants(co.DnsZone)
        self._default_zone = default_zone

    def get_hinfo(self, cpu, os):
        return "\t".join((cpu, os))

    def get_ip(self, a_ip, try_lookup=False):
        logger.debug2("_get_ip(%s)" % a_ip)
        if not self._ip_cache.has_key(a_ip):
            ipnumber.clear()
            if try_lookup:
                try:
                    ipnumber.find_by_ip(a_ip)
                except Errors.NotFoundError:
                    ipnumber.populate(a_ip)
                    ipnumber.write_db()
            else:
                ipnumber.populate(a_ip)
                ipnumber.write_db()
            self._ip_cache[a_ip] = int(ipnumber.entity_id)
        return self._ip_cache[a_ip]

    def get_dns_owner(self, name, _type=None, try_lookup=False, make=True):
        assert name[-1] == '.'
        mt = {'dns_owner': dnsowner, 'a_record': arecord, 'cname_record': cname}
        if not self._dns_owners.has_key(name):
            for z in self._all_zones:
                if z.postfix is not None and name.endswith(z.postfix):
                    zone = z
                    break
            else:
                zone = co.other_zone
            dnsowner.clear()
            if try_lookup:  # Only used in revmap, so type is irrelevant
                try:
                    dnsowner.find_by_name(name)
                except Errors.NotFoundError:
                    if not make:
                        raise
                    dnsowner.populate(zone, name)
                    dnsowner.write_db()
            elif not make:
                raise Errors.NotFoundError
            else:
                dnsowner.populate(zone, name)
                dnsowner.write_db()
            self._dns_owners[name] = (_type or 'dns_owner', int(dnsowner.entity_id))
        found_type, found_id = self._dns_owners[name]
        logger.debug2("get_dns_owner(%s, %s) -> %i" % (name, _type, found_id))
        if _type is None or _type == found_type:
            return mt[found_type], found_id
        raise ValueError, "Found type: %s, expected %s" % (_type, found_type)

    def filter_name(self, name):
        if not name.endswith(self._default_zone.postfix):
            if name[-1] == '.':
                if not self._filter_warned.has_key(name):
                    logger.warn("bad target postfix: %s" % name)
                    self._filter_warned[name] = True
                return name
            return name+self._default_zone.postfix
        return name

def clear_db():
    logger.info("clear_db()")
    for tab in ('general_dns_record', 'reserved_host',
                'override_reversemap', 'other_mx', 'cname_record', 'dns_host_info',
                'a_record'):
        db.execute("delete from %s" % tab)
    db.execute("delete from entity_name where value_domain=:vd", {
        'vd': int(co.hostname_namespace)})
    db.commit()
    
def usage(exitcode=0):
    print """Usage: [options]

    Import an existing zone-file and corresponding reverse-map into
    Cerebrum.

    --help: help
    -h | --hosts filename: filename for hosts file
    -c | --clear: clear database
    -z | --zone filename: filename for zone file
    -Z | --zone-def name: a dns_zone.name entry
    -r | --reverse filename: filename for reverse map (should be ran
           after import of all forward maps are completed)
    -i | --import: start import of the above mentioned files
    --netgroups filename: filename with netgroups
    -n : start netgroup import
    -H header_end : regexp that identifies end of header part of forward map

    Note that the part before the header_splitter will not be imported
    from the zone file or the reverse map.  That is because this part
    of the file contains special records like subdomains that we do
    not support.  Any CNAMES etc. should be moved below that line.

    Example:
      contrib/import_dns.py -z data/uio.no.orig -h data/hosts.orig -i
    """
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'ch:z:r:inZ:H:M:', [
            'help', 'clear', 'zone=', 'reverse=', 'import',
            'hosts=', 'netgroups=', 'zone-def='])
    except getopt.GetoptError:
        usage(1)
    if not opts:
        usage(1)

    global parser, zone, mx_target_prefix
    zone = hosts_file = header_end = None
    mx_target_prefix = "mx_target_"
    logger.debug("opts: %s" % str(opts))
    for opt, val in opts:
        if opt in ('--help', ):
            usage()
        elif opt in ('--clear', '-c'):
            clear_db()
        elif opt in ('--zone', '-z'):
            zone_file = val
        elif opt in ('--zone-def', '-Z'):
            zone = co.DnsZone(val)
            int(zone) # Triggers error if missing
        elif opt in ('--reverse', '-r'):
            rev = RevMap(val, zone)
            rev.records_to_revdb()
        elif opt in ('--hosts', '-h'):
            hosts_file = val
        elif opt in ('--netgroups',):
            netgroup_file = val
        elif opt in ('-H',):
            header_end = val
        elif opt in ('-M',):
            mx_target_prefix = val
        elif opt in ('--import', '-i'):
            if zone is None:
                raise ValueError("-Z is required")
            if header_end is None:
                raise ValueError("-H is required")
            forward = ForwardMap(zone_file, zone, header_end)
            forward.process_zone_file()
            if hosts_file:
                h = Hosts(hosts_file, zone)
                h.update_records(forward.recs)
            forward.records_to_db()
        elif opt in ('-n',):
            if zone is None:
                raise ValueError("-Z is required")
            Netgroups(netgroup_file, zone)

if __name__ == '__main__':
    main()

# arch-tag: 42732516-2596-4d60-b3d3-adc4443c9cad
