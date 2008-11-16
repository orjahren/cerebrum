# -*- coding: iso-8859-1 -*-
# Copyright 2002-2008 University of Oslo, Norway
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

"""Driver-independent API for accessing databases."""

# TBD: Because the connect() factory function takes care of selecting
#      what DB-API driver should be used, the need for hardcoding
#      names of specific database module is reduced -- at least as
#      long as you're only accessing your Cerebrum database.
#
#      However, one might need to collect data from other databases,
#      possibly using a different driver; how could this best be
#      implemented?
#
#      Currently, the function can be told what Database subclass to
#      use in the DB_driver keyword argument.

import re
import sys
import os
from types import DictType, StringType
from cStringIO import StringIO
from mx import DateTime

import cereconf
from Cerebrum import Errors
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import SqlScanner
from Cerebrum.Utils import NotSet, read_password
from Cerebrum.extlib import db_row


# Exceptions defined in DB-API 2.0; the exception classes below are
# automatically added to the inheritance hierarchy of exception classes in
# dynamically imported driver modules. This way we can catch any kind of
# db-specific error exceptions by catching Cerebrum.Database.Error
# (db-independent).
#
# The problem here is that the MRO rules have been tightened from 2.4 to
# 2.5. The hierarchies as we used to build them (in r135) are no longer
# *consistent*. This is an error in 2.5. Furthermore, as of 2.5 in order to
# catch an exception, the type mentioned in the "except:"-clause has to be
# derived from BaseException. If it is not, *no* exception will match the said
# exception clause AND THIS WILL HAPPEN SILENTLY. Python 2.6 (or was it 2.7?)
# has a plan to warn about such constructs (and there is a bug report
# submitted on the issue). Please not that as of 2.5, the base class of
# CommonExceptionBase cannot be of type object (type(object) -> <type
# 'type'>), precisely because object does NOT inherit from BaseException.
#
# Furthermore with 2.4 and earlier, there may be a different __str__ before
# ours in the MRO, and we cannot always re-arrange the base classes to
# compensate (as of 2.5, CommonExceptionBase.__str__ will always be called)
class CommonExceptionBase(Exception):
    def __str__(self):
        # Call superclass' method to get the error message
        main_message = super(CommonExceptionBase, self).__str__()
        
        # Occasionally, we need to know what the offending sql is. This is
        # particularily practical in that case.
        body = [main_message,]
        for attr in ("operation", "sql", "parameters", "binds",):
            if hasattr(self, attr):
                body.append("%s=%s" % (attr, getattr(self, attr)))

        return "\n".join(body)
    # end __str__
# end CommonExceptionBase
    
class Warning(CommonExceptionBase):
    """Driver-independent base class of DB-API Warning exceptions.

    Exception raised for important warnings like data truncations while
    inserting, etc."""
    pass

class Error(CommonExceptionBase):
    """Driver-independent base class of DB-API Error exceptions.
    
    Exception that is the base class of all other error exceptions. You
    can use this to catch all errors with one single 'except'
    statement. Warnings are not considered errors and thus should not use
    this class as base."""
    pass

class InterfaceError(Error):
    """Driver-independent base class of DB-API InterfaceError exceptions.

    Exception raised for errors that are related to the database
    interface rather than the database itself."""
    pass

class DatabaseError(Error):
    """Driver-independent base class of DB-API DatabaseError exceptions.

    Exception raised for errors that are related to the database."""
# end class DatabaseError

class DataError(DatabaseError):
    """Driver-independent base class of DB-API DataError exceptions.

    Exception raised for errors that are due to problems with the
    processed data like division by zero, numeric value out of range,
    etc."""
    pass
class OperationalError(DatabaseError):
    """Driver-independent base class of DB-API OperationalError exceptions.

    Exception raised for errors that are related to the database's
    operation and not necessarily under the control of the programmer,
    e.g. an unexpected disconnect occurs, the data source name is not
    found, a transaction could not be processed, a memory allocation
    error occurred during processing, etc."""
    pass
class IntegrityError(DatabaseError):
    """Driver-independent base class of DB-API IntegrityError exceptions.

    Exception raised when the relational integrity of the database is
    affected, e.g. a foreign key check fails."""
    pass
class InternalError(DatabaseError):
    """Driver-independent base class of DB-API InternalError exceptions.

    Exception raised when the database encounters an internal error,
    e.g. the cursor is not valid anymore, the transaction is out of
    sync, etc."""
    pass
class ProgrammingError(DatabaseError):
    """Driver-independent base class of DB-API ProgrammingError exceptions.

    Exception raised for programming errors, e.g. table not found or
    already exists, syntax error in the SQL statement, wrong number of
    parameters specified, etc."""
    pass
class NotSupportedError(DatabaseError):
    """Driver-independent base class of DB-API NotSupportedError exceptions.

    Exception raised in case a method or database API was used which
    is not supported by the database, e.g. requesting a .rollback() on
    a connection that does not support transaction or has transactions
    turned off."""
    pass

API_EXCEPTION_NAMES = (
    "Warning", "Error", "InterfaceError", "DatabaseError",
    "DataError", "OperationalError", "IntegrityError",
    "InternalError", "ProgrammingError", "NotSupportedError")
"""Tuple holding the names of the standard DB-API exceptions."""

API_TYPE_NAMES = (
    "STRING", "BINARY", "NUMBER", "DATETIME")
"""Tuple holding the names of the standard types defined by the DB-API."""

API_TYPE_CTOR_NAMES = (
    "Date", "Time", "Timestamp", "DateFromTicks",
    "TimeFromTicks", "TimestampFromTicks", "Binary")
"""Tuple holding the names of the standard DB-API type constructors."""

