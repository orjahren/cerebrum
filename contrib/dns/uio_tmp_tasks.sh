#!/bin/bash 

# Collection of scripts for common tasks while tsting at UiO.  Will be
# removed/converted once we near a stable implementation.

migrate_uio() {
    # nukes existing dns data, end re-imports them
    ./makedb.py --drop design/mod_dns.sql 
    ./contrib/dns/test_utils.py --del
    ./makedb.py design/mod_dns.sql 

    echo "Du m� ha kj�rt fetch_src_files, renamet filene til *.orig"
    echo "og lagt inn linja"
    echo "; AUTOGENERATED: do not edit below this line"
    echo "p� rett plass i begge filene for at dette skal virke"
    # uio.no : "F�r MX records for Organizational units" linja
    # 129.240 : etter NS linjene

    ./contrib/dns/strip4cmp.py -i data/129.240.orig -o data/129.240.orig.cmp -r
    ./contrib/dns/strip4cmp.py -i data/uio.no.orig -o data/uio.no.orig.cmp -z

    time ./contrib/dns/import_dns.py -z data/uio.no.orig -r data/129.240.orig -h data/hosts.orig -i
    time ./contrib/dns/import_dns.py --netgroups data/netgroup.host.orig -n
    time ./contrib/generate_nismaps.py --group_spread NIS_mng@uio --user_spread NIS_user@uio -n data/netgroup.host.new
    time ./contrib/dns/build_zone.py -r data/129.240.new
    time ./contrib/dns/build_zone.py -b data/uio.no.new
    ./contrib/dns/strip4cmp.py -i data/129.240.new -o data/129.240.new.cmp -r
    ./contrib/dns/strip4cmp.py -i data/uio.no.new -o data/uio.no.new.cmp -z

    echo diff -u data/129.240.orig.cmp data/129.240.new.cmp
    echo diff -u data/uio.no.orig.cmp data/uio.no.new.cmp 
}

fetch_src_files() {
    scp nissen:/site/bind9/pz/uio.no nissen:/site/bind9/pz/129.240 .
    scp cerebellum:/cerebrum/yp/src/hosts cerebellum:/cerebrum/yp/src/netgroup.host .
    tar czf uio-zone-`date '+%Y-%m-%d'`.tgz uio.no 129.240 netgroup.host hosts
    rm -f uio.no 129.240 netgroup.host hosts
}

case "$1" in
    --migrate)
	migrate_uio
	;;
    --fetch)
	fetch_src_files
	;;
    *)
	echo "Usage: old_and_large.sh --migrate | --fetch"
	;;
esac

# arch-tag: dfc54693-f7c1-4c6a-b97c-a0f3450b3696
