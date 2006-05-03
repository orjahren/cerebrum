#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2004 University of Oslo, Norway
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

''' This file is a UiT specific extension to Cerebrum
'''


import cerebrum_path
import cereconf
import getopt
import sys
import string
import os
import urllib
import datetime
from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.modules.no import fodselsnr
from Cerebrum.Constants import Constants
from Cerebrum.modules.no.Stedkode import Stedkode
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit import Email
import locale
locale.setlocale(locale.LC_ALL,"en_US.ISO-8859-1")

    
class execute:

    def __init__(self):
        #init variables
        self.split_char = ";" # char used to split data from the source_file
        self.db = Factory.get('Database')()
        self.person = Factory.get('Person')(self.db)
        self.account = Factory.get('Account')(self.db)
        self.constants = Factory.get('Constants')(self.db)
        self.OU = Factory.get('OU')(self.db)
        
        self.logger = Factory.get_logger('console')
        self.db.cl_init(change_program='slurp_x')
        bootstrap_inst = self.account.search(name=cereconf.INITIAL_ACCOUNTNAME)
        bootstrap_id=bootstrap_inst[0]['account_id']
        #print "bootstrap_id = %s" % bootstrap_id
    #reads the input source file

    def get_guest_data(self):
        guest_host = cereconf.GUEST_HOST
        guest_host_dir = cereconf.GUEST_HOST_DIR
        guest_host_file = cereconf.GUEST_HOST_FILE
        guest_file = cereconf.GUEST_FILE
        ret = urllib.urlretrieve("http://%s%s%s" % (guest_host,guest_host_dir,guest_host_file),"%s" % (guest_file))
        return ret

    def read_data(self,file):
        file_handle = open(file,"r")
        lines = file_handle.readlines()
        file_handle.close()
        return lines

    # creates a person object in cerebrum
    def create_person(self,data_list):
        #print data_list
        try: 
            personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost = data_list.split(self.split_char)
        except ValueError,m:
            sys.stderr.write("VALUEERROR: %s: Line=%s" % (m,data_list))
            return 1
            

        my_stedkode = Stedkode(self.db)
        my_stedkode.clear()
        self.person.clear()


        try:
            fnr = fodselsnr.personnr_ok(personnr)
            self.logger.info("process %s" % (fnr))
            (year,mon,day) = fodselsnr.fodt_dato(fnr)
        except fodselsnr.InvalidFnrError:
            self.logger.warn("Ugyldig f�dselsnr: %s" % personnr)
            return 1
        
        try:
            self.person.find_by_external_id(self.constants.externalid_fodselsnr,personnr)
        except Errors.NotFoundError:
            pass
        
        gender = self.constants.gender_male
        if(fodselsnr.er_kvinne(fnr)):
            gender = self.constants.gender_female

        self.person.populate(self.db.Date(year,mon,day),gender)

        self.person.affect_names(self.constants.system_x,self.constants.name_first,self.constants.name_last,self.constants.name_full)
        self.person.populate_name(self.constants.name_first,fornavn)
        self.person.populate_name(self.constants.name_last,etternavn)

        fult_navn = "%s %s" % (fornavn,etternavn)
        self.person.populate_name(self.constants.name_full,fult_navn)

        self.person.affect_external_id(self.constants.system_x,self.constants.externalid_fodselsnr)
        self.person.populate_external_id(self.constants.system_x,self.constants.externalid_fodselsnr,fnr)
        
        # setting affiliation and affiliation_status
        #print "aff before = %s" % affiliation
        orig_affiliation = affiliation
        affiliation = int(self.constants.PersonAffiliation(affiliation))
        #print "aff after = '%s'" % affiliation

        #print "aff_status before = '%s'" % affiliation_status
        affiliation_status = int(self.constants.PersonAffStatus(orig_affiliation,affiliation_status.lower()))
        #print "aff_status after = %s" % affiliation_status

        fakultet = ou[0:2]
        institutt = ou[2:4]
        avdeling = ou[4:6]
        # get ou_id of stedkode used
        my_stedkode.find_stedkode(fakultet,institutt,avdeling,cereconf.DEFAULT_INSTITUSJONSNR)
        ou_id = my_stedkode.entity_id
        #print "populating person affiliation..."
        # populate the person affiliation table
        self.person.populate_affiliation(int(self.constants.system_x),
                                         int(ou_id),
                                         int(affiliation),
                                         int(affiliation_status)
                                         )

        #write the person data to the database
        #print "write to db..."
        op = self.person.write_db()
        # return sanity messages
        if op is None:
            self.logger.info("**** EQUAL ****")
        elif op == True:
            self.logger.info("**** NEW ****")
        elif op == False:
            self.logger.info("**** UPDATE ****")


    def expire_date_conversion(self,expire_date):
        # historical reasons dictate that dates may be received on the format dd.mm.yyyy
        # if this is the case, we need to convert it to yyyy-mm-dd
        day,month,year = expire_date.split("-",2)
        expire_date="%s-%s-%s" % (year,month,day)
        return expire_date


    def update_account(self,data_list):
        num_new_list = []
        num_old_list = []
        personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost = data_list.split(self.split_char)
        #print "update"
        # need to check and update the following data: affiliation,expire_date,gecos,ou and spread

        #update expire_date
        self.account.expire_date = expire_date

        # update gecos
        full_name = "%s %s" % (fornavn,etternavn)
        self.account.gecos = full_name

        #update spread
        old_spreads = self.account.get_spread()
        
        spread_list = string.split(spreads,",")
        for i in spread_list:
            num_new_list.append(int(self.constants.Spread(i)))

        for o in old_spreads:
            num_old_list.append(int(self.constants.Spread(o['spread'])))


        for old_spread in num_old_list:
            #print "old_spread = %s" % old_spread
            if old_spread not in num_new_list:
                #print "deleting spread %s" % old_spread
                self.account.delete_spread(int(old_spread))

        for new_spread in num_new_list:
            if new_spread not in num_old_list:
                #print "adding spread %s" % new_spread
                self.account.add_spread(int(new_spread))

        #update ou and affiliation (setting of account_type)
        self.OU.clear()
        self.OU.find_stedkode(ou[0:2],ou[2:4],ou[4:6],cereconf.DEFAULT_INSTITUSJONSNR)
        my_account_types = self.account.get_account_types()
        #for i in my_account_types:
        #    #print "deleting old account_type"
        #    self.account.del_account_type(i.ou_id,i.affiliation)

        if(affiliation=="MANUELL"):
            self.account.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)),priority=400)
        elif(affiliation=="TILKNYTTET"):
            self.account.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)),priority=350)
        else:
            raise errors.ValueError("invalid affiliation: %s in guest database" % (affiliation))
        
        self.account.write_db()


    def create_account(self,data_list):
        data_list = data_list.rstrip()
        personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost = data_list.split(self.split_char)
        posix_user = PosixUser.PosixUser(self.db)
        group = Factory.get('Group')(self.db)
        self.person.clear()
        posix_user.clear()
        group.clear()
        self.OU.clear()
        my_accounts = None
        self.account = Factory.get('Account')(self.db)

        num_new_list = []
        num_old_list = []
        spread_list = string.split(spreads,",")
        
        try:
            self.person.find_by_external_id(self.constants.externalid_fodselsnr,personnr,self.constants.system_x,self.constants.entity_person)
        except Errors.NotFoundError:
            #print "person with ssn = %s does not exist in cerebrum. unable to check for account" % personnr
            return 1,bruker_epost

        try:
            #self.account.find(self.person.get_primary_account())
            account_list = self.person.get_accounts(filter_expired=False)
            #print "foo=%s" % account_list[0][0]
            #default_account = "%s" % int(account_list[0])
            self.account.find(account_list[0][0])
            account_types = self.account.get_account_types()
            for account_type in account_types:
                #print "account_type[affiliation] = %s" % account_type['affiliation']
                if ((account_type['affiliation']==self.constants.affiliation_manuell) or (account_type['affiliation']==self.constants.affiliation_tilknyttet)):
                    self.update_account(data_list)
                    
        except Errors.NotFoundError:
            pass
            
        #my_accounts = self.person.get_accounts()
        if(account_list == None):

            spread_list = string.split(spreads,",")
            spread_list.append('ldap@uit') # <- default spread for ALL sys_x users/accounts.
            #for i in spread_list:
            #    print "code value = %s,%s" % (self.constants.Spread(i),int(self.constants.Spread(i)))
                
            #try:

            #except Errors.NotFoundError:
            #    self.logger("Unable to create account for person %s. Person does not exist in cerebrum" % (personnr))
            #    return 1


            full_name = "%s %s" % (fornavn,etternavn)
            if ('AD_account' in spread_list):
                username = self.account.get_uit_uname(personnr,full_name,'AD')
            else:
                username = self.account.get_uit_uname(personnr,full_name)
            
            group.find_by_name("posixgroup",domain=self.constants.group_namespace)
            new_expire_date = self.expire_date_conversion(expire_date)
            #print "new = %s" % new_expire_date
            bootstrap_inst = self.account.search(name=cereconf.INITIAL_ACCOUNTNAME)
            bootstrap_id=bootstrap_inst[0]['account_id']
            posix_user.populate(name = username,
                                owner_id = self.person.entity_id,
                                owner_type = self.constants.entity_person,
                                np_type = None,
                                creator_id = bootstrap_id,
                                expire_date = expire_date,
                                posix_uid = posix_user.get_free_uid(),
                                gid_id = group.entity_id,
                                gecos = full_name,
                                shell = self.constants.posix_shell_bash
                                )
            try:
                posix_user.write_db()


                # add the correct spreads to the account
                for spread in spread_list:
                    #print "%s,%s,%s" % (posix_user.entity_id,int(self.constants.entity_account),int(self.constants.group_memberop_union))
                    posix_user.add_spread(int(self.constants.Spread(spread)))
                    posix_user.set_home_dir(int(self.constants.Spread(spread)))
                
                    
                #group.add_member(posix_user.entity_id,int(self.constants.entity_account),int(self.constants.group_memberop_union))
                posix_user.set_password(personnr)
                posix_user.write_db()
                # lets set the account_type table
                # need: oi_id, affiliation and priority
                self.OU.find_stedkode(ou[0:2],ou[2:4],ou[4:6],cereconf.DEFAULT_INSTITUSJONSNR)

                if(affiliation=="MANUELL"):
                    posix_user.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)),priority=400)
                elif(affiliation=="TILKNYTTET"):
                    posix_user.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)),priority=350)
                else:
                    raise errors.ValueError("invalid affiliation: %s in guest database" % (affiliation))


                #posix_user.set_account_type(self.OU.ou_id,int(self.constants.PersonAffiliation(affiliation)))
                self.send_mail(bruker_epost,username,spread_list)
                if("AD_account" in spread_list):

                    #only send email to nybruker@asp.uit.no if AD_account is one of the chosen spreads.
                    self.send_ad_email(full_name,personnr,ou,affiliation_status,expire_date,hjemmel,kontaktinfo,bruker_epost,ansvarlig_epost)
                self.confirm_registration(personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost)
                return  posix_user.entity_id,bruker_epost
            except Errors:
                self.logger("Error in creating posix account for person %s" % personnr)
                return 1,bruker_epost
            #posix_user.get_homedir_id(self.constants.spread_uit_ldap_person)
            posix_user.write_db()
        else:
            self.logger.info("person %s already has an account in cerebrum" % personnr)
            #print "my accounts=%s" % account_list
            #
            #print"%s,%s" % (datetime.date.today(),expire_date)
            my_date= expire_date.split("-")
            if (self.account.is_expired() and (datetime.date(int(my_date[0]),int(my_date[1]),int(my_date[2])) > datetime.date.today())):
                # This account is expired in cerebrum. expire_date from the guest database
                # is set in the future. need to update expire_date in the database
                self.logger.info("updating expire date to" % expire_date)
                self.account.expire_date = expire_date
            
            
            for account_type in account_types:
                if((self.constants.affiliation_student == account_type['affiliation'])or (self.constants.affiliation_ansatt == account_type['affiliation'])):
                    # This person already has a student account. we must now add new spreads (if any).
                    # indicating that this account is now to be sent to the new spreads listed.
                    # FS/SLP4 is still authoritative on account data, including expire date,
                    # and as such,no other manipulation of the account will be done
                    old_spreads = self.account.get_spread()
                    for o in old_spreads:
                        num_old_list.append(int(self.constants.Spread(o['spread'])))
                    for i in spread_list:
                        if i !='':
                            num_new_list.append(int(self.constants.Spread(i)))
                    for new_spread in num_new_list:
                        if new_spread not in num_old_list:
                            #print "adding spread %s" % new_spread
                            self.account.add_spread(int(new_spread))
            return self.account.entity_id,bruker_epost # <- even if the account exists we have to update email information from system_x by returning the account_id here

    def send_ad_mail(self,name,ssn,ou,type,expire_date,why,contact_data,external_email,registrator_email):
        ad_message="""
%s har sendt inne en foresp�rsel om ny AD konto. F�lgende data er registrert om denne personen.

Navn: %s
personnummer:%s
stedkode: %s
type:%s
utl�ps dato:%s
grunn: %s
kontakt data: %s
ekstern epost: %s

""" % (registrator_email,name,ssn,ou,type,expire_date,why,contact_data,external_email)

        SENDMAIL="/usr/sbin/sendmail"
        p=os.popen("%s -t" % SENDMAIL, "w")
        p.write("From bas-admin@cc.uit.no\n")
        p.write("To: nybruker2@asp.uit.no\n")
        p.write("Bcc: kenneth.johansen@cc.uit.no\n")
        p.write("subject: Registrering av ny AD bruker\n")
        p.write("\n")
        p.write("%s" % ad_message)
        sts = p.close()
        if sts != None:
            self.logger("Sendmail exit status: %s" % sts)


    def confirm_registration(self,personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,ansvarlig_epost,bruker_epost):
        confirm_message="""
F�lgende data er motatt og behandlet i system X.

Personnr: %s
Fornavn: %s
Etternavn: %s
ou: %s
Tilknytning: %s
Tilknytnings type: %s
utl�ps dato: %s
skal eksporteres til disse ende systemene: %s
Hjemmel: %s
kontakt info: %s
Ekstern epost: %s
Ansvarlig epost: %s

""" % (personnr,fornavn,etternavn,ou,affiliation,affiliation_status,expire_date,spreads,hjemmel,kontaktinfo,bruker_epost,ansvarlig_epost)
        SENDMAIL="/usr/sbin/sendmail"
        p=os.popen("%s -t" % SENDMAIL, "w")
        p.write("From bas-admin@cc.uit.no\n")
        p.write("To: %s\n" % ansvarlig_epost)
        p.write("Bcc: kenneth.johansen@cc.uit.no\n")
        p.write("subject: Registrering av bruker\n")
        p.write("\n")
        p.write("%s" % confirm_message)
        sts = p.close()
        if sts != None:
            self.logger("Sendmail exit status: %s" % sts)
        
        
    def send_mail(self,email_address,user_name,spreads):
        #This function sends an email to the email_address given
        

        message="""
Translation in english follows.
        
Dette er en automatisk generert epost. Du er registrert i BAS og har f�tt tildelt brukernavn og passord.
For � aktivisere kontoen din m� du g� til orakel tjenesten ved uit. http://uit.no/orakel.
\n
I samsvar med de data som ble registrert ved din innmeldelse vil du bli eksponert til disse systemene: %s.
I tilfellet FRIDA kan det ta opp til ett par virkedager f�r kontoen er klar.
Har du noen sp�rsm�l kan du ta kontakt med orakel@uit.no eller bas-admin@cc.uit.no. \n
-----------------------------------------------------------------------------------

This is an automated message. You are now registered in BAS and have received a username and password.
To activate your account you need to visit the oracle service at uit.  http://uit.no/orakel
\n
According to the data registered you will be exported to the following systems: %s.
Notice that it may take a few days before your FRIDA account is activated.
If you have any questions you can either contact orakel@uit.no or bas-admin@cc.uit.no\n
        """ % (spreads,spreads)

        SENDMAIL="/usr/sbin/sendmail"
        p=os.popen("%s -t" % SENDMAIL, "w")
        p.write("From bas-admin@cc.uit.no\n")
        p.write("To: %s\n" % email_address)
        p.write("Bcc: kenneth.johansen@cc.uit.no\n")
        p.write("subject: Registrering av bruker\n")
        p.write("\n")
        p.write("%s" % message)
        sts = p.close()
        if sts != None:
            self.logger("Sendmail exit status: %s" % sts)


