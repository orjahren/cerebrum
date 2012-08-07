#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# 
# Copyright 2012 University of Oslo, Norway
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
"""A script for sending out SMS to new users. Originally created for sending out
usernames to student accounts created by process_students.py, but it could
hopefully be used by other user groups if necessary."""

import sys, os, getopt
from mx.DateTime import now

import cerebrum_path, cereconf
from Cerebrum import Errors
from Cerebrum.Utils import Factory, SMSSender

logger = Factory.get_logger('cronjob')
db = Factory.get('Database')()
db.cl_init(change_program='send_welcome_sms')
co = Factory.get('Constants')(db)
sms = SMSSender(logger=logger)

def usage(exitcode=0):
    print """Usage: %(scriptname)s [--commit] [options...]

    This script finds accounts that has the given trait and sends out a welcome
    SMS to them with their username. The 'sms_welcome' trait is set on SMS'ed
    accounts to avoid sending them duplicate SMSs.

    Note that we will not send out an SMS to the same account twice in a period
    of 180 days. We don't want to spam the users.

    --trait TRAIT   The trait that defines new accounts. Default: trait_student_new

    --phone-types   The phone types and source systems to get phone numbers
                    from. Can be a comma separated list, and its format is:

                        <source sys name>:<contact type>,...

                    E.g. FS:MOBILE,FS:PRIVATEMOBILE,SAP:MOBILE

                    Source systems: FS, SAP
                    Contact types: MOBILE, PRIVATEMOBILE

                    Default: FS:MOBILE

    --affiliations  A comma separated list of affiliations. If set, the person
                    must have at least one affiliation of these types.

    --message-cereconf If the message is located in cereconf, this is its
                    variable name. Default: AUTOADMIN_WELCOME_SMS

    --message       The message to send to the users. Should not be given if
                    --message-cereconf is specified.

    --too-old DAYS  How many days the given trait can exist before we give up
                    trying to send the welcome SMS. This is for the cases where
                    the phone number e.g. is incorrect, or the person hasn't a
                    phone number. After a while it will be too late to try
                    sending the SMS. When the given number of days has passed,
                    the trait will be deleted, and a warning will be logged.
                    Default: 180 days.

    --commit        Actual send out the SMSs and update traits.

    --help          Show this and quit
    """ % {'scriptname': os.path.basename(sys.argv[0])}
    sys.exit(exitcode)


def process(trait, message, phone_types, affiliations, too_old, commit=False):
    """Go through the given trait type and send out welcome SMSs to the users.
    Remove the traits, and set a new message-is-sent-trait, to avoid spamming
    the users."""
    logger.info('send_welcome_sms started')
    if not commit:
        logger.debug('In dryrun mode')

    ac = Factory.get('Account')(db)
    pe = Factory.get('Person')(db)

    for row in ac.list_traits(code=trait):
        if row['date'] < (now() - too_old):
            logger.warn('Too old trait %s for entity_id=%s, giving up',
                        trait, row['entity_id'])
            remove_trait(ac, row['entity_id'], trait, commit)
            continue
        ac.clear()
        ac.find(row['entity_id'])
        logger.debug('Found user %s', ac.account_name)
        if ac.owner_type != co.entity_person:
            logger.warn('Tagged new user %s not personal', ac.account_name)
            # TODO: remove trait?
            continue

        # check person affiliations
        if affiliations:
            affs = []
            for a in pe.list_affiliations(person_id=ac.owner_id):
                affs.append(a['affiliation'])
                affs.append(a['status'])
            if not any(a in affs for a in affiliations):
                logger.debug('No required person affiliation for %s, skipping',
                             ac.account_name)
                # TODO: Doesn't remove trait, in case the person gets it later on.
                #       Should the trait be removed?
                continue
        pe.clear()
        pe.find(ac.owner_id)

        # Check if user already has been texted. If so, the trait is removed.
        tr = ac.get_trait(co.trait_sms_welcome)
        if tr and tr['date'] > (now() - 180):
            logger.debug('User %s already texted last %d days, removing trait',
                         ac.account_name, 180)
            remove_trait(ac, row['entity_id'], trait, commit)
            continue

        # get phone number
        phone = get_phone_number(pe=pe, phone_types=phone_types)
        if not phone:
            logger.debug('Person %s had no phone number, skipping for now',
                         ac.account_name)
            continue
        email = ''
        try:
            if hasattr(ac, 'get_primary_mailaddress'):
                email = ac.get_primary_mailaddress()
        except Errors.NotFoundError:
            pass
        msg = message % {'username': ac.account_name,
                         'email': email}
        if not send_sms(phone, msg, commit):
            logger.warn('Could not send SMS to %s (%s)', ac.account_name, phone)
            continue
        # sms sent, now update the traits
        ac.delete_trait(trait)
        ac.populate_trait(code=co.trait_sms_welcome, date=now())
        ac.write_db()
        if commit:
            db.commit()
        else:
            db.rollback()
        logger.debug('Traits updated for %s', ac.account_name)
    if not commit:
        logger.debug('Changes rolled back')
    logger.info('send_welcome_sms done')

def remove_trait(ac, ac_id, trait, commit=False):
    """Remove a given trait from an account."""
    ac.clear()
    ac.find(ac_id)
    logger.debug("Deleting trait %s from account %s", trait, ac.account_name)
    ac.delete_trait(code=trait)
    ac.write_db()
    if commit:
        db.commit()
    else:
        db.rollback()

def get_phone_number(pe, phone_types):
    """Search through a person's contact info and return the first found info
    value as defined by the given types and source systems."""
    for sys, type in phone_types:
        for row in pe.get_contact_info(source=sys, type=type):
            return row['contact_value']

def send_sms(phone, message, commit=False):
    """Send an SMS to a given phone number"""
    logger.debug('Sending SMS to %s: %s', phone, message)
    if not commit:
        logger.debug('Dryrun mode, SMS not sent')
        return True
    return sms(phone, message)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'h',
                ['trait=', 'phone-types=', 'affiliations=', 'message=',
                 'too-old=', 'message-cereconf=', 'commit'])
    except getopt.GetoptError, e:
        print e
        usage(1)

    affiliations = []
    phone_types = []
    message = trait = None
    commit = False
    too_old = 180

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
        elif opt == '--trait':
            trait = getattr(co, arg)
        elif opt == '--too-old':
            too_old = int(arg)
            assert 0 < too_old, "--too_old must be a positive integer"
        elif opt == '--phone-types':
            phone_types.extend((co.human2constant(t[0], co.AuthoritativeSystem),
                                co.human2constant(t[1], co.ContactInfo)) 
                                for t in (a.split(':') for a in arg.split(',')))
        elif opt == '--affiliations':
            affiliations.extend(co.human2constant(a, (co.PersonAffiliation,
                                                      co.PersonAffStatus)) 
                                for a in arg.split(','))
        elif opt == '--message':
            if message:
                print 'Message already set'
                usage(1)
            message = arg
        elif opt == '--message-cereconf':
            if message:
                print 'Message already set'
                usage(1)
            message = arg
        elif opt == '--commit':
            commit = True
        else:
            print "Unknown argument: %s" % opt
            usage(1)

    # DEFAULTS
    if not affiliations:
        affiliations.append(co.affiliation_student)
    if not message:
        message = cereconf.AUTOADMIN_WELCOME_SMS
    if not phone_types:
        phone_types = [(co.system_fs, co.contact_mobile_phone,)]
    if not trait:
        trait = co.trait_student_new

    process(trait=trait, message=message, phone_types=phone_types,
            affiliations=affiliations, too_old=too_old, commit=commit)

if __name__ == '__main__':
    main()
