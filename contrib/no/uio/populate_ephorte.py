#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

import getopt
import sys
import cerebrum_path
import cereconf
from sets import Set
from Cerebrum import Utils
from Cerebrum import Errors
from Cerebrum.Utils import Factory, XMLHelper, SimilarSizeWriter
from Cerebrum.modules import CLHandler
from Cerebrum.modules.no.uio.Ephorte import EphorteRole

progname = __file__.split("/")[-1]
__doc__ = """
This script adds ephorte_roles and ephorte-spreads to persons
(employees) in Cerebrum according to the rules in
ephorte-sync-spec.rst

Usage: %s [options]
  -p fname : stedinfo

""" % progname

db = Factory.get('Database')()
db.cl_init(change_program="populate_ephorte")
co = Factory.get('Constants')(db)
ac = Factory.get('Account')(db)
pe = Factory.get('Person')(db)
group = Factory.get('Group')(db)
ephorte_role = EphorteRole(db)
ou = Factory.get("OU")(db)
cl = CLHandler.CLHandler(db)
logger = Factory.get_logger("cronjob")
ou_map_warnings = []
ou_mismatch_warnings = {'pols': [], 'ephorte': []}

class SimpleRole(object):
    def __init__(self, role_type, adm_enhet, arkivdel, journalenhet, auto_role=True):
        self.role_type = role_type
        self.adm_enhet = adm_enhet
        self.arkivdel = arkivdel
        self.journalenhet = journalenhet
        self.auto_role = auto_role

    def __eq__(self, b):
        return (self.role_type == b.role_type and self.adm_enhet == b.adm_enhet and
                self.arkivdel == b.arkivdel and self.journalenhet == b.journalenhet)

    def __str__(self):
        return "role_type=%s, adm_enhet=%s, arkivdel=%s, journalenhet=%s" % (
            self.role_type, self.adm_enhet, self.arkivdel,
            self.journalenhet)


