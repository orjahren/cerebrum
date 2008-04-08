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

import getopt
import sys
import os
import mx
from sets import Set

progname=__file__.split(os.sep)[-1]
__doc__="""
    usage:: %s [-d|--dryrun]
    --dryrun : do no commit changes to database
    --logger-name name: name of logger to use
    --logger-level level: loglevel to use
""" % (progname)


import cerebrum_path
import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum.Utils import Factory
from Cerebrum.Constants import Constants
from Cerebrum.modules import PosixUser
from Cerebrum.modules.no.uit.access_SYSX import SYSX
from Cerebrum.modules.no.uit import Email

from Cerebrum.modules.no.uit.EntityExpire import EntityExpiredError


accounts=persons=logger=None
sysx=None
skipped=added=updated=unchanged=deletedaff=0


db=Factory.get('Database')()
db.cl_init(change_program='process_systemx')
co=Factory.get('Constants')(db)
logger=Factory.get_logger("cronjob")


def get_existing_accounts():

    ou = Factory.get('OU')(db)
        
    #get persons that comes from sysX and their accounts
    pers=Factory.get("Person")(db)
    tmp_persons={}
    logger.info("Loading persons...")
    pid2sysxid={}
    sysx2pid={}
    for row in pers.list_external_ids(id_type=co.externalid_sys_x_id):
        if (row['source_system'] == int(co.system_x) or
            (not pid2sysxid.has_key(int(row['entity_id'])))):
            pid2sysxid[int(row['entity_id'])]=int(row['external_id'])
            sysx2pid[int(row['external_id'])]=int(row['entity_id'])
            tmp_persons[int(row['external_id'])]=ExistingPerson()

    for row in pers.list_affiliations(
        source_system=co.system_x,
        fetchall=False):
        tmp=pid2sysxid.get(row['person_id'],None)
        if tmp is not None:
            ou.clear()
            try:
                ou.find(int(row['ou_id']))            
                tmp_persons[tmp].append_affiliation(
                    int(row['affiliation']), int(row['ou_id']), 
                    int(row['status']))
            except EntityExpiredError, msg:
                logger.error("Skipping affiliation to ou_id %s (expired) for " \
                             "person with sysx_id %s." % (row['ou_id'], tmp))
                continue

    tmp_ac={}
    account_obj=Factory.get('Account')(db)
    logger.info("Loading accounts...")
    
    for row in account_obj.list(filter_expired=False,fetchall=False):
        sysx_id=pid2sysxid.get(int(row['owner_id']),None)

        if not sysx_id or not tmp_persons.has_key(sysx_id):
            continue
        
        # Exclude accounts that are NOT a person's PRIMARY account =====
        x = account_obj.get_account_types(owner_id = row['owner_id'])
        if x and (x[0]['account_id'] != row['account_id']):
            logger.warn('Excluded account because it is not the primary account: %s' % (row['account_id']))
            continue
        # ==============================================================
        
        tmp_ac[row['account_id']]=ExistingAccount(sysx_id,row['expire_date'])
        
    # Posixusers
    posix_user_obj=PosixUser.PosixUser(db)
    for row in posix_user_obj.list_posix_users():
        tmp=tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            tmp.set_posix(int(row['posix_uid']))

    # quarantines
    for row in account_obj.list_entity_quarantines(
        entity_types=co.entity_account):
        tmp=tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_quarantine(int(row['quarantine_type']))

    # Spreads
    spread_list=[co.spread_uit_ldap_account,co.spread_uit_fd,\
                 co.spread_uit_sut_user,co.spread_uit_fronter_account, \
                 co.spread_uit_ad_account,co.spread_uit_frida]
    for spread_id in spread_list:
        is_account_spread=is_person_spread=False
        spread=co.Spread(spread_id)
        if spread.entity_type == co.entity_account:
            is_account_spread=True
        elif spread.entity_type == co.entity_person:
            is_person_spread=True
        else:
            logger.warn("Unknown spread type")
            continue
        for row in account_obj.list_all_with_spread(spread_id):
            if is_account_spread:
                tmp=tmp_ac.get(int(row['entity_id']), None)
            if is_person_spread:
                tmp=tmp_persons.get(int(row['entity_id']), None)
            if tmp is not None:
                tmp.append_spread(int(spread_id))
    
    # Account homes
    # FIXME: This does not work for us!
    for row in account_obj.list_account_home():
        tmp=tmp_ac.get(int(row['account_id']), None)
        if tmp is not None and row['disk_id']:
            tmp.set_home(int(row['home_spread']), int(row['disk_id']),
                         int(row['homedir_id']))

    # Affiliations
    for row in account_obj.list_accounts_by_type(filter_expired=False):
        tmp=tmp_ac.get(int(row['account_id']), None)
        if tmp is not None:
            ou.clear()
            try:
                ou.find(int(row['ou_id']))            
                tmp.append_affiliation(int(row['affiliation']), int(row['ou_id']))
            except EntityExpiredError, msg:
                logger.warn("Skipping affiliation to ou_id %s (OU expired) for person with account_id %s. (Is person affiliation on OU not deleted because of grace?)" % (row['ou_id'], row['account_id']))
                continue


    # traits
    for row in account_obj.list_traits(co.trait_sysx_registrar_notified):
        tmp=tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_trait(co.trait_sysx_registrar_notified,row['strval'])
    for row in account_obj.list_traits(co.trait_sysx_user_notified):
        tmp=tmp_ac.get(int(row['entity_id']), None)
        if tmp is not None:
            tmp.append_trait(co.trait_sysx_user_notified,row['strval'])

    # organize sysx id's
    for acc_id, tmp in tmp_ac.items():
        sysx_id=tmp_ac[acc_id].get_sysxid()
        tmp_persons[sysx_id].append_account(acc_id)

    logger.info(" found %i persons and %i accounts" % (
        len(tmp_persons), len(tmp_ac)))
    return tmp_persons, tmp_ac  


