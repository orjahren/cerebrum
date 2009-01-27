#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

progname = __file__.split("/")[-1]
__doc__="""This script overrides display name for a list of users from the portal.

usage:: %s [options]

options is
    --help                : show this
    -d | --dryrun         : do not change DB
    --logger-name name    : log name to use
    --logger-level level  : log level to use
""" % ( progname, )


from sgmllib import SGMLParser
import getopt
import sys
import os

import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory


db=Factory.get('Database')()
db.cl_init(change_program=progname)
const=Factory.get('Constants')(db)
account=Factory.get('Account')(db)
person=Factory.get('Person')(db)

logger=Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)


# Parse content from Portal HTML
class ExtractContent(SGMLParser):
    def reset(self):                              
        SGMLParser.reset(self)
        self.uitusers = []
        self.next_are_users = False

    def start_div(self, attrs):
        self.next_are_users = False
        uitusers = [v for k, v in attrs if k=='id' and v == 'uitusers']
        if uitusers:
            self.next_are_users = True

    def handle_data(self, text):
        if self.next_are_users:
            self.uitusers.append(text)

    def output(self):
        return "".join(self.uitusers)

# Get users from Portal HTML
def get_changes(filename, url):

    changes = {}

    # Load file
    logger.info("Copying changelog HTML page from Portal to local file")
    os.system("wget -q -O " + filename + " " + url)

    # Read file
    logger.info("Opening changelog file")
    f = open(filename, "r")
    content = f.read()
    f.close()

    # Parse file
    logger.info("Parsing changelog file")
    parser = ExtractContent()
    parser.feed(content)
    
    # Go through all lines in changelog
    logger.info("Verifying lines in changelog file")
    for line in  parser.output().split('\n'):
       username = None
       firstname = None
       lastname = None

       # Parse each line
       aux = line.split(';')
       if len(aux) >= 3:
           username = aux[0].strip()
           firstname = aux[1].strip()
           lastname = aux[2].strip()

       # Check for repeated usernames
       if username in changes:
           logger.warn("Repeated username in changelog. Only last entry is considered! Username: %s." % username)

       if username and firstname and lastname:
           changes[username] = (unicode(firstname, 'UTF-8').encode('iso-8859-1'), unicode(lastname, 'UTF-8').encode('iso-8859-1'))
       else:
           logger.info("Skipped line because of missing data. Username: %s. Firstname: %s. Lastname %s." % (username, firstname, lastname))

    return changes


# Change names in Portal HTML (if changed)
def change_names(changes):

    logger.info("Creating dict person_id -> cached names")
    registered_changes = 0
    cached_names = person.getdict_persons_names(source_system=const.system_cached, name_types=(const.name_first,const.name_last))
    
    logger.info("Creating dict username -> owner_id")
    cached_acc2owner = {}
    acc_list = account.search(expire_start=None)
    for acc in acc_list:
        cached_acc2owner[acc['name']] = acc['owner_id']

    logger.info("Processing list of potential namechanges")
    for accountname in changes.keys():
        (firstname, lastname) = changes[accountname]
        fullname = ' '.join((firstname, lastname))

        # Find the account owner in dict
        owner = cached_acc2owner.get(accountname, None)
        if owner:

            # Look up cached names for given owner
            cached_name = cached_names.get(owner, None)
            if cached_name:

                # Override name if names differ
                if firstname != cached_name.get(int(const.name_first)) or lastname != cached_name.get(int(const.name_last)):

                    account.clear()
                    person.clear()

                    try:
                        account.find_by_name(accountname)
                    except Errors.NotFoundError:
                        logger.error("Account %s not found, cannot set new display name" % (accountname))
                        continue

                    try:
                        person.find(account.owner_id)
                    except Errors.NotFoundError:
                        logger.error("Account %s owner %d not found, cannot set new display name" % (account,account.owner_id))
                        continue

                    source_system = const.system_override
                    person.affect_names(source_system,
                                        const.name_first,
                                        const.name_last,
                                        const.name_full)
                    person.populate_name(const.name_first, firstname)
                    person.populate_name(const.name_last, lastname)
                    person.populate_name(const.name_full, fullname)

                    try:
                        person.write_db()
                    except db.DatabaseError, m:
                        logger.error("Database error, override names not updated for %s: %s" % (accountname, m))
                        continue

                    person._update_cached_names()
                    try:
                        person.write_db()
                    except db.DatabaseError, m:
                        logger.error("Database error, cached name not updated for %s: %s" % (accountname, m))
                        continue

                    logger.info("Name changed for user %s: %s %s" % (accountname, firstname, lastname))
                    registered_changes = registered_changes + 1

                # Do nothing if names are equal
                else:
                    continue
                    
            else:
                logger.error("Cached names for %s not found in dict, cannot set new display name" % (accountname))
                continue

        else:
            logger.warn("Account %s not found in dict, cannot set new display name" % (accountname))
            continue

    logger.info("Registered %s changes" % (registered_changes))


def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'d',
            ['dryrun','help'])
    except getopt.GetoptError,m:
        usage(1,m)

    dryrun = False
    tmpfile = '/tmp/last_portal_dump'
    url = 'http://www2.uit.no/portal/page/portal/UiT%20Administrator%20verktoy/navnalias'

    for opt,val in opts:
        if opt in('-d','--dryrun'):
            dryrun = True
        elif opt in ('-h','--help'):
            usage()

    changes = get_changes(tmpfile, url)
    # Test data
    # changes = {'rmi000':('Romulus','Mikalsen'), 'bto001':('Bjarne','Betjent')}
    change_names(changes)

    if (dryrun):
      db.rollback()
      logger.info("Dryrun, rollback changes")
    else:
      db.commit()
      logger.info("Committed changes to DB")



def usage(exitcode=0,msg=None):
    if msg: print msg
    print __doc__
    sys.exit(exitcode)


if __name__=='__main__':
    main()

