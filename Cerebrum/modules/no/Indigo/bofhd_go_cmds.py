# -*- coding: iso-8859-1 -*-
import cereconf

import mx
import pickle
from Cerebrum.Utils import Factory
from Cerebrum.modules.bofhd.errors import CerebrumError, PermissionDenied
from Cerebrum import Constants
from Cerebrum import Utils
from Cerebrum import Cache
from Cerebrum import Errors
from Cerebrum.modules.bofhd.cmd_param import Parameter,Command,FormatSuggestion,GroupName,GroupOperation
from Cerebrum.Constants import _CerebrumCode
from Cerebrum.modules.bofhd.auth import BofhdAuth
from Cerebrum.modules.bofhd.utils import _AuthRoleOpCode

def format_day(field):
    fmt = "yyyy-MM-dd"                  # 10 characters wide
    return ":".join((field, "date", fmt))

"""This class contains the bofh-functions needed by the indigo
www-interface.  To avoid code-duplication we re-use a number of
commands from the uio-module.  Currently none of these commands are
available to the standard command-line based bofh client.

To modify permissions, temporary start a separate bofhd with the
normal bofhd_uio_cmds so that the perm commands are available.
"""

class BofhdExtension(object):
    OU_class = Utils.Factory.get('OU')
    Account_class = Factory.get('Account')
    Group_class = Factory.get('Group')
    all_commands = {}

    copy_commands = (
        '_get_account', '_get_ou', '_format_ou_name', '_get_person',
        '_get_disk', '_get_group', '_map_person_id',
        'person_accounts', '_get_entity', 'group_user',
        'group_memberships', 'person_find', 'group_search',
        '_get_boolean', 'group_info', '_entity_info', 'num2str',
        'group_list', 'misc_list_passwords', '_get_cached_passwords',
        'user_password', '_get_entity_name', 'group_add_entity',
        'group_remove_entity', '_group_remove_entity',
        '_get_group_opcode', '_get_name_from_object',
        '_group_add_entity', '_group_count_memberships',
        'group_create', 'spread_add', '_get_constant',
        'misc_clear_passwords')

    def __new__(cls, *arg, **karg):
        # A bit hackish.  A better fix is to split bofhd_uio_cmds.py
        # into seperate classes.
        from Cerebrum.modules.no.uio.bofhd_uio_cmds import BofhdExtension as \
             UiOBofhdExtension

        for func in BofhdExtension.copy_commands:
            setattr(cls, func, UiOBofhdExtension.__dict__.get(func))
            if func[0] != '_' and func not in ('num2str',):
                BofhdExtension.all_commands[func] = UiOBofhdExtension.all_commands[func]
        x = object.__new__(cls)
        return x

    def __init__(self, server, default_zone='uio'):
        self.server = server
        self.logger = server.logger
        self.db = server.db
        self.const = Factory.get('Constants')(self.db)
        self.ba = BofhdAuth(self.db)

        # From uio
        self.num2const = {}
        self.str2const = {}
        for c in dir(self.const):
            tmp = getattr(self.const, c)
            if isinstance(tmp, _CerebrumCode):
                self.num2const[int(tmp)] = tmp
                self.str2const[str(tmp)] = tmp
        self._cached_client_commands = Cache.Cache(mixins=[Cache.cache_mru,
                                                           Cache.cache_slots,
                                                           Cache.cache_timeout],
                                                   size=500,
                                                   timeout=60*60)


    def get_help_strings(self):
        group_help = {
            }
        command_help = {
            }
        arg_help = {
            }
        return (group_help, command_help,
                arg_help)
    
    def get_commands(self, account_id):
        try:
            return self._cached_client_commands[int(account_id)]
        except KeyError:
            pass
        commands = {}
        for k in self.all_commands.keys():
            tmp = self.all_commands[k]
            if tmp is not None:
                if tmp.perm_filter:
                    if not getattr(self.ba, tmp.perm_filter)(account_id, query_run_any=True):
                        continue
                commands[k] = tmp.get_struct(self)
        self._cached_client_commands[int(account_id)] = commands
        return commands

    all_commands['get_auth_level'] = None
    def get_auth_level(self, operator):
        if self.ba.is_superuser(operator.get_entity_id()):
            return cereconf.BOFHD_AUTH_LEVEL['super']

        if self.ba.is_schoolit(operator.get_entity_id()):
            return cereconf.BOFHD_AUTH_LEVEL['schoolit']

        return cereconf.BOFHD_AUTH_LEVEL['other']

    all_commands['list_defined_spreads'] = None
    def list_defined_spreads(self, operator):
        return [{'code_str': str(y),
                 'desc': y._get_description(),
                 'entity_type': str(self.const.EntityType(y.entity_type))}
                for y in self.const.fetch_constants(self.const.Spread)]

    all_commands['get_entity_spreads'] = None
    def get_entity_spreads(self, operator, entity_id):
        entity = self._get_entity(id=int(entity_id))
        return [{'spread': str(self.const.Spread(int(row['spread']))),
                 'spread_desc': self.const.Spread(int(row['spread']))._get_description()}
                for row in entity.get_spread()]

    all_commands['get_default_email'] = None
    def get_default_email(self, operator, entity_id):
        account = self._get_account(entity_id)
        return account.get_primary_mailaddress()

    all_commands['user_get_pwd'] = None
    def user_get_pwd(self, operator, id):
        account = self._get_account(int(id),'id')
        pwd = account.get_account_authentication(self.const.auth_type_plaintext)
        return {'password': pwd,
                'uname': account.account_name}

    all_commands['list_active'] = None
    def list_active(self, operator):
        active = list()
        # IVR 2007-03-11 fetch the source system, which determines people that
        # are considered 'active'.
        source = int(getattr(self.const, cereconf.CWEB_ACTIVE_SOURCE_SYSTEM))
        for row in self.person.list_affiliations(source_system=source):
            active.append(row['person_id'])
        return active
        
    all_commands['user_info'] = None
    def user_info(self, operator, entity_id):
        account = self._get_account(entity_id)
        return {'entity_id': account.entity_id,
                'owner_id': account.owner_id,
                'owner_type': account.owner_type}

    all_commands['person_info'] = None
    def person_info(self, operator, person_id):
        try:
            person = self._get_person(*self._map_person_id(person_id))
        except Errors.TooManyRowsError:
            raise CerebrumError("Unexpectedly found more than one person")
        data = [{'name': person.get_name(self.const.system_cached,
                                         getattr(self.const,
                                                 cereconf.DEFAULT_GECOS_NAME)),
                 'export_id': person.export_id,
                 'birth': person.birth_date,
                 'entity_id': person.entity_id}]
        affiliations = []
        sources = []