def expire_date_conversion(expire_date):
    # historical reasons dictate that dates may be received on the format dd.mm.yyyy
    # if this is the case, we need to convert it to yyyy-mm-dd
    day,month,year=expire_date.split("-",2)
    expire_date="%s-%s-%s" % (year,month,day)
    return expire_date


def _send_mailq(mailq):
    for item in mailq:
        type=item['template']
        info=item['person_info']
        account_id=item['account_id']
        send_mail(type,info,account_id)        


def send_mail(type, person_info, account_id):
    sender=cereconf.SYSX_EMAIL_NOTFICATION_SENDER
    cc=None    
    if type=='ansvarlig':
        t_code=co.trait_sysx_registrar_notified
        template= cereconf.CB_SOURCEDATA_PATH + '/templates/sysx/ansvarlig.tpl'
        recipient=person_info.get('ansvarlig_epost')
        person_info['AD_MSG']=""
        if 'AD_account' in person_info.get('spreads'):
            person_info['AD_MSG']="Merk: Personen har ikke f�tt generert AD konto enda. Dette m� gj�res i samarbeid med den lokale IT-avdelingen."
    elif type=='bruker':
        recipient=person_info.get('bruker_epost',None)
        if recipient in (None,""):
            logger.info('No recipient when sending bruker_epost, message not sent')
            return
        t_code=co.trait_sysx_user_notified
        template= cereconf.CB_SOURCEDATA_PATH + '/templates/sysx/bruker.tpl'
        if 'AD_account' in person_info.get('spreads'):
            template= cereconf.CB_SOURCEDATA_PATH + '/templates/sysx/ad_bruker.tpl'
    else:
        logger.error("Unknown type '%s' in send_mail()" % type)
        return

    # record the username in person_info dict.
    ac=Factory.get('Account')(db)
    logger.debug("send_mail(): acc_id is ->%s<" % account_id)
    ac.find(account_id)    
    person_info['USERNAME']=ac.account_name

    # spreads may be a list
    if isinstance(person_info['spreads'],list):
        person_info['spreads']=",".join(person_info['spreads'])
    
    #hrrmpfh.. We talk to Oracle in iso-8859-1 format. Convert text
    for k in person_info.keys():
        person_info[k]=person_info[k].decode('iso-8859-1').encode('utf-8')

    # finally, send the message    
    debug=dryrun
    ret=Utils.mail_template(recipient, template, sender=sender, cc=cc,
                substitute=person_info, charset='utf-8', debug=debug)
    if debug:
        print "DRYRUN: mailmsg=\n%s" % ret
        
    # set trait on user
    r=ac.populate_trait(t_code,strval=recipient,date=mx.DateTime.today())
    logger.info("TRAIT populate result:%s", r)
    ac.write_db()
 