class Cursor(object):
    """Driver-independent cursor wrapper class.

    Instances are created by calling the .cursor() method of an object
    of the appropriate Database subclass."""

    def __init__(self, db):
        self._db = db
        real = db.driver_connection()
        self._cursor = real.cursor()
        self._sql_cache = Cache.Cache(mixins=[Cache.cache_mru,
                                              Cache.cache_slots],
                                      size=100)
        self._row_class = None
        # Copy the Database-specific type constructors; these have
        # already been converted into static methods by
        # Database._register_driver_types().
        for ctor in API_TYPE_CTOR_NAMES:
            setattr(self, ctor, getattr(db, ctor))
        for exc_name in API_EXCEPTION_NAMES:
            setattr(self, exc_name, getattr(db, exc_name))

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 cursor object methods.
    #

    # Use the `property' type (new in Python 2.2) for easy access to
    # the default cursor's attributes.

    def _get_description(self): return self._cursor.description
    description = property(_get_description, None, None,
                           "DB-API 2.0 .read-only attribute 'description'.")
    def _get_rowcount(self): return self._cursor.rowcount
    rowcount = property(_get_rowcount, None, None,
                        "DB-API 2.0 read-only attribute 'rowcount'.")
    def _get_arraysize(self): return self._cursor.arraysize
    def _set_arraysize(self, size): self._cursor.arraysize = size
    arraysize = property(_get_arraysize, _set_arraysize, None,
                         "DB-API 2.0 read-write attribute 'arraysize'.")

    # .callproc() is optional, hence not implemented here.

    def close(self):
        """Do DB-API 2.0 .close()."""
        return self._cursor.close()

    def execute(self, operation, parameters=()):
        """Do DB-API 2.0 .execute()."""
        sql, binds = self._translate(operation, parameters)
        #
        # The Python DB-API 2.0 says that the return value of
        # .execute() is 'unspecified'; however, for maximum
        # compatibility with the underlying database module, we return
        # this 'unspecified' value anyway.
        try:
            try:
                return self._cursor.execute(sql, binds)
            finally:
                if self.description:
                    # Retrieve the column names involved in the query.
                    fields = [ d[0].lower() for d in self.description ]
                    # Make a db_row class that corresponds to this set of
                    # column names.
                    self._row_class = db_row.make_row_class(fields)
                else:
                    # Not a row-returning query; clear self._row_class.
                    self._row_class = None
        except self.DatabaseError, exc:
            # stuff extra information into the exception object, in case we
            # want to print this baby later.
            exc.operation = operation
            exc.sql = sql
            exc.parameters = repr(parameters)
            exc.binds = repr(binds)
            raise exc
    # end execute

    def _translate(self, statement, params):
        """Translate SQL and bind params to the driver's dialect."""
        if params:
            #
            # To ease this wrapper's job in converting the bind
            # parameters to the paramstyle required by the driver
            # module, we require `params' to be a mapping (even though
            # the DB-API allows both sequences and mappings).
            assert type(params) == DictType

            # None of the database engines understand _CerebrumCode,
            # so we convert them to plain integers to simplify usage.
            from Cerebrum.Constants import _CerebrumCode
            for k in params:
                if isinstance(params[k], _CerebrumCode):
                    params[k] = int(params[k])
        try:
            driver_sql, pconv = self._sql_cache[statement]
            return (driver_sql, pconv(params))
        except KeyError:
            pass
        out_sql = []
        pconv = self._db.param_converter()
        sql_done = False
        p_item = None
        for token, text in SqlScanner.SqlScanner(StringIO(statement)):
            translation = []
            if sql_done:
                #
                # Token found after end-of-statement indicator; raise
                # an error.  It's the caller's responsibility to feed
                # us one statement at a time.
                raise self.ProgrammingError, \
                      "Token '%s' found after end of SQL statement." % text
            elif p_item:
                #
                # We're in the middle of parsing an SQL portability
                # item; collect all of the item's arguments before
                # trying to translate it into the SQL dialect of this
                # Cursor's database backend.
                if token == SqlScanner.SQL_PORTABILITY_ARG:
                    p_item.append(text)
                    continue
                else:
                    #
                    # We've got all the portability item's arguments;
                    # translate them into a set of SQL tokens.
                    translation.extend(self._db.sql_repr(*p_item))
                    # ... and indicate that we're no longer collecting
                    # arguments for a portability item.
                    p_item = None
            if token == SqlScanner.SQL_END_OF_STATEMENT:
                sql_done = True
            elif token == SqlScanner.SQL_PORTABILITY_FUNCTION:
                #
                # Set `p_item' to indicate that we should start
                # collecting portability item arguments.
                p_item = [text]
            elif token == SqlScanner.SQL_BIND_PARAMETER:
                # The name of the bind variable is the token without
                # any preceding ':'.
                name = text[1:]
                if not params.has_key(name):
                    raise self.ProgrammingError, \
                          "Bind parameter %s has no value." % text
                translation.append(pconv.register(name))
            else:
                translation.append(text)
            if translation:
                out_sql.extend(translation)
        #
        # If the input statement ended with a portability item, no
        # non-SQL_PORTABILITY_ARG token has triggered inclusion of the
        # final p_item into out_sql.
        if p_item:
            out_sql.extend(self._db.sql_repr(*p_item))
            p_item = None
        driver_sql = " ".join(out_sql)
        # Cache for later use.
        self._sql_cache[statement] = (driver_sql, pconv)
        return (driver_sql, pconv(params))

    def executemany(self, operation, seq_of_parameters):
        """Do DB-API 2.0 .executemany()."""
        ret = None
        for p in seq_of_parameters:
            ret = self.execute(operation, p)
            if self.description is not None:
                # The operation created a result set; this constitutes
                # undefined behaviour for .executemany().
                raise self.ProgrammingError, \
                      ".executemany() produced result set."
        return ret
##        return self._cursor.executemany(operation, seq_of_parameters)

    def fetchone(self):
        """Do DB-API 2.0 .fetchone()."""
        return self._cursor.fetchone()

    def fetchmany(self, size=None):
        """Do DB-API 2.0 .fetchmany()."""
        if size is None:
            size = self.arraysize
        return self._cursor.fetchmany(size)

    def fetchall(self):
        """Do DB-API 2.0 .fetchall()."""
        return self._cursor.fetchall()

    # .nextset() is optional, hence not implemented here.

    def setinputsizes(self, sizes):
        """Do DB-API 2.0 .setinputsizes()."""
        return self._cursor.setinputsizes(sizes)

    def setoutputsize(self, size, column=None):
        """Do DB-API 2.0 .setoutputsize()."""
        if column is None:
            return self._cursor.setoutputsize(size)
        else:
            return self._cursor.setoutputsize(size, column)

    def driver_cursor(self):
        """Return the driver cursor object underlying this Cursor."""
        return self._cursor

    def __iter__(self):
        """Return iterator over the current query's results."""
        return RowIterator(self)

    def wrap_row(self, row):
        """Return `row' wrapped in a db_row object."""
        return self._row_class(row)

    def query(self, query, params=(), fetchall=True):
        """Perform an SQL query, and return all rows it yields.

        If the query produces any result, this can be returned in two
        ways.  In both cases every row is wrapped in a db_row object.

        1. If `fetchall' is true (the default), all rows are
           immediately fetched from the database, and returned as a
           sequence.

        2. If 'fetchall' is false, this method returns an iterator
           object, suitable for e.g. returning one row on demand per
           iteration in a for loop.  This approach can in some cases
           lead to much lower memory consumption.

        """

