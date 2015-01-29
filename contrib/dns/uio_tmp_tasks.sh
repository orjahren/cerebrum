#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Collection of scripts for common tasks while tsting at UiO.  Will be
# removed/converted once we near a stable implementation.
import os
import sys
import time

revmaps = [
    '129.240', '158.36.184', '158.36.185', '158.36.186', '158.36.187',
    '158.36.189', '158.36.190', '158.36.191']
revmaps.extend(['193.157/193.157.%s' % n for n in range(108, 255+1)])

def run(cmd):
    start = time.time()
    exitcode = os.system(cmd)
    print "DONE: %s, exit=%i, duration= %g seconds" % (
        cmd, exitcode, time.time() - start)
    if exitcode != 0:
        print "Command had exit != 0, aborting"
        sys.exit(1)

def new_db():
    # /local/opt/postgresql/bin/dropdb -U cerebrum cerebrum_dns
    # /local/opt/postgresql/bin/createdb -U cerebrum -E unicode cerebrum_dns

    # Trenger egentlig ikke alle disse tabellene, men �nsker � slipe �
    # kl� p� CLASS_CONSTANTS

    cmd = ["./makedb.py"]
    for mod in ('bofhd_tables', 'bofhd_auth', 'mod_posix_user',
                'mod_changelog', 'mod_stedkode', 'mod_email', 'mod_entity_trait',
                'mod_lt', 'mod_printer_quota', 'mod_dns', 'mod_job_runner'):
        cmd.append("--extra-file=design/%s.sql" % mod)
    run(" ".join(cmd))

def build_maps(tgt_dir):
    bz = './contrib/dns/build_zone.py'
    cfg_dir = '/cerebrum/etc/cerebrum/dns'
    
    run("%s --head %s/uio.no.static_head --head %s/uio.no.head -Z uio -b %s/uio.no" % (bz, cfg_dir, cfg_dir, tgt_dir))
    # Revmaps
    run("%s --head %s/129.240.head -m 129.240.0.0/16 -r %s/129.240" % (bz, cfg_dir, tgt_dir))
    cmd = [bz, '--head', '%s/revmap-default.head' % cfg_dir]
    for rev in revmaps:
        if rev != '129.240':
            cmd.extend(['-m', '%s.0/24' % os.path.basename(rev), '-r', '%s/%s' % (tgt_dir, rev)])
    run(" ".join(cmd))
    # Netgroups
    run("./contrib/dns/generate_nismaps.py --group_spread NIS_mng@uio --user_spread NIS_user@uio -n %s/netgroup.host || true" % tgt_dir)
    # hosts file
    run("%s -Z uio --hosts %s/hosts" % (bz, tgt_dir))
    
def migrate_uio():
    # nukes existing dns data, end re-imports them
    run("./makedb.py --drop design/mod_dns.sql || true")
    run("./contrib/dns/test_utils.py --del")
    run("./makedb.py design/mod_dns.sql")

    print "Du m� ha kj�rt fetch_src_files og lagt filene i data/src"
    run("./contrib/dns/import_dns.py -H 'Alt over dette er _head' -Z uio -z data/src/uio.no -h data/src/hosts -i")
    cmd = ["./contrib/dns/import_dns.py"]
    for rev in revmaps:
        cmd.extend(['-r', 'data/src/%s' % rev])
    run("%s" % " ".join(cmd))
    run("./contrib/dns/import_dns.py -Z uio --netgroups data/src/netgroup.host -n")

def do_diff(src_dir, tgt_dir):
    cmd = ["./contrib/dns/strip4cmp.py -Z uio"]
    lines = []
    for rev in revmaps:
        if rev.startswith("193"):
            tgt_rev = rev[rev.rindex('/')+1:]
        else:
            tgt_rev = rev
        for t in (src_dir, tgt_dir):
            if(t == tgt_dir):
                orig = '%s/%s' % (t, tgt_rev)
	    else:
                orig = '%s/%s' % (t, rev)
            if not os.path.exists('%s.cmp' % orig):
                cmd.append("-i %s -o %s.cmp -r" % (orig, orig))
        lines.append("diff -u %s/%s.cmp %s/%s.cmp\n" % (src_dir, rev, tgt_dir, tgt_rev))
    if len(cmd) > 1:
        run(" ".join(cmd))
        print "".join(lines)

    cmd = ["./contrib/dns/strip4cmp.py -Z uio"]
    for t in (src_dir, tgt_dir):
        if not os.path.exists('%s/uio.no.cmp' % t):
            if(t == tgt_dir):
                cmd.append("-i %s/uio.no -o %s/uio.no.cmp  -H '; AUTOGENERATED: do not edit below this line' -z" % (t, t))
            else:
                cmd.append("-i %s/uio.no -o %s/uio.no.cmp -z" % (t, t))

    if len(cmd) > 1:
        run(" ".join(cmd))
        print "diff -u %s/uio.no.cmp %s/uio.no.cmp" % (src_dir, tgt_dir)

def fetch_src_files():
    print ("mkdir tmpdns\n"
           "cd tmpdns\n"
           "scp nissen:/site/bind9/pz/{uio.no,129.240} .\n"
           "scp nissen:/site/bind9/pz/158.36.{184,185,186,187,189,190,191} .\n"
           "mkdir 193.157\n"
           "scp nissen:/site/bind9/pz/193.157/193.157.* 193.157/\n"
           "scp cerebellum:/cerebrum/yp/src/hosts cerebellum:/cerebrum/yp/src/netgroup.host .\n"
           "tar czf uio-zone-`date '+%Y-%m-%d'`.tgz *\n")

# tgt_dir = '/cerebrum/dumps/dns'
tgt_dir = 'data/new'  # do: "cd data/new/; for a in /cerebrum/dumps/dns/*; do ln -s $a; done"
src_dir ='data/src' 
if len(sys.argv) != 2:
    print "Usage: old_and_large.sh --migrate | --fetch | --new-db | --build | --diff"
    sys.exit(1)
if sys.argv[1] == '--migrate':
    migrate_uio()
elif sys.argv[1] == '--new-db':
    new_db()
elif sys.argv[1] == '--fetch':
    fetch_src_files()
elif sys.argv[1] == '--build':
    build_maps(tgt_dir)
elif sys.argv[1] == '--diff':
    do_diff(src_dir, tgt_dir)

