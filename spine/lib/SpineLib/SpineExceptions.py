# -*- coding: iso-8859-1 -*-

# Copyright 2004, 2005 University of Oslo, Norway
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


"""Module for all exceptions in Spine which should be sent to clients.

Contains SpineException, which should be the base class for all exceptions
which should be sent to users.

Implement exceptions localy, in the modules where they fit the most.
Exceptions which have no obvious location can be implemented here.
"""

class SpineException(Exception):
    """Base-class for all exceptions in spine."""

class AccessDeniedError(SpineException):
    """Raised if client dont have access to the method."""

class AlreadyLockedError(SpineException):
    """Raised if a locking error occurs."""

class ReadOnlyAttributeError(SpineException):
    """Raised if the attribute trying to be written is read-only."""

class DatabaseError(SpineException):
    """Raised if an error occurs with the database."""

class CreationError(DatabaseError):
    """Raised if creation of an object fails."""

class DeletionError(DatabaseError):
    """Raised if deletion of an object fails."""

class AlreadyExistsError(DatabaseError):
    """Raised if a unique constraint is violated in the database."""

class TransactionError(SpineException):
    """Raised if the error is related to a transaction."""

class ClientProgrammingError(SpineException):
    """Raised when the client does something illegal."""

class ValueError(ClientProgrammingError):
    """Raised when the client does something involving an invalid value."""

class ServerProgrammingError(SpineException):
    """Raised when something illegal is done in the server-side code."""

class NotFoundError(SpineException):
    """Raised when one or more objects are not found."""

class TooManyMatchesError(SpineException):
    """Raised when a search, find, get or something similar has too many matches."""

# arch-tag: 7c3b53d8-649b-4dfc-8582-1664e52b6e0e
