# -*- coding: utf-8 -*-
# Copyright 2002-2016 University of Oslo, Norway
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
Address, Gender etc. type.

"""
from Cerebrum import Constants
from Cerebrum.Constants import \
    _AccountCode, \
    _AuthoritativeSystemCode, \
    _OUPerspectiveCode, \
    _PersonAffiliationCode, \
    _PersonAffStatusCode, \
    _QuarantineCode, \
    _SpreadCode, \
    _AddressCode
from Cerebrum.modules.PosixUser import \
    _PosixShellCode
from Cerebrum.modules.Email import \
    _EmailSpamLevelCode, \
    _EmailSpamActionCode, \
    _EmailDomainCategoryCode, \
    EmailConstants
from Cerebrum.modules.EntityTrait import \
    _EntityTraitCode
from Cerebrum.modules.consent import Consent


class Constants(Constants.Constants):
    system_lt = _AuthoritativeSystemCode('LT', 'LT')
    system_ureg = _AuthoritativeSystemCode('Ureg', 'Migrerte data, utdatert')
    system_fs_derived = _AuthoritativeSystemCode('FS-auto',
                                                 'Utledet av FS data')
    system_folk_uio_no = _AuthoritativeSystemCode('folk.uio.no',
                                                  'http://folk.uio.no/')

    perspective_lt = _OUPerspectiveCode('LT', 'LT')

    account_test = _AccountCode('testbruker', 'Testkonto')
    account_kurs = _AccountCode('kursbruker', 'Kurskonto')
    account_uio_guest = _AccountCode('gjestebruker_uio', 'Manuell gjestekonto')

    affiliation_ansatt = _PersonAffiliationCode(
        'ANSATT', 'Registrert som aktiv ansatt ved UiO')
    affiliation_status_ansatt_vit = _PersonAffStatusCode(
        affiliation_ansatt, 'vitenskapelig', 'Vitenskapelig ansatt')
    affiliation_status_ansatt_bil = _PersonAffStatusCode(
        affiliation_ansatt, 'bilag', 'Bilagslønnet')
    affiliation_status_ansatt_ltreg = _PersonAffStatusCode(
        affiliation_ansatt, 'ltreg', 'Registert som gjest, utdatert')
    affiliation_status_ansatt_tekadm = _PersonAffStatusCode(
        affiliation_ansatt, 'tekadm', 'Teknisk/administrativt ansatt')
    affiliation_status_ansatt_perm = _PersonAffStatusCode(
        affiliation_ansatt, 'permisjon', 'Ansatt, for tiden i permisjon')

    affiliation_student = _PersonAffiliationCode(
        'STUDENT', 'Student ved UiO, registrert i FS')
    affiliation_status_student_soker = _PersonAffStatusCode(
        affiliation_student, 'soker', 'Registrert med søknad i FS')
    affiliation_status_student_tilbud = _PersonAffStatusCode(
        affiliation_student, 'tilbud', 'Registrert tilbud om opptak i FS')
    affiliation_status_student_opptak = _PersonAffStatusCode(
        affiliation_student, 'opptak',
        'Registrert med gyldig studierett i FS ')
    affiliation_status_student_ny = _PersonAffStatusCode(
        affiliation_student, 'ny',
        'Registrert med ny, gyldig studierett i FS')
    affiliation_status_student_aktiv = _PersonAffStatusCode(
        affiliation_student, 'aktiv', 'Registrert som aktiv student i FS')
    affiliation_status_student_emnestud = _PersonAffStatusCode(
        affiliation_student, 'emnestud',
        'Registrert som aktiv emnestudent i FS')
    affiliation_status_student_drgrad = _PersonAffStatusCode(
        affiliation_student, 'drgrad',
        'Registrert som aktiv doktorgradsstudent i FS')
    affiliation_status_student_privatist = _PersonAffStatusCode(
        affiliation_student, 'privatist', 'Registrert som privatist i FS')
    affiliation_status_student_evu = _PersonAffStatusCode(
        affiliation_student, 'evu', 'Registrert som EVU-student i FS')
    affiliation_status_student_perm = _PersonAffStatusCode(
        affiliation_student, 'permisjon',
        'Registrert med gyldig permisjon i FS')
    affiliation_status_student_alumni = _PersonAffStatusCode(
        affiliation_student, 'alumni', 'Har fullført studieprogram i FS')

    affiliation_tilknyttet = _PersonAffiliationCode(
        'TILKNYTTET', 'Tilknyttet UiO uten å være student eller ansatt')
    affiliation_tilknyttet_fagperson = _PersonAffStatusCode(
        affiliation_tilknyttet, 'fagperson', 'Registrert som fagperson i FS')
    affiliation_tilknyttet_emeritus = _PersonAffStatusCode(
        affiliation_tilknyttet, 'emeritus',
        'Registrert med rolle EMERITUS i SAPUiO')
    affiliation_tilknyttet_bilag = _PersonAffStatusCode(
        affiliation_tilknyttet, 'bilag',
        'Registrert med rolle BILAGSLØN i SAPUiO')
    affiliation_tilknyttet_ekst_forsker = _PersonAffStatusCode(
        affiliation_tilknyttet, 'ekst_forsker',
        'Registrert med rolle EF-FORSKER eller SENIORFORS i SAPUiO')
    affiliation_tilknyttet_gjesteforsker = _PersonAffStatusCode(
        affiliation_tilknyttet, 'gjesteforsker',
        'Registrert med rolle GJ-FORSKER i SAPUiO')
    affiliation_tilknyttet_assosiert_person = _PersonAffStatusCode(
        affiliation_tilknyttet, 'assosiert_person',
        'Registrert med rolle ASSOSIERT i SAPUiO')
    affiliation_tilknyttet_frida_reg = _PersonAffStatusCode(
        affiliation_tilknyttet, 'frida_reg',
        'Registrert med rolle REGANSV og REG-ANSV i SAPUiO')
    affiliation_tilknyttet_ekst_stip = _PersonAffStatusCode(
        affiliation_tilknyttet, 'ekst_stip',
        'Registrert med rolle EF-STIP i SAPUiO')
    affiliation_tilknyttet_sivilarbeider = _PersonAffStatusCode(
        affiliation_tilknyttet, 'sivilarbeider',
        'Personer registrert i LT med gjestetypekode=SIVILARB')
    affiliation_tilknyttet_diverse = _PersonAffStatusCode(
        affiliation_tilknyttet, 'diverse',
        'Personer registrert i LT med gjestetypekode=IKKE ANGITT')
    affiliation_tilknyttet_pcvakt = _PersonAffStatusCode(
        affiliation_tilknyttet, 'pcvakt',
        'Personer registrert i LT med gjestetypekode=PCVAKT')
    affiliation_tilknyttet_unirand = _PersonAffStatusCode(
        affiliation_tilknyttet, 'unirand',
        'Personer registrert i LT med gjestetypekode=UNIRAND')
    affiliation_tilknyttet_grlaerer = _PersonAffStatusCode(
        affiliation_tilknyttet, 'grlaerer',
        'Personer registrert i LT med gjestetypekode=GRUPPELÆRER')
    affiliation_tilknyttet_ekst_partner = _PersonAffStatusCode(
        affiliation_tilknyttet, 'ekst_partner',
        'Personer registrert i LT med gjestetypekode=EKST. PART')
    affiliation_tilknyttet_studpol = _PersonAffStatusCode(
        affiliation_tilknyttet, 'studpol',
        'Personer registrert i LT'
        ' med gjestetypekode=ST-POL FRI eller ST-POL UTV')
    affiliation_tilknyttet_studorg = _PersonAffStatusCode(
        affiliation_tilknyttet, 'studorg',
        'Personer registrert i LT'
        ' med gjestetypekode=ST-ORG FRI eller ST-ORG UTV')
    affiliation_tilknyttet_innkjoper = _PersonAffStatusCode(
        affiliation_tilknyttet, 'innkjoper',
        'Registrert med rolle INNKJØPER i SAPUiO')
    affiliation_tilknyttet_isf = _PersonAffStatusCode(
        affiliation_tilknyttet, 'isf',
        'Person tilknyttet Institutt for samfunnsforskning')
    affiliation_tilknyttet_ekstern = _PersonAffStatusCode(
        affiliation_tilknyttet, 'ekstern',
        'Person tilknyttet enhet med avtale om utvidede IT-tilganger (FEIDE)')

    affiliation_manuell = _PersonAffiliationCode(
        'MANUELL', 'Tilknyttet enheter/institusjoner som USIT har avtale med')
    affiliation_manuell_alumni = _PersonAffStatusCode(
        affiliation_manuell, 'alumni', 'Uteksaminerte studenter')
    affiliation_manuell_ekstern = _PersonAffStatusCode(
        affiliation_manuell, 'ekstern',
        'Person tilknyttet enhet med avtale om begrensede IT-tilganger')

    # We override the default settings for shells, thus this file
    # should be before PosixUser in cereconf.CLASS_CONSTANTS

    posix_shell_bash = _PosixShellCode('bash', '/local/gnu/bin/bash')
    posix_shell_csh = _PosixShellCode('csh', '/bin/csh')
    posix_shell_false = _PosixShellCode('false', '/bin/false')
    posix_shell_ksh = _PosixShellCode('ksh', '/bin/ksh')
    posix_shell_ma104 = _PosixShellCode('ma104', '/local/bin/ma104')
    posix_shell_nologin = _PosixShellCode('nologin', '/local/etc/nologin')
    posix_shell_nologin_autostud = _PosixShellCode(
        'nologin.autostud', '/local/etc/shells/nologin.autostud')
    posix_shell_nologin_brk = _PosixShellCode(
        'nologin.brk', '/local/etc/shells/nologin.brk')
    posix_shell_nologin_chpwd = _PosixShellCode(
        'nologin.chpwd', '/local/etc/shells/nologin.chpwd')
    posix_shell_nologin_ftpuser = _PosixShellCode(
        'nologin.ftpuser', '/local/etc/shells/nologin.ftpuser')
    posix_shell_nologin_nystudent = _PosixShellCode(
        'nologin.nystuden', '/local/etc/shells/nologin.nystudent')
    posix_shell_nologin_permisjon = _PosixShellCode(
        'nologin.permisjo', '/local/etc/shells/nologin.permisjon')
    posix_shell_nologin_pwd = _PosixShellCode(
        'nologin.pwd', '/local/etc/shells/nologin.pwd')
    posix_shell_nologin_sh = _PosixShellCode(
        'nologin.sh', '/local/etc/shells/nologin.sh')
    posix_shell_nologin_sluttet = _PosixShellCode(
        'nologin.sluttet', '/local/etc/shells/nologin.sluttet')
    posix_shell_nologin_stengt = _PosixShellCode(
        'nologin.stengt', '/local/etc/shells/nologin.stengt')
    posix_shell_nologin_teppe = _PosixShellCode(
        'nologin.teppe', '/local/etc/shells/nologin.teppe')
    posix_shell_puberos = _PosixShellCode(
        'puberos', '/local/bin/puberos')
    posix_shell_pwsh = _PosixShellCode(
        'pwsh', '/etc/pw/sh')
    posix_shell_sftp_server = _PosixShellCode(
        'sftp-server', '/local/openssh/libexec/sftp-server')
    posix_shell_simonshell = _PosixShellCode(
        'simonshell', '/hom/simon/simonshell')
    posix_shell_sh = _PosixShellCode('sh', '/bin/sh')
    posix_shell_sync = _PosixShellCode('sync', '/bin/sync')
    posix_shell_tcsh = _PosixShellCode('tcsh', '/local/bin/tcsh')
    posix_shell_true = _PosixShellCode('true', '/bin/true')
    posix_shell_zsh = _PosixShellCode('zsh', '/local/bin/zsh')

    spread_uio_nis_user = _SpreadCode(
        'NIS_user@uio', Constants.Constants.entity_account,
        'User in NIS domain "uio"')
    spread_uio_nis_fg = _SpreadCode(
        'NIS_fg@uio', Constants.Constants.entity_group,
        'File group in NIS domain "uio"')
    spread_uio_nis_ng = _SpreadCode(
        'NIS_ng@uio', Constants.Constants.entity_group,
        'Net group in NIS domain "uio"')
    spread_ifi_nis_user = _SpreadCode(
        'NIS_user@ifi', Constants.Constants.entity_account,
        'User in NIS domain "ifi"')
    spread_ifi_nis_fg = _SpreadCode(
        'NIS_fg@ifi', Constants.Constants.entity_group,
        'File group in NIS domain "ifi"')
    spread_ifi_nis_ng = _SpreadCode(
        'NIS_ng@ifi', Constants.Constants.entity_group,
        'Net group in NIS domain "ifi"')
    spread_hpc_nis_user = _SpreadCode(
        'NIS_user@hpc', Constants.Constants.entity_account,
        'User in NIS domain, exported to HPC')
    spread_hpc_nis_fg = _SpreadCode(
        'NIS_fg@hpc', Constants.Constants.entity_group,
        'File group in NIS domain "uio" exported to HPC')
    spread_uio_ldap_person = _SpreadCode(
        'LDAP_person', Constants.Constants.entity_person,
        'Person included in LDAP directory')
    spread_isf_ldap_person = _SpreadCode(
        'LDAP_isf_person', Constants.Constants.entity_person,
        'Person included in ISF-s LDAP directory')
    spread_uio_ldap_ou = _SpreadCode(
        'LDAP_OU', Constants.Constants.entity_ou,
        'OU included in LDAP directory')
    spread_uio_ldap_account = _SpreadCode(
        'LDAP_account', Constants.Constants.entity_account,
        'Account included the LDAP directory')
    spread_uio_org_ou = _SpreadCode(
        'ORG_OU', Constants.Constants.entity_ou,
        'OU defined as part of UiOs org.structure proper')
    spread_uio_ad_account = _SpreadCode(
        'AD_account', Constants.Constants.entity_account,
        'Account included in Active Directory at UiO')
    spread_uio_ad_group = _SpreadCode(
        'AD_group', Constants.Constants.entity_group,
        'Group included in Active Directory at UiO')
    spread_uio_ad_xpand = _SpreadCode(
        'Xpand_group', Constants.Constants.entity_group,
        "Group included in Xpand's AD-OU")

    spread_uio_ua = _SpreadCode(
        'UA@uio', Constants.Constants.entity_person,
        'Person exported to UA')

    # Spreads for Exchange
    spread_exchange_account = _SpreadCode(
        'exchange_acc@uio', Constants.Constants.entity_account,
        'An account with an Exchange-mailbox at UiO')
    spread_exchange_group = _SpreadCode(
        'exch_group@uio', Constants.Constants.entity_group,
        'A mail enabled security group for Exchange')
    spread_exchange_shared_mbox = _SpreadCode(
        'exch_shared_mbox', Constants.Constants.entity_group,
        'Group exposed as a shared mailbox in Exchange')

    spread_uio_ldap_guest = _SpreadCode(
        'guest@ldap', Constants.Constants.entity_account,
        'LDAP/RADIUS spread for wireless accounts')

    # exchange-related-jazz
    # this code should be removed from the cerebrum-db as soon as
    # migration to Exchange is completed. Removal will serve two
    # purposes; firstly as a code clean-up, secondly as a check that
    # the migration was completed properly and no mailboxes are
    # registered as IMAP-accounts.
    spread_uio_imap = _SpreadCode(
        'IMAP@uio', Constants.Constants.entity_account,
        'E-mail user at UiO')
    spread_fronter_kladdebok = _SpreadCode(
        'CF@uio_kladdebok', Constants.Constants.entity_group,
        'Group representing a course that should be exported to the '
        'ClassFronter instance on kladdebok.uio.no. Should only be given to '
        'groups that have been automatically generated from FS.')
    spread_fronter_blyant = _SpreadCode(
        'CF@uio_blyant', Constants.Constants.entity_group,
        'Group representing a course that should be exported to the '
        'ClassFronter instance on blyant.uio.no. Should only be given to '
        'groups that have been automatically generated from FS.''')
    spread_fronter_petra = _SpreadCode(
        'CF@uio_petra', Constants.Constants.entity_group,
        'Group representing a course that should be exported to the '
        'ClassFronter instance on petra.uio.no. Should only be given to '
        'groups that have been automatically generated from FS.')
    spread_fronter_dotcom = _SpreadCode(
        'CF@fronter.com', Constants.Constants.entity_group,
        'Group representing a course that should be exported to the '
        'ClassFronter instance on fronter.com. Should only be given to '
        'groups that have been automatically generated from FS.')

    # LDAP: Brukere, grupper

    # TODO: Kunne begrense tillatte spreads for spesielt priviligerte
    # brukere.

    quarantine_generell = _QuarantineCode('generell', 'Generell splatt')
    quarantine_teppe = _QuarantineCode('teppe',
                                       'Kalt inn på teppet til drift')
    quarantine_slutta = _QuarantineCode('slutta', 'Personen har slutta')
    quarantine_system = _QuarantineCode('system', 'Systembrukar som ikke'
                                        ' skal logge inn')
    quarantine_permisjon = _QuarantineCode('permisjon',
                                           'Brukeren har permisjon')
    quarantine_svakt_passord = _QuarantineCode('svakt_passord',
                                               'For dårlig passord')
    quarantine_autopassord = _QuarantineCode(
        'autopassord',
        'Passord ikke skiftet trass pålegg')
    quarantine_auto_emailonly = _QuarantineCode(
        'auto_kunepost',
        'Ikke ordinær student, tilgang til bare e-post')
    quarantine_auto_inaktiv = _QuarantineCode('auto_inaktiv',
                                              'Ikke aktiv student, utestengt')
    quarantine_autoekstern = _QuarantineCode('autoekstern',
                                             'Ekstern konto gått ut på dato')
    quarantine_autointsomm = _QuarantineCode('autointsomm',
                                             'Sommerskolen er ferdig for i år')
    quarantine_nologin = _QuarantineCode('nologin',
                                         'Gammel ureg karantene nologin')
    quarantine_nologin_brk = _QuarantineCode(
        'nologin_brk',
        'Gammel ureg karantene nologin_brk')
    quarantine_nologin_ftpuser = _QuarantineCode(
        'nologin_ftpuser',
        'Gammel ureg karantene nologin_ftpuser')
    quarantine_nologin_nystudent = _QuarantineCode(
        'nologin_nystuden',
        'Gammel ureg karantene nologin_nystudent')
    quarantine_nologin_sh = _QuarantineCode('nologin_sh',
                                            'Gammel ureg karantene nologin_sh')
    quarantine_nologin_stengt = _QuarantineCode(
        'nologin_stengt',
        'Gammel ureg karantene nologin_stengt')
    quarantine_ou_notvalid = _QuarantineCode(
        'ou_notvalid',
        'OU not valid from external source')
    quarantine_ou_remove = _QuarantineCode('ou_remove',
                                           'OU is clean and may be removed')
    quarantine_guest_release = _QuarantineCode(
        'guest_release',
        'Guest user is released but not available.')
    quarantine_oppringt = _QuarantineCode(
        'oppringt',
        'Brukeren er sperret for oppringt-tjenesten.')
    quarantine_vpn = _QuarantineCode('vpn',
                                     'Brukeren er sperret for VPN-tjenesten.')
    quarantine_equant = _QuarantineCode(
        'equant',
        'Brukeren er sperret for Equant tjenesten.')
    quarantine_radius = _QuarantineCode(
        'radius', 'Bruker er sperret for RADIUS-innlogging.')
    quarantine_cert = _QuarantineCode('cert', 'Bruker er sperret av CERT.')
    email_domain_category_uio_globals = _EmailDomainCategoryCode(
        'UIO_GLOBALS',
        "All local_parts defined in domain 'UIO_GLOBALS' are treated"
        " as overrides for all domains posessing this category.")
    email_spam_level_none = _EmailSpamLevelCode(
        'no_filter', 9999, "No email will be filtered as spam")
    email_spam_level_standard = _EmailSpamLevelCode(
        'standard_spam', 7, "Only filter email that obviously is spam")
    email_spam_level_heightened = _EmailSpamLevelCode(
        'most_spam', 5, "Filter most emails that look like spam")
    email_spam_level_aggressive = _EmailSpamLevelCode(
        'aggressive_spam', 3, "Filter everything that resembles spam")
    email_spam_action_none = _EmailSpamActionCode(
        'noaction', "Deliver spam just like legitimate email")
    email_spam_action_folder = _EmailSpamActionCode(
        'spamfolder', "Deliver spam to a separate IMAP folder")
    email_spam_action_delete = _EmailSpamActionCode(
        'dropspam', "Reject messages classified as spam")

    trait_email_server_weight = _EntityTraitCode(
        'em_server_weight', Constants.Constants.entity_host,
        "The relative weight of this server when assigning new users to "
        "an e-mail server.")

    trait_email_pause = _EntityTraitCode(
        'email_pause', EmailConstants.entity_email_target,
        'Pauses delivery of email')

    # TBD: These may fit better into mod_disk_quota as actual mixin
    # tables for disk_info and host_info
    trait_host_disk_quota = _EntityTraitCode(
        'host_disk_quota', Constants.Constants.entity_host,
        "The default quota each user gets for disks on this host, "
        "stored in numval.")
    trait_disk_quota = _EntityTraitCode(
        'disk_quota', Constants.Constants.entity_disk,
        "The existence of this trait means this disk has quota. "
        "numval contains the default quota.  If it is NULL, the default "
        "quota value is taken from the host_disk_quota trait.")

    # Owner trait for GuestUsers module.
    trait_uio_guest_owner = _EntityTraitCode(
        'guest_owner_uio', Constants.Constants.entity_account,
        "When a guest account is requested a group must be set as "
        "owner for the account for the given time.")

    trait_account_generation = _EntityTraitCode(
        'ac_generation', Constants.Constants.entity_account,
        "When a users homedir is archived, this value is increased.")

    trait_student_disk = _EntityTraitCode(
        'student_disk', Constants.Constants.entity_disk,
        "When set, the disk in question is designated as"
        " hosting students' home areas")

    # Trait for tagging a person's primary affiliation, to be used by the web
    # presentations.
    trait_primary_aff = _EntityTraitCode(
        "primary_aff", Constants.Constants.entity_person,
        "A person's chosen primary affiliation,"
        " for use at the web presentations")

    # Trait for tagging -adm,-drift,-null accounts
    trait_sysadm_account = _EntityTraitCode(
        "sysadm_account", Constants.Constants.entity_account,
        "An account used for system administration,"
        " e.g. foo-adm, foo-drift and foo-null users")

    # Trait for tagging important accounts
    trait_important_account = _EntityTraitCode(
        "important_acc", Constants.Constants.entity_account,
        "An account that is important")

    # Trait for passphrase stats
    trait_has_passphrase = _EntityTraitCode(
        'has_passphrase',
        Constants.Constants.entity_account,
        "Account uses passphrase")

    address_other_street = _AddressCode('OTHER_STREET', 'Other street address')
    address_other_post = _AddressCode('OTHER_POST', 'Other post address')

    # Consent related stuff
    consent_office365 = Consent.Constants.EntityConsent(
        'office365',
        entity_type=Constants.Constants.entity_person,
        consent_type=Consent.Constants.consent_opt_in,
        description="Export to office365?")

    # Temporary access for new students:
    #
    # Trait to tag students with temporary access to IT-services
    trait_tmp_student = _EntityTraitCode(
        'tmp_student',
        Constants.Constants.entity_account,
        'Account is granted temporary access')
    #
    # Quarantine for revoking access
    quarantine_auto_tmp_student = _QuarantineCode(
        'auto_tmp_student',
        'Account is no longer active')
