from ceresync import config
from ceresync import errors
import SpineClient
import unittest
import os
import errno
import signal
import atexit
import types
import sys
import stat
import time

log = config.logger

class AlreadyRunning(Exception):
    """Thrown when the client is already running and the pid file exists"""
    def __init__(self, pidfile, pidfile_mtime):
        self.pidfile = pidfile
        Exception.__init__(self, "Already running for %s secs with pid file %s" % (int(time.time() - pidfile_mtime), pidfile))

class AlreadyRunningWarning(AlreadyRunning):
    """Thrown when the client is already running and the pid file exists,
    but has been running for less than an hour."""
    pass

def create_pidfile(pid_file):

    # I don't like setting sighandlers in such a hidden location, but I
    # didn't know of any better place to put it. The sighandler is required
    # because atexit doesn't work when the program is killed by a signal.
    oldhandler = signal.getsignal(signal.SIGTERM)
    def termhandler(signum, frame):
        print >>sys.stderr, "Killed by signal %d" % signum
        remove_pidfile(pid_file)
        if type(oldhandler) == types.FunctionType:
            oldhandler()
        elif oldhandler != signal.SIG_IGN:
            # Is this correct? sys.exit(1) here caused random segfaults,
            # but this might skip som cleanup stuff.
            os._exit(1)
    signal.signal(signal.SIGTERM, termhandler)

    pid_dir = os.path.dirname(pid_file)
    if not os.path.isdir(pid_dir):
        try:
            os.makedirs(pid_dir, 0755)
        except:
            pass # fdopen below will give a better error message

    try:
        pidfile = os.fdopen(os.open(pid_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL), 'w')
        # Make sure the pid file is removed when exiting.
        atexit.register(remove_pidfile, pid_file)
    except OSError, e:
        if e.errno == errno.EEXIST:
            try:
                mtime = os.stat(e.filename)[stat.ST_MTIME]
            except OSError, e:
                if e.errno == errno.ENOENT:
                    # Pidfile has been removed since we tried to create it.
                    # Warn and ignore.
                    raise AlreadyRunningWarning(e.filename, None)
                else:
                    raise
            if time.time() - mtime < 3600:
                # e.filename is less than an hour old. Just warn.
                raise AlreadyRunningWarning(e.filename, mtime)
            raise AlreadyRunning(e.filename, mtime)
        else:
            raise

    pidfile.write(str(os.getpid()) + "\n")
    pidfile.close()
    log.debug("Created pid file " + pid_file)
    return pid_file

def remove_pidfile(pid_file):
    if not os.path.exists(pid_file):
        return # File doesn't exist, nothing to do
    try:
        os.remove(pid_file)
    except OSError, e:
        # "No such file or directory" is OK, other errors are not
        if e.errno != errno.ENOENT:
            raise
    log.debug("Removed pid file " + pid_file)

class Sync:
    def __init__(self, incr=False, id=-1, auth_type=None):
        self.incr=incr
        self.auth_type= auth_type or config.get('sync','auth_type')

        # Create a pid file, and store the file name for use in the destructor
        self.pid_file = None # Make sure self.pid_file exists, in case create_pidfile() fails.
        self.pid_file = create_pidfile(config.get('sync', 'pid_file', "/var/run/cerebrum/ceresync.pid"))

        connection = SpineClient.SpineClient(config=config,
                                             logger=config.logger).connect()
        import SpineCore
        try:
            self.session = connection.login(config.get('spine', 'login'),
                                            config.get('spine', 'password'))
        except SpineCore.Spine.LoginError, e:
            raise errors.LoginError(e)

        encoding= config.get('sync','encoding', default='')
        if encoding != '':
            self.session.set_encoding(encoding)

        self.tr = self.session.new_transaction()
        self.cmd = self.tr.get_commands()
        self.view = self.tr.get_view()
        account_spread=config.get('sync', 'account_spread')
        group_spread=config.get('sync', 'group_spread')
        
        self.view.set_account_spread(self.tr.get_spread(account_spread))
        self.view.set_group_spread(self.tr.get_spread(group_spread))
        self.view.set_authentication_method(self.tr.get_authentication_type(self.auth_type))
        self.view.set_changelog(id)

    def __del__(self):
        try:
            for i in self.session.get_transactions():
                try: i.rollback()
                except: pass
        except: pass
        try: self.session.logout()
        except: pass
        if self.pid_file:
            remove_pidfile(self.pid_file)

    def set_authtype(self, auth_type):
        self.auth_type = auth_type
        self.view.set_authentication_method(self.tr.get_authentication_type(auth_type))

    def _do_get(self, objtype, incr):
        if incr is None:
            incr=self.incr
        if incr:
            m = "get_%ss_cl" % objtype
        else:
            m = "get_%ss" % objtype
        res=[]
        for obj in getattr(self.view, m)():
            obj.type=objtype
            config.apply_override(obj, objtype)
            config.apply_default(obj, obj.type)
            config.apply_quarantine(obj, obj.type)
            res.append(obj)
        return res
    
    def get_accounts(self, incr=None):
        return self._do_get("account", incr)
        
    def get_groups(self, incr=None):
        return self._do_get("group", incr)

    def get_persons(self, incr=None):
        return self._do_get("person", incr)        

    def get_ous(self, incr=None):
        return self._do_get("ou", incr)
    
    def close(self):
        self.tr.commit()
        self.session.logout()

