#!/usr/bin/env python2.2

# $Id$

# Simple script for changing a users password using a web based
# interface.

# The script uses two templates.
# - pform.html must contain the following form fields: newpass,
#   newpass2, pass, uname.  The field action must also be set.
# - receipt.html must contain the string @MSG@ which will be replaced
#   with a message describing how the operation went.

import cgi
# import cgitb; cgitb.enable(display=0, logdir="/tmp")
import xmlrpclib
import sys
import cStringIO
import traceback
sys.path.insert(0, "/etc/cerebrum")
import cereconf

def handle_request():
    form = cgi.FieldStorage()

    print "Content-type: text/html\n"
    
    if not form.has_key("action"):
        print get_tpl("pform.html")
    else:
        msg = change_password(form)
        tpl = get_tpl("receipt.html")
        print tpl.replace("@MSG@", msg)

def get_tpl(name):
    f = open("%s/%s" % (cereconf.TEMPLATE_DIR, name), 'rb')
    ret = ''
    while(1):
        line = f.readline()
        if line == '': break
        ret += line
    return ret

# 
# This part processes the password change request, including
# authentication, and handles any errors.
#

def change_password(dta):
    """Return a string with a message describing how the request went."""

    if cereconf.ENABLE_BOFHD_CRYPTO:
        # TODO: Check server cert
        from M2Crypto.m2xmlrpclib import Server, SSL_Transport
        svr = Server(cereconf.BOFH_URL,
                     SSL_Transport(), encoding='iso8859-1')
    else:
        svr = xmlrpclib.Server(cereconf.BOFH_URL, encoding='iso8859-1')
        
    # Simple sanity check of values
    for k in 'newpass', 'pass', 'uname':
        if dta.getfirst(k, '') == '':
            return "Field %s cannot be blank" % k
    if dta.getfirst('newpass') <> dta.getfirst('newpass2'):
        return "New passwords must be equal"
        
    try:
        secret = svr.login(dta.getfirst('uname'), dta.getfirst('pass'))
        svr.run_command(secret, "account_password", dta.getfirst('uname'),
                        dta.getfirst('newpass'))
    except xmlrpclib.Fault, m:
        if m.faultCode == 666:
            return "The operation did not succeed: <pre>%s</pre>" % m.faultString
        else:
            return _internalError(m.faultString, sys.exc_info())
    except:
        return _internalError('local error', sys.exc_info())
    return "Password changed OK!"

def _internalError(msg, stack):
    sys.stderr.write("passweb.py error: %s\nStack trace: %s" %
                     (msg,  _unhandledExceptionString(stack)))
    return "Internal error, debug information has been logged: %s" % msg

def _unhandledExceptionString(exceptiontuple):
    strfile = cStringIO.StringIO()
    exc_type, exc_value, exc_traceback = exceptiontuple
    strfile.write("Unhandled Exception Fault: %s %s\n" % (
        exc_type, exc_value
        ))
    traceback.print_exception(
        exc_type,
        exc_value,
        exc_traceback,
        None,
        strfile
        )
    return strfile.getvalue()

handle_request()
