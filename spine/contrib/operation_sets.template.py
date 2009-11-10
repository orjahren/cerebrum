#!/usr/bin/env python

"""
The op_sets dictionary contains operation sets with the operation set name as key and a list of tuples as value.

The tuples are (op_code, op_attr) where op_attr can be None.
"""
op_sets = {
    'cmodify_itea': [
        ('spread_edit', 'user@ansatt'),
        ('spread_edit', 'user@stud'),
        ('spread_edit', 'group@ntnu'),
        ('spread_edit', 'user@ntnu'),
    ],
    
    'cmodify_idi': [
        ('spread_edit', 'user@idi'),
    ],
    
    'cmodify_user': [
        ('account_delete', None),
        ('account_edit', None),
        ('address_edit', None),
        ('affiliation_edit', None),
        ('contact_edit', None),
        ('external_id_edit', None),
        ('group_delete', None),
        ('group_edit', None),
        ('homedir_edit', None),
        ('note_edit', None),
        ('person_delete', None),
        ('person_edit', None),
        ('set_password', None),
        ('quarantine_edit', "remote"),
        ('quarantine_edit', "sluttet"),
        ('quarantine_edit', "svakt_passord"),
    ],
    'ccreate_user': [
        ('account_create', None),
        ('group_create', None),
        ('person_create', None),
    ],
    'cadmin_client': [
        ('group_read', None),
        ('person_read', None),
        ('account_read', None),
        ('note_read', None),
        ('external_id_read', None),
    ],

    'login': [
        ('login_access', None),
    ],

    'cabuse': [
        ('quarantine_edit', "sperret"),
    ],

    'csync_stud': [
        ('syncread_account', None),
        ('syncread_group', None),
        ('spread_edit', 'user@stud'),
        ('spread_edit', 'group@stud'),
    ],

    'csync_kerberos': [
        ('syncread_account', None),
        ('syncread_group', None),
        ('spread_edit', 'user@kerberos'),
        ('spread_edit', 'group@ntnu'),
    ],
    # Spine stuff, included for backwards compatibility
    'modify_itea': [
        ('Account.add_spread', 'user@ansatt'),
        ('Account.add_spread', 'user@stud'),
        ('Account.delete_spread', 'user@ansatt'),
        ('Account.delete_spread', 'user@stud'),
        ('Group.add_spread', 'group@ntnu'),
        ('Group.delete_spread', 'group@ntnu'),
        ('Person.add_spread', 'user@ntnu'),
        ('Person.delete_spread', 'user@ntnu'),
	],
    
    'modify_idi': [
        ('Account.add_spread', 'user@idi'),
        ('Account.delete_spread', 'user@idi'),
	],
    
    'modify_user': [
        ('Account.add_note', None),
        ('Account.add_quarantine', "sluttet"),
        ('Account.add_quarantine', "remote"),
        ('Account.add_quarantine', "svakt_passord"),
        ('Account.delete', None),
        ('Account.demote_posix', None),
        ('Account.promote_posix', None),
        ('Account.remove_affiliation', None),
        ('Account.remove_external_id', None),
        ('Account.remove_homedir', None),
        ('Account.remove_note', None),
        ('Account.remove_quarantine', None),
        ('Account.set_affiliation', None),
        ('Account.set_description', None),
        ('Account.set_expire_date', None),
        ('Account.set_external_id', None),
        ('Account.set_gecos', None),
        ('Account.set_homedir', None),
        ('Account.set_password', None),
        ('Account.set_primary_group', None),
        ('Account.set_shell', None),
        ('Group.add_member', None),
        ('Group.add_note', None),
        ('Group.add_quarantine', None),
        ('Group.delete', None),
        ('Group.demote_posix', None),
        ('Group.promote_posix', None),
        ('Group.remove_external_id', None),
        ('Group.remove_member', None),
        ('Group.remove_note', None),
        ('Group.remove_quarantine', None),
        ('Group.set_description', None),
        ('Group.set_expire_date', None),
        ('Group.set_external_id', None),
        ('Person.add_affiliation', None),
        ('Person.add_contact_info', None),
        ('Person.add_note', None),
        ('Person.add_quarantine', None),
        ('Person.create_address', None),
        ('Person.delete', None),
        ('Person.remove_contact_info', None),
        ('Person.remove_external_id', None),
        ('Person.remove_name', None),
        ('Person.remove_note', None),
        ('Person.remove_quarantine', None),
        ('Person.set_birth_date', None),
        ('Person.set_deceased_date', None),
        ('Person.set_description', None),
        ('Person.set_email_domain', None),
        ('Person.set_export_id', None),
        ('Person.set_external_id', None),
        ('Person.set_gender', None),
        ('Person.set_name', None),
    ],
    'create_user': [
        ('Group.create_account', None),
        ('Person.create_account', None),
        ('OU.create_group', None),
        ('OU.create_person', None),
    ],
    'user_client': [
        ('Account.get_email_targets', None),
        ('Account.get_homepath', None),
        ('Account.get_name', None),
        ('Group.is_expired', None),
        ('Group.get_name', None),
        ('Group.get_description', None),
        ('Commands.get_account_by_name', None),
        ('Commands.strptime', None),
        ('EmailAddress.full_address', None),
        ('EmailForward.get_enable', None),
        ('EmailForward.get_forward_to', None),
        ('EmailTarget.get_forwards', None),
        ('EmailTarget.get_server', None),
        ('EmailTarget.get_target_type', None),
        ('EmailTarget.get_vacations', None),
        ('EmailVacation.get_enable', None),
        ('EmailVacation.get_end_date', None),
        ('EmailVacation.get_start_date', None),
        ('EmailVacation.get_target', None),
        ('EmailVacation.get_vacation_text', None),
        ('Host.get_id', None),
        ('Host.get_name', None),
        ('Date.get_day', None),
        ('Date.get_hour', None),
        ('Date.get_minute', None),
        ('Date.get_month', None),
        ('Date.get_second', None),
        ('Date.get_unix', None),
        ('Date.get_year', None),
        ('OU.get_name', None),
    ],
    'admin_client': [
        ('AccountAuthentication.get_account', None),
        ('AccountAuthentication.get_auth_data', None),
        ('AccountAuthentication.get_method', None),
        ('Account.get_accounts', None),
        ('Account.get_active_quarantines', None),
        ('Account.get_affiliations', None),
        ('Account.get_all_quarantines', None),
        ('Account.get_authentications', None),
        ('Account.get_create_date', None),
        ('Account.get_creator', None),
        ('Account.get_description', None),
        ('Account.get_direct_groups', None),
        ('Account.get_entity_name', None),
        ('Account.get_expire_date', None),
        ('Account.get_gecos', None),
        ('Account.get_groups', None),
        ('Account.get_history', None),
        ('Account.get_homedir', None),
        ('Account.get_homes', None),
        ('Account.get_homepath', None),
        ('Account.get_id', None),
        ('Account.get_name', None),
        ('Account.get_notes', None),
        ('Account.get_np_type', None),
        ('Account.get_owner', None),
        ('Account.get_owner_type', None),
        ('Account.get_posix_uid', None),
        ('Account.get_primary_group', None),
        ('Account.get_quarantine', None),
        ('Account.get_quarantines', None),
        ('Account.get_shell', None),
        ('Account.get_spreads', None),
        ('Account.get_type', None),
        ('Account.get_typestr', None),
        ('Account.get_traits', None),
        ('AccountHome.get_account', None),
        ('AccountHome.get_homedir', None),
        ('AccountHome.get_spread', None),
        ('Account.is_expired', None),
        ('Account.is_posix', None),
        ('Account.is_quarantined', None),
        ('AccountAffiliation.get_account', None),
        ('AccountAffiliation.get_affiliation', None),
        ('AccountAffiliation.get_ou', None),
        ('AccountAffiliation.get_person', None),
        ('AccountAffiliation.get_priority', None),
        ('AccountSearcher.add_intersection', None),
        ('AccountSearcher.length', None),
        ('AccountSearcher.search', None),
        ('AccountSearcher.set_name_like', None),
        ('AccountSearcher.set_search_limit', None),
        ('AccountType.get_description', None),
        ('AccountType.get_id', None),
        ('AccountType.get_name', None),
        ('AccountView.get_dumper_size', None),
        ('AddressType.get_description', None),
        ('AddressType.get_id', None),
        ('AddressType.get_name', None),
        ('AuthenticationType.get_description', None),
        ('AuthenticationType.get_id', None),
        ('AuthenticationType.get_name', None),
        ('AuthOperationCode.get_description', None),
        ('AuthOperationCode.get_id', None),
        ('AuthOperationCode.get_name', None),
        ('AuthOperation.get_id', None),
        ('AuthOperation.get_op', None),
        ('AuthOperation.get_op_set', None),
        ('AuthOperationSet.get_description', None),
        ('AuthOperationSet.get_id', None),
        ('AuthOperationSet.get_name', None),
        ('AuthOperationSet.get_operations', None),
        ('CerewebMotd.get_create_date', None),
        ('CerewebMotd.get_creator', None),
        ('CerewebMotd.get_id', None),
        ('CerewebMotd.get_message', None),
        ('CerewebMotd.get_subject', None),
        ('CerewebOption.get_entity', None),
        ('CerewebOption.get_id', None),
        ('CerewebOption.get_key', None),
        ('CerewebOption.get_section', None),
        ('CerewebOption.get_value', None),
        ('ChangeLog.get_change_by', None),
        ('ChangeLog.get_change_program', None),
        ('ChangeLog.get_dest_entity', None),
        ('ChangeLog.get_id', None),
        ('ChangeLog.get_message', None),
        ('ChangeLog.get_params', None),
        ('ChangeLog.get_subject_entity', None),
        ('ChangeLog.get_timestamp', None),
        ('ChangeLog.get_type', None),
        ('ChangeType.get_category', None),
        ('ChangeType.get_id', None),
        ('ChangeType.get_message', None),
        ('ChangeType.get_type', None),
        ('Commands.create_cereweb_option', None),
        ('Commands.find_email_address', None),
        ('Commands.get_account_by_name', None),
        ('Commands.get_group_by_name', None),
        ('Commands.get_host_by_name', None),
        ('Commands.get_date', None),
        ('Commands.get_date_now', None),
        ('Commands.get_datetime', None),
        ('Commands.get_email_domain_by_name', None),
        ('Commands.get_email_domains_by_category', None),
        ('Commands.get_extentions', None),
        ('Commands.get_free_uid', None),
        ('Commands.get_group_by_name', None),
        ('Commands.get_last_changelog_id', None),
        ('Commands.has_extention', None),
        ('Commands.strptime', None),
        ('Commands.suggest_usernames', None),
        ('ContactInfoType.get_description', None),
        ('ContactInfoType.get_id', None),
        ('ContactInfoType.get_name', None),
        ('Disk.get_accounts', None),
        ('Disk.get_active_quarantines', None),
        ('Disk.get_all_quarantines', None),
        ('Disk.get_description', None),
        ('Disk.get_direct_groups', None),
        ('Disk.get_entity_name', None),
        ('Disk.get_external_id', None),
        ('Disk.get_external_ids', None),
        ('Disk.get_groups', None),
        ('Disk.get_history', None),
        ('Disk.get_host', None),
        ('Disk.get_id', None),
        ('Disk.get_notes', None),
        ('Disk.get_path', None),
        ('Disk.get_quarantine', None),
        ('Disk.get_quarantines', None),
        ('Disk.get_spreads', None),
        ('Disk.get_type', None),
        ('Disk.get_typestr', None),
        ('DiskSearcher.search', None),
        ('DiskSearcher.set_path_like', None),
        ('DiskSearcher.set_description_like', None),
        ('DiskSearcher.set_search_limit', None),
        ('DiskSearcher.length', None),
        ('DumpClass.get_dumper_size', None),
        ('EmailAddress.get_change_date', None),
        ('EmailAddress.get_create_date', None),
        ('EmailAddress.get_domain', None),
        ('EmailAddress.get_expire_date', None),
        ('EmailAddress.get_id', None),
        ('EmailAddress.get_local_part', None),
        ('EmailAddress.get_target', None),
        ('EmailDomainCategorization.get_category', None),
        ('EmailDomainCategorization.get_domain', None),
        ('EmailDomainCategory.get_description', None),
        ('EmailDomainCategory.get_domains', None),
        ('EmailDomainCategorySearcher.search', None),
        ('EmailDomainCategorySearcher.set_search_limit', None),
        ('EmailDomainCategorySearcher.length', None),
        ('EmailDomainCategory.get_id', None),
        ('EmailDomainCategory.get_name', None),
        ('EmailDomain.get_categories', None),
        ('EmailDomain.get_description', None),
        ('EmailDomain.get_id', None),
        ('EmailDomain.get_name', None),
        ('EmailDomain.get_typestr', None),
        ('EmailDomain.get_persons', None),
        ('EmailDomainSearcher.search', None),
        ('EmailDomainSearcher.set_name_like', None),
        ('EmailDomainSearcher.set_search_limit', None),
        ('EmailDomainSearcher.length', None),
        ('EmailForward.get_enable', None),
        ('EmailForward.get_forward_to', None),
        ('EmailForward.get_target', None),
        ('EmailServerType.get_description', None),
        ('EmailServerType.get_id', None),
        ('EmailServerType.get_name', None),
        ('EmailServerTypeSearcher.search', None),
        ('EmailServerTypeSearcher.length', None),
        ('EmailServerTypeSearcher.set_search_limit', None),
        ('EmailSpamAction.get_description', None),
        ('EmailSpamAction.get_id', None),
        ('EmailSpamAction.get_name', None),
        ('EmailSpamLevel.get_description', None),
        ('EmailSpamLevel.get_id', None),
        ('EmailSpamLevel.get_level', None),
        ('EmailSpamLevel.get_name', None),
        ('EmailTarget.get_addresses', None),
        ('EmailTarget.get_alias_value', None),
        ('EmailTarget.get_target_entity', None),
        ('EmailTarget.get_id', None),
        ('EmailTarget.get_primary_address', None),
        ('EmailTarget.get_server', None),
        ('EmailTarget.get_target_type', None),
        ('EmailTarget.get_typestr', None),
        ('EmailTarget.get_using_uid', None),
        ('EmailTargetSearcher.search', None),
        ('EmailTargetSearcher.set_target_entity', None),
        ('EmailTargetType.get_description', None),
        ('EmailTargetType.get_id', None),
        ('EmailTargetType.get_name', None),
        ('EmailTargetTypeSearcher.search', None),
        ('EmailVacation.get_enable', None),
        ('EmailVacation.get_end_date', None),
        ('EmailVacation.get_start_date', None),
        ('EmailVacation.get_target', None),
        ('EmailVacation.get_vacation_text', None),
        ('EmailVirusFound.get_description', None),
        ('EmailVirusFound.get_id', None),
        ('EmailVirusFound.get_name', None),
        ('EmailVirusRemoved.get_description', None),
        ('EmailVirusRemoved.get_id', None),
        ('EmailVirusRemoved.get_name', None),
        ('EntityAddress.get_address_text', None),
        ('EntityAddress.get_address_type', None),
        ('EntityAddress.get_city', None),
        ('EntityAddress.get_country', None),
        ('EntityAddress.get_entity', None),
        ('EntityAddress.get_p_o_box', None),
        ('EntityAddress.get_postal_number', None),
        ('EntityAddress.get_source_system', None),
        ('EntityContactInfo.get_description', None),
        ('EntityContactInfo.get_entity', None),
        ('EntityContactInfo.get_preference', None),
        ('EntityContactInfo.get_source_system', None),
        ('EntityContactInfo.get_type', None),
        ('EntityContactInfo.get_value', None),
        ('EntityEmailDomain.get_affiliation', None),
        ('EntityEmailDomain.get_domain', None),
        ('EntityExternalId.get_external_id', None),
        ('EntityExternalId.get_id_type', None),
        ('EntityExternalId.get_source_system', None),
        ('EntityExternalIdTypeSearcher.search', None),
        ('Entity.get_accounts', None),
        ('Entity.get_active_quarantines', None),
        ('Entity.get_all_quarantines', None),
        ('Entity.get_direct_groups', None),
        ('Entity.get_entity_name', None),
        ('Entity.get_groups', None),
        ('Entity.get_history', None),
        ('Entity.get_id', None),
        ('Entity.get_notes', None),
        ('Entity.get_quarantine', None),
        ('Entity.get_quarantines', None),
        ('Entity.get_spreads', None),
        ('Entity.get_type', None),
        ('Entity.get_typestr', None),
        ('EntityName.get_entity', None),
        ('EntityName.get_name', None),
        ('EntityName.get_value_domain', None),
        ('EntityQuarantine.get_create_date', None),
        ('EntityQuarantine.get_creator', None),
        ('EntityQuarantine.get_description', None),
        ('EntityQuarantine.get_disable_until', None),
        ('EntityQuarantine.get_end_date', None),
        ('EntityQuarantine.get_entity', None),
        ('EntityQuarantine.get_start_date', None),
        ('EntityQuarantine.get_type', None),
        ('EntitySpread.get_entity', None),
        ('EntitySpread.get_entity_type', None),
        ('EntitySpread.get_spread', None),
        ('EntityTrait.get_code', None),
        ('EntityTrait.get_date', None),
        ('EntityTrait.get_target', None),
        ('EntityTrait.get_numval', None),
        ('EntityTrait.get_strval', None),
        ('EntityType.get_description', None),
        ('EntityType.get_id', None),
        ('EntityType.get_name', None),
        ('GenderType.get_description', None),
        ('GenderType.get_id', None),
        ('GenderType.get_name', None),
        ('GenderTypeSearcher.search', None),
        ('Group.get_accounts', None),
        ('Group.get_active_quarantines', None),
        ('Group.get_all_quarantines', None),
        ('Group.get_create_date', None),
        ('Group.get_creator', None),
        ('Group.get_description', None),
        ('Group.get_direct_groups', None),
        ('Group.get_entity_name', None),
        ('Group.get_expire_date', None),
        ('Group.get_external_id', None),
        ('Group.get_external_ids', None),
        ('Group.get_group_members', None),
        ('Group.get_groups', None),
        ('Group.get_history', None),
        ('Group.get_id', None),
        ('Group.get_members', None),
        ('Group.get_name', None),
        ('Group.get_notes', None),
        ('Group.get_posix_gid', None),
        ('Group.get_quarantine', None),
        ('Group.get_quarantines', None),
        ('Group.get_spreads', None),
        ('Group.get_type', None),
        ('Group.get_typestr', None),
        ('Group.get_traits', None),
        ('Group.get_visibility', None),
        ('Group.is_posix', None),
        ('Group.is_expired', None),
        ('Group.is_quarantined', None),
        ('GroupMember.get_group', None),
        ('GroupMember.get_member', None),
        ('GroupMember.get_member_type', None),
        ('GroupSearcher.length', None),
        ('GroupSearcher.search', None),
        ('GroupSearcher.set_name_like', None),
        ('GroupSearcher.set_search_limit', None),
        ('GroupVisibilityType.get_description', None),
        ('GroupVisibilityType.get_id', None),
        ('GroupVisibilityType.get_name', None),
        ('HomeDirectory.get_account', None),
        ('HomeDirectory.get_disk', None),
        ('HomeDirectory.get_home', None),
        ('HomeDirectory.get_id', None),
        ('HomeDirectory.get_status', None),
        ('HomeStatus.get_description', None),
        ('HomeStatus.get_id', None),
        ('HomeStatus.get_name', None),
        ('Host.get_accounts', None),
        ('Host.get_active_quarantines', None),
        ('Host.get_all_quarantines', None),
        ('Host.get_description', None),
        ('Host.get_direct_groups', None),
        ('Host.get_disks', None),
        ('Host.get_entity_name', None),
        ('Host.get_email_server_type', None),
        ('Host.get_external_id', None),
        ('Host.get_external_ids', None),
        ('Host.get_groups', None),
        ('Host.get_history', None),
        ('Host.get_id', None),
        ('Host.get_name', None),
        ('Host.get_notes', None),
        ('Host.get_quarantine', None),
        ('Host.get_quarantines', None),
        ('Host.get_spreads', None),
        ('Host.get_type', None),
        ('Host.get_typestr', None),
        ('HostSearcher.search', None),
        ('HostSearcher.set_name_like', None),
        ('HostSearcher.set_description_like', None),
        ('HostSearcher.set_search_limit', None),
        ('HostSearcher.length', None),
        ('LanguageType.get_description', None),
        ('LanguageType.get_id', None),
        ('LanguageType.get_name', None),
        ('NameType.get_description', None),
        ('NameType.get_id', None),
        ('NameType.get_name', None),
        ('NameTypeSearcher.search', None),
        ('Note.get_create_date', None),
        ('Note.get_creator', None),
        ('Note.get_description', None),
        ('Note.get_entity', None),
        ('Note.get_id', None),
        ('Note.get_subject', None),
        ('OU.get_accounts', None),
        ('OU.get_acronym', None),
        ('OU.get_acronyms', None),
        ('OU.get_active_quarantines', None),
        ('OU.get_addresses', None),
        ('OU.get_address', None),
        ('OU.get_all_contact_info', None),
        ('OU.get_all_quarantines', None),
        ('OU.get_avdeling', None),
        ('OU.get_children', None),
        ('OU.get_contact_info', None),
        ('OU.get_direct_groups', None),
        ('OU.get_display_name', None),
        ('OU.get_entity_name', None),
        ('OU.get_external_id', None),
        ('OU.get_external_ids', None),
        ('OU.get_fakultet', None),
        ('OU.get_groups', None),
        ('OU.get_history', None),
        ('OU.get_id', None),
        ('OU.get_institusjon', None),
        ('OU.get_institutt', None),
        ('OU.get_landkode', None),
        ('OU.get_name', None),
        ('OU.get_names', None),
        ('OU.get_notes', None),
        ('OU.get_parent', None),
        ('OU.get_quarantine', None),
        ('OU.get_quarantines', None),
        ('OU.get_short_name', None),
        ('OU.get_sort_name', None),
        ('OU.get_spreads', None),
        ('OU.get_stedkode', None),
        ('OU.get_type', None),
        ('OU.get_typestr', None),
        ('OU.is_quarantined', None),
        ('OUName.get_acronym', None),
        ('OUName.get_display_name', None),
        ('OUName.get_language', None),
        ('OUName.get_name', None),
        ('OUName.get_ou', None),
        ('OUName.get_short_name', None),
        ('OUName.get_sort_name', None),
        ('OUPerspectiveType.get_description', None),
        ('OUPerspectiveType.get_id', None),
        ('OUPerspectiveType.get_name', None),
        ('OUPerspectiveType.get_roots', None),
        ('OUPerspectiveTypeSearcher.search', None),
        ('OUSearcher.length', None),
        ('OUSearcher.search', None),
        ('OUSearcher.set_name_like', None),
        ('OUSearcher.set_search_limit', None),
        ('OUStructure.get_ou', None),
        ('OUStructure.get_parent', None),
        ('OUStructure.get_perspective', None),
        ('PersonAffiliation.get_affiliation', None),
        ('PersonAffiliation.get_create_date', None),
        ('PersonAffiliation.get_deleted_date', None),
        ('PersonAffiliation.get_last_date', None),
        ('PersonAffiliation.get_ou', None),
        ('PersonAffiliation.get_person', None),
        ('PersonAffiliation.get_source_system', None),
        ('PersonAffiliation.get_status', None),
        ('PersonAffiliation.marked_for_deletion', None),
        ('PersonAffiliationSearcher.length', None),
        ('PersonAffiliationSearcher.search', None),
        ('PersonAffiliationSearcher.set_ou', None),
        ('PersonAffiliationSearcher.set_person', None),
        ('PersonAffiliationSearcher.set_affiliation', None),
        ('PersonAffiliationSearcher.set_source_system', None),
        ('PersonAffiliationSearcher.set_search_limit', None),
        ('PersonAffiliationStatus.get_name', None),
        ('PersonAffiliationStatusSearcher.search', None),
        ('PersonAffiliationType.get_description', None),
        ('PersonAffiliationType.get_id', None),
        ('PersonAffiliationType.get_name', None),
        ('PersonAffiliationTypeSearcher.search', None),
        ('Person.get_accounts', None),
        ('Person.get_active_quarantines', None),
        ('Person.get_addresses', None),
        ('Person.get_address', None),
        ('Person.get_affiliations', None),
        ('Person.get_all_contact_info', None),
        ('Person.get_all_quarantines', None),
        ('Person.get_birth_date', None),
        ('Person.get_cached_full_name', None),
        ('Person.get_contact_info', None),
        ('Person.get_deceased_date', None),
        ('Person.get_description', None),
        ('Person.get_direct_groups', None),
        ('Person.get_email_domain', None),
        ('Person.get_entity_name', None),
        ('Person.get_export_id', None),
        ('Person.get_external_ids', None),
        ('Person.get_gender', None),
        ('Person.get_groups', None),
        ('Person.get_history', None),
        ('Person.get_id', None),
        ('Person.get_name', None),
        ('Person.get_names', None),
        ('Person.get_notes', None),
        ('Person.get_primary_account', None),
        ('Person.get_quarantine', None),
        ('Person.get_quarantines', None),
        ('Person.get_spreads', None),
        ('Person.get_traits', None),
        ('Person.get_type', None),
        ('Person.get_typestr', None),
        ('Person.is_quarantined', None),
        ('PersonName.get_name', None),
        ('PersonName.get_name_variant', None),
        ('PersonName.get_person', None),
        ('PersonName.get_source_system', None),
        ('PersonNameSearcher.search', None),
        ('PersonNameSearcher.length', None),
        ('PersonNameSearcher.set_name_like', None),
        ('PersonNameSearcher.set_name_variant', None),
        ('PersonNameSearcher.set_search_limit', None),
        ('PersonNameSearcher.set_source_system', None),
        ('PersonSearcher.add_intersection', None),
        ('PersonSearcher.length', None),
        ('PersonSearcher.search', None),
        ('PersonSearcher.set_search_limit', None),
        ('PersonSearcher.set_birth_date', None),
        ('PosixShell.get_id', None),
        ('PosixShell.get_name', None),
        ('PosixShell.get_shell', None),
        ('PosixShellSearcher.search', None),
        ('PosixShellSearcher.set_name', None),
        ('PrimaryEmailAddress.get_address', None),
        ('PrimaryEmailAddress.get_target', None),
        ('QuarantineType.get_description', None),
        ('QuarantineType.get_id', None),
        ('QuarantineType.get_name', None),
        ('QuarantineTypeSearcher.search', None),
        ('RequestCode.get_description', None),
        ('RequestCode.get_id', None),
        ('RequestCode.get_name', None),
        ('Request.get_destination', None),
        ('Request.get_entity', None),
        ('Request.get_id', None),
        ('Request.get_operation', None),
        ('Request.get_requester', None),
        ('Request.get_run_at', None),
        ('Request.get_state_data', None),
        ('SearchClass.get_search_objects', None),
        ('SourceSystem.get_description', None),
        ('SourceSystem.get_id', None),
        ('SourceSystem.get_name', None),
        ('Spread.get_description', None),
        ('Spread.get_id', None),
        ('Spread.get_name', None),
        ('SpreadSearcher.search', None),
        ('SpreadSearcher.set_entity_type', None),
        ('Transaction.get_account_type', None),
        ('Transaction.get_address_type', None),
        ('Transaction.get_authentication_type', None),
        ('Transaction.get_auth_operation_code', None),
        ('Transaction.get_contact_info_type', None),
        ('Transaction.get_email_domain_category', None),
        ('Transaction.get_email_server_type', None),
        ('Transaction.get_email_spam_action', None),
        ('Transaction.get_email_spam_level', None),
        ('Transaction.get_email_target_type', None),
        ('Transaction.get_email_virus_found', None),
        ('Transaction.get_email_virus_removed', None),
        ('Transaction.get_encoding', None),
        ('Transaction.get_entity_external_id_type', None),
        ('Transaction.get_entity_type', None),
        ('Transaction.get_gender_type', None),
        ('Transaction.get_group_member_operation_type', None),
        ('Transaction.get_group_visibility_type', None),
        ('Transaction.get_home_status', None),
        ('Transaction.get_language_type', None),
        ('Transaction.get_name_type', None),
        ('Transaction.get_ou_perspective_type', None),
        ('Transaction.get_person_affiliation_type', None),
        ('Transaction.get_posix_shell', None),
        ('Transaction.get_quarantine_type', None),
        ('Transaction.get_request_code', None),
        ('Transaction.get_source_system', None),
        ('Transaction.get_spread', None),
        ('Transaction.get_value_domain', None),
        ('ValueDomain.get_description', None),
        ('ValueDomain.get_id', None),
        ('ValueDomain.get_name', None),
        ('View.get_accounts_cl', None),
        ('View.get_accounts', None),
        ('View.get_groups_cl', None),
        ('View.get_groups', None),
        ('View.get_ous_cl', None),
        ('View.get_ous', None),
        ('View.get_persons_cl', None),
        ('View.get_persons', None),
    ],
    'my_self': [
        ('Account.get_accounts', None),
        ('Account.get_authentications', None),
        ('Account.get_create_date', None),
        ('Account.get_creator', None),
        ('Account.get_direct_groups', None),
        ('Account.get_entity_name', None),
        ('Account.get_expire_date', None),
        ('Account.get_external_id', None),
        ('Account.get_external_ids', None),
        ('Account.get_gecos', None),
        ('Account.get_groups', None),
        ('Account.get_history', None),
        ('Account.get_homedir', None),
        ('Account.get_homes', None),
        ('Account.get_homepath', None),
        ('Account.get_id', None),
        ('Account.get_name', None),
        ('Account.get_owner', None),
        ('Account.get_owner_type', None),
        ('Account.get_posix_uid', None),
        ('Account.get_primary_group', None),
        ('Account.get_quarantines', None),
        ('Account.get_shell', None),
        ('Account.get_spreads', None),
        ('Account.get_type', None),
        ('Account.get_typestr', None),
        ('Account.is_expired', None),
        ('Account.is_posix', None),
        ('Account.is_quarantined', None),
        ('Account.set_password', None),
        ('Account.set_shell', None),
        ('EmailForward.set_enable', None),
        ('EmailTarget.get_addresses', None),
        ('EmailTarget.get_alias_value', None),
        ('EmailTarget.get_target_entity', None),
        ('EmailTarget.get_id', None),
        ('EmailTarget.get_primary_address', None),
        ('EmailTarget.get_target_type', None),
        ('EmailTarget.get_typestr', None),
        ('EmailTarget.get_using_uid', None),
        ('EmailTarget.set_alias_value', None),
        ('EmailTarget.set_primary_address', None),
        ('EmailTarget.add_forward', None),
        ('EmailTarget.add_vacation', None),
        ('EmailTarget.remove_forward', None),
        ('EmailTarget.remove_vacation', None),
        ('EmailVacation.get_enable', None),
        ('EmailVacation.get_end_date', None),
        ('EmailVacation.get_start_date',None),
        ('EmailVacation.get_vacation_text', None),
        ('EntityExternalId.get_external_id', None),
        ('EntityExternalId.get_id_type', None),
        ('Person.get_accounts', None),
        ('Person.get_active_quarantines', None),
        ('Person.get_addresses', None),
        ('Person.get_address', None),
        ('Person.get_affiliations', None),
        ('Person.get_all_affiliations', None),
        ('Person.get_all_contact_info', None),
        ('Person.get_all_quarantines', None),
        ('Person.get_birth_date', None),
        ('Person.get_cached_full_name', None),
        ('Person.get_contact_info', None),
        ('Person.get_deceased_date', None),
        ('Person.get_description', None),
        ('Person.get_direct_groups', None),
        ('Person.get_email_domain', None),
        ('Person.get_entity_name', None),
        ('Person.get_export_id', None),
        ('Person.get_external_id', None),
        ('Person.get_external_ids', None),
        ('Person.get_gender', None),
        ('Person.get_groups', None),
        ('Person.get_id', None),
        ('Person.get_name', None),
        ('Person.get_names', None),
        ('Person.get_primary_account', None),
        ('Person.get_quarantine', None),
        ('Person.get_quarantines', None),
        ('Person.get_spreads', None),
        ('Person.is_quarantined', None),
        ('PersonAffiliation.get_affiliation', None),
        ('PersonAffiliation.get_ou', None),
        ('PersonAffiliation.get_status', None),
    ],

    'abuse': [
        ('Account.add_quarantine', "sperret"),
    ],



    'sync_stud': [
        ('View.get_accounts', None),
        ('View.get_accounts_cl', None),
        ('View.get_groups', None),
        ('View.get_groups_cl', None),
        ('View.set_changelog', None),
        ('View.set_account_spread', 'user@stud'),
        ('View.set_group_spread', 'group@ntnu'),
        ('View.set_authentication_method', 'MD5-crypt'),
        ('View.set_authentication_method', 'crypt3-DES'),
        ('Commands.get_last_changelog_id', None),

        ('Transaction.get_home_status', None),
        ('Commands.get_host_by_name', None),
        ('HomeDirectorySearcher.add_join', None),
        ('HomeDirectorySearcher.set_status', None),
        ('HomeDirectorySearcher.search', None),
        ('DiskSearcher.set_host', None),
        ('HomeDirectory.get_disk', None),
        ('HomeDirectory.get_home', None),
        ('HomeDirectory.get_account', None),
        ('Disk.get_path', None),
        ('Account.get_name', None),
        ('Account.get_posix_uid', None),
        ('Account.get_primary_group', None),
        ('Group.get_posix_gid', None),
        ('HomeDirectory.set_status', None),
        ],

    'sync_kerberos': [
        ('View.get_accounts', None),
        ('View.get_accounts_cl', None),
        ('View.get_groups', None),
        ('View.get_groups_cl', None),
        ('View.set_changelog', None),
        ('View.set_account_spread', 'user@kerberos'),
        ('View.set_group_spread', 'group@ntnu'),
        ('View.set_authentication_method', 'PGP-kerberos'),
        ('Commands.get_last_changelog_id', None),
        ],
    'testset': [
        ('syncread_group', None),
        ('syncread_account', None),
        ('syncread_person', None),
        ('syncread_ou', None),
        ('syncread_alias', None),
        ('syncread_homedir', None),
        ('homedir_set_status', 'not_created'),
        ],
}


