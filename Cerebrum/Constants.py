"""
The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type.
"""

from Cerebrum.DatabaseAccessor import DatabaseAccessor

class _CerebrumCode(DatabaseAccessor):
    _lookup_code_column = 'code'
    _lookup_str_column = 'code_str'

    def __init__(self, str):
        self.str = str
        self.int = None
        
    def __str__(self):
        return self.str
    
    def __int__(self):
        if self.int is None:
            self.int = self.sql.query_1("SELECT %s FROM %s WHERE %s=:str" %
                                   (self._lookup_code_column, self._lookup_table,
                                    self._lookup_str_column), {'str': self.str})
        return self.int

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
    pass

class _AuthoritativeSystemCode(_CerebrumCode):
    "Mappings stored in the authoritative_system_code table"
    _lookup_table = 'authoritative_system_code'
    pass

class _OUPerspectiveCode(_CerebrumCode):
    "Mappings stored in the ou_perspective_code table"
    _lookup_table = 'ou_perspective_code'
    pass

class Constants(DatabaseAccessor):

    """Defines a number of variables that are used to get access to the
    string/int value of the corresponding database key."""

    entity_person = _EntityTypeCode('p')
    entity_ou = _EntityTypeCode('o')
    entity_account = _EntityTypeCode('a')
    entity_group = _EntityTypeCode('g')

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

    affiliation_status_valid = _PersonAffStatusCode('VALID')

    # UIO specific constants, belong in UiOConstants once we get the
    # CerebrumFactory up and running
    system_lt = _AuthoritativeSystemCode('LT')
    system_fs = _AuthoritativeSystemCode('FS')

    perspective_lt = _OUPerspectiveCode('LT')
    perspective_fs = _OUPerspectiveCode('FS')

    def __init__(self, database):
        super(Constants, self).__init__(database)

        _CerebrumCode.sql = database

def main():
    from Cerebrum import Database

    Cerebrum = Database.connect(user="cerebrum")
    co = Constants(Cerebrum)

    skip = dir(DatabaseAccessor)
    for x in filter(lambda x: x[0] != '_' and not x in skip, dir(co)):
        print "co.%s: %s = %d" % (x, getattr(co, x), getattr(co, x))

if __name__ == '__main__':
    main()
