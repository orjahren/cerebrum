# -*- coding: iso-8859-1 -*-
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

import time
import os
import sys
import getopt
import mx
from mx import DateTime
__doc__="""
Uit specific extension for Cerebrum. Read data from SystemX
"""

import cerebrum_path
import cereconf

class SYSX:

    _default_datafile = os.path.join(cereconf.DUMPDIR,'System_x','guest_data')
    _guest_host = cereconf.GUEST_HOST
    _guest_host_dir = cereconf.GUEST_HOST_DIR
    _guest_host_file = cereconf.GUEST_HOST_FILE
    _guest_file = cereconf.GUEST_FILE
    today=str(mx.DateTime.today())
    
    sysxids = {}
    sysxfnrs = {}
    SPLIT_CHAR=':'

    def __init__(self,data_file=None,update=False):
                
        if data_file:
            self.sysx_data = data_file
        else:
            self.sysx_data = self._default_datafile
        
        if update:
            self._update()


    def read_from_sysx(self):
        url = "http://%s%s%s" % (
            self._guest_host, 
            self._guest_host_dir,
            self._guest_host_file) 
        target_file = self.sysx_data
        print "read from: %s" % url
        print "write to: %s" % target_file
        try:        
            import urllib
            fname,headers = urllib.urlretrieve(url,target_file)
        except Exception,m:
            print "Failed to get data from %s: reason: %s" % (url,m)
            return 0
        else:
            return 1


    def load_sysx_data(self):
        data = []
        file_handle = open(self.sysx_data,"r")
        lines = file_handle.readlines()
        file_handle.close()
        for line in lines:
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue
            data.append(line)
        return data


    def _prepare_data(self,data_list):
        data_list = data_list.rstrip()
        try:
            id,fodsels_dato,personnr,gender,fornavn,etternavn,ou, \
            affiliation,affiliation_status,expire_date,spreads,hjemmel, \
            kontaktinfo,ansvarlig_epost,bruker_epost,national_id, \
            approved = data_list.split(self.SPLIT_CHAR) 
        except ValueError,m:
            self.logger.error("data_list:%s##%s" % (data_list,m))
            sys.exit(1)
        else:
            if spreads:
                spreads=spreads.split(',')
            else:
                spreads=[]
            return {'id': id,
                    'fodsels_dato': fodsels_dato,
                    'personnr': personnr,
                    'gender': gender,
                    'fornavn': fornavn.strip(),
                    'etternavn': etternavn.strip(),
                    'ou': ou,
                    'affiliation':affiliation,
                    'affiliation_status': affiliation_status.lower(),
                    'expire_date':expire_date,
                    'spreads': spreads,
                    'ansvarlig_epost':ansvarlig_epost,
                    'bruker_epost':bruker_epost,
                    'national_id': national_id,
                    'approved':approved }


    def _update(self):
        return self.read_from_sysx()


    def list(self,filter_expired=True,filter_approved=False):
        self._load_data(filter_expired=filter_expired)


    def _load_data(self,update=False,filter_expired=True):
        if update: self._update()
        for item in self.load_sysx_data():
            sysx_data = self._prepare_data(item)
            if filter_expired:
                if sysx_data['expire_date']<self.today:
                    continue
            self.sysxids[sysx_data['id']]=sysx_data
            if sysx_data['personnr']:
                self.sysxfnrs[sysx_data['personnr']]=sysx_data                
        
        
def usage():
    print __doc__
        
def main():   
    do_update=False
    filter_expired=False
    try:   
        opts,args = getopt.getopt(sys.argv[1:],'uhf',
            ['update','help','filter_expired'])
    except getopt.GetoptError,m:
        print "Unknown option: %s" % (m)
        usage()
        
    for opt,val in opts:
        if opt in ('-h','--help'):
            usage()
        elif opt in ('-u','--update'):
            do_update = True
        elif opt in ('-f','--filter_expired'):
            filter_expired = True

    sysx = SYSX(update=do_update)
    sysx.list(filter_expired=filter_expired)
    print "SYS_IDs: %d" % len(sysx.sysxids)
    print "SYS_Fnrs: %d" % len(sysx.sysxfnrs)
    
if __name__ == '__main__':
    main()

