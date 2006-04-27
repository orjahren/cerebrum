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

# $Id$

# This is an example of scheduling settings that can be used in a
# cerebrum installation.  See the documentation for job_runner for
# details.
import time
import ftplib
from Cerebrum.modules.job_runner.job_actions import *
from Cerebrum.modules.job_runner.job_utils import When, Time

def get_jobs():
    sbin = '/cerebrum/share/cerebrum/contrib/no/uit'
    ypsrc = '/cerebrum/yp/src'
    etc = '/cerebrum/etc/cerebrum'
    contrib_uit='/cerebrum/share/cerebrum/contrib/no/uit'
    dumps='/cerebrum/var/dumps'
    source='/cerebrum/var/source'
    date = time.localtime()
    year = date[0]
    month = date[1]
    day = date[2]
    time_stamp= "%02d%02d%02d" % (year,month,day)
    print "time_stamp =%s" % time_stamp
    return {
        ##################################
        # generate import files          #
        ##################################

        # generate import files for students

        'import_from_fs':  Action(call=System('%s/import_from_FS.py' % contrib_uit,
                                              params=['--db-user=fsbas', '--db-service=fsprod','-s','-o','-p','-f','-e','-u','-U','-r']),max_freq=60,pre=None),

        'update_fnr' : Action(pre =['import_from_fs'],
                              call=System('%s/fnr_update.py' % contrib_uit,
                                          params=['%s/FS/fnr_update.xml' % dumps]),max_freq=60),
        
        'update_undervenhet' : Action(pre=['update_fnr'],
                                      call=System('%s/undervenhet_update.py' % contrib_uit,
                                                  params=['-u','%s/FS/underv_enhet.xml' % dumps]),max_freq=60),

        'institution_update' : Action(pre=['update_undervenhet'],
                                      call=System('%s/institution_update.py' % contrib_uit,
                                                  params=['-E','/cerebrum/var/dumps/FS/emner.xml','-S','/cerebrum/var/dumps/FS/studieprog.xml']),max_freq=60),

        'merge_xml_files' : Action(pre=['institution_update'],
                                   call=System('%s/merge_xml_files.py' % contrib_uit,
                                               params=['-d','fodselsdato:personnr','-f','%s/FS/person.xml' % dumps,'-t','person','-o','%s/FS/merged_persons.xml'% dumps]),max_freq=60),

        # generate import files for employees

        'get_user_info' : Action(pre=None,
                                 call=System('%s/get_user_info.py' % contrib_uit),
                                 max_freq=60),
        
        'get_slp4_data' : Action(pre = ['get_user_info'],
                                 call=System('%s/get_slp4_data.py' % contrib_uit),
                                 max_freq=60),

        'parse_user_info' : Action(pre=['get_slp4_data'],
                                   call=System('%s/parse_user_info.py' % contrib_uit,
                                   params=['-e']),
                                   max_freq=60),

        'generate_persons' : Action(pre=['parse_user_info'],
                                    call=System('%s/generate_persons.py' % contrib_uit,
                                    params=['-t','AD']),
                                    max_freq=60),

        # generate ou files

        'generate_ou' : Action(pre=None,
                               call=System('%s/generate_OU.py' % contrib_uit,
                                           params=['-r','-f','%s/fs-sted.txt' % source,'-o','%s/stedkoder_v2.txt' % source,'-O','%s/ou/uit_ou_%s.xml' % (dumps,time_stamp)]),
                               max_freq=60),


        ###############################################
        # import data (xml files) to cerebrum         #
        ###############################################

        # import student data to cerebrum

        'import_FS' : Action(pre=['merge_xml_files'],
                             call=System('%s/import_FS.py' % contrib_uit,
                                         params=['-s','%s/FS/studieprog.xml' % dumps,'-p','%s/FS/merged_persons.xml' % dumps,'-g']),max_freq=60),


        # import employee data to cerebrum

        'import_LT' : Action(pre=['generate_persons'],
                             call=System('%s/import_LT.py' % contrib_uit,
                                         params=['-p','%s/employees/uit_persons_%s.xml'% (dumps,time_stamp)]),
                             max_freq=60),

        # import ou data to cerebrum
        'import_ou' : Action(pre=['generate_ou'],
                             call=System('%s/import_OU.py' % contrib_uit,
                                         params=['-v','-o','%s/ou/uit_ou_%s.xml' % (dumps,time_stamp),'--perspective=perspective_fs','--source-system=system_fs']),
                             max_freq=60),

        ####################################
        # cerebrum data processing         #
        ####################################

        # processing student data
        
        'process_students' : Action(call=System('%s/process_students.py' % sbin,
                                                params=['-C','/cerebrum/etc/cerebrum/studconfig.xml','-S','/cerebrum/var/dumps/FS/studieprog.xml','-s','/cerebrum/var/dumps/FS/merged_persons.xml','-c','-u','-e','/cerebrum/var/dumps/FS/emner.xml','--only-dump-results','result_file.txt','--workdir','/cerebrum/var/log']),
                                                max_freq=60),

        # processing employee data
        
        'process_employees' : Action(call=System('%s/process_employees.py' % contrib_uit,
                                                 params=['-f','%s/employees/uit_persons_%s.xml' % (dumps,time_stamp)]),
                                     max_freq=60),

        ################################
        # cerebrum export data         #
        ################################

        # cerebrum export to FRIDA
        'export_frida' : Action(pre=None,
                                call=System('%s/export_frida.py' % contrib_uit,
                                            params=['-p','%s/employees/uit_persons_%s.xml' % (dumps,time_stamp),'-s','%s/ou/uit_ou_%s.xml' % (dumps,time_stamp),'-o','%s/Frida/frida_%s.xml'%(dumps,time_stamp)]),
                                max_freq=60),

        'generate_fronter_groups' : Action(pre=None,
                                           call=System('%s/new_populate_external_groups.py' % contrib_uit),
                                           post=['export_fronter_xml'],
                                           max_freq=60),

        'export_fronter_xml' : Action(pre=None,
                                      call=System('%s/export_xml_fronter.py' % contrib_uit),
                                      post=['copy_fronter_xml'],
                                      max_freq=60),

        'export_ldap' : Action(pre=None,
                               call=System('%s/export_ldap.py' % contrib_uit),
                               max_freq=60,
                               post=['export_ldap_copy']),
        
        'export_sut' : Action(pre=None,
                              call=System('%s/export_sut.py' % contrib_uit,
                                           params=['-s','%s/sut/uit_persons_%s' % (dumps,time_stamp)]),
                              post=['copy_export_sut'],
                              max_freq=60),

        'copy_export_sut' : Action(pre=None,
                                   call=System('/usr/bin/scp',
                                               params=['%s/sut/uit_persons_%s' % (dumps,time_stamp) ,'root@flam.student.uit.no:/its/apache/data/sliste.dta']),
                                   max_freq=60),

        'export_ldap_copy' : Action(pre=None,
                                    call=System('%s/ldapmodify.py' % contrib_uit),
                                    max_freq=60,
                                    post=None),
        
        'copy_fronter_xml' : Action(pre=None,
                                    call=System('%s/copy_fronter.xml.py' % contrib_uit),
                                    max_freq=60,
                                    post=None),

        ###############
        # daily jobs  #
        ###############

       
        'daily_import_FS_LT' : Action(pre=['import_FS'],
                                    post=['import_LT']),

        #'daily_import_all' : Action(pre=['daily_import_FS_LT'],
        #                            post=['daily_import_OU']),
        
      
        'daily_import' : Action(pre=['import_ou'],
                             post=['daily_import_FS_LT']),
        
        'daily_process_students' : Action(pre=['daily_import'],
                                          post=['process_students']),

        'daily_process_employees' : Action(pre=['daily_import'],
                                          post=['process_employees']),

        

        'daily_process_all' : Action(pre=['daily_process_students'],
                                     call=None,
                                     post=['daily_process_employees']),
        

        'daily_export_all' : Action(pre=['daily_process_all'],
                                    call=None,
                                    post=['export_ldap','export_sut','generate_fronter_groups','export_frida']),

        'full_pupp' : Action(pre=None,
                             call=None,
                             when=When(time=[Time(min=[00],hour=[02])]),
                             post=['daily_process_all','daily_export_all']),

        
        'run_export_ldap' : Action(pre=None,
                                   call=System('%s/export_ldap.py' % contrib_uit),
                                   max_freq=60*5,when=When(freq=10*60),
                                   post=['export_ldap_copy']),

        'run_export_sut' : Action(pre=None,
                                  call=System('%s/export_sut.py' % contrib_uit,
                                              params=['-s','%s/sut/uit_persons_%s' % (dumps,time_stamp)]),
                                  max_freq=60*5,when=When(freq=10*60),
                                  post=['copy_export_sut']),
       
        'run_slurp' : Action(pre=None,
                             call=System('%s/slurp_x.py' % contrib_uit,
                                         params=['-s','%s/System_x/guest_data' % (dumps),'-u']),
                             when=When(time=[Time(min=[00],hour=[06])]),
                             post=None)

        # Kast gamle changelog entries hver l�rdag kl 06:00
        #'db_clean_changelog' = Action(pre=None,
        #                              call=System('%s/no/uio/db_clean.py' % contrib,
        #                                          params=['--changelog', '--logger-level=INFO']),
        #                              max_freq=3*24*60*60,
        #                              when = When(time=[Time(wday=[5], hour=[6], min=[0])]))

        
        #post=['export_frida','generate_fronter_groups','export_ldap','export_sut'])


       


        
        # 'import_ou':  Action(pre=['import_from_lt'],
#                              call=System('%s/import_OU.py' % sbin),
#                              max_freq=6*60*60),
#         'import_lt':  Action(pre=['import_ou', 'import_from_lt'],
#                              call=System('%s/import_LT.py' % sbin),
#                              max_freq=6*60*60),
#         'import_from_fs':  Action(call=System('%s/import_from_FS.py' % sbin),
#                                   max_freq=6*60*60),
#         'import_fs':  Action(pre=['import_from_fs'],
#                              call=System('%s/import_FS.py' % sbin),
#                              max_freq=6*60*60),
#         'process_students': Action(pre=['import_fs'],
#                                    call=System('%s/process_students.py' % sbin),
#                                    max_freq=5*60),
#         'backup': Action(call=System('%s/backup.py' % sbin),
#                          max_freq=23*60*60),
#         'rotate_logs': Action(call=System('%s/rotate_logs.py' % sbin),
#                               max_freq=23*60*60),
#         'daily': Action(pre=['import_lt', 'import_fs', 'process_students'],
#                         call=None,
#                         when=When(time=[Time(min=[10], hour=[1])]),
#                         post=['backup', 'rotate_logs']),
#         'generate_passwd': Action(call=System('%s/generate_nismaps.py' % sbin,
#                                               params=['--user_spread', 'NIS_user@uio',
#                                                       '-p', '%s/passwd' % ypsrc]),
#                                   max_freq=5*60),
#         'generate_group': Action(call=System('%s/generate_nismaps.py' % sbin,
#                                               params=['--group_spread', 'NIS_fg@ifi',
#                                                       '-g', '%s/group' % ypsrc]),
#                                  max_freq=15*60),
#         'convert_ypmap': Action(call=System('make',
#                                             params=['-s', '-C', '/var/yp'],
#                                             stdout_ok=1), multi_ok=1),
#         'dist_passwords': Action(pre=['generate_passwd', 'convert_ypmap'],
#                                  call=System('%s/passdist.pl' % sbin),
#                                  max_freq=5*60, when=When(freq=10*60)),
#         'dist_groups': Action(pre=['generate_group', 'convert_ypmap'],
#                               call=System('%s/passdist.pl' % sbin),
#                               max_freq=5*60, when=When(freq=30*60))
        }

# arch-tag: b678d411-6b71-4c47-a5e6-4c2bf6b42d58