##         query = query.strip()
##         assert query.lower().startswith("select")
        
        if not fetchall:
            # If the cursor to iterate over is used for other queries
            # before the iteration is finished, things won't work.
            # Hence, we generate a fresh cursor to use for this
            # iteration.
            self = self._db.cursor()
        self.execute(query, params)
        if self.description is None:
            # TBD: This should only occur for operations that do
            # not return rows (e.g. "UPDATE" or "CREATE TABLE");
            # should we raise an exception here?
            return None
        if fetchall:
            # Return all rows, wrapped up in db_row instances.
            R = self._row_class
            return [ R(row) for row in self.fetchall() ]
        else:
            return iter(self)

    def query_1(self, query, params=()):
        """Perform an SQL query that should yield at most one row.

        Like query(), but:

        1. The method can raise the exceptions NotFoundError
           (indicating a query returned no rows) or TooManyRowsError
           (query returned more than one row).

        2. When the query returns a single row, but each returned row
           contains multiple columns, the method will return a single
           row object.

        3. Otherwise (i.e. the query returns a single row with a
           single column) the method will return the value within the
           row object (and not the row object itself)."""

        res = self.query(query, params)
        if len(res) == 1:
            if len(res[0]) == 1:
                return res[0][0]
            return res[0]
        elif len(res) == 0:
            raise Errors.NotFoundError, repr(params)
        else:
            raise Errors.TooManyRowsError, repr(params)

    def ping(self):
        """Check that communication with the database works.

        Do a database-side no-op with the cursor represented by this
        object.  The no-op should result in an exception being raised
        if the cursor is no longer able to communicate with the
        database.

        """
        self.execute("""SELECT 1 AS foo [:from_dual]""")


class RowIterator(object):
    def __init__(self, cursor):
        self._csr = cursor
        self._queue = []

    def __iter__(self):
        return self

    def next(self):
        if not self._queue:
            self._queue.extend(self._csr.fetchmany())
        if not self._queue:
            raise StopIteration
        row = self._queue.pop(0)
        return self._csr.wrap_row(row)


#
# Support for conversion from 'named' to the other bind parameter
# styles.
#
class convert_param_base(object):
    """Convert bind parameters to appropriate paramstyle."""

    __slots__ = ('map',)
    # To be overridden in subclasses.
    param_format = None

    def __init__(self):
        self.map = []

    def __call__(self, param_dict):
        #
        # DCOracle2 does not treat bind parameters passed as a list
        # the same way it treats params passed as a tuple.  The DB API
        # states that "Parameters may be provided as sequence or
        # mapping", so this can be construed as a bug in DCOracle2.
        return tuple([param_dict[i] for i in self.map])

    def register(self, name):
        return self.param_format % {'name': name}


class convert_param_nonrepeat(convert_param_base):
    __slots__ = ()
    def register(self, name):
        self.map.append(name)
        return super(convert_param_nonrepeat, self).register(name)

class convert_param_qmark(convert_param_nonrepeat):
    __slots__ = ()
    param_format = '?'

class convert_param_format(convert_param_nonrepeat):
    __slots__ = ()
    param_format = '%%s'


class convert_param_numeric(convert_param_base):
    __slots__ = ()
    def register(self, name):
        if name not in self.map:
            self.map.append(name)
        # Construct return value on our own, as it must include a
        # numeric index associated with `name` and not `name` itself.
        return ':' + str(self.map.index(name) + 1)


class convert_param_to_dict(convert_param_base):
    __slots__ = ()
    def __init__(self):
        # Override to avoid creating self.map; that's not needed here.
        pass

    def __call__(self, param_dict):
        # Simply return `param_dict` as is.
        return param_dict

class convert_param_named(convert_param_to_dict):
    __slots__ = ()
    param_format = ':%(name)s'

class convert_param_pyformat(convert_param_to_dict):
    __slots__ = ()
    param_format = '%%(%(name)s)s'


class Database(object):
    """Abstract superclass for database driver classes."""

    _db_mod = None
    """The name of the DB-API module to use, or a module object.

    Prior to first instantiation, this class attribute can be a string
    specifying the full name of the database module that should be
    imported.

    During the first instantiation of a Database subclass, that
    subclass's _db_mod attribute is set to the module object of the
    dynamically imported database driver module."""

    param_converter = None
    """The bind parameter converter class used by this driver class."""

    # Not sure that this is the proper default, but as a quick hack it
    # seems to work for us here in Norway.
    encoding = 'ISO_8859_1'
    """The default character set encoding to use."""

    def __init__(self, do_connect=True, *db_params, **db_kws):
        if self.__class__ is Database:
            #
            # The 'Database' class itself is purely virtual; no
            # instantiation is allowed.
            raise NotImplementedError, \
                  "Can't instantiate abstract class <Database>."
        # Figure out if we need to import the driver module.
        mod = self._db_mod or self.__class__.__name__
        if type(mod) == StringType:
            #
            # Yup, need to import; name of driver module is now in
            # `mod'.  All first-time instantiation magic is done in
            # _kickstart().
            self._kickstart(mod)

        self._db = None
        self._cursor = None

        self._connect_data = {}

        if do_connect:
            # Start a connection
            self.connect(*db_params, **db_kws)

    def _kickstart(self, module_name):
        """Perform necessary magic after importing a new driver module."""
        self_class = self.__class__
        # 
        # We're in the process of instantiating this subclass for the first
        # time; we need to import the DB-API 2.0 compliant module.
        self_class._db_mod = Utils.dyn_import(module_name)

        #
        # At the time of importing the driver module, that module's DB-API
        # compliant exceptions are made to inherit from the general-purpose
        # exceptions defined in this module.  This allows us to catch database
        # exceptions in a driver-independent manner.
        for name in API_EXCEPTION_NAMES:
            base = getattr(Utils.this_module(), name)
            exc = getattr(self._db_mod, name)
            if not issubclass(exc, base):
                # monkey patch "our" classes in. Be careful here wrt old-style
                # and new-style classes. Be mindful of the MRO, since we may
                # want our hooks to take precedence.
                exc.__bases__ += (base,)
            if hasattr(self_class, name):
                continue
            setattr(self_class, name, exc)
        #
        # The type constructors provided by the driver module should
        # be accessible as (static) methods of the database's
        # connection objects.
        for ctor_name in API_TYPE_CTOR_NAMES:
            if hasattr(self_class, ctor_name):
                #
                # There already is an implementation of this
                # particular ctor in this class, probably for a good
                # reason (e.g. the driver module doesn't supply this
                # type ctor); skip to next ctor.