def _populate_account_affiliations(account_id, sysx_id):
    """Assert that the account has the same sysX affiliations as the person.
    """

    changes=[]
    account_affs=accounts[account_id].get_affiliations()

    logger.debug("-->Person SysXID=%s has affs=%s" %  (sysx_id,
        persons[sysx_id].get_affiliations()))
    logger.debug("-->Account_id=%s,SysXID=%s has account affs=%s" % (account_id,
        sysx_id,account_affs))
    for aff, ou, status in persons[sysx_id].get_affiliations():
        if not (aff,ou) in account_affs:
            changes.append(('set_ac_type', (ou, aff)))
##  TODO: Fix removal of account affs
    return changes

def _promote_posix(acc_obj):

        group = Factory.get('Group')(db)
        pu = PosixUser.PosixUser(db)
        uid = pu.get_free_uid()
        shell = co.posix_shell_bash
        grp_name = "posixgroup"
        group.clear()
        group.find_by_name(grp_name,domain=co.group_namespace)
        try:
            pu.populate(uid, group.entity_id, None, shell, parent=acc_obj)
            pu.write_db()
        except Exception,msg:
            logger.error("Error during promote_posix. Error was: %s" % msg)
            return False
        # only gets here if posix user created successfully
        logger.info("%s promoted to posixaccount (uidnumber=%s)" %  \
            (acc_obj.account_name, uid))
        return True


def _handle_changes(a_id,changes):
        
    do_promote_posix=False
    ac=Factory.get('Account')(db)
    ac.find(a_id)
    for chg in changes:
        ccode,cdata=chg
        if ccode=='spreads_add':
            for s in cdata:
                ac.add_spread(s)
                ac.set_home_dir(s)
        elif ccode=='quarantine_add':
            ac.quarantine_add(cdata)
        elif ccode=='quarantine_del':
            ac.quarantine_del(cdata)
        elif ccode=='set_ac_type':
            ac.set_account_type(cdata[0], cdata[1])
        elif ccode=='gecos':
            ac.gecos=cdata
        elif ccode=='expire_date':
            ac.expire_date=cdata
        elif ccode=='promote_posix':
            do_promote_posix=True
        else:
            logger.error("Change account: %s(id=%d): Unknown changecode: %s, " \
            "changedata=%s" % (ac.account_name,a_id,ccode,cdata))
            continue
    ac.write_db()
    if do_promote_posix:
        _promote_posix(ac)
    logger.info("Change Account %s(id=%d): All changes written" % \
        (ac.account_name,a_id))


def _update_email(acc_id,bruker_epost):
    
    em=Email.email_address(db)
    ad_email=em.get_employee_email(acc_id,db)

    account_obj=Factory.get('Account')(db)
    account_obj.find(acc_id)
    person_obj=Factory.get('Person')(db)
    person_obj.find(account_obj.owner_id)
    if (len(ad_email)>0):
        ad_email=ad_email[account_obj.account_name]
    else:
        ## TODO: Use default maildomain whenever AD email is nonexistant!
        ## No need to check for student aff.
        person_aff=person_obj.list_affiliations(person_id=person_obj.entity_id,
            affiliation=co.affiliation_student)
        logger.debug("update_email(): person_aff=%s" % person_aff)
        if(len(person_aff)>0):
            logger.debug("update_email(): %s has student affiliation" % account_obj.entity_id)
            ad_email="@".join((account_obj.account_name,"mailbox.uit.no"))
        elif(bruker_epost!=""):
            ## FIXME: Never ever set extrernal email here !!!
            ad_email="%s" % bruker_epost
        else:
            no_mailbox_domain=cereconf.NO_MAILBOX_DOMAIN
            ad_email= "@".join((account_obj.account_name,no_mailbox_domain))
            logger.warning("update_email(): Using NO_MAILBOX_DOMAIN=>'%s'" % ad_email)
    
    current_email=""
    try:
        current_email=account_obj.get_primary_mailaddress()
    except Errors.NotFoundError:
        # no current primary mail.
        pass

    if (current_email.lower() != ad_email.lower()):
        # update email!
        logger.debug("Email update needed old='%s', new='%s'" % ( current_email, ad_email))
        try:
            em.process_mail(account_obj.entity_id,"defaultmail",ad_email)
        except Exception,m:
            logger.critical("EMAIL UPDATE FAILED: account_id=%s , email=%s,error:%s" % (account_obj.entity_id,ad_email,m))
            sys.exit(2)
    else:
        logger.debug("Email update not needed old=new='%s'" % (current_email))