def main():

    try:
        opts,args = getopt.getopt(sys.argv[1:],'s:u',['source_file','update'])
    except getopt.GetoptError:
        usage()

    ret = 0
    source_file = 0
    update = 0
    for opt,val in opts:
        if opt in('-s','--source_file'):
            source_file = val
        if opt in ('-u','--update'):
            update = 1

    if (source_file == 0):
        usage()
    else:
        x_create = execute()
        if(update ==1):
            x_create.get_guest_data()
        data = x_create.read_data(source_file)
        for line in data:
            if (line[0] != '#'):
                ret = x_create.create_person(line)
        x_create.db.commit()
        #accounts needs to be created after person objects are stored
        #Therefore we need to traverse the list again and generate
        #accounts.
        for line in data:
            if (line[0] != '#'):
                ret,bruker_epost = x_create.create_account(line)
                #print "ret = %s" % ret
                x_create.db.commit()
                if ret != 1:
                    #print "SET EMAIL: acc_id=%s, email=%s " % (ret, bruker_epost)
                    email_class = Email.email_address(x_create.db)
                    email_class.process_mail(ret,"defaultmail",bruker_epost)
                    email_class.db.commit()                    
        #x_create.db.commit()
        
                               
def usage():
    print """
    usage:: python slurp_x.py -s
    -s | --source_file    source file containing information needed to create
                          person and user entities in cerebrum
    -u | --update_data :  updates the datafile containing guests from the guest database
    """
    sys.exit(1)


if __name__=='__main__':
    main()

# arch-tag: badbe824-b426-11da-846c-fe4d7376a8b8