"""
op_roles = { (entity_type, entity_name, op_set, op_target), }
entity_type = 'group' | 'account'
entity_name = group_name | account_name
op_set = name of an op_set as defined above
op_target = (target_entity, target_id, target_value)
target_entity = 'entity' | 'global'
target_id = int
target_attr = None
"""
op_roles = [
    ('group', 'cereweb_orakel', 'cmodify_user', ('global_ou', None, None)),
    ('group', 'cereweb_orakel', 'cmodify_user', ('global_person', None, None)),
    ('group', 'cereweb_orakel', 'cmodify_user', ('global_account', None, None)),
    ('group', 'cereweb_orakel', 'ccreate_user', ('global_person', None, None)),
    ('group', 'cereweb_orakel', 'ccreate_user', ('global_group', None, None)),
    ('group', 'cereweb_orakel', 'cmodify_itea', ('global', None, None)),
    ('group', 'cereweb_orakel', 'cadmin_client', ('global', None, None)),

    ('group', 'cereweb_basic', 'ccreate_user', ('ou', 23, None)), # ou 23 er it-avdelingen
    ('group', 'cereweb_basic', 'cmodify_user', ('ou', 23, None)),
    ('group', 'cereweb_basic', 'cadmin_client', ('global', None, None)),
    ('group', 'cereweb_basic', 'login', ('cereweb', None, None)),

    # Backwards compatibility with spine.
    ('group', 'cereweb_orakel', 'modify_user', ('entity', None, None)),
    ('group', 'cereweb_orakel', 'create_user', ('entity', None, None)),
    ('group', 'cereweb_orakel', 'modify_itea', ('global', None, None)),
    ('group', 'cereweb_orakel', 'admin_client', ('global', None, None)),
    ('group', 'cereweb_basic', 'admin_client', ('global', None, None)),
    ('account', 'steinarh', 'testset', ('global_ou', None, None)),
    ('account', 'steinarh', 'testset', ('global_person', None, None)),
    ('account', 'steinarh', 'testset', ('global_group', None, None)),
    ('account', 'steinarh', 'testset', ('global_account', None, None)),
    ('account', 'steinarh', 'testset', ('host', 'jak.itea.ntnu.no')),
    ('account', 'steinarh', 'testset', ('spread', 'user@ansatt')),
    ('account', 'steinarh', 'testset', ('disk', '/home/ahomea')),
    ('account', 'steinarh', 'testset', ('ou', 'OI-ITAVD')),
    ('account', 'steinarh', 'testset', ('ou', 'IME-IMF')),
]