class PopulateEphorte(object):
    def __init__(self, ephorte_sko_file):
        "Pre-fetch information about OUs in ePhorte and Cerebrum."

        logger.info("Fetching OU info from Cerebrum")
        ephorte_sko_ignore = ['null', '[Ufordelt]'] # Special sko, ignore
        sko2ou_id = {}           # stedkode -> ouid 
        self.ouid_2roleinfo = {} # ouid -> (arkivdel, journalenhet) 
        self.ouid2sko = {}       # ouid -> stedkode 
        for row in ou.get_stedkoder():
            sko = "%02i%02i%02i" % tuple([
                int(row[x]) for x in ('fakultet', 'institutt', 'avdeling')])
            ou_id = int(row['ou_id'])
            self.ouid2sko[ou_id] = sko
            sko2ou_id[sko] = ou_id
            # Specal case, SO
            if sko in cereconf.EPHORTE_SO_SKO:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_so), int(co.ephorte_journenhet_so))
            # Special case, NIKK
            elif sko in cereconf.EPHORTE_NIKK_SKO:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_nikk), int(co.ephorte_journenhet_nikk))
            # Default case
            else:
                self.ouid_2roleinfo[ou_id] = (
                    int(co.ephorte_arkivdel_sak_uio), int(co.ephorte_journenhet_uio))
        logger.info("Found info about %d sko in cerebrum" % len(self.ouid2sko))

        logger.info("Find OUs with spread ePhorte_ou (StedType=Arkivsted in POLS)")
        self.pols_ephorte_ouid2name = {}
        for row in ou.search(spread=co.spread_ephorte_ou):
            self.pols_ephorte_ouid2name[int(row['ou_id'])] = row['display_name']
        logger.info("Found %d ous with spread ePhorte_ou" %
                    len(self.pols_ephorte_ouid2name.keys()))
        ##
        ## GRUSOMT HACK
        ##
        # Dette hacket med � lese en fil som representerer
        # ephorte-steder skal vekk s� snart vi kan kj�re ekte
        # synkronisering av steder.
        #
        # ephorte_sko_file can be generated by running the command:
        # ./run_import.sh -d admindel -t AdminDel -p eph-conn.props
        #
        # This must be done automatically to prevent a situation where
        # the file is not synced with the info in the ephort app.
        # 
        logger.info("Fetching OU info from ePhorte reading file %s" % ephorte_sko_file)
        lines = file(ephorte_sko_file).readlines()
        tmp = lines.pop(0).split(';')
        posname2num = dict((tmp[n], n) for n in range(len(tmp)))
        self.app_ephorte_ouid2name = {}
        for line in lines:
            ephorte_sko = line.split(";")[posname2num['AI_FORKDN']]
            ephorte_name = line.split(";")[posname2num['AI_ADMBET']]
            ou_id = sko2ou_id.get(ephorte_sko)
            if ou_id is None:
                if ephorte_sko not in ephorte_sko_ignore:
                    logger.warn("Unknown ePhorte sko: '%s'" % ephorte_sko)
                continue
            self.app_ephorte_ouid2name[ou_id] = ephorte_name
        logger.info("Found %d ephorte sko from app." %
                     len(self.app_ephorte_ouid2name.keys()))
        for ou_id in Set(self.app_ephorte_ouid2name.keys()) - \
                Set(self.pols_ephorte_ouid2name.keys()):
            # Add ou to list that is sent in warn mail
            ou_mismatch_warnings['ephorte'].append((self.ouid2sko[ou_id],
                                                    self.app_ephorte_ouid2name[ou_id]))
            logger.info("OU (%6s: %s) in ephorte app, but has not ephorte spread" % (
                self.ouid2sko[ou_id], self.app_ephorte_ouid2name[ou_id]))
        for ou_id in Set(self.pols_ephorte_ouid2name.keys()) - \
                Set(self.app_ephorte_ouid2name.keys()):
            # Add ou to list that is sent in warn mail
            ou_mismatch_warnings['pols'].append((self.ouid2sko[ou_id],
                                                 self.pols_ephorte_ouid2name[ou_id]))
            logger.info("OU (%6s, %s) has ephorte spread, but is not in ephorte" % (
                self.ouid2sko[ou_id], self.pols_ephorte_ouid2name[ou_id]))
        ##
        ## GRUSOMT HACK SLUTT
        ##

        # Find the OU hierarchy 
        self.ou_id2parent = {}
        for row in ou.get_structure_mappings(co.perspective_sap):
            i = row['parent_id'] and int(row['parent_id']) or None
            self.ou_id2parent[int(row['ou_id'])] = i

        # superuser-rollen skal ha UiOs rotnode som adm_enhet
        self._superuser_role = SimpleRole(
            int(co.ephorte_role_sy), sko2ou_id[cereconf.EPHORTE_UIO_ROOT_SKO],
            int(co.ephorte_arkivdel_sak_uio), int(co.ephorte_journenhet_uio),
            auto_role=False)

    def map_ou2role(self, ou_id):
        arkiv, journal = self.ouid_2roleinfo[ou_id]
        return SimpleRole(int(co.ephorte_role_sb), ou_id, arkiv, journal)

    def find_person_info(self, person_id):
        ret = {'person_id': person_id}
        try:
            pe.clear()
            pe.find(person_id)
            tmp_id = pe.get_external_id(source_system=co.system_sap,
                                        id_type=co.externalid_sap_ansattnr)
            ret['sap_ansattnr'] = tmp_id[0]['external_id']
            ret['first_name'] = pe.get_name(source_system=co.system_sap,
                                            variant=co.name_first)
            ret['last_name'] = pe.get_name(source_system=co.system_sap,
                                           variant=co.name_last)
        except Errors.NotFoundError:
            logger.warn("Couldn't find person with id %s" % person_id)

        try:
            a_id = ac.list_accounts_by_type(person_id=person_id, primary_only=True)
            ac.clear()
            ac.find(a_id[0]['account_id'])
            ret['uname'] = ac.account_name
        except (Errors.NotFoundError, IndexError):
            logger.info("Couldn't find primary account for person %s" % person_id)
            ret['uname'] = ""
            

        return ret
    
    def run(self):
        """Automatically add roles and spreads for employees according to
        rules in ephorte-sync-spec.rst """

        logger.info("Listing affiliations")
        person2ou = {} # person -> {ou_id:1, ...}
        non_ephorte_ous = []
        # Find where an employee has an ANSATT affiliation and check
        # if that ou is an ePhorte ou. If not try to map to nearest
        # ePhorte OU as specified in ephorte-sync-spec.rst
        for row in pe.list_affiliations(source_system=co.system_sap,
                                        affiliation=co.affiliation_ansatt):
            ou_id = int(row['ou_id'])
            if ou_id is not None and ou_id not in self.app_ephorte_ouid2name:
                if not ou_id in non_ephorte_ous:
                    non_ephorte_ous.append(ou_id)
                    logger.debug("OU %s is not an ePhorte OU. Try parent: %s" % (
                        self.ouid2sko[ou_id],
                        self.ouid2sko.get(self.ou_id2parent.get(ou_id))))
                ou_id = self.ou_id2parent.get(ou_id)
            # No ePhorte OU found. Log a warning
            if ou_id is None or ou_id not in self.app_ephorte_ouid2name:
                sko = self.ouid2sko[int(row['ou_id'])]
                person_info = self.find_person_info(row['person_id'])
                ou_map_warnings.append(person_info)
                tmp_msg = "Failed mapping '%s' to known ePhorte OU. " % sko
                tmp_msg += "Skipping affiliation %s@%s for person %s" % (
                    co.affiliation_ansatt, sko, row['person_id'])
                logger.warn(tmp_msg)
                continue
            person2ou.setdefault(int(row['person_id']), {})[ou_id] = 1

        logger.info("Listing roles")
        person2roles = {}
        for row in ephorte_role.list_roles():
            person2roles.setdefault(int(row['person_id']), []).append(
                SimpleRole(int(row['role_type']), int(row['adm_enhet']),
                           row['arkivdel'], row['journalenhet'],
                           auto_role=(row['auto_role']=='T')))

        has_ephorte_spread = {}
        for row in pe.list_all_with_spread(co.spread_ephorte_person):
            has_ephorte_spread[int(row['entity_id'])] = True

        # Ideally, the group should have persons as members, but bofh
        # doesn't have much support for that, so we map user->owner_id
        # instead
        superusers = []
        group.find_by_name(cereconf.EPHORTE_ADMINS)
        for account_row in group.search_members(group_id=group.entity_id,
                                                indirect_members=True,
                                                member_type=co.entity_account):
            account_id = int(account_row["member_id"])
            ac.clear()
            ac.find(account_id)
            superusers.append(int(ac.owner_id))

        # All neccessary data has been fetched. Now we can check if
        # persons have the roles they should have.
        logger.info("Start comparison of roles")
        for person_id, ous in person2ou.items():
            auto_roles = []  # The roles an employee automatically should get
            existing_roles = person2roles.get(person_id, [])
            # Add saksbehandler role for each ephorte ou where an
            # employee has an affiliation
            for t in ous:
                auto_roles.append(self.map_ou2role(t))
            if person_id in superusers:
                auto_roles.append(self._superuser_role)
            # All employees shall have ephorte spread
            if not has_ephorte_spread.get(person_id):
                pe.clear()
                pe.find(person_id)
                pe.add_spread(co.spread_ephorte_person)

            for ar in auto_roles:
                # Check if role should be added
                if ar in existing_roles:
                    existing_roles.remove(ar)
                else:
                    logger.debug("Adding role (pid=%i): %s" % (person_id, ar))
                    ephorte_role.add_role(person_id, ar.role_type, ar.adm_enhet,
                                          ar.arkivdel, ar.journalenhet)
            for er in existing_roles:
                # Only saksbehandler role that has been given
                # automatically can be removed. Any other roles have
                # been given in bofh and should not be touched.
                if er.auto_role and er.role_type == int(co.ephorte_role_sb):
                    logger.debug("Removing role (pid=%i): %s" % (person_id, er))
                    ephorte_role.remove_role(person_id, er.role_type, er.adm_enhet,
                                             er.arkivdel, er.journalenhet)

        logger.info("All done")
        db.commit()