class Build(object):

    def __init__(self):
        #init variables
        ac=Factory.get('Account')(db)
        ac.find_by_name(cereconf.INITIAL_ACCOUNTNAME)        
        self.bootstrap_id=ac.entity_id
        gr=Factory.get('Group')(db)
        gr.find_by_name("posixgroup",domain=co.group_namespace)
        self.posix_group=gr.entity_id
        self.num_expired=0
        

    def process_all(self):
        for item in sysx.sysxids.items():
            logger.debug("-----------------------------")
            sysx_id, sysx_person= item
            self._process_sysx(int(sysx_id),sysx_person)


    def _CreateAccount(self,sysx_id):
        today=mx.DateTime.today()
        default_creator_id=self.bootstrap_id
        default_group_id=self.posix_group
        p_obj=Factory.get('Person')(db)
        logger.info("Try to create user for person with sysx_id=%s" % sysx_id)
        try:
            p_obj.find_by_external_id(co.externalid_sys_x_id, sysx_id)
        except Errors.NotFoundError:
            logger.warn("OUCH! person (sysx_id=%s) not found" % sysx_id)
            return None
        else:
            person_id=p_obj.entity_id

        if not persons[sysx_id].get_affiliations():
            logger.error("Person (sysx_id=%s) has no sysX affs" % sysx_id)
            return None

        try:
            first_name=p_obj.get_name(co.system_cached, co.name_first)
        except Errors.NotFoundError:
            # This can happen if the person has no first name and no
            # authoritative system has set an explicit name_first variant.
            first_name=""
        try:
            last_name=p_obj.get_name(co.system_cached, co.name_last)
        except Errors.NotFoundError:
            # See above.  In such a case, name_last won't be set either,
            # but name_full will exist.
            last_name=p_obj.get_name(co.system_cached, co.name_full)
            assert last_name.count(' ') == 0
        full_name=" ".join((first_name,last_name))

        try:
            fnr=p_obj.get_external_id(id_type=co.externalid_fodselsnr)[0]['external_id']
        except IndexError:
            fnr=sysx_id

        account=PosixUser.PosixUser(db)
        uname=account.suggest_unames(fnr, first_name, last_name)
        account.populate(name=uname,
            owner_id=person_id,
            owner_type=co.entity_person,
            np_type=None,
            creator_id=default_creator_id,
            expire_date=today,
            posix_uid=account.get_free_uid(),
            gid_id=self.posix_group,
            gecos=account.simplify_name(full_name,as_gecos=True),
            shell=co.posix_shell_bash
            )
        
        password=account.make_passwd(uname)
        account.set_password(password)
        tmp=account.write_db()
        logger.debug("new Account=%s, write_db=%s" % (account.account_name,tmp))

        acc_obj= ExistingAccount(sysx_id,today)
        #register new account as posix
        acc_obj.set_posix(int(account.posix_uid))
        accounts[account.entity_id]=acc_obj
        return account.entity_id
        


    def _process_sysx(self,sysx_id, person_info):
        logger.info("Starting process of sysXid=%s" % (sysx_id))
        p_obj=persons.get(sysx_id,None)
        if not p_obj:
            logger.error("ERROR Nonexistent sysx_id %s. Skipping" % (sysx_id))
            return None
            
        changes=[]
        mailq=[]

        if not p_obj.has_account():
            acc_id=self._CreateAccount(sysx_id)
            mailq.append( {
                'account_id': acc_id,
                'person_info': person_info, 
                'template': 'bruker'
                })
        else:
            acc_id=p_obj.get_account()
    
        acc_obj=accounts[acc_id]

        # check if account is a posix account
        if not acc_obj.get_posix():
            changes.append(('promote_posix',True))

        # Update expire if needed
        current_expire= acc_obj.get_expire_date()
        new_expire=mx.DateTime.DateFrom(person_info['expire_date'])
        today= mx.DateTime.today()
        if ((new_expire > today) and (new_expire > current_expire)):
            # If new expire is later than current expire 
            # then update expire            
            changes.append(('expire_date',"%s" % new_expire))
 
        #check account affiliation and status        
        changes.extend(_populate_account_affiliations(acc_id,sysx_id))
        
        #check gecos?

        #make sure all spreads defined in sysX is set
        tmp_spread=[int(co.Spread('ldap@uit'))]
        for s in person_info.get('spreads'):
            tmp_spread.append(int(co.Spread(s)))
            if s=='SUT@uit':
                tmp_spread.append(int(co.Spread('fd@uit')))
        sysX_spreads=Set(tmp_spread)
        cb_spreads=Set(acc_obj.get_spreads())
        to_add=sysX_spreads - cb_spreads
        if to_add:
            changes.append(('spreads_add',to_add))
        
        #check account homes for each spread
        # FIXME: Get homes for all spreads. There is a bug in list_account_home()
              
        #check quarantine
        if person_info.get('approved') == 'Yes':
            if co.quarantine_sys_x_approved in acc_obj.get_quarantines():
                changes.append(('quarantine_del',co.quarantine_sys_x_approved))
        else:
            # make sure this account is quarantined
            if co.quarantine_sys_x_approved not in acc_obj.get_quarantines():
                changes.append(('quarantine_add',co.quarantine_sys_x_approved))

        if changes:
            logger.debug("Changes [%i/%s]: %s" % (
                acc_id, 
                sysx_id, 
                repr(changes)))
            _handle_changes(acc_id,changes)
            mailq.append( {
                'account_id': acc_id,
                'person_info': person_info, 
                'template': 'ansvarlig'
                })
            _send_mailq(mailq)
        # always update email for sysx persons
        _update_email(acc_id,person_info['bruker_epost'])



    def check_expired_sourcedata(self, expire_date):
        expire=mx.DateTime.DateFrom(expire_date)
        today= mx.DateTime.today()
        if ( expire < today):
            return True
        else: 
            return False


