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

"""Access to Cerebrum code values.

The Constants class defines a set of methods that should be used to
get the actual database code/code_str representing a given Entity,
Address, Gender etc. type."""

from Cerebrum import Constants
from Cerebrum.Constants import \
     _AuthoritativeSystemCode, \
     _OUPerspectiveCode, \
     _SpreadCode, \
     _QuarantineCode, \
     _EntityExternalIdCode, \
     _PersonAffiliationCode, \
     _PersonAffStatusCode, \
     _AccountCode, \
     _ContactInfoCode, \
     _CerebrumCode, \
     _AddressCode, \
     _AuthenticationCode
from Cerebrum.modules.PosixUser import \
     _PosixShellCode
from Cerebrum.modules.Email import \
     _EmailServerTypeCode
from Cerebrum.modules.EntityTrait import \
     _EntityTraitCode

class Constants(Constants.Constants):

    # ID's from external systems
    externalid_sys_x_id = _EntityExternalIdCode(
        'SYS_X_ID',
        Constants.Constants.entity_person,
        'Internal sys_x identifier')
    externalid_paga_ansattnr = _EntityExternalIdCode(
        'PAGA_ANSATTNR',
        Constants.Constants.entity_person,
        'Internal PAGA identifier')
    externalid_hifm_ansattnr = _EntityExternalIdCode(
        'HIFM_ANSATTNR',
        Constants.Constants.entity_person,
        'Internal HIFM identifier')
    externalid_sito_ansattnr = _EntityExternalIdCode(
        'SITO_ANSATTNR',
        Constants.Constants.entity_person,
        'Internal SITO identifier')
    externalid_sito_ou = _EntityExternalIdCode(
        'SITO_OU',
        Constants.Constants.entity_ou,
        'internal sito ou identifier')


    # Authoritative systems
    system_hifm = _AuthoritativeSystemCode('HIFM', 'H�gskolen i Alta')
    system_hitos = _AuthoritativeSystemCode('HITOS', 'H�gskolen i Troms�')
    system_lt = _AuthoritativeSystemCode('SLP4', 'SLP4')
    system_x = _AuthoritativeSystemCode('SYS_X', 'Manuelt personal system')
    system_tlf = _AuthoritativeSystemCode('TLF', 'Telefoni system')
    system_sysacc = _AuthoritativeSystemCode('SYSACC', 'System Accounts')
    system_paga = _AuthoritativeSystemCode('PAGA', 'PAGA')
    system_sito = _AuthoritativeSystemCode('SITO', 'SITO')
    system_flyt = _AuthoritativeSystemCode('FLYT', 'FLYT')
    system_fs_derived = _AuthoritativeSystemCode('FS-auto','Utledet av FS data')
    # Account codes
    account_test = _AccountCode('T', 'Testkonto')
    account_felles_drift = _AccountCode('FD','Felles Drift') 
    account_felles_intern = _AccountCode('FI','Felles Intern') 
    account_kurs = _AccountCode('K','Kurs') 
    account_forening = _AccountCode('F','Forening') 
    account_maskin = _AccountCode('M','Maskin') 
    account_prosess = _AccountCode('P','Prosess') 
    account_uit_guest = _AccountCode('gjestebruker_uit', 'Manuell gjestekonto')

    # Contact codes
    contact_workphone2 = _ContactInfoCode('PHONE_WORK_2', 'Secondary Work Phone')
    contact_room = _ContactInfoCode('ROOM@UIT', 'Location and room number')
    contact_building = _ContactInfoCode('BYGG@UIT', 'Building name')


    # address codes
    address_location = _AddressCode('Lokasjon', 'Campus')
    
    # OU Structure perspective
    perspective_sito = _OUPerspectiveCode('SITO', 'SITO')

    affiliation_ansatt_sito = _PersonAffiliationCode(
        'SITO',
        'Ansatt ved studentsamskipnaden i tromso')

    affiliation_ansatt = _PersonAffiliationCode(
        'ANSATT',
        'Ansatt ved UiT (i f�lge LT)') 
    affiliation_flyt_ansatt_hih = _PersonAffiliationCode('ANSATT_HIH','Ansatt ved HiH')
    affiliation_flyt_student_hih = _PersonAffiliationCode('STUDENT_HIH','Student ved HiH') 

    #
    # Affiliation status
    #
    affiliation_status_flyt_hih_ansatt_faculty = _PersonAffStatusCode(affiliation_ansatt,'ansatt HiH','Vitenskapelig')
    affiliation_status_flyt_hih_ansatt_tekadm = _PersonAffStatusCode(affiliation_ansatt,'ansatt HiH','Teknisk/administrativt')

    affiliation_status_ansatt_perm = _PersonAffStatusCode(
        affiliation_ansatt, 'permisjon', 'Ansatt, for tiden i permisjon')

    affiliation_status_flyt_ansatt_hifm = _PersonAffStatusCode(
    affiliation_ansatt,
    'ansatt HIFm',
    'Ansatte fra H�yskolen i Alta')
    
    affiliation_status_ansatt_sito_sterk = _PersonAffStatusCode(
        affiliation_ansatt_sito,
        'sito_sterk',
        'Ansatt med sterk uit tilknytning')
    
    affiliation_status_ansatt_sito_svak = _PersonAffStatusCode(
        affiliation_ansatt_sito,
        'sito_svak',
        'Ansatt med svak uit tilknytning')

    affiliation_status_ansatt_sys_x = _PersonAffStatusCode(
        affiliation_ansatt, 
        'sys_x-ansatt',
        'Manuelt gitt tilgang til AD (b�r nyanseres)')

    # Student affiliation and status
    affiliation_student = _PersonAffiliationCode(
        'STUDENT', 
        'Student ved UiT (i f�lge FS)')
    affiliation_status_flyt_hih_student_aktiv = _PersonAffStatusCode(
        affiliation_student,'student HiH','Aktiv student')
    affiliation_status_flyt_student_hifm = _PersonAffStatusCode(
        affiliation_student,
        'student HIFm',
        'Student fra H�yskolen i Alta')
    affiliation_status_student_soker = _PersonAffStatusCode(
        affiliation_student, 'soker', 'Registrert med s�knad i FS')

    affiliation_status_student_sys_x = _PersonAffStatusCode(
        affiliation_student, 
        'sys_x-student',
        'Manuelt gitt tilgang til SUT (b�r nyanseres)')
    affiliation_status_student_tilbud = _PersonAffStatusCode(
        affiliation_student, 
        'tilbud', 
        'Har f�tt tilbud om opptak')
    affiliation_status_student_opptak = _PersonAffStatusCode(
        affiliation_student, 
        'opptak', 
        'Har studierett ved studieprogram')
    affiliation_status_student_perm = _PersonAffStatusCode(
        affiliation_student, 
        'permisjon', 
        'Har gyldig permisjonstatus i FS')
    affiliation_status_student_alumni = _PersonAffStatusCode(
        affiliation_student, 
        'alumni', 
        'Har fullf�rt studieprogram i FS')
    affiliation_status_student_drgrad = _PersonAffStatusCode(
        affiliation_student, 
        'drgrad', 
        'Registrert student p� doktorgrad')
    affiliation_status_student_emnestud = _PersonAffStatusCode(
        affiliation_student, 'emnestud', 'Registrert som aktiv emnestudent i FS') 


    #Tilknyttet affiliation and status
    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 
        'Tilknyttet UiT uten � v�re student eller ansatt')
    affiliation_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet, 
        'fagperson', 
        'Registrert som fagperson i FS')
    affiliation_tilknyttet_emeritus = _PersonAffStatusCode(
        affiliation_tilknyttet, 
        'emeritus',
        'Registrert i LT med gjestetypekode EMERITUS')
    affiliation_tilknyttet_ekst_stip = _PersonAffStatusCode(
        affiliation_tilknyttet, 
        'ekst_stip',
        'Personer registrert i LT med gjestetypekode=EF-STIP')    
    
    # Manuell affiliation
    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL', 
        'Tilknyttet enheter/instutusjoner som UiT har avtale med')
    affiliation_manuell_alumni = _PersonAffStatusCode(
        affiliation_manuell, 'alumni', 'Uteksaminerte studenter')
    affiliation_manuell_sito = _PersonAffStatusCode(
        affiliation_manuell, 
        'sito', 
        'Sito')
    affiliation_manuell_gjest_u_konto = _PersonAffStatusCode(
        affiliation_manuell,
        'gjest_u_konto',
        'gjest uten konto')
    affiliation_manuell_unn = _PersonAffStatusCode(
        affiliation_manuell,
        'UNN',
        'Universitets sykheuset i Nord Norge')
    affiliation_manuell_gjest = _PersonAffStatusCode(
        affiliation_manuell, 
        'gjest', 
        'Gjest')
    affiliation_manuell_utdanning_no = _PersonAffStatusCode(
        affiliation_manuell, 
        'utdanning_no',
        'Utdanning.no')
    affiliation_manuell_akademisk_kvarter = _PersonAffStatusCode(
        affiliation_manuell, 
        'akademisk_kvart', 
        'Akademisk Kvarter')
    affiliation_manuell_norges_universitetet = _PersonAffStatusCode(
        affiliation_manuell, 
        'norges_universi', 
        'Norgesuniversitetet')
    affiliation_manuell_kirkutdnor = _PersonAffStatusCode(
        affiliation_manuell, 
        'kirkutdnor', 
        'Kirkelig Utdanningssenter Nord-Norge')
    affiliation_manuell_gjesteforsker = _PersonAffStatusCode(
        affiliation_manuell, 'gjesteforsker',
        'Gjesteforsker (under utfasing)')
    affiliation_manuell_konsulent = _PersonAffStatusCode(
        affiliation_manuell, 'konsulent',
        'Konsulent (under utfasing)')
    affiliation_status_gjest_u_account = _PersonAffStatusCode(
        affiliation_manuell,
        'gjest_u_konto',
        'Gjest uten konto')

    # upersonlige kontoer
    affiliation_upersonlig = _PersonAffiliationCode(
        'UPERSONLIG', 'Fellesbrukere, samt andre brukere uten eier')
    affiliation_upersonlig_felles = _PersonAffStatusCode(
        affiliation_upersonlig, 'felles', 'Felleskonti')
    affiliation_upersonlig_kurs = _PersonAffStatusCode(
        affiliation_upersonlig, 'kurs', 'Kurskonti')
    affiliation_upersonlig_pvare = _PersonAffStatusCode(
        affiliation_upersonlig, 'pvare', 'Programvarekonti')
    affiliation_upersonlig_term_maskin = _PersonAffStatusCode(
        affiliation_upersonlig, 'term_maskin', 'Terminalstuemaskin')
    affiliation_upersonlig_bib_felles = _PersonAffStatusCode(
        affiliation_upersonlig, 'bib_felles', 'Bibliotek felles')


    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS
    posix_shell_bash = _PosixShellCode(
        'bash', 
        '/bin/bash')
    posix_shell_csh = _PosixShellCode(
        'csh', 
        '/bin/csh')
    posix_shell_false = _PosixShellCode(
        'false', 
        '/bin/false')
    posix_shell_nologin = _PosixShellCode(
        'nologin', 
        '/local/etc/nologin')
    posix_shell_sh = _PosixShellCode(
        'sh', 
        '/bin/sh')
    posix_shell_zsh = _PosixShellCode(
        'zsh',
        '/local/bin/zsh')
    
    # Spread constants
    spread_ifi_nis_user = _SpreadCode(
        'NIS_user@ifi', 
        Constants.Constants.entity_account,
        'User in NIS domain "ifi"')
    spread_uit_nis_user = _SpreadCode(
        'NIS_user@uit', 
        Constants.Constants.entity_account,
        'User in NIS domain "uit"')
    spread_uit_nis_user = _SpreadCode(
        'NIS_user@uit', 
        Constants.Constants.entity_account,
        'User in NIS domain "uit"')
    spread_uit_student_disk = _SpreadCode(
        'student_disk@uit',
        Constants.Constants.entity_disk,
        'Student disk spread')
    spread_uit_fronter = _SpreadCode(
        'fronter@uit', 
        Constants.Constants.entity_group,
        'fronter user')
    spread_uit_fronter_account = _SpreadCode(
        'fronter_acc@uit',
        Constants.Constants.entity_account,
        'fronter account')
    spread_uit_evu = _SpreadCode(
        'evu@uit', 
        Constants.Constants.entity_account,
        'evu person')
    spread_uit_frida = _SpreadCode(
        'frida@uit',
        Constants.Constants.entity_account,
        'Accounts with FRIDA spread')
    spread_uit_cristin = _SpreadCode(
        'cristin@uit',
        Constants.Constants.entity_account,
        'Accounts with CRISTIN spread')
    spread_uit_ldap_account = _SpreadCode(
        'ldap@uit',
        Constants.Constants.entity_account,
        'Accounts with ldap spread')
    spread_uit_ldap_person = _SpreadCode(
        'LDAP_person', Constants.Constants.entity_person,
        'Person included in LDAP directory')
    spread_uit_ldap_guest = _SpreadCode(
        'guest@ldap', Constants.Constants.entity_account,
        'LDAP/RADIUS spread for wireless accounts')
    spread_uit_ad_account = _SpreadCode(
        'AD_account',
        Constants.Constants.entity_account,
        'account included in Active Directory')
    spread_uit_ad_group = _SpreadCode(
        'AD_group',
        Constants.Constants.entity_group,
        'group included in Active Directory')
    spread_uit_ad_lit_admin = _SpreadCode(
        'AD_litadmin',  
        Constants.Constants.entity_account,
        'AD admin local IT') 
    spread_uit_ad_admin = _SpreadCode(
        'AD_admin',
        Constants.Constants.entity_account,
        'AD admin central IT')    
    spread_uit_ad_lit_admingroup = _SpreadCode(
        'AD_group_litadmn',
        Constants.Constants.entity_group,
        'AD admingroup for local IT')
    spread_uit_exchange = _SpreadCode(
        'exchange_mailbox',
        Constants.Constants.entity_account,
        'Accounts with exchange mailbox')
    spread_uit_sutmail = _SpreadCode(
        'sut_mailbox',
        Constants.Constants.entity_account,
        'Accounts with sut mailbox')
    spread_sito = _SpreadCode(
        'SITO',
        Constants.Constants.entity_account,
        'Accounts generated for sito users')

    # Email constants
    spread_uit_imap = _SpreadCode(
        'IMAP@uit', 
        Constants.Constants.entity_account,
        'IMAP account')
    email_server_type_exchange_imap= _EmailServerTypeCode(
            'exchange_imap',
            "Server is an Exchange server")

    # Quarantine constants
    quarantine_ou_notvalid = _QuarantineCode('ou_notvalid',
                                             'OU not valid from external source')

    quarantine_auto_emailonly = _QuarantineCode('auto_kunepost', 
                                                'Ikke ordin<E6>r student, tilgang til bare e-post')
    
    quarantine_auto_inaktiv = _QuarantineCode('auto_inaktiv', 
                                             'Ikke aktiv student, utestengt')
    quarantine_tilbud = _QuarantineCode(
            'Tilbud',
            "Pre-generert konto til studenter som har f�tt studietilbud,"
            "men som ikke har aktivert kontoen.")
    quarantine_sys_x_approved = _QuarantineCode(
            'sys-x_approved',
            'Konto fra system-x som ikke er godkjent')
    quarantine_generell = _QuarantineCode(
            'generell', 
            'Generell splatt')
    quarantine_slutta = _QuarantineCode(
            'slutta', 
            'Personen har slutta')
    quarantine_system = _QuarantineCode(
            'system', 
            'Systembrukar som ikke skal logge inn')
    quarantine_permisjon = _QuarantineCode(
            'permisjon', 
            'Brukeren har permisjon')
    quarantine_svakt_passord = _QuarantineCode(
            'svakt_passord', 
            'For d�rlig passord')
    quarantine_autopassord = _QuarantineCode(
            'autopassord',
            'Passord ikke skiftet trass p�legg')
    quarantine_sut_disk_usage = _QuarantineCode(
            'sut_disk',
            "Bruker for mye disk p� sut")
            
    # Auth codes
    auth_type_md5_crypt_hex = _AuthenticationCode(
            'MD5-crypt2',
            "MD5-derived 32 bit password non unix style, no salt")
    auth_type_md5_b64= _AuthenticationCode(
            'MD5-crypt_base64',
            "MD5-derived 32 bit password base 64 encoded")
    auth_type_pgp_activedir= _AuthenticationCode(
            'PGP-offline_key',
            "PGP encrypted password for use in Active Directory")


    # Trait codes
    trait_sito_registrar_notified = _EntityTraitCode(
        'sito_req_mailed', Constants.Constants.entity_account,
        "Trait set on account when sito processing is done"
        )

    trait_sito_user_notified = _EntityTraitCode(
        'sito_user_mailed', Constants.Constants.entity_account,
        "Trait set on account after account created mail is sent to user"
        )
    
    trait_sysx_registrar_notified = _EntityTraitCode(
        'sysx_reg_mailed', Constants.Constants.entity_account,
        "Trait set on account when systemx processing is done"
        )
    trait_sysx_user_notified = _EntityTraitCode(
        'sysx_user_mailed', Constants.Constants.entity_account,
        "Trait set on account after account created mail is sent to user"
        )

    # ePhorte codes
    spread_ephorte_person = _SpreadCode('ePhorte_person',
                                        Constants.Constants.entity_person,
                                        'Person included in ePhorte export')
                                        
    trait_sysx_registrar_notified = _EntityTraitCode(
        'sysx_reg_mailed', Constants.Constants.entity_account,
        "Trait set on account when systemx processing is done"
        )
    trait_sysx_user_notified = _EntityTraitCode(
        'sysx_user_mailed', Constants.Constants.entity_account,
        "Trait set on account after account created mail is sent to user"
        )
