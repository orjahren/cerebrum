#! /usr/bin/env python
# -*- encoding: iso-8859-1 -*-
import os
import sys
import time
import getopt
import mx

import cerebrum_path
import cereconf

from Cerebrum.Utils import Factory
from Cerebrum import Errors

fileMode = 'w'
bufferSize = 16384
               
class Export2Kjernen(object):
    
    def __init__(self, outfile, verbose, doTiming):
        self.db = Factory.get('Database')()
        self.co = Factory.get('Constants')(self.db)
        self._person = Factory.get('Person')(self.db)
        self._ou = Factory.get('OU')(self.db)
        self._account = Factory.get('Account')(self.db)
        self._iso_format = '%Y.%m.%d'
        self.outfile = outfile
        self.verbose = verbose
        self.doTiming = doTiming

    def get_stedkoder(self):
        if self.verbose:
            print 'Fetching stedkoder...'
        koder = {}
        ## only ous with stedkode
        for row in self._ou.list_external_ids(id_type=self.co.externalid_stedkode, entity_type=self.co.entity_ou, source_system=self.co.system_kjernen):
            koder[row['entity_id']] = row['external_id'][2:]
        return koder

    def get_birthdates(self):
        """Fetch all birthdates as YYYY.mm.dd."""
        if self.verbose:
            print 'Fetching birthdates...'
        bdates = {}
        for row in self._person.list_persons():
            bdates[row['person_id']] = row['birth_date'].strftime(self._iso_format)
        return bdates

    def get_nins(self):
        """Link person til her/his norwegian national identity numbers."""
        if self.verbose:
            print 'Fetching nins...'
        nins = {}
        for row in self._person.list_external_ids(id_type=self.co.externalid_fodselsnr):
            nins[row["entity_id"]]=row["external_id"]
        return nins

    def get_emails(self):
        """Link person til her/his email-address."""
        if self.verbose:
            print 'Fetching emailaddreses...'
        emails = {}
        for row in self._person.list_contact_info(contact_type=self.co.contact_email):
            emails[row["entity_id"]]=row["contact_value"]
        return emails
     
    def get_lastnames(self):
        """Link person til her/his surname."""
        if self.verbose:
            print 'Fetching lastnames...'
        lastnames = {}
        for row in self._person.list_persons_name(name_type=self.co.name_last):
            lastnames[row['person_id']] = row['name']
        return lastnames

    def get_firstnames(self):
        """Link person til her/his givenname(s)."""
        if self.verbose:
            print 'Fetching firstnames...'
        firstnames = {}
        for row in self._person.list_persons_name(name_type=self.co.name_first):
            firstnames[row['person_id']] = row['name']
        return firstnames

    def get_entities(self):
        """Fetch all usernames."""
        if self.verbose:
            print 'Fetching entities...'
        entities = {}
        for row in self._account.list_names(self.co.account_namespace):
            entities[row['entity_id']] = row['entity_name']
        return entities
    
    def get_traits(self):
        """Fetch all usernames that are defined as a primary username."""
        if self.verbose:
            print 'Fetching traits...'
        traits = {}
        for row in self._account.list_traits(code=self.co.trait_primary_account):
            traits[row['entity_id']] = row['target_id']
        return traits

    def get_accounts(self, entities, traits):
        """Link person and username."""
        if self.verbose:
            print 'Fetching accounts...'
        accounts = {}
        for row in self._account.list():
            ## fetch only usernames.
            if entities.get(traits.get(row['owner_id'], ''), ''):
                accounts[row['owner_id']] = \
                    entities.get(traits.get(row['owner_id'], ''), '')
        return accounts


    def get_affiliations(self):
        """Connect person to her/his affilations.
            
            Affiliations are returned as:
            affs = {
                personid: [('aff','aff_status', 'ouid', 'created'), ...],
                personid1 : [(),],
             }
        """
        if self.verbose:
            print 'Fetching affiliations...'
        affs = {}
        affs_status = {}
        ous = {}
        aff_created = {}
        for row in self._person.list_affiliations():
            affs[row['person_id']] = \
                self._person.const.PersonAffiliation(row['affiliation']).str.lower()
            affs_status[row['person_id']] = \
                self._person.const.PersonAffStatus(row['status']).str.lower()
            ous[row['person_id']] = row['ou_id']
            aff_created[row['person_id']] = \
                row['create_date'].strftime(self._iso_format)
            
        return (affs, ous, affs_status, aff_created)
 
    def write_file(self):
        if self.verbose:
            print 'Writing persons to', self.outfile
        i = 0
        no_account = 0
        f = open(self.outfile, fileMode, bufferSize)
        for k in self.nins.keys():
            ## export only persons that has an account.
            account = self.accounts.get(k, '')
            if account:
                out_line = '%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;%s;\n' % \
                    (k,
                    self.nins[k][:6],
                    self.nins[k][6:],
                    self.birthdates.get(k, ''),
                    self.firstnames.get(k,''),
                    self.lastnames.get(k, ''),
                    self.emails.get(k, ''),
                    self.affs.get(k, ''),
                    self.affs_status.get(k, ''),
                    self.stedkoder.get(self.ous.get(k, ''), ''),
                    account,
                    self.created.get(k, ''))

                f.write(out_line)
                i += 1
            else:
                no_account += 1

        f.flush()
        f.close()
        if self.verbose:
            print '--------------------------------------------------------------------------------'
            print 'Total persons written:',i
            print 'Persons with no account:',no_account
            print '================================================================================'

    def print_time(self, before):
        print 'Time = %.2f secs' % (time.time() - before)

    def export_persons(self):
        totalBefore = 0
        before = 0
        if self.doTiming:
            totalBefore = time.time()
            before = totalBefore
        self.stedkoder = self.get_stedkoder()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.birthdates = self.get_birthdates()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.nins = self.get_nins()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.emails = self.get_emails()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        (self.affs, self.ous, self.affs_status, self.created) = self.get_affiliations()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.lastnames = self.get_lastnames()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.firstnames = self.get_firstnames()
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.accounts = self.get_accounts(self.get_entities(), self.get_traits())
        if self.doTiming and self.verbose:
            self.print_time(before)
            before = time.time()
        self.write_file()
        if self.doTiming and self.verbose:
            self.print_time(before)
        if self.doTiming:
            print 'Total time = %.2f secs' % (time.time() - totalBefore)

