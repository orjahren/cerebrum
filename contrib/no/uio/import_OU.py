#!/usr/bin/env python2.2

import re
import pickle
import sys

from Cerebrum import Database,Constants,Errors
from Cerebrum.modules.no.uio import OU
import pprint
pp = pprint.PrettyPrinter(indent=4)


class StedData(object):
    colnames = """fakultetnr, instituttnr, gruppenr, forkstednavn, stednavn,
        akronym, stedpostboks, fakultetnr_for_org_sted,
        instituttnr_for_org_sted, gruppenr_for_org_sted,
        opprettetmerke_for_oppf_i_kat, telefonnr,
        adrtypekode_besok_adr, adresselinje1_besok_adr,
        adresselinje2_besok_adr, poststednr_besok_adr,
        poststednavn_besok_adr, landnavn_besok_adr,
        adrtypekode_intern_adr, adresselinje1_intern_adr,
        adresselinje2_intern_adr, poststednr_intern_adr,
        poststednavn_intern_adr, landnavn_intern_adr,
        adrtypekode_alternativ_adr, adresselinje1_alternativ_adr,
        adresselinje2_alternativ_adr, poststednr_alternativ_adr,
        poststednavn_alternativ_adr, landnavn_alternativ_adr"""
    re_cols = re.compile(r"\s+", re.DOTALL)
    colnames = re.sub(re_cols, "", colnames)
    colnames = colnames.split(",")

    def parse_line(self, line):
	info = line.split("\034")
        stedinfo = {}
        for c in self.colnames:
            stedinfo[c] = info.pop(0)
            if(stedinfo[c] == ''):
                stedinfo[c] = None
        stedkode = get_stedkode_str( stedinfo['fakultetnr'],
                                     stedinfo['instituttnr'],
                                     stedinfo['gruppenr'] )
        return (stedkode, stedinfo)

verbose = 1
stedfile = "/u2/dumps/LT/sted.dta"

if len(sys.argv) == 2:
    stedfile = sys.argv[1]

def main():
    Cerebrum = Database.connect()
    steder = les_sted_info()
    co = Constants.Constants(Cerebrum)
    ou = OU.OU(Cerebrum)
    new_ou = OU.OU(Cerebrum)
    i = 1
    stedkode2ou = {}
    ou.clear()
    for k in steder.values():
        i = i + 1

        if verbose:
            print "Processing %s %s" % (
                get_stedkode_str(k['fakultetnr'], k['instituttnr'],
                                 k['gruppenr']),
                k['forkstednavn'])
        new_ou.clear()

        new_ou.populate(k['stednavn'], k['fakultetnr'],
                        k['instituttnr'], k['gruppenr'], acronym=k['akronym'],
                        short_name=k['forkstednavn'],
                        display_name=k['stednavn'],
                        sort_name=k['stednavn'])
        new_ou.affect_addresses(co.system_lt, co.address_street,
                                co.address_post)
        new_ou.populate_address(co.address_post, addr="%s\n%s" %
                                (k['adresselinje1_intern_adr'],
                                 k['adresselinje2_intern_adr']),
                                zip=k['poststednr_intern_adr'],
                                city=k['poststednavn_intern_adr'])
        new_ou.populate_address(co.address_street, addr="%s\n%s" %
                                (k['adresselinje1_besok_adr'],
                                 k['adresselinje2_besok_adr']),
                                zip=k['poststednr_besok_adr'],
                                city=k['poststednavn_besok_adr'])
        try:
            ou.find_stedkode(k['fakultetnr'], k['instituttnr'], k['gruppenr'])
            ou.find(ou.ou_id)

            if not (new_ou == ou):
                if verbose: print "  is changed"
                new_ou.write_db(ou)
            new_ou.ou_id = ou.ou_id
        except Errors.NotFoundError:
            if verbose: print "  is new"
            new_ou.write_db()
            
        stedkode = get_stedkode_str(k['fakultetnr'], k['instituttnr'],
                                    k['gruppenr'])
        stedkode2ou[stedkode] = new_ou.ou_id
        Cerebrum.commit()

    existing_ou_mappings = {}
    for node in ou.get_structure_mappings(co.perspective_lt):
        existing_ou_mappings[node.ou_id] = node.parent_id

    # Now populate ou_structure
    if verbose:
        print "Populate ou_structure"
    for stedkode in steder.keys():
        rec_make_stedkode(stedkode, ou, existing_ou_mappings, steder,
                          stedkode2ou, co)

def rec_make_stedkode(stedkode, ou, existing_ou_mappings, steder,
                      stedkode2ou, co):
    """Recursively create the ou_id -> parent_id mapping"""
    sted = steder[stedkode]
    org_stedkode = get_stedkode_str(sted['fakultetnr_for_org_sted'],
                                    sted['instituttnr_for_org_sted'],
                                    sted['gruppenr_for_org_sted'])
    if(not stedkode2ou.has_key(org_stedkode)):
        print "Error in dataset, %s references missing STEDKODE: %s, using None" % \
              (stedkode, org_stedkode)
        org_stedkode = None
        org_stedkode_ou = None
    else:
        org_stedkode_ou = stedkode2ou[org_stedkode]

    if(existing_ou_mappings.has_key(stedkode2ou[stedkode])):
        if(existing_ou_mappings[stedkode2ou[stedkode]] != org_stedkode_ou):
            print "Mapping for %s changed TODO (%s != %s)" % (
                stedkode, existing_ou_mappings[stedkode2ou[stedkode]],
                org_stedkode_ou)
        return

    if(org_stedkode_ou != None and (stedkode != org_stedkode) and
       (not existing_ou_mappings.has_key(org_stedkode_ou))):
        rec_make_stedkode(org_stedkode, ou, existing_ou_mappings, steder,
                          stedkode2ou, co)

    ou.find(stedkode2ou[stedkode])
    if stedkode2ou.has_key(org_stedkode):
        ou.set_parent(co.perspective_lt, stedkode2ou[org_stedkode])
    else:
        ou.set_parent(co.perspective_lt, None)
    existing_ou_mappings[stedkode2ou[stedkode]] = org_stedkode_ou

def les_sted_info():
    steder = {}
    f = file(stedfile)

    dta = StedData()

    for line in f.readlines():
        (stedkode, sted) = dta.parse_line(line)
        steder[stedkode] = sted
    return steder

def get_stedkode_str(faknr, instnr, groupnr):
    str = "%02d-%02d-%02d" % ( int(faknr), int(instnr), int(groupnr) )
    return str

if __name__ == '__main__':
    main()