##                 print "Skipping copy of type ctor %s to class %s." % \
##                       (ctor_name, self_class.__name__)
                continue
            f = getattr(self._db_mod, ctor_name)
            setattr(self_class, ctor_name, staticmethod(f))
        #
        # Likewise we copy the driver-specific type objects to the
        # connection object's class.
        for type_name in API_TYPE_NAMES:
            if hasattr(self_class, type_name):
                # Already present as attribute; skip.
##                 print "Skipping copy of type %s to class %s." % \
##                       (type_name, self_class.__name__)
                continue
            type_obj = getattr(self._db_mod, type_name)
            setattr(self_class, type_name, type_obj)
        #
        # Set up a "bind parameter converter" suitable for the driver
        # module's `paramstyle' constant.
        if self.param_converter is None:
            converter_name = 'convert_param_%s' % self._db_mod.paramstyle
            cls = getattr(Utils.this_module(), converter_name)
            self_class.param_converter = cls

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 module-level interface.
    #
    def connect(self, *params, **kws):
        """Connect to a database; args are driver-dependent."""
        if self._db is None:
            self._db = self._db_mod.connect(*params, **kws)
            #
            # Open a cursor; this can be used by most methods, so that
            # they won't have to open cursors all over the place.
            self._cursor = self.cursor()
        else:
            # TBD: Should probably use a standard DB-API exception
            # here.
            raise Errors.DatabaseConnectionError

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 connection object methods.
    #
    def close(self):
        """Close the database connection."""
        self._db.close()
        self._db = None

    def commit(self):
        """Perform a commit() on the connection this instance embodies."""
        return self._db.commit()

    def rollback(self):
        """Perform a rollback() on the connection this instance embodies."""
        return self._db.rollback()

    def cursor(self):
        """Generate and return a fresh cursor object."""
        return Cursor(self)

    ####################################################################
    #
    #   Methods corresponding to DB-API 2.0 cursor object methods.
    #
    #   These methods operate via this object default cursor.
    #
    def _get_description(self): return self._cursor.description
    description = property(_get_description, None, None,
                           "DB-API 2.0 .description for default cursor.")
    def _get_rowcount(self): return self._cursor.rowcount
    rowcount = property(_get_rowcount, None, None,
                        "DB-API 2.0 .rowcount for default cursor.")
    def _get_arraysize(self): return self._cursor.arraysize
    def _set_arraysize(self, size): self._cursor.arraysize = size
    arraysize = property(_get_arraysize, _set_arraysize, None,
                         "DB-API 2.0 .arraysize for default cursor.")

    def execute(self, operation, parameters=()):
        """Do DB-API 2.0 .execute() on instance's default cursor."""
        return self._cursor.execute(operation, parameters)

    def executemany(self, operation, seq_of_parameters):
        """Do DB-API 2.0 .executemany() on instance's default cursor."""
        return self._cursor.executemany(operation, seq_of_parameters)

    def fetchone(self):
        """Do DB-API 2.0 .fetchone() on instance's default cursor."""
        return self._cursor.fetchone()

    def fetchmany(self, size=None):
        """Do DB-API 2.0 .fetchmany() on instance's default cursor."""
        return self._cursor.fetchmany(size=(size or self.arraysize))

    def fetchall(self):
        """Do DB-API 2.0 .fetchall() on instance's default cursor."""
        return self._cursor.fetchall()

    def setinputsizes(self, sizes):
        """Do DB-API 2.0 .setinputsizes() on instance's default cursor."""
        return self._cursor.setinputsizes(sizes)

    def setoutputsize(self, size, column=None):
        """Do DB-API 2.0 .setoutputsize() on instance's default cursor."""
        if column is None:
            return self._cursor.setoutputsize(size)
        else:
            return self._cursor.setoutputsize(size, column)

    ####################################################################
    #
    #   Methods that does not directly correspond to anything in the
    #   DB-API 2.0 spec.
    #
    def driver_connection(self):
        """Return the unwrapped connection object underlying this instance."""
        return self._db

    def query(self, *params, **kws):
        """Perform an SQL query, and return all rows it yields.

        If the query produces any result, this can be returned in two
        ways.  In both cases every row is wrapped in a db_row object.

        1. If `fetchall' is true (the default), all rows are
           immediately fetched from the database, and returned as a
           sequence.

        2. If 'fetchall' is false, this method returns an iterator
           object, suitable for e.g. returning one row on demand per
           iteration in a for loop.  This approach can in some cases
           lead to much lower memory consumption.

        """

        return self._cursor.query(*params, **kws)

    def query_1(self, query, params=()):
        """Perform an SQL query that should yield at most one row.

        Like query(), but:

        1. The method can raise the exceptions NotFoundError
           (indicating a query returned no rows) or TooManyRowsError
           (query returned more than one row).

        2. When the query returns a single row, but each returned row
           contains multiple columns, the method will return a single
           row object.

        3. Otherwise (i.e. the query returns a single row with a
           single column) the method will return the value within the
           row object (and not the row object itself)."""

        return self._cursor.query_1(query, params)

    def pythonify_data(self, data):
        """Convert type of values in row to native Python types."""
        if isinstance(data, (list, tuple,
                             # When doing type conversions, db_row
                             # objects are treated as sequences.
                             db_row.abstract_row)):
            tmp = []
            for i in data:
                tmp.append(self.pythonify_data(i))
            # type(data) should not be affected by sequence conversion.
            data = type(data)(tmp)
        elif isinstance(data, dict):
            tmp = {}
            for k in data.keys():
                tmp[k] = self.pythonify_data(data[k])
            # type(data) should not be affected by dict conversion.
            data = type(data)(tmp)
        return data

    def nextval(self, seq_name):
        """Return a new value from sequence SEQ_NAME.

        The sequence syntax varies a bit between RDBMSes, hence there
        is no default implementation of this method."""

        return self.query_1("""
        SELECT [:sequence schema=cerebrum name=%s op=next]
        [:from_dual]""" % seq_name)

    def ping(self):
        """Check that communication with the database works.

        Force the underlying database driver module to raise an
        exception if the database communication channel represented by
        this object for some reason isn't working properly.

        """
        c = self.cursor()
        c.ping()
        c.close()

    def sql_repr(self, op, *args):
        """Translate SQL portability item to SQL dialect of this driver."""
        method = getattr(self, '_sql_port_%s' % op, None)
        if not method:
            raise self.ProgrammingError, "Unknown portability op '%s'" % op
        kw_args = {}
        for k, v in [x.split("=", 1) for x in args]:
            if k in kw_args:
                raise self.ProgrammingError, \
                      "Keyword argument '%s' use multiple times in '%s' op." \
                      % (k, op)
            kw_args[k] = v
        return method(**kw_args)

    def _sql_port_get_config(self, var):
        if not hasattr(cereconf, var):
            raise ValueError
        val = getattr(cereconf, var)
        if type(val) == str:
            return ["'%s'" % val]
        raise ValueError

    def _sql_port_get_constant(self, name):
        Constants = Utils.Factory.get('Constants')(self)
        return ["%d" % int(getattr(Constants, name))]

    def _sql_port_boolean(self, default=None):
        pass

    # FIXME: deprecated, moved to Utils
    def _read_password(self, database, user):
        return read_password(user, database)

    def sql_pattern(self, column, pattern, ref_name=None,
                    case_sensitive=NotSet):
        """Convert a pattern with wildcards into a tuple consisting of
        an SQL expression and the value for comparison.

        * If pattern is None, test for NULL.
        * The name of the reference variable defaults to the column
          name (without any table reference), and can be specified
          explicitly using ref_name.
        * case_sensitive can be explicitly True or False.  If unset,
          the search will be case sensitive if the pattern contains
          upper case letters.

        """
        if pattern is None:
            return "%s IS NULL" % column, pattern
        if ref_name is None:
            ref_name = column.split('.')[-1]
        if case_sensitive is NotSet:
            case_sensitive = pattern.lower() != pattern
        if not case_sensitive:
            pattern = pattern.lower()
            column = "LOWER(%s)" % column
        value = pattern.replace("*", "%")
        value = value.replace("?", "_")
        if not case_sensitive or '%' in value or '?' in value:
            operand = "LIKE"
        else:
            operand = "="
        return "%s %s :%s" % (column, operand, ref_name), value