#        for row in person.get_affiliations():
#            ou = self._get_ou(ou_id=row['ou_id'])
#            affiliations.append("%s@%s" % (
#                self.const.PersonAffStatus(row['status']),
#                self._format_ou_name(ou)))
#            sources.append(str(self.const.AuthoritativeSystem(row['source_system'])))
        if affiliations:
            data[0]['affiliation_1'] = affiliations[0]
            data[0]['source_system_1'] = sources[0]
        else:
            data[0]['affiliation_1'] = "<none>"
            data[0]['source_system_1'] = "<nowhere>"
        for i in range(1, len(affiliations)):
            data.append({'affiliation': affiliations[i],
                         'source_system': sources[i]})
        account = self.Account_class(self.db)
        account_ids = [int(r['account_id'])
                       for r in account.list_accounts_by_owner_id(person.entity_id)]
        if (self.ba.is_superuser(operator.get_entity_id()) or
            operator.get_entity_id() in account_ids):
            for row in person.get_external_id(id_type=self.const.externalid_fodselsnr):
                data.append({'fnr': row['external_id'],
                             'fnr_src': str(
                    self.const.AuthoritativeSystem(row['source_system']))})
        return data


    all_commands['user_create'] = None
    def user_create(self, operator, uname, owner_id):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")
        account = self.Account_class(self.db)
        entity = self._get_entity(id=int(owner_id))
        if entity.entity_type == int(self.const.entity_person):
            np_type=None
        else:
            np_type = self.const.account_program  # TODO: What value?  Or drop-down?

        account.populate(uname, entity.entity_type, owner_id, np_type,
                         operator.get_entity_id(), None)
        passwd = account.make_passwd(uname)
        account.set_password(passwd)
        account.write_db()
        operator.store_state("new_account_passwd", {
            'account_id': int(account.entity_id),
            'password': passwd})
        return "Ok, user created"

    all_commands['user_suggest_uname'] = None
    def user_suggest_uname(self, operator, owner_id):
        person = self._get_person("entity_id", owner_id)
        fname, lname = [person.get_name(self.const.system_cached, v)
                        for v in (self.const.name_first, self.const.name_last) ]
        account = self.Account_class(self.db)
        return account.suggest_unames(self.const.account_namespace, fname, lname)

    all_commands['misc_history'] = None
    def misc_history(self, operator, days):
        if not self.ba.is_superuser(operator.get_entity_id()):
            raise PermissionDenied("Currently limited to superusers")

        types = (self.const.account_create, self.const.account_password,
                 self.const.ou_create, self.const.person_create)
        sdate = mx.DateTime.now() - mx.DateTime.oneDay * int(days)
        # Collect in a dict to remove duplicates etc.
        tmp = {}
        for r in self.db.get_log_events(sdate=sdate, types=types):
            tmp.setdefault(int(r['subject_entity']), {})[int(r['change_type_id'])] = r

        ret = []
        for entity_id, changes in tmp.items():
            if (changes.has_key(int(self.const.account_password)) and not
                changes.has_key(int(self.const.account_create))):
                # TBD: n�r er det OK � vise passordet?
                del(changes[int(self.const.account_password)])
            
            for k, v in changes.items():
                cl = self.num2const[int(k)]
                params = ''
                if k == int(self.const.account_password):
                    if v['change_params']:
                        params = pickle.loads(v['change_params'])
                        params = params.get('password', '')
                tmp = {
                    'tstamp': v['tstamp'],
                    'change_type': str(cl),
                    'misc': params,
                    }
                entity = self._get_entity(id=int(v['subject_entity']))
                if entity.entity_type == int(self.const.entity_person):
                    person = self._get_person("entity_id", entity.entity_id)
                    name = person.get_name(self.const.system_cached,
                                           self.const.name_full)
                    tmp['person_id'] = int(person.entity_id)
                elif entity.entity_type == int(self.const.entity_account):
                    account = self.Account_class(self.db)
                    account.find(entity.entity_id)
                    name = account.account_name
                    tmp['person_id'] = int(account.owner_id)
                else:
                    ou = self.OU_class(self.db)
                    ou.find(entity.entity_id)
                    name = ou.name
                tmp['name'] = name
                ret.append(tmp)
        return ret

    def get_format_suggestion(self, cmd):
        return self.all_commands[cmd].get_fs()

# arch-tag: d1ad56e6-7155-11da-87dd-ea237fa9df60