class ExistingAccount(object):
    def __init__(self, sysx_id, expire_date):
        self._affs=[]
        self._expire_date= expire_date
        self._sysx_id=sysx_id        
        self._owner_id=None
        self._uid=None
        self._home={}
        self._quarantines=[]
        self._spreads=[]
        self._traits=[]

    def append_affiliation(self, affiliation, ou_id):
        self._affs.append((affiliation, ou_id))

    def append_quarantine(self, q):
        self._quarantines.append(q)
    
    def append_spread(self, spread):
        self._spreads.append(spread)

    def append_trait(self, trait_code, trait_str):
        self._traits.append((trait_code, trait_str))
    
    def get_affiliations(self):
        return self._affs
    
    def get_expire_date(self):
        return self._expire_date
    
    def get_posix(self):
        return self._uid

    def get_home(self, spread):
        return self._home.get(spread, (None, None))

    def get_home_spreads(self):
        return self._home.keys()
        
    def get_quarantines(self):
        return self._quarantines   

    def get_spreads(self):
        return self._spreads
        
    def get_sysxid(self):
        return int(self._sysx_id)
    
    def get_traits(self):
        return self._traits
    
    def has_affiliation(self, aff_cand):
        return aff_cand in [aff for aff, ou in self._affs]

    def has_homes(self):
        return len(self._home) > 0
    
    def set_posix(self, uid):
        self._uid=uid

    def set_home(self, spread, disk_id, homedir_id):
        self._home[spread]=(disk_id, homedir_id)
    

class ExistingPerson(object):
    def __init__(self):
        self._affs=[]
        self._groups=[]
        self._spreads=[]
        self._accounts=[]

    def append_affiliation(self, affiliation, ou_id, status):
        self._affs.append((affiliation, ou_id, status))

    def get_affiliations(self):
        return self._affs

    def append_group(self, group_id):
        self._groups.append(group_id)

    def get_groups(self):
        return self._groups

    def append_spread(self, spread):
        self._spreads.append(spread)

    def get_spreads(self):
        return self._spreads
    
    def has_account(self):
        return len(self._accounts) > 0
        
    def append_account(self,acc_id):
        self._accounts.append(acc_id)
        
    def get_account(self):
        return self._accounts[0]


def main():
    global sysx
    global accounts,persons,dryrun
    

    dryrun=False
    
    try:
        opts,args=getopt.getopt(sys.argv[1:],'d',['dryrun'])
    except getopt.GetoptError,m:
        print "Unknown option: %s" % (m)
        usage()

    ret=0
    update=0
    for opt,val in opts:
        if opt in ('--dryrun'):
            dryrun=True    
   
    sysx=SYSX()
    sysx.list()
    logger.info("Got %d persons from file" % len(sysx.sysxids))
    persons,accounts=get_existing_accounts()

    build=Build()
    build.process_all()  
    
    if dryrun:
        logger.info("Dryrun: Rollback all changes")
        db.rollback()
    else:
        logger.info("Committing all changes to database")
        db.commit()
        

def usage():
    print __doc__
    sys.exit(1)


if __name__=='__main__':
    main()