def usage(p):
    print '\nUsage: %s [OPTIONS]\n\n    OPTIONS\n\t-h, --help\t\tshow this help and exit.\n\t-o FILE, --output=FILE\twrite report to FILE.\n\t-t  --time\t\tcombination with verbose will show seconds\n\t\t\t\tper. operation and total; otherwise just\n\t\t\t\ttotal time.\n\t-v, --verbose\t\tshow status-messages to stdout.\n' % p


def main(argv):
    opts = None
    args = None
    prog = os.path.basename(argv[0])
    try:
        opts, args = getopt.getopt(argv[1:], 'ho:tv', ['help', 'output=', 'time', 'verbose'])
    except getopt.GetoptError, err:
        print str(err)
        usage(prog)
        sys.exit(1)
    output = None
    verbose = False
    doTiming = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage(prog)
            sys.exit(0)
        elif opt in ('-v', '--verbose'):
            verbose = True
        elif opt in ('-o', '--output'):
            output = arg
        elif opt in ('-t', '--time'):
            doTiming = True
        else:
            assert False, "unhandled option"
            sys.exit(2)
    if not output:
        usage(prog)
        sys.exit(3)
    export_kj = Export2Kjernen(output, verbose, doTiming)
    export_kj.export_persons()
    

if __name__ == '__main__':
    main(sys.argv)