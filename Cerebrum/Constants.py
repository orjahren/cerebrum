# Copyright 2002 University of Oslo, Norway
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

"""Access to Cerebrum code values.

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type."""

from Cerebrum import cereconf
from Cerebrum.DatabaseAccessor import DatabaseAccessor

class _CerebrumCode(DatabaseAccessor):
    """Abstract base class for accessing code tables in Cerebrum."""

    _lookup_table = None                # Abstract class.
    _lookup_code_column = 'code'
    _lookup_str_column = 'code_str'
    _lookup_desc_column = 'description'

    def __init__(self, code):
        self.int = None
        self._desc = None
        if type(code) is int:
            self.int = code
            self.str = self.sql.query_1("SELECT %s FROM %s WHERE %s=:code" %
                                        (self._lookup_str_column,
                                         self._lookup_table,
                                         self._lookup_code_column),
                                        locals())
        elif type(code) is str:
            self.str = code
        else:
            raise ValueError
        
    def __str__(self):
        return self.str
    
    def _get_description(self):
        if self._desc is None:
            self._desc = self.sql.query_1("SELECT %s FROM %s WHERE %s=:str" %
                                          (self._lookup_desc_column,
                                           self._lookup_table,
                                           self._lookup_str_column),
                                          self.__dict__)
        return self._desc
    description = property(
        _get_description, None, None, "This code value's description.")

    def __int__(self):
        if self.int is None:
            self.int = int(self.sql.query_1("SELECT %s FROM %s WHERE %s=:str" %
                                            (self._lookup_code_column,
                                             self._lookup_table,
                                             self._lookup_str_column),
                                            self.__dict__))
        return self.int

    def __coerce__(self, other):
        """Support mixed-mode integer arithmetic."""
        if isinstance(other, int):
            return self.__int__(), other
        return None

class _EntityTypeCode(_CerebrumCode):
    "Mappings stored in the entity_type_code table"
    _lookup_table = 'entity_type_code'
    pass

class _ContactInfoCode(_CerebrumCode):
    "Mappings stored in the contact_info_code table"
    _lookup_table = 'contact_info_code'
    pass

class _AddressCode(_CerebrumCode):
    "Mappings stored in the address_code table"
    _lookup_table = 'address_code'
    pass

class _GenderCode(_CerebrumCode):
    "Mappings stored in the gender_code table"
    _lookup_table = 'gender_code'
    pass

class _PersonExternalIdCode(_CerebrumCode):
    "Mappings stored in the person_external_id_code table"
    _lookup_table = 'person_external_id_code'
    pass

class _PersonNameCode(_CerebrumCode):
    "Mappings stored in the person_name_code table"
    _lookup_table = 'person_name_code'
    pass

class _PersonAffiliationCode(_CerebrumCode):
    "Mappings stored in the person_affiliation_code table"
    _lookup_table = 'person_affiliation_code'
    pass

class _PersonAffStatusCode(_CerebrumCode):
    "Mappings stored in the person_aff_status_code table"
    # TODO: tror ikke dette er riktig?  I.E, pk=affiliation+status?
    _lookup_code_column = 'status'
    _lookup_str_column = 'status_str'
    _lookup_table = 'person_aff_status_code'

    def __init__(self, affiliation, status):
        self.affiliation = affiliation
        super(_PersonAffStatusCode, self).__init__(status)

    def __int__(self):
        if self.int is None:
            self.int = int(self.sql.query_1("""
            SELECT %s FROM %s WHERE affiliation=:aff AND %s=:str""" %
                                            (self._lookup_code_column,
                                             self._lookup_table,
                                             self._lookup_str_column),
                                            {'str': self.str,
                                             'aff' : int(self.affiliation)}))
        return self.int

    ## Should __str__ be overriden as well, to indicate both
    ## affiliation and status?

class _AuthoritativeSystemCode(_CerebrumCode):
    "Mappings stored in the authoritative_system_code table"
    _lookup_table = 'authoritative_system_code'
    pass

