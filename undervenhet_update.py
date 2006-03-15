#!/usr/bin/env python
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


''' This file is a UiT specific extension to Cerebrum
It inserts a fake undenhet info the emner 

'''


import cerebrum_path
import cereconf
import getopt
import sys


def insert_temp_undervenhet(undervenhet,message):
    #print "insert temp undervenhet."
    message +="***insert temp undervenhet***\n"

    try:
        file_handle = open(undervenhet,"r+")
        file_handle.seek(-15,2)

        # lets insert the following 2 lines at the end of the file
        file_handle.writelines("<undenhet institusjonsnr=\"186\" emnekode=\"FLS-007\" versjonskode=\"1\" emnenavnfork=\"Felles-007\" emnenavn_bokmal=\"Dette er en falsk undervisnings enhet\" faknr_kontroll=\"0\" instituttnr_kontroll=\"0\" gruppenr_kontroll=\"0\" terminnr=\"1\" terminkode=\"H�ST\" arstall=\"2005\"/>\n")
        file_handle.writelines("</undervenhet>")
        file_handle.close()
    except Exception,m:
        sys.write.stderr("Error updating %s file, error was: %s" % (undervenhet, m))
        
    #log_handle.writelines("insert_temp_undervenhet...done\n")
    return message


def main():
    try:
	opts,args = getopt.getopt(sys.argv[1:],'u:','undervenhet=')
    except getopt.GetoptError:
	usage()
	sys.exit()
    
#    log_path = "%s/%s" % (cereconf.CB_PREFIX,'var/log/')
#    log_file= "%s/%s" % (log_path,"sut.log")
#    log_handle = open (log_file,"w")
    undervenhet_file = 0
    message = ""
    for opt,val in opts:
	if opt in('-u','--undervenhet'):
	    undervenhet_file = val
    
    if(undervenhet_file != 0):
	message = insert_temp_undervenhet(undervenhet_file,message)
    else:
	usage()

def usage():
    print """Usage: python undervenhet_update.py -u <file>
    
	-u | --undervenhet:        inserts a temp undervenhet into the file given
    """
	


if __name__=='__main__':
    main()
        
# arch-tag: bb4c91a0-b426-11da-9f85-c955c31ee92c