class PostgreSQLBase(Database):
    """PostgreSQL driver base class."""

    rdbms_id = "PostgreSQL"

    def __init__(self, *args, **kws):
        for cls in self.__class__.__mro__:
            if issubclass(cls, PostgreSQLBase):
                return super(PostgreSQLBase, self).__init__(*args, **kws)
        raise NotImplementedError, \
              "Can't instantiate abstract class <PostgreSQLBase>."

    def _sql_port_table(self, schema, name):
        return [name]

    def _sql_port_sequence(self, schema, name, op):
        if op == 'next':
            return ["nextval('%s')" % name]
        elif op == 'current':
            return ["currval('%s')" % name]
        else:
            raise ValueError, 'Invalid sequnce operation: %s' % op

    def _sql_port_sequence_start(self, value):
        return ['START', value]

    def _sql_port_from_dual(self):
        return []

    def _sql_port_now(self):
        return ['NOW()']

class PgSQL(PostgreSQLBase):
    """PostgreSQL driver class."""

    _db_mod = "pyPgSQL.PgSQL"

    def connect(self, user=None, password=None, service=None,
                client_encoding=None):
        call_args = vars()
        del call_args['self']
        cdata = self._connect_data
        cdata.clear()
        cdata['call_args'] = call_args
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME
        if user is None:
            user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        if password is None and user is not None:
            password = read_password(user, service)
        cdata['real_user'] = user
        cdata['real_password'] = password
        cdata['real_service'] = service
        if client_encoding is None:
            client_encoding = self.encoding
        else:
            self.encoding = client_encoding

        super(PgSQL, self).connect(user=user, password=password,
                                   database=service,
                                   client_encoding=client_encoding,
                                   unicode_results=(client_encoding == 'UTF-8'))

        # Ensure that pyPgSQL and PostgreSQL client agrees on what
        # encoding to use.
        if client_encoding is not None:
            if isinstance(client_encoding, str):
                enc = client_encoding
            elif isinstance(client_encoding, tuple):
                enc = client_encoding[0]
            self.execute("SET CLIENT_ENCODING TO '%s'" % client_encoding)
            # Need to commit here, and as no real work has been done
            # yet, it should be safe.
            #
            # Without an explicit COMMIT, a ROLLBACK (either explicit
            # or implicit, e.g. as the result of some statement
            # causing a failure) will reset the PostgreSQL's client to
            # CLIENT_ENCODING = 'default charset for database'.
            self.commit()

        # self.numericType is used by spine to test whether to
        # auto-convert query-results to int.
        self.numericType = self._db_mod.PgNumeric

    # According to its documentation, this driver module implements
    # the Binary constructor as a method of the connection object.
    #
    # The reason given for this deviance from the DB-API specification
    # is that in PostgreSQL, Large objects has no meaning outside the
    # context of a connection.
    #
    # However, as it turns out, the connection object of this driver
    # doesn't really have a Binary constructor, either.  Thus, the
    # best we can do is to raise a NotImplementedError. :-(
    def Binary(string): raise NotImplementedError
    Binary = staticmethod(Binary)

    def pythonify_data(self, data):
        """Convert type of value(s) in data to native Python types."""
        if isinstance(data, self._db_mod.PgNumeric):
            if data.getScale() > 0:
                data = float(data)
            elif data <= sys.maxint:
                data = int(data)
            else:
                data = long(data)
            # Short circuit, no need to involve super here.
            return data
        return super(PgSQL, self).pythonify_data(data)


class PsycoPGBase(PostgreSQLBase):
    """PostgreSQL driver class using psycopg."""

    # This is a base class for psycopg-driver family. Set to the appropriate
    # value in the subclasses.
    # _db_mod = None
    
    def connect(self, user=None, password=None, service=None,
                client_encoding=None, host=None, port=None):
        dsn = []
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME
        if user is None:
            user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        if host is None:
            host = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('host')
        if port is None:
            port = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('port')
        if password is None and user is not None:
            password = read_password(user, service, host)
        
        if service is not None:
            dsn.append('dbname=' + service)
        if user is not None:
            dsn.append('user=' + user)
        if password is not None:
            dsn.append('password=' + password)
        if host is not None:
            dsn.append('host=' + host)
        if port is not None:
            dsn.append('port=' + str(port))

        dsn_string = ' '.join(dsn)

        if client_encoding is None:
            client_encoding = self.encoding
        else:
            self.encoding = client_encoding

        super(PsycoPGBase, self).connect(dsn_string)
        self._db.set_isolation_level(1)  # read-committed
        self.execute("SET CLIENT_ENCODING TO '%s'" % client_encoding)
        self.commit()

        # self.numericType is used by spine to test whether to
        # auto-convert query-results to int.
        self.numericType = self._db_mod.NUMBER

    def cursor(self):
        return PsycoPGCursor(self)