def mail_warnings(mailto, debug=False):
    """
    If warnings of certain types occur, send those as mail to address
    specified in mailto. If cereconf.EPHORTE_MAIL_TIME is specified,
    just send if time when script is run matches with specified time.
    """

    from mx import DateTime

    # Check if we should send mail today
    mail_today = False
    today = DateTime.today()
    for day in getattr(cereconf, 'EPHORTE_MAIL_TIME', []):
        if getattr(DateTime, day, None) == today.day_of_week:
            mail_today = True
    
    if mail_today and ou_map_warnings:
        mail_txt = '\n'.join(["%11s   %-10s   %s %s" %(
            x['sap_ansattnr'], x['uname'], x['first_name'], x['last_name'])
                              for x in ou_map_warnings])
        substitute = {'WARNINGS': mail_txt}
        send_mail(mailto, cereconf.EPHORTE_MAIL_WARNINGS, substitute,
                  debug=debug)

    if mail_today and (ou_mismatch_warnings['ephorte'] or
                       ou_mismatch_warnings['pols']):
        pols_warnings = '\n'.join(["%6s  %s" % x for x in
                                   ou_mismatch_warnings['pols']])
        ephorte_warnings = '\n'.join(["%6s  %s" % x for x in
                                      ou_mismatch_warnings['ephorte']])
        substitute = {'POLS_WARNINGS': pols_warnings,
                      'EPHORTE_WARNINGS': ephorte_warnings}
        send_mail(mailto, cereconf.EPHORTE_MAIL_WARNINGS2, substitute,
                  debug=debug)

def send_mail(mailto, mail_template, substitute, debug=False):
    ret = Utils.mail_template(mailto, mail_template, substitute=substitute,
                              debug=debug)
    if ret:
        logger.debug("Not sending mail:\n%s" % ret)
    else:
        logger.debug("Sending mail to: %s" % mailto)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'p:',
                                   ['help', 'mail-warnings-to=', 'mail-dryrun'])
    except getopt.GetoptError:
        usage(1)

    mail_warnings_to = None
    mail_dryrun = False
    for opt, val in opts:
        if opt in ('--help',):
            usage()
        elif opt in ('-p',):
            pop = PopulateEphorte(val)
            pop.run()
        elif opt in ('--mail-warnings-to',):
            mail_warnings_to = val
        elif opt in ('--mail-dryrun',):
            mail_dryrun = True
    if not opts:
        usage(1)
    if mail_warnings_to:
        mail_warnings(mail_warnings_to, debug=mail_dryrun)

def usage(exitcode=0):
    print __doc__
    sys.exit(exitcode)

if __name__ == '__main__':
    main()
