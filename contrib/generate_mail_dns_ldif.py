#!/usr/bin/env python2.2

import os, re
import cerebrum_path
import cereconf
from Cerebrum import Entity
from Cerebrum.modules import Email
from Cerebrum.Utils import Factory,SimilarSizeWriter

Cerebrum = Factory.get('Database')()
co = Factory.get('Constants')(Cerebrum)

dn_suffix = 'ou=mail-dns,dc=uio,dc=no'

# Only consider hosts with these lowercased hosts as lowest priority MX record
# and which are also A records
uio_mx_dict = {
    'pat.uio.no':	1,
    'mons.uio.no':	1,
    'goggins.uio.no':	1,
    'miss.uio.no':	1,
    'smtp.uio.no':	1
    }

dig_cmd  = '/local/bin/dig %s. @%s. axfr'
dig_args = (('uio.no',     'nissen.uio.no'),
            ('ifi.uio.no', 'bestemor.ifi.uio.no'))

# Expect /local/bin/dig output like this:
#   ; <<>> DiG 9.2.1 <<>> uio.no. @nissen.uio.no. axfr
#   bb.uio.no.              86400   IN      CNAME   beeblebrox.uio.no.
#   beeblebrox.uio.no.      86400   IN      MX      10 smtp.uio.no.
#   beeblebrox.uio.no.      86400   IN      A       129.240.10.17
dig_line_re = re.compile(r'(\S+)\.\s+\d+\s+IN\s+(A|MX|CNAME)\s+(.*[^.\n])\.?$')
dig_version_re = re.compile(r';[ <>]+DiG 9\.', re.IGNORECASE)
filename = "%s/%s" % (cereconf.LDAP_DUMP_DIR,'mail-dns.ldif')

def get_hosts_and_cnames():
    """Return host->cnames, cname->host and lowercase->host dictionaries"""
    got_host    = {}
    host2cnames = {}
    cname2host  = {}
    host2mx     = {}
    host2host   = {}
    for args in dig_args:
        dig_version_found = 0
        f = os.popen(dig_cmd % args, 'r')
        while 1:
            line = f.readline()
            if line == '':
                break
            match = dig_line_re.match(line)
            if match:
                name, type, info = match.groups()
                lname = name.lower()
                info = info.lower()
                host2host[lname] = name
                if type == 'A':
                    got_host[lname] = 1
                elif type == 'CNAME':
                    if not host2cnames.has_key(info):
                        host2cnames[info] = {}
                    host2cnames[info][lname] = 1
                    cname2host[lname] = info
                elif type == 'MX':
                    prio, mx = info.split()
                    if not host2mx.has_key(lname):
                        host2mx[lname] = {}
                    host2mx[lname][prio] = mx
            elif dig_version_re.match(line):
                dig_version_found = 1
        if f.close() is not None:
            raise Exception("Dig failed: %s tree not updated" % dn_suffix)
        if not dig_version_found:
            raise Exception("Dig version changed.  Check output format.")
    hosts = {}
    for host, mx_dict in host2mx.items():
        if got_host.has_key(host):
            prio = 99.0e9
            mx = "-"
            for p, m in mx_dict.items():
                p = int(p)
                if p < prio:
                    prio = p
                    mx = m
            if uio_mx_dict.has_key(mx):
                if host2cnames.has_key(host):
                    hosts[host] = host2cnames[host].keys()
                    hosts[host].sort()
                else:
                    hosts[host] = ()
    for cname in cname2host.keys():
        if not host2cnames.has_key(cname2host[cname]):
            del cname2host[cname]
    return hosts, cname2host, host2host

def write_mail_dns():
    hosts, cnames, host2host = get_hosts_and_cnames()
    f = SimilarSizeWriter(filename,'w')
    f.set_size_change_limit(10)

    def handle_domain_host(host):
        f.write("host: %s\n" % host2host[host])
        for cname in hosts[host]:
            f.write("cn: %s\n" % host2host[cname])
            del cnames[cname]
        del hosts[host]

    f.write("""
dn: %s
objectClass: top
objectClass: norOrganizationalUnit
ou: %s
description: Maskiner og domener ved UiO, brukes til mail

""" % (dn_suffix, dn_suffix.split(',')[0].split('=')[1]))
    email = Email.EmailDomain(Cerebrum)
    email_domain = {}
    for dom_entry in email.list_email_domains():
	email_domain[int(dom_entry['domain_id'])] = dom_entry['domain']
    for no_exp_dom in email.list_email_domains_with_category(co.email_domain_category_noexport):
	del email_domain[int(no_exp_dom['domain_id'])]
    domains = email_domain.values()
    domains.sort()
    for domain in domains:
        f.write("""dn: cn=%s,%s 
objectClass: uioHost
cn: %s
""" % (domain, dn_suffix, domain))
        domain = domain.lower()
        if cnames.has_key(domain):
            handle_domain_host(cnames[domain])
        elif hosts.has_key(domain):
            handle_domain_host(domain)
        f.write('\n')

    sorted_hosts = hosts.keys()
    sorted_hosts.sort()
    for host in sorted_hosts:
        f.write("""dn: host=%s,%s
objectClass: uioHost
host: %s
cn: %s
""" % (host2host[host], dn_suffix, host2host[host], host2host[host]))
        for cname in hosts[host]:
            f.write("cn: %s\n" % host2host[cname])
        f.write('\n')
    f.close()

write_mail_dns()