class PsycoPG1(PsycoPGBase):
    _db_mod = "psycopg"
# enc class PsycoPG1


class PsycoPG2(PsycoPGBase):
    _db_mod = "psycopg2"

    def cursor(self):
        return PsycoPG2Cursor(self)
# end class PsycoPG2            


class PsycoPGCursor(Cursor):
    def execute(self, operation, parameters=()):
        # IVR 2008-10-30 TBD: This is not really how the psycopg framework
        # is supposed to be used. There is an adapter mechanism, and we should
        # really register our type conversion hooks there.
        for k in parameters:
            if type(parameters[k]) is DateTime.DateTimeType:
                parameters[k] = self.TimestampFromTicks(parameters[k].ticks())
            elif (type(parameters[k]) is unicode and
                  self._db.encoding != 'UTF-8'):
                # pypgsql1 does not support unicode (only utf-8)
                parameters[k] = parameters[k].encode(self._db.encoding)
        if (type(operation) is unicode and
                self._db.encoding != 'UTF-8'):
                operation = operation.encode(self._db.encoding)

        # A static method is slightly faster than a lambda.
        def utf8_decode(s):
            """Converts a str containing UTF-8 octet sequences into
            unicode objects."""
            return s.decode('UTF-8')

        ret = super(PsycoPGCursor, self).execute(operation, parameters)
        self._convert_cols = {}
        if self.description is not None:
            for n in range(len(self.description)):
                if (self.description[n][1] == self._db.NUMBER and
                    self.description[n][5] <= 0):  # pos 5 = scale in DB-API spec
                    self._convert_cols[n] = long
                elif (self._db.encoding == 'UTF-8' and
                      self.description[n][1] == self._db.STRING):
                    self._convert_cols[n] = utf8_decode
        return ret

    def query(self, query, params=(), fetchall=True):
        # The PsycoPG driver returns floats for all columns of type
        # numeric.  The PyPgSQL driver only does this if the column is
        # defined to have digits.  This method makes PsycoPG behave
        # the same way
        ret = super(PsycoPGCursor, self).query(
            query, params=params, fetchall=fetchall)
        if fetchall and self._convert_cols:
            for r in range(len(ret)):
                for n, conv in self._convert_cols.items():
                    if ret[r][n] is not None:
                        ret[r][n] = conv(ret[r][n])
        return ret

    def wrap_row(self, row):
        """Return `row' wrapped in a db_row object."""
        ret = self._row_class(row)
        for n, conv in self._convert_cols.items():
            if ret[n] is not None:
                ret[n] = conv(ret[n])
        return ret


class PsycoPG2Cursor(PsycoPGCursor):
    def execute(self, operation, parameters=()):
        ret = super(PsycoPG2Cursor, self).execute(operation, parameters)
        db_mod = self._db._db_mod

        def date_to_mxdatetime(dt):
            return DateTime.DateTime(dt.year, dt.month, dt.day)
        def datetime_to_mxdatetime(dt):
            return DateTime.DateTime(dt.year, dt.month, dt.day,
                                     dt.hour, dt.minute, dt.second)

        if self.description is not None:
            for n, item in enumerate(self.description):
                if item[1] == db_mod._psycopg.DATE:
                    self._convert_cols[n] = date_to_mxdatetime
                elif item[1] == db_mod._psycopg.DATETIME:
                    self._convert_cols[n] = datetime_to_mxdatetime
        return ret
    # end execute
# end PsycoPG2Cursor
    


class OracleBase(Database):
    """Oracle database driver class."""

    rdbms_id = "Oracle"

    def __init__(self, *args, **kws):
        for cls in self.__class__.__mro__:
            if issubclass(cls, OracleBase):
               return super(OracleBase, self).__init__(*args, **kws)
        raise NotImplementedError, \
              "Can't instantiate abstract class <OracleBase>."

    def _sql_port_table(self, schema, name):
        return ['%(schema)s.%(name)s' % locals()]

    def _sql_port_sequence(self, schema, name, op):
        if op == 'next':
            return ['%(schema)s.%(name)s.nextval' % locals()]
        elif op == 'current':
            return ['%(schema)s.%(name)s.currval' % locals()]
        else:
            raise self.ProgrammingError, 'Invalid sequence operation: %s' % op

    def _sql_port_sequence_start(self, value):
        return ['START', 'WITH', value]

    def _sql_port_from_dual(self):
        return ["FROM", "DUAL"]

    def _sql_port_now(self):
        return ['SYSDATE']


class DCOracle2(OracleBase):

    _db_mod = "DCOracle2"

    def connect(self, user=None, password=None, service=None,
                client_encoding=None):
        cdata = self._connect_data
        cdata.clear()
        cdata['arg_user'] = user
        cdata['arg_password'] = password
        cdata['arg_service'] = service
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME
        if user is None:
            user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        if password is None:
            password = read_password(user, service)
        conn_str = '%s/%s@%s' % (user, password, service)
        cdata['conn_str'] = conn_str
        if client_encoding is None:
            client_encoding = self.encoding
        else:
            self.encoding = client_encoding
        
        # The encoding names in Oracle don't look like PostgreSQL's,
        # so we translate them into a single standard.
        encoding_names = { 'ISO_8859_1': "american_america.we8iso8859p1",
                           'UTF-8': "american_america.utf8" }
        os.environ['NLS_LANG'] = encoding_names.get(client_encoding,
                                                    client_encoding)
        #
        # Call superclass .connect with appropriate CONNECTIONSTRING;
        # this will in turn invoke the connect() function in the
        # DCOracle2 module.
        super(Oracle, self).connect(conn_str)

    def pythonify_data(self, data):
        """Convert type of values in row to native Python types."""
        # Short circuit; no conversion is necessary for DCOracle2.
        return data