# In windows, the only way to get both pipes and return value from a process is
# with using subprocess. Subprocess is not available under Python 2.3, so to
# also be able to support Python 2.3 (on Unix at least), we make a wrapper
# class using either subprocess or popen.Popen3
try:
    import subprocess
except ImportError:
    try:
        from popen2 import Popen3
    except ImportError:
        log.error("Neither subprocess nor a usable popen2 module was found.")
        sys.exit(1)
    class Process(object):
        def __init__(self, cmd):
            self.p= Popen3(cmd, capturestderr=True)
        def write(self, message):
            self.p.tochild.write(message)
            self.p.tochild.close()
        def read(self):
            return self.p.fromchild.read()
        def wait(self):
            return self.p.wait()
        def error(self):
            return self.p.childerr.read()
else:
    class Process(object):
        def __init__(self, cmd):
            PIPE= subprocess.PIPE
            self.p= subprocess.Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        def write(self, message):
            self.p.stdin.write(message)
            self.p.stdin.close()
        def read(self):
            return self.p.stdout.read()
        def wait(self):
            return self.p.wait()
        def error(self):
            return self.p.stderr.read()

class Pgp:
    def __init__(self, pgp_prog=None, enc_opts='', dec_opts='', keyid=None):
        pgp_prog= pgp_prog or config.get('pgp', 'prog')
        enc_opts= enc_opts or config.get('pgp', 'encrypt_opts')
        dec_opts= dec_opts or config.get('pgp', 'decrypt_opts')
        keyid= keyid or config.get('pgp', 'keyid')

        self.pgp_enc_cmd= [ pgp_prog,
            '--recipient', keyid,
            '--default-key', keyid,
        ] + enc_opts.split()
        self.pgp_dec_cmd= [pgp_prog] + dec_opts.split()
    def decrypt(self, cryptstring):
        if not cryptstring:
            return None
        p= Process(self.pgp_dec_cmd)
        try:
            p.write(cryptstring)
        except IOError, e:
            log.error(p.error())
            sys.exit(1)
        message= p.read()
        if p.wait() != 0:
            log.error(p.error())
            sys.exit(1)
        return message
    def encrypt(self, message):
        if not message:
            return None
        p= Process(self.pgp_enc_cmd)
        try:
            p.write(message)
        except IOError, e:
            log.error(p.error())
            sys.exit(1)
        cryptstring= p.read()
        if p.wait() != 0:
            log.error(p.error())
            sys.exit(1)
        return cryptstring

class PgpTestCase(unittest.TestCase):
    def setUp(self):
        self.p= Pgp()
        self.message= 'FooX123.-=/'

    def testEncrypt(self):
        e= self.p.encrypt(self.message).strip()
        assert e.startswith('-----BEGIN PGP MESSAGE-----') and \
            e.endswith('-----END PGP MESSAGE-----')

    def testEncryptDecrypt(self):
        cryptstring= self.p.encrypt(self.message)
        assert self.message == self.p.decrypt(cryptstring), \
                'encryption and decryption yield wrong result'

if __name__ == '__main__':
    unittest.main()
