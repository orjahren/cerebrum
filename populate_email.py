#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2002, 2003 University of Oslo, Norway
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


progname = __file__.split("/")[-1]
__doc__="""
This script creates emailaddressen of CN type for accounts in Cerebrum that has
exchange spread.

usage:: %s [options]

options is
    -h | --help          : show this
    -d | --dryrun        : do not change DB
    --try-all            : try all email alternatives, default is only try first
    --logger-name name   : log name to use
    --logger-level level : log level to use
""" % ( progname, )


import getopt
import sys
import os


import cerebrum_path
import cereconf
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory, simple_memoize
from Cerebrum.modules import PosixUser
from Cerebrum.modules.Email import EmailDomain, EmailAddress, EmailTarget
from Cerebrum.modules.no.uit import Email
from Cerebrum.Constants import _CerebrumCode, _SpreadCode
from sets import Set

db = Factory.get('Database')()
ac = Factory.get('Account')(db)
p = Factory.get('Person')(db)
ou = Factory.get('OU')(db)
co = Factory.get('Constants')(db)
db.cl_init(change_program=progname)

logger=Factory.get_logger('console')


def _get_alternatives(account_name):
    ac.clear()
    ac.find_by_name(account_name)
    alternatives=list()
    first_choise=ac.get_email_cn_local_part(given_names=1, max_initials=1, keep_dash=True)
    alternatives.append(first_choise)
    # find other alternatives
    given_names=(3,2,1,0,-1)
    max_initials=(1,2,0,3,4)
    for nm in given_names:
        for mlm in max_initials:
            for dash in (True,False):
                local_part = ac.get_email_cn_local_part(given_names=nm, max_initials=mlm, keep_dash=dash)
                if "." not in local_part:
                    continue
                if local_part not in alternatives:
                   alternatives.append(local_part)

    logger.debug("Alternatives for %s: %s" % (account_name,alternatives))
    return alternatives


def is_cnaddr_free(local_part,domain_part):

    domain = EmailDomain(db)
    domain.find_by_domain(domain_part)
    ea =EmailAddress(db)
    tmp_ac=Factory.get('Account')(db)
    try:
        ea.find_by_local_part_and_domain(local_part, domain.entity_id)
    except Errors.NotFoundError:
        #addr is free, good.
        pass
    else:
        logger.warn("email addr %s@%s not free!" % (local_part,domain_part))
        return False

    res = tmp_ac.search_ad_email(local_part=local_part,domain_part=domain_part)
    if res:
       logger.warn("email addr %s@%s not free!" % (local_part,domain_part))
       return False

    return True


def get_cn_addr(username):

    alternatives=_get_alternatives(username)
    if try_only_first:
       logger.info("Trying only first alternative!")
       alternatives = alternatives[:1]
    for em_addr in alternatives:
        if is_cnaddr_free(em_addr, cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES):
           return (em_addr,cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES)
    return None,cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES

def get_sko(ou_id):
    ou.clear()
    ou.find(ou_id)
    return "%02d%02d%02d" % (ou.fakultet,ou.institutt,ou.avdeling)
get_sko=simple_memoize(get_sko)



def save_ad_email(username,lp,dp):
    tmp_ac = Factory.get('Account')(db)
    tmp_ac.find_by_name(username)
    tmp_ac.set_ad_email(lp,dp)
    logger.debug("AD_MAIL_SET: account=%s,lp=%s,dp=%s" % (username,lp,dp))


def check_affs(pers_affs=None):
    # this needs to be discussed
    logger.debug("Person affs: %s" %(pers_affs,))
    
    #do not build uit.no addresses for affs in these sko's
    no_exchange_skos =cereconf.EMPLOYEE_FILTER_EXCHANGE_SKO
    tmp=Set()
    for aff,sko in pers_affs:
        for x in no_exchange_skos:
            if sko.startswith(x):
                logger.debug("Filter pers aff %s at %s" % (aff,sko))
                tmp.add(( aff,sko))
                break
    pers_affs = Set(pers_affs) - tmp
    logger.debug("After sko filter: P Affs: %s" %(pers_affs,))
    to_remove=list()
    for aff,ouid in pers_affs:
        if aff in ('STUDENT/drgrad','ANSATT/vitenskapelig', 'ANSATT/tekadm'):
            return True
        elif aff in ('MANUELL/gjest','STUDENT/aktiv','STUDENT/evu',
                     'STUDENT/tilbud'):
            to_remove.append((aff,ouid))
    pers_affs=Set(pers_affs)-Set(to_remove)
    logger.debug("After affs filter: P Affs: %s" % pers_affs)
    if len(pers_affs)>0:
        return True
    else:
        return False


def process_mail():
    tmp_ac=Factory.get('Account')(db)
    tmp_p =Factory.get('Person')(db)


    logger.info("Start get constants")
    num2const=dict()
    for c in dir(co):
        tmp = getattr(co, c)
        if isinstance(tmp, _CerebrumCode):
            num2const[int(tmp)] = tmp

    logger.info("Get all accounts with exchange@uit spread")
    exch_users=list()
    uname2accid=dict()
    accid2owner=dict()
    for row in ac.search(spread=co.spread_uit_exchange):
        exch_users.append(row['name'])
        uname2accid[row['name']]=row['account_id']
        accid2owner[row['account_id']]=row['owner_id']
    logger.info("got %d accounts" % len(exch_users))

    logger.info("Loading ad_email with uit.no addresses")
    tmp_ac=Factory.get('Account')(db)
    has_cn_addr=list()
    for row in tmp_ac.search_ad_email():
        has_cn_addr.append(row['account_name'])

    logger.info("Loading person affs")
    pers_affs=dict()
    for row in tmp_p.list_affiliations(fetchall = False):
        aff_stat = "%s" % (num2const[row['status']])
        pers_affs.setdefault(row['person_id'],list()).append((aff_stat,
                                                              get_sko(row['ou_id'])))

    from sets import Set
    build = Set(exch_users) - Set(has_cn_addr)
    logger.info("%d users candidates for cn mailaddrs, list=%s" % (len(build),build))
    for uname in build:
        logger.info("---------------------")
        logger.info("Uname %s not in ad_email" % (uname,))
        try:
            tmp_p_affs=pers_affs[accid2owner[uname2accid[uname]]]
        except KeyError:
            logger.error("%s has exchange, but is missing affs!" % uname)
            continue
        if check_affs(pers_affs=tmp_p_affs):
            (lp,dp)=get_cn_addr(uname)
            if lp:
                logger.info("Uname will get '%s@%s'" % (lp,dp))
                save_ad_email(uname,lp,dp)
            else:
                logger.error("No autogenerated emails for %s was free, "
                             "handle manually" % (uname,))
        else:
            logger.warn("User not entitled to emailaddr first.last@uit.no!")


def usage(c=0,m=None):
    if m: print m
    print __doc__
    sys.exit(c)

try:
   opts,args = getopt.getopt(sys.argv[1:],'u:dh',
                                  ['user=','dryrun', 'try-all','help'])
except getopt.GetoptError,m:
   usage(1,m)

try_only_first=True
username=None
dryrun=False

for opt,val in opts:
   if opt in('-u','--user'):
       username = val
   elif opt in('-d','--dryrun'):
       dryrun=True
   elif opt in('--try-all',):
       try_only_first=False
   elif opt in ('-h','--help'):
       usage(0,"")

process_mail()

if dryrun:
    print "dryrun"
    db.rollback()
else:
    print "commit"
    db.commit()

sys.exit()