class cx_Oracle(OracleBase):

    _db_mod = "cx_Oracle"

    def connect(self, user=None, password=None, service=None,
                client_encoding=None):
        cdata = self._connect_data
        cdata.clear()
        cdata['arg_user'] = user
        cdata['arg_password'] = password
        cdata['arg_service'] = service
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME
        if user is None:
            user = cereconf.CEREBRUM_DATABASE_CONNECT_DATA.get('user')
        if password is None:
            password = read_password(user, service)
        conn_str = '%s/%s@%s' % (user, password, service)
        cdata['conn_str'] = conn_str
        if client_encoding is None:
            client_encoding = self.encoding
        else:
            self.encoding = client_encoding
        
        # The encoding names in Oracle don't look like PostgreSQL's,
        # so we translate them into a single standard.
        encoding_names = { 'ISO_8859_1': "american_america.we8iso8859p1",
                           'UTF-8': "american_america.utf8" }
        os.environ['NLS_LANG'] = encoding_names.get(client_encoding,
                                                    client_encoding)

        # Call superclass .connect with appropriate CONNECTIONSTRING;
        # this will in turn invoke the connect() function in the
        # cx_Oracle module.
        super(cx_Oracle, self).connect(conn_str)

    def pythonify_data(self, data):
        """Convert type of values in row to native Python types."""
        # Short circuit; no conversion is necessary for DCOracle2.
        return data

    def cursor(self):
        return cx_OracleCursor(self)
    # end cursor
# end cx_Oracle



class cx_OracleCursor(Cursor):
    """A special cursor subclass to handle cx_Oracle's quirks.

    This class is a workaround for cx_Oracle's feature where it refuses to
    accept unused names in bind dictionary in the the execute() method. We
    redefine a dictionary with 'used-only' bind names, and send that
    dictionary to the backend's execute(). This hack implies a performance
    hit, since we parse each statement (at least) twice.
    """

    def execute(self, operation, parameters=()):
        # Translate Cerebrum-specific hacks ([:]-syntax we love, e.g.). We
        # must do this, before feeding operation to the backend, since we've
        # effectively extended sql syntax.
        sql, binds = self._translate(operation, parameters)
        # Now that we have raw sql, we need to check if binds contains some
        # superfluous identifiers. If it does, we have to purge them.

        # 1. Prepare the statement (so that the backend can report some useful
        #    information about this.) This costs extra time, but it is
        #    inevitable, since bindnames() requires a prepared statement.
        self._cursor.prepare(sql)
        # 2. Extract the bind names. This is the list we compare to binds. The
        #    problem is of course that this bastard upcases the names.
        actual_binds = self._cursor.bindnames()

        mybinds = dict()
        for next_bind in actual_binds:
            if next_bind in binds:
                mybinds[next_bind] = binds[next_bind]
            elif next_bind.lower() in binds:
                mybinds[next_bind.lower()] = binds[next_bind.lower()]
            else:
                # what to do?
                raise ValueError("Cannot remap bind name %s to "
                                 "actual parameter" % next_bind)

        # super().execute will redo a considerable part of the work here. It
        # is a performance hit (FIXME: how much of a performance hit?), but
        # right now (2008-06-30) we do not care.
        return super(cx_OracleCursor, self).execute(sql, mybinds)
    # end execute
# end cx_OracleCursor



class SQLite(Database):
    """This class defines an abstraction for the SQLite backend.

    The class is a hairy monstrosity of an enormous hack. SQLite does NOT
    support a number of elementary sql92 constructs and datatypes. Thus, some
    of the essentials in Cerebrum have to be remapped into different
    datatypes.

    Furthermore, SQLite by itself does NOT support value typing in the
    database (although it parses column types from sql), so any piece of code
    relying on this will probably not fail when it should have.

    This backend is for testing purposes only, so that people could run
    elementary tests without a network connection or without a true database
    to talk to.
    """

    _db_mod = 'pysqlite2.dbapi2'
    rdbms_id = 'sqlite'
    # SQLite does not support datetime, thus we store dates as
    # ISO8601-formatted strings. One MUST make sure that this format matches
    # however CURRENT_TIMESTAMP is represented.
    _mx_format = "%Y-%m-%d %H:%M:%S"

    def _sqlite2mx(self, string):
        return DateTime.strptime(s, self._mx_format)

    def _mx2sqlite(self, dt):
        return "%s" % dt.strftime(self._mx_format)

    def __init__(self, *rest, **kwargs):
        # Python DB-API 2.0 requires certain type ctors to be present in the
        # module. For some reason these are absent from pysqlite2.
        if isinstance(self._db_mod, basestring):
            mod = Utils.dyn_import(self._db_mod)
            mod.STRING = str
            mod.BINARY = mod.Binary
            mod.NUMBER = float
            mod.DATETIME = DateTime.DateTime

        super(SQLite, self).__init__(*rest, **kwargs)

        # provide seamless operation with mx.DateTime.
        self._db_mod.register_converter("timestamp", self._sqlite2mx)
        self._db_mod.register_converter("date", self._sqlite2mx)
        self._db_mod.register_adapter(DateTime.DateTimeType, self._mx2sqlite)
    # end __init__

    def connect(self, user=None, password=None, service=None,
                client_encoding=None):
        if service is None:
            service = cereconf.CEREBRUM_DATABASE_NAME

        super(SQLite, self).connect(database=service)

        if client_encoding is not None:
            self.encoding = client_encoding
    # end connect

    def cursor(self):
        return SQLiteCursor(self)
    # end cursor

    def _sql_port_now(self):
        return ["CURRENT_TIMESTAMP"] # self._mx2sqlite(DateTime.now())]

    def _sql_port_table(self, schema, name):
        return [name]

    # IVR 2007-10-30 FIXME: This craches if sql statements are cached.
    def _sql_port_sequence(self, schema, name, op):
        if op == 'next':
            value = self._nextval_sequence(name)
            return ["%d" % value]
        elif op == 'current':
            value = self._currval_sequence(name)
            return ["%d" % value]
        else:
            raise ValueError, 'Invalid sequnce operation: %s' % op
    # end _sql_port_sequence

    def _nextval_sequence(self, name):
        self.execute("INSERT INTO %s VALUES (1+(SELECT max(value) FROM %s))" %
                     (name, name))
        return self._currval_sequence(name)
    # end _nextval_sequence

    def _currval_sequence(self, name):
        return self.query_1("SELECT MAX(value) AS value FROM %s" % name)
    # end _currval_sequence

    def nextval(self, seq_name):
        """Return a new value from sequence SEQ_NAME.

        The sequence syntax varies a bit between RDBMSes, hence there
        is no default implementation of this method."""

        return self._nextval_sequence(seq_name)
    # end nextval

    def ping(self):
        """Check that communication with the database works.

        Force the underlying database driver module to raise an
        exception if the database communication channel represented by
        this object for some reason isn't working properly.
        """
        # it's SQLite -- we are always on!
        pass
    # end ping
    
