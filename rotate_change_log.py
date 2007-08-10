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
import cerebrum_path
import cereconf
import os
import bz2
from Cerebrum.Utils import Factory
from Cerebrum.modules import ChangeLog
from Cerebrum.Constants import Constants

logger = Factory.get_logger("cronjob")

class access_log:

    def __init__(self,file_dump,change_type_list=None):
        
        self.db = Factory.get('Database')()
        self.constants = Factory.get('Constants')(self.db)

        # no_touch_change_type_id contains a list over change_type_id's which will not be deleted under any sircumstances.
        self.no_touch_change_type_id=(int(self.constants.account_create),
                                      int(self.constants.account_password),
                                      int(self.constants.quarantine_add),
                                      int(self.constants.quarantine_del),
                                      int(self.constants.person_create),
                                      int(self.constants.entity_add),
                                      int(self.constants.entity_ext_id_mod),
                                      int(self.constants.entity_ext_id_add),
                                      int(self.constants.group_create),
                                      int(self.constants.group_add),
                                      int(self.constants.ou_create))

        try:
            for change_type in change_type_list:
                if int(change_type) in self.no_touch_change_type_id:
                    logger.error("%s is not a valid change_type." % int(change_type))
                    sys.exit(1)
        except TypeError:
            # no change_type given
            self.logger.debug("No change type given as parameter to program")
        if(file_dump !=None):
            if not (os.path.isfile(file_dump)):
                self.file_handle=bz2.BZ2File(file_dump,"w")
                self.logger.debug("opening %s for writing" % file_dump)
            else:
               #file already exists. concatenate data
               self.file_handle=open(file_dump,"a")
               logger.debug("opening %s for appending" % file_dump)
        else:
            #no data will be stored in log files
            logger.debug("No dump file spesified")


    #get all change_ids we want to delete.
    def get_change_ids(self,date=None,change_program=None,change_type=None):
        #convert the type_list to a type_tuple
        type_tuple=()
        type_tuple=change_type
        log_rows =self.get_old_log_events(sdate=date,types=type_tuple,change_program=change_program)
        return log_rows

    def delete_change_ids(self,id_list):
        try:
            # we've had some trouble deleting entries from the change_log table when other scripts also tries
            # to update it. adding a lock table command to prevent this.
            self.db.query("lock table change_log")
            for row in id_list:
                self.file_handle.writelines("%s,%s,%s,%s,%s,%s,%s,%s\n" % (row['tstamp'],row['change_id'],row['subject_entity'],row['change_type_id'],row['dest_entity'],row['change_params'],row['change_by'],row['change_program']))
                self.db.remove_log_event(row['change_id'])
            self.file_handle.close()
        except AttributeError, m:
            logger.debug("No dump file has been given. deleting withouth taking backup")
            # unable to write to file. no log file has been given
        self.db.commit()
        

    def get_old_log_events(self, start_id=0, max_id=None, types=None,
                       subject_entity=None, dest_entity=None,
                       any_entity=None, change_by=None, sdate=None,change_program=None):
        if any_entity and (dest_entity or subject_entity):
            raise self.ProgrammingError, "any_entity is mutually exclusive with dest_entity or subject_entity"
        where = ["change_id >= :start_id"]
        bind = {'start_id': int(start_id)}
        if subject_entity is not None:
            where.append("subject_entity=:subject_entity")
            bind['subject_entity'] = int(subject_entity)
        if dest_entity is not None:
            where.append("dest_entity=:dest_entity")
            bind['dest_entity'] = int(dest_entity)
        if any_entity is not None:
            where.append("subject_entity=:any_entity OR "
                         "dest_entity=:any_entity")
            bind['any_entity'] = int(any_entity)
        if change_by is not None:
            where.append("change_by=:change_by")
            bind['change_by'] = int(change_by)
        if max_id is not None:
            where.append("change_id <= :max_id")
            bind['max_id'] = int(max_id)
        if types is not None:
            where.append("change_type_id IN("+", ".join(
                ["%s" % x for x in types])+")")
        if change_program is not None:
            where.append("change_program IN('"+"','".join(
                ["%s" % x for x in change_program])+"')")
        if self.no_touch_change_type_id is not None:
            where.append("change_type_id NOT IN("+",".join(
                ["%s" % x for x in self.no_touch_change_type_id])+")")
        if sdate is not None:
            where.append("tstamp < :sdate")
            bind['sdate'] = sdate
        where = "WHERE (" + ") AND (".join(where) + ")"
        logger.debug("WJHERE=%s" % where)
        return self.db.query("""
        SELECT tstamp, change_id, subject_entity, change_type_id, dest_entity,
               change_params, change_by, change_program
        FROM [:table schema=cerebrum name=change_log] %s
        ORDER BY change_id""" % where, bind, fetchall=False)


def main():
    
    try:
        opts,args = getopt.getopt(sys.argv[1:],'d:D:c:C:',['dump_file=','date=','change_program=','change_type=',])
    except getopt.GetoptError:
        usage()
        sys.exit(1)
    change_type=None
    dump_file=None
    date=None
    change_program=None
    change_type_list=None
    change_program_list=None
    for opt,val in opts:
        if opt in('-d','--dump_file'):
            dump_file= val
        if opt in('-D','--date'):
            date=val
        if opt in ('-c','change_program'):
            change_program=val
        if opt in ('-C','--change_type'):
            change_type=val

    if (date==None):
        usage()
        sys.exit(1)
    if((change_program==None)and(change_type==None)):
        usage()
        sys.exit(1)

    if(change_type):
        change_type_list = change_type.split(",")
    if(change_program):
        change_program_list = change_program.split(",")
    
    log = access_log(dump_file,change_type_list)
    id_list = log.get_change_ids(date,change_program_list,change_type_list)
    log.delete_change_ids(id_list)

def usage():
    print """
    Rotate_change_log removes entries from the change_log table.
    Usage: python rotate_change_log.py -D <date> [-d <file>] [-c <change_program>][-C <change_type>] | -c <change_program> | -C <change_type>]
    -d | --dump_file file : removed data will be dumped into this file. If no dump file is spesified,
                            the data will be lost.
    -D | --date           : All entries listed in change_program and change_type,
                            older than this date, will be deleted. format is: YYYY-MM-DD
    -c | --change_program : Comma sepparated list. All entries from these scripts will be deleted
    -C | --change_type    : Comma sepparated list. All entries of these change_types will be deleted.

    Note: --date must be used in conjunction with --change_program and/or --change_type.
    For historical reasons account_create and account_password entries will not be allowed deleted.
    The resulting log file (if any) will be stored in bz2 format
    """

if __name__=='__main__':
    main()

