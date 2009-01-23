#!/usr/bin/env python
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
__doc__="""This utility creates an exchange email for a user.

usage:: %s [options] 

options are
    -a | --account  : account name to modify
    -e | --email    : exhange email address to set
    -n | --noprimary: do not set this to primary
    -h | --help     : show this
    -d | --dryrun   : do not change DB
    --logger-name name   : log name to use 
    --logger-level level : log level to use
""" % ( progname, )


import getopt
import sys
import os
import re

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no.uit import Email


db = Factory.get('Database')()
ac = Factory.get('Account')(db)
co = Factory.get('Constants')(db)
db.cl_init(change_program=progname)

logger=Factory.get_logger('cronjob')

em=Email.email_address(db,logger=logger)

valid_exchange_domains = [cereconf.NO_MAILBOX_DOMAIN_EMPLOYEES, ]

def set_mail(account, localpart, domain, is_primary=True):

   # Validate localpart
   validate = re.compile('^(([\w-]+\.)+[\w-]+|([a-zA-Z]{1}|[\w-]{2,}))$')
   if not validate.match(localpart) or localpart[len(localpart)-1:] == '-':
       logger.error('Invalid localpart: %s' , localpart)
       sys.exit(0)

   # Set / validate domain
   # NOTE: Cannot use find_by_domain because we have lots of invalid domains in our domain table!
   if domain not in valid_exchange_domains:
       logger.error('Can only set emails for domains: ' , valid_exchange_domains)
       sys.exit(0)

   # Find account
   ac.clear()
   try:
      ac.find_by_name(account)
   except:
      logger.error('Account %s not found' % (account))
      sys.exit(0)

   # Re-build email address
   email = '%s@%s' % (localpart, domain)

   # Set email address in ad email table
   if is_primary:
       ac.set_ad_email(localpart, domain)

   # Update email tables immediately
   logger.info('Running email processing for %s' % account)
   em.process_mail(ac.entity_id, email, is_primary)



def main():
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'a:e:ndh',
                                  ['account=','email=','noprimary','dryrun','help'])
    except getopt.GetoptError,m:
        usage(1,m)
        
    dryrun = False
    account = None
    email = None
    primary = True
    for opt,val in opts:
        if opt in('-d','--dryrun'):
            dryrun = True
        elif opt in ('-e', '--email='):
            email = val
        elif opt in ('-n', '--noprimary'):
            primary = False
        elif opt in ('-a', '--account='):
            account = val
        elif opt in ('-h','--help'):
            usage()

    if account is None or email is None:
        usage()

    splitmail = email.split('@')
    if len(splitmail) != 2:
        logger.error('You must specify one localpart and one domain. E.g. example@test.com')
        usage()

    set_mail(account, splitmail[0], splitmail[1], primary)
    
    if (dryrun):
        db.rollback()
        logger.info("Dryrun, rollback changes")
    else:
        db.commit()
        logger.info("Committing all changes to DB")


def usage(exitcode=0,msg=None):
    if msg: print msg        
    print __doc__
    sys.exit(exitcode)


if __name__=='__main__':
    main()
    