# end SQLite

class SQLiteCursor(Cursor):
    """SQLite-specific cursor hacks.
    
    This class tries to hide some of the shortcomings of the SQLite backend. 
    """
    identifier_start = '[a-zA-Z]'
    identifier_body = '[a-zA-Z0-9_]'
    sql_special = ' "%&\'()*'
    delimited_identifier = '"[a-zA-Z0-9%s]+"' % re.escape(sql_special)
    regular_identifier = '%s%s*' % (identifier_start, identifier_body)

    def _translate(self, statement, params):
        retval = super(SQLiteCursor, self)._translate(statement, params)
        # IVR 2007-10-30 FIXME: For the love of Britney's underwear, FIX THIS!
        # (sequence references cannot be cached.)
        if statement in self._sql_cache:
            del self._sql_cache[statement]
        return retval
    # end _translate


    def _parameter_fixup(self, parameters):
        """We want to force utf-8 for our parameters."""

        for param in parameters:
            if type(parameters[param]) is str:
                # IVR 2008-03-19 FIXME: This is sooooo broken. How do I know
                # here if the parameter is in latin-1?
                parameters[param] = parameters[param].decode("latin-1")

        return parameters
    # end _parameter_fixup


    def _sequence_initial_fixup(self, operation):
        """Deep magic to compensate for SQLite's lack of sequences.

        This method converts CREATE SEQUENCE in Cerebrum-syntax to CREATE
        TABLE in SQL92 and records the initial value.

        @rtype: tuple (of 3 basestring)
        @return:
          Returns the modified sql, name of the sequence and its starting
          value, if any. If L{operation} is not a CREATE SEQUENCE, it is
          returned unmodified and sequence name/start value are None/None.

          If L{operation} *is* in fact a CREATE SEQUENCE statement, remap it
          into CREATE TABLE, register the sequence name and the initial value
          (if any). If no initial value is specified, 1 is assumed.
        """

        # rex for create sequence statements
        sequence_rex = re.compile("CREATE SEQUENCE (%s|%s)" %
                                  (self.delimited_identifier,
                                   self.regular_identifier),
                                  re.IGNORECASE)
        # rex for initial value in create sequence statements
        sequence_initial = re.compile("\[:sequence_start\s+value\s*=\s*(\d+)\]",
                                      re.IGNORECASE)

        # Since sequences are not supported, we have to hack around them
        create_sequence = sequence_rex.search(operation)
        sequence_start_value = None
        sequence_name = None
        if create_sequence:
            sequence_start_value = 0
            sequence_name = create_sequence.group(1)
            # here we substitute create table for create sequence...
            operation = sequence_rex.sub("""
                           CREATE TABLE \\1
                           (value INTEGER NOT NULL PRIMARY KEY)
                           """, operation)
            # check if the start value has been specified
            mobj = sequence_initial.search(operation)
            if mobj:
                # grab the start value ...
                # (-1 to compensate for how nextval() works)
                sequence_start_value = int(mobj.group(1)) - 1
                # ... and remove the []-junk from the sql statement
                operation = sequence_initial.sub("", operation)

        return operation, sequence_name, sequence_start_value
    # end _sequence_initial_fixup
        

    def _sequence_final_fixup(self, sequence_name, start_value):
        """Insert the initial value into specified sequence."""
        # ... and here we make sure that a 'start value' exists
        super(SQLiteCursor, self).execute("INSERT INTO %s VALUES (%d)" %
                                          (sequence_name, start_value))
    # end _sequence_final_fixup
        

    def _date_fixup(self, operation):
        """Remap DATE in table creation to TEXT.

        SQLite does not support the date datatype. Thus we remap all
        occurrences of DATE to TEXT. 
        """

        if re.search("create table", operation,
                     re.IGNORECASE|re.MULTILINE|re.DOTALL):
            # Swap all DATE uncritically to TEXT. This is hairy, this is
            # scary, but I don't see any other way out :( 
            operation = re.sub("\s+DATE(\s+|,)", " TEXT\\1", operation)

        return operation
    # end _date_fixup


    def _constraint_fixup(self, operation):
        """Remap some ADD CONSTRAINT statements.

        Actually, since SQLite supports only two, we'll simply ignore all add
        constraints. This may fail, if this code is used to migrate a database
        (which occasionally adds columns via add constraint), but for this
        backend it probably would not matter anyway.
        """

        constraint_rex = re.compile("ALTER TABLE (%s|%s) ADD CONSTRAINT" %
                                    (self.delimited_identifier,
                                     self.regular_identifier),
                                    re.IGNORECASE)
        if constraint_rex.search(operation):
            return ""

        return operation
    # end _constraint_fixup


    def execute(self, operation, parameters=()):
        """Execute the specified operation.

        Hmm... a fix of a patch of an extension of a hack. This is badly
        broken by design, but it will not be better until SQLite starts
        supporting the much needed datatypes and syntax.
        """

        parameters = self._parameter_fixup(parameters)

        operation, seq_name, seq_start = self._sequence_initial_fixup(operation)
        
        operation = self._date_fixup(operation)

        operation = self._constraint_fixup(operation)

        retval = super(SQLiteCursor, self).execute(operation, parameters)

        if seq_name is not None:
            self._sequence_final_fixup(seq_name, seq_start)

        return retval
    # end execute
# end SQLiteCursor


# Define some aliases for driver class names that are already in use.
PostgreSQL = PgSQL
Oracle = DCOracle2

def connect(*args, **kws):
    """Return a new instance of this installation's Database subclass."""
    if kws.has_key('DB_driver'):
        mod = sys.modules.get(__name__)
        db_driver = kws['DB_driver']
        del kws['DB_driver']
        cls = getattr(mod, db_driver)
    else:
        cls = Utils.Factory.get('DBDriver')
    return cls(*args, **kws)

if __name__ == '__main__':
    db = connect(database='cerebrum')
    rows = db.query(
        """SELECT * FROM
          [:table schema=cerebrum name=entity_info] i,
          [:table schema=cerebrum name=entity_type_code] t
        WHERE t.code_str='p'""")
    print "Description:", [x[0] for x in db.description]
    for i in range(len(rows)):
        print i, rows[i]
    print "EOF"
