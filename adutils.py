#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright 2003 University of Oslo, Norway
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

import socket
import re
import time

import cerebrum_path
import cereconf
from Cerebrum.Utils import Factory
from Cerebrum import Errors
from Cerebrum import Entity
from Cerebrum import QuarantineHandler
from Cerebrum.modules import MountHost

db = Factory.get('Database')()
co = Factory.get('Constants')(db)
account = Factory.get('Account')(db)
person = Factory.get('Person')(db)
moho = MountHost.MountHost(db)
disk = Factory.get('Disk')(db)
host = Factory.get('Host')(db)
quarantine = Entity.EntityQuarantine(db)
ou = Factory.get('OU')(db)
logger = Factory.get_logger(cereconf.DEFAULT_LOGGER_TARGET)



class SocketCom(object):
    """Class for Basic socket communication to connect to the ADserver"""

    p = re.compile('210 OK')
    s = re.compile('(&pass&.+)&|(&pass&.+)\n')
    
    def __init__(self):
        self.connect()

        
    def connect(self):    
        try:
            self.sockobj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sockobj.connect((cereconf.AD_SERVER_HOST, cereconf.AD_SERVER_PORT))
            logger.debug("Connected")
            logger.debug(">> %s" % self.sockobj.recv(8192).strip())
            logger.debug("<< Authenticating")
            self.sockobj.send(cereconf.AD_PASSWORD)
            self.read()
            logger.debug("Connecting to:%s %s" % (cereconf.AD_SERVER_HOST, cereconf.AD_SERVER_PORT))    
        except Exception,m:
            logger.fatal("Failed connecting to:%s %s: Reason:%s" % (cereconf.AD_SERVER_HOST, cereconf.AD_SERVER_PORT, m))
            raise 


    def send(self, message):
        m = self.s.search(message)
        if m:
            if not m.group(2):
                gr=1
            else:
                gr=2            
            logger.debug('<< %s&pass&XXXXXXXX%s' % (message[0:m.start(gr)],message[m.end(gr):-1]))
        else:
            logger.debug("<< %s" %  message.strip())
        self.sockobj.send(message)
        

    def read(self,out=1):
        received = []
        rec = []

        while 1:
            data = self.sockobj.recv(8192)
            if data[3] != '-': break
            m=self.p.search(data)
            if m: break
            received.append(data)
        received.append(data)
        #process data
        for i in received:
            rec.append(i.strip())                       
        if out:     
            for elem in rec:
                 logger.debug('>> %s' % elem)
        return rec    

    def readgrp(self,out=1):
        received = []
        rec = ''
        while 1:
            data = self.sockobj.recv(8192)
            m=self.p.search(data)
            if m: 
                break
            else:
                received.append(data)
        received.append(data)
        #process data
        for i in received:
            i.strip()
            rec = '%s%s' % (rec,i)                      
        if out:     
            logger.debug('>> %s' % rec)
        return rec    

    def close(self):
        logger.debug("Finished, ending session")
        self.sockobj.send("QUIT\n")
        self.sockobj.close()


def now():
    return time.ctime(time.time())


#Shared procedures for adsync and adquicksync.

def get_user_info(account_id, account_name, spread):

    home_dir = find_home_dir(account_id, account_name, spread)
    #login_script = find_login_script(account_name)
    profile_path = find_profile_path(account_id,account_name, spread)
        
    account.clear()
    account.find(account_id)
    try:
        person_id = account.owner_id
        person.clear()
        person.find(person_id)
        full_name = person.get_name(int(co.system_cached), int(co.name_full)) 
        if not full_name:
            logger.debug('getting persons full_name failed, account.owner_id: %s' % person_id)
    except Errors.NotFoundError:        
        #This account is missing a person_id.
        full_name = account.account_name
        
    account_disable = '1'
    if not account.is_expired():
        account_disable='0'
    #if account.has_spread(int(co.spread_uit_fd)):
    #    if not chk_quarantine(account_id):
    #        account_disable = '0'       

    return (full_name, account_disable, home_dir, cereconf.AD_HOME_DRIVE, profile_path)


def chk_quarantine(account_id):
    # Check against quarantine.
    quarantine.clear()
    quarantine.find(account_id)
    quarantines = quarantine.get_entity_quarantine(only_active=True)
    qua = []
    for row in quarantines:
        qua.append(row['quarantine_type']) 
    qh = QuarantineHandler.QuarantineHandler(db, qua)
    try:
        if qh.is_locked():           
            return True
    except KeyError:
        pass
    return False        


def get_primary_ou(account_id):
    account.clear()
    account.find(account_id)
    acc_types = account.get_account_types()
    if acc_types:
        return acc_types[0]['ou_id']
    return None


def get_ad_ou(ldap_path):
    ou_list = []
    p = re.compile(r'OU=(.+)')
    ldap_list = ldap_path.split(',')
    for elem in ldap_list:
        ret = p.search(elem)
        if ret:
            ou_list.append(ret.group(1))
    return ou_list


def get_crbrm_ou(ou_id):
     ou.clear()
     ou.find(cereconf.AD_CERE_ROOT_OU_ID)       
     return 'OU=%s' % ou.acronym
        
#    Do not use OU placement at UiO.
#    try:      
#        ou.clear()
#        ou.find(ou_id)
#        path = ou.structure_path(co.perspective_lt)
#        #TBD: Utvide med spread sjekk, OUer uten acronym, problem?
#        return 'OU=%s' % path.replace('/',',OU=')
#    except Errors.NotFoundError:
#        logger.debug("Could not find OU with id: %s" % ou_id)


def id_to_ou_path(ou_id,ourootname):
    crbrm_ou = get_crbrm_ou(ou_id)
    if crbrm_ou == ourootname:
        if cereconf.AD_DEFAULT_OU == '0':
            crbrm_ou = 'CN=Users,%s' % ourootname
        elif cereconf.AD_DEFAULT_OU == '-1':
            crbrm_ou = ourootname
        else:
            crbrm_ou = get_crbrm_ou(cereconf.AD_DEFAULT_OU)

    crbrm_ou = crbrm_ou.replace(ourootname,cereconf.AD_LDAP)
    return crbrm_ou

def find_home_dir(account_id, account_name, disk_spread):

    return '\\\\fdtop.fd.uit.no\\share\\homes\\%s' % (account_name)

#     try:
#         account.clear()
#         account.find(account_id)
#         disk.clear()
#         disk_id=account.get_home(disk_spread)
#         disk.find(disk_id['disk_id'])
#         try:
#             moho.clear()        
#             moho.find(disk.host_id)     
#             home_srv = moho.mount_name                  
#         except Errors.NotFoundError:
#             host.clear()
#             host.find(disk.host_id)
#             home_srv = host.name
#         return "\\\\%s\\%s" % (home_srv,account_name)
#     except Errors.NotFoundError:
#         logger.debug("Failure finding the disk of account: %s" % account_id)
        

def find_profile_path(account_id,account_name,disk_spread):
    return '\\\\fdtop.fd.uit.no\\share\\profiles\\%s' % (account_name)


def find_login_script(account):
    #This value is a specific UIT standard.
    return ""


if __name__ == '__main__':
    pass

# arch-tag: 9b05a07d-6348-44f5-bbbd-ca027cc515cc
