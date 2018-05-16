#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

# This is a python port of the PRISS pq daemon.
#
#   This daemon is the backend for the PRISS Quota system. It listens
#   to port 'prissquota' (8106) on the ureg2000 machine and resolves
#   incoming requests. The requests are resolved against the UREG2000
#   Oracle database running on this host.

# TODO:  If the database is down, return ok for all commands

import SocketServer
import socket
import signal
import os
from time import gmtime, strftime, time
import pwd

import cerebrum_path

from Cerebrum import Errors
from Cerebrum.modules.no.uio import PrinterQuotas
from Cerebrum.Utils import Factory

rev = '$Revision$'
rev = rev[rev.find(" ")+1:]
rev = rev[:rev.find(" ")]
# 2NN answers, meaning last command was a success.
helo    = "220 PRISS Quota Daemon V%s ready" % rev
firstok = "250 Nice to meet you,"
ok      = "250 OK"
no      = "251 NO"
quota_values = "252 "
bye     = "280 Bye"
#
# 5NN answers, meaning last command caused problems
edbdown  = "511 Database down"
ebadpage = "512 Invalid pagecount"
enouser  = "513 No such user"
ecmd     = "514 Unknown command"
eerror   = "515 Unknown error"

# pqdlog = "/u2/log/priss/prissquotad"
pqdlog = "/cerebrum/var/log/prissquotad"
db = Factory.get('Database')()
my_pid = os.getpid()

class MyServer(SocketServer.TCPServer):
    allow_reuse_address = 1    # Seems to make sense in testing environment

# class RequestHandler(SocketServer.BaseRequestHandler):
class RequestHandler(SocketServer.StreamRequestHandler):
    def process_commands(self):
        self.send(helo)
        cmd = self.get()

        # Our first input line must be of the type
        #    HELO username hostname
        #
        if not (len(cmd) == 3 and cmd[0] == "HELO") :
            self.log('ERROR', "HELO expected %s received" % cmd);
            self.send("%s %s" % (ecmd, str(cmd)));
            return
        else:
            # Get information based on username
            try:
                account = Factory.get('Account')(db)
                account.clear()
                account.find_by_name(cmd[1])
            except Errors.NotFoundError:
                self.log('ERROR', "Invalid username %s from %s" % (
                    cmd[1], self.client_address))
                self.send(enouser)
                return
            try:
                pq = PrinterQuotas.PrinterQuotas(db)
                pq.find(account.entity_id)
            except Errors.NotFoundError:
                self.log('TRACE', "%s / %i has no quota" % (cmd[1],  account.entity_id))
                pq = None  # User has no quota
                pass
            self.log('INFO', "HELO %s %s from %s" % (
                cmd[1], cmd[2], self.client_address))
            self.send("%s %s." % (firstok, cmd[1]))
            self.printer_quota = pq
            
            done = 0
            while not done:
                cmd = self.get()
    
                if not cmd[0]:
                    self.log('ERROR', "Connection down? !")
                    self.send(eerror)
                    done = 1
                elif cmd[0] == 'QUERYPQ':
                    tmp = "%s;%s;%s;%s;%s;%s;%s" % (
                        pq.printer_quota,
                        pq.pages_printed,
                        pq.pages_this_semester,
                        pq.termin_quota,
                        pq.has_printerquota,
                        pq.weekly_quota,
                        pq.max_quota)
                    self.send("%s%s" % (quota_values, tmp))
                elif cmd[0] == 'QUIT':
                    self.send(bye)
                    done = 1
                elif cmd[0] == 'CANP' and len(cmd) == 3:
                    self.send(self.check_quota(cmd[1], cmd[2]))
                elif cmd[0] == 'SUBP' and len(cmd) == 3:
                    self.send(self.subtract_quota(cmd[1], cmd[2]))
                else:
                    self.log('ERROR', "Unknown command %s" %  str(cmd))
                    self.send(ecmd)
                    done = 1

    def alarm_handler(self, signum, frame):
        raise IOError, "Timout"
        
    def handle(self):
        signal.alarm(30)
        signal.signal(signal.SIGALRM, self.alarm_handler)
        try:
            self.process_commands()
        except IOError, msg:
            self.log('ERROR', "IOError: %s" % msg)
        except ValueError, msg:
            self.log('ERROR', "ValueError: %s" % msg)
            self.send(ebadpage)
        signal.alarm(0)
            
    def check_quota(self, printer, pageunits):
        # check_quota() - Given a username (username from HELO), and a positive
        #                 number of pageunits, it will use SQL to check that
        #                 the user has enough pages on his quota to cover at
        #                 one page at this pageunit. The printername is purely
        #                 for logging purposes.
        #
        # Possible &send() feedback: ok, no, edbdown, badpage

        if (self.printer_quota is None or
            self.printer_quota.has_printerquota in (None, '0', 'F')):
            return ok
        pageunits = float(pageunits)
        self.log('TRACE', 'check_quota: %s@%s %s' % (
            pageunits, printer, self.printer_quota.account_id))
        if pageunits <= 0:
            return ebadpage
        if (self.printer_quota is None) or (self.printer_quota.printer_quota >= pageunits):
            return ok
        return no

    def subtract_quota(self, printer, pageunits):
        # A LOT of printers don't have page accounting, and even though
        # this should be filtered out at an earlier stage it miiight
        # happen that we get a request to subtract 0 pages. Just OK that.
        pageunits = float(pageunits)
        if pageunits == 0:
            self.log('TRACE', "subtract_quota: 0_PAGE_REQUEST")
            return ok
        if pageunits < 0:
            self.log('TRACE', "subtract_quota: BAD_PAGE")
            return ebadpage

        if self.printer_quota is None:
            return ok

        self.log('TRACE', "subtract_quota: %s for %i" % (
            pageunits, self.printer_quota.account_id))
        self.printer_quota.pages_printed += pageunits
        self.printer_quota.printer_quota -= pageunits
        self.printer_quota.write_db()
        db.commit()
        return ok        

    # send(line) - send a line (terminated by CR NL)
    def send(self, msg):
        self.wfile.write("%s^M\n" % msg)

    # @foo = &get; - Returns a list of tokens
    def get(self):
        return self.rfile.readline().rstrip().split()

    def log(self, lvl, msg):
        f = file(pqdlog, "a")
        f.write("%s [%s] %s %s\n" % (strftime("%Y-%m-%d %H:%M:%S", gmtime()), my_pid, lvl, msg))
        f.close()

if __name__ == '__main__':
    server = MyServer(('', socket.getservbyname("prissquota", "tcp")), RequestHandler)
    server.serve_forever()