class _OUPerspectiveCode(_CerebrumCode):
    "Mappings stored in the ou_perspective_code table"
    _lookup_table = 'ou_perspective_code'
    pass

class _AccountCode(_CerebrumCode):
    "Mappings stored in the ou_perspective_code table"
    _lookup_table = 'account_code'
    pass

class _ValueDomainCode(_CerebrumCode):
    "Mappings stored in the value_domain_code table"
    _lookup_table = 'value_domain_code'
    pass

class _AuthenticationCode(_CerebrumCode):
    "Mappings stored in the value_domain_code table"
    _lookup_table = 'authentication_code'
    pass

## Module spesific constant.  Belongs somewhere else
class _PosixShellCode(_CerebrumCode):
    "Mappings stored in the posix_shell_code table"
    _lookup_table = 'posix_shell_code'
    _lookup_desc_column = 'shell'
    pass

class _GroupMembershipOpCode(_CerebrumCode):
    "Mappings stored in the ou_perspective_code table"
    _lookup_table = 'group_membership_op_code'
    pass


class Constants(DatabaseAccessor):

    """Singleton whose members make up all needed coding values.

    Defines a number of variables that are used to get access to the
    string/int value of the corresponding database key."""

    entity_person = _EntityTypeCode('person')
    entity_ou = _EntityTypeCode('ou')
    entity_account = _EntityTypeCode('account')
    entity_group = _EntityTypeCode('group')

    contact_phone = _ContactInfoCode('PHONE')
    contact_fax = _ContactInfoCode('FAX')

    address_post = _AddressCode('POST')
    address_street = _AddressCode('STREET')

    gender_male = _GenderCode('M')
    gender_female = _GenderCode('F')

    externalid_fodselsnr = _PersonExternalIdCode('NO_BIRTHNO')

    name_first = _PersonNameCode('FIRST')
    name_last = _PersonNameCode('LAST')
    name_full = _PersonNameCode('FULL')
    
    affiliation_student = _PersonAffiliationCode('STUDENT')
    affiliation_employee = _PersonAffiliationCode('EMPLOYEE')

    affiliation_status_student_valid = _PersonAffStatusCode(
        affiliation_student, 'VALID')
    affiliation_status_employee_valid = _PersonAffStatusCode(
        affiliation_employee, 'VALID')

    # UIO specific constants, belong in UiOConstants once we get the
    # CerebrumFactory up and running
    system_lt = _AuthoritativeSystemCode('LT')
    system_fs = _AuthoritativeSystemCode('FS')

    perspective_lt = _OUPerspectiveCode('LT')
    perspective_fs = _OUPerspectiveCode('FS')

    account_program = _AccountCode('P')

    posix_shell_bash = _PosixShellCode('bash')

    group_namespace = _ValueDomainCode(cereconf.DEFAULT_GROUP_NAMESPACE)
    account_namespace = _ValueDomainCode(cereconf.DEFAULT_ACCOUNT_NAMESPACE)

    auth_type_md5 = _AuthenticationCode("md5")
    
    group_memberop_union = _GroupMembershipOpCode('union')
    group_memberop_intersection = _GroupMembershipOpCode('intersection')
    group_memberop_difference = _GroupMembershipOpCode('difference')

    def __init__(self, database):
        super(Constants, self).__init__(database)

        _CerebrumCode.sql = database

def main():
    from Cerebrum import Database
    from Cerebrum import Errors

    Cerebrum = Database.connect()
    co = Constants(Cerebrum)

    skip = dir(Cerebrum)
    for x in filter(lambda x: x[0] != '_' and not x in skip, dir(co)):
        try:
            print "co.%s: %s = %d" % (x, getattr(co, x), getattr(co, x))
        except Errors.NotFoundError:
            print "NOT FOUND: co.%s" % x

if __name__ == '__main__':
    main()
