#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2006-2017 University of Oslo, Norway
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

"""
This file is part of the Cerebrum framework.

This script generates an XML file, suitable for importing into the CRISTIN
project, formerly called FRIDA.

The output format is specified at: <http://www.cristin.no/institusjonsdata/>

Although the original specification places a limit on the length of certain
(string) values, we do not enforce those. Furthermore, the address
'calculations' are a bit involved.

Since this script aggregates data from various sources, we cannot obtain all
the necessary information from data files or cerebrum alone. Therefore:

* Most of the information about people is fetched from the SAP source file
  Cerebrum has no information about employments (stillingskode,
  stillingsandel, aktivDatoFra/Til).

* Most of the information about OUs is fetched from the source files (two
  essential things are missing in cerebrum -- NSDKode for OUs (something that
  can easily be fixed by importing these as EntityExternalIDs), and
  start/termination dates for OUs (which cannot easily be deduced, although an
  'expired' OU gets a quarantine that we can look up)

Additionally, we have to look up phd-students in FS or Cerebrum, since neither
of the HR systems tracks students. Cerebrum is the preferred solution, since
the data is checked on import.
"""

import getopt
import sys
import time

import cereconf

from Cerebrum import Errors
from Cerebrum.Utils import Factory
from Cerebrum.utils.atomicfile import AtomicFileWriter
from Cerebrum.extlib import xmlprinter

from Cerebrum.modules.xmlutils.system2parser import system2parser
from Cerebrum.modules.xmlutils.xml2object import DataAddress
from Cerebrum.modules.xmlutils.xml2object import DataContact
from Cerebrum.modules.xmlutils.xml2object import DataEmployment


logger = Factory.get_logger("cronjob")
cerebrum_db = Factory.get("Database")()
constants = Factory.get("Constants")(cerebrum_db)
ou_db = Factory.get("OU")(cerebrum_db)
person_db = Factory.get("Person")(cerebrum_db)
source_system = None


class OUNotFoundException(Exception):
    """Exception for cases where OU is not defined in XML."""
    pass


def output_element(writer, value, element, attributes=dict()):
    """A helper function to output XML elements.

    The output element would look like this:

      <ELEMENT KEY1="VALUE1" KEY2="VALUE2" ... >
        VALUE
      </ELEMENT>

    ... where KEY,VALUE pairs come from ATTRIBUTES

    This function is just a shorthand, to avoid mistyping the element names
    in open and close tags.

    :param xmlprinter writer: The XML writer backend, with an open file.
    :param str value: The element value
    :param str element: The tag-name of the element
    :param dict attributes: Optional set of attributes for the element

    """
    # If there are no attributes and no textual value for the element, we do
    # not need it.
    if not attributes and (value is None or not str(value)):
        return

    writer.startElement(element, attributes)
    writer.data(str(value))
    writer.endElement(element)


def xml2dict(xmlobject, attributes):
    """Extract the essential attributes from en XML-object.

    Returns a dictionary that represents the same information.

    """
    result = dict()
    for attr in attributes:
        value = getattr(xmlobject, attr)
        # FIXME: hack to make things easier afterwards
        if value and attr == "place":
            value = value[1]
        result[attr] = value

    if "place" not in result:
        logger.error("%s has no place!", xmlobject)
        raise OUNotFoundException("%s has no place!", xmlobject)

    return result


def extract_names(person_db, kinds):
    """Return a mapping kind->name of names of the required kinds."""

    result = dict()
    all_names = person_db.get_all_names()
    for name in all_names:
        kind = int(name["name_variant"])
        source = int(name["source_system"])
        value = name["name"]
        if kind not in kinds:
            continue

        # if we have not seen the proper name variant, grab it now
        if kind not in result:
            result[kind] = value
        # ... and if current source matches source_system, then this is the
        # best match possible, so take it.
        elif int(source) == int(source_system):
            result[kind] = value

    return result


def output_contact(writer, xmlobject, *seq):
    """Output contact information (seq) for xmlobject.

    seq is a sequence of tuples (kind, xml-attribute-name).

    """
    for attribute, element in seq:
        # We have to respect the relative priority order
        # TBD: Should we hide this ugliness inside DataContact?
        contacts = filter(lambda x: x.kind == attribute,
                          xmlobject.itercontacts())
        contacts.sort(lambda x, y: cmp(x.priority, y.priority))
        if contacts:
            output_element(writer, contacts[0].value, element)


def find_publishable_sko(sko, ou_cache):
    """Locate a publishable OU starting from sko and return its sko.

    We walk upwards the hierarchy tree until we run out of parents or a until
    a suitable publishable OU is located.

    """

    ou = ou_cache.get(sko)
    while ou:
        if ou.publishable:
            publishable_sko = ou.get_id(ou.NO_SKO, None)
            if not publishable_sko:
                logger.warn("OU %s has no SKO and will not be published",
                            list(ou.iterids()))
            return publishable_sko

        parent_sko = None
        if ou.parent:
            assert ou.parent[0] == ou.NO_SKO
            parent_sko = ou.parent[1]
        ou = ou_cache.get(parent_sko)

    return None


def output_OU(writer, ou):
    """Publish a particular OU.

    Each OU is described thus:

      <enhet>
        <institusjonsnr>...</...>      <!-- stedkode.institusjon -->
        <avdnr>...</avdnr>             <!-- stedkode.fakultet -->
        <undavdnr>...</undavdnr>       <!-- stedkode.institutt -->
        <gruppenr>...</gruppenr>       <!-- stedkode.avdeling -->
        <institusjonsnrUnder>...</...> <!-- parent.stedkode.institusjon -->
        <avdnrUnder>...</...>          <!-- parent.stedkode.fakultet -->
        <undavdnrUnder>...</...>       <!-- parent.stedkode.institutt -->
        <gruppenrUnder>...</...>       <!-- parent.stedkode.avdeling -->

        <datoAktivFra>...</...>        <!-- LT.STED.DATO_OPPRETTET -->
        <datoAktivTil>...</...>        <!-- LT.STED.DATO_NEDLAGT -->
        <navnBokmal>...</...>          <!-- LT.STED.STEDLANGNAVN_BOKMAL
                                                    STEDKORTNAVN_BOKMAL
                                                    STEDNAVNFULLT
                                                    STEDNAVN -->
        <navnEngelsk>...</...>         <!-- LT.STED.STEDLANGNAVN_ENGELSK
                                                    STEDKORTNAVN_ENGELSK -->
        <akronym>...</...>             <!-- LT.STED.AKRONYM -->
        <postadresse>...</...>  <!-- LT.STED.ADDRESSELINJE{1+2}_INTERN_ADR -->
        <postnrOgPoststed>...</...>    <!-- LT.STED.POSTSTEDNR_INTERN_ADR +
                                            LT.STED.POSTSTEDNAVN_INTERN_ADR -->
        <land>...</...>                <!-- LT.STED.LANDNAVN_INTERN_ADR -->
        <telefonnr>                    <!-- LT.STEDKOMM.TELEFONNR &&
                                            LT.STEDKOMM.KOMMTYPEKODE = "TLF" &&
                                            MIN(LT.STEDKOMM.TLFPREFTEGN) -->
        <telefaxnr>                    <!-- LT.STEDKOMM.TELEFONNR &&
                                            LT.STEDKOMM.KOMMTYPEKODE = "FAX"
                                            MIN(LT.STEDKOMM.TLFPREFTEGN -->
        <epost>                        <!-- LT.STEDKOMM.KOMMNRVERDI &&
                                            LT.STEDKOMM.KOMMTYPEKODE = "EPOST"
                                            MIN(LT.STEDKOMM.TLFPREFTEGN) -->
        <URLBokmal>                    <!-- LT.STEDKOMM.KOMMNRVERDI &&
                                            LT.STEDKOMM.KOMMTYPEKODE = "URL"
                                            MIN(LT.STEDKOMM.TLFPREFTEGN) -->
      </enhet>

    """

    if ou is None:
        return
    sko = ou.get_id(ou.NO_SKO)

    # output OU info
    writer.startElement("enhet")
    for value, element in ((cereconf.DEFAULT_INSTITUSJONSNR, "institusjonsnr"),
                           (sko[0], "avdnr"),
                           (sko[1], "undavdnr"),
                           (sko[2], "gruppenr")):
        output_element(writer, value, element)

    # Is a missing parent at all possible here?
    if ou.parent:
        assert ou.parent[0] == ou.NO_SKO
        psko = ou.parent[1]
    else:
        psko = (None, None, None)

    for value, element in (
            (cereconf.DEFAULT_INSTITUSJONSNR, "institusjonsnrUnder"),
            (psko[0], "avdnrUnder"),
            (psko[1], "undavdnrUnder"),
            (psko[2], "gruppenrUnder")):
        output_element(writer, value, element)

    for attribute, element in (("start_date", "datoAktivFra"),
                               ("end_date", "datoAktivTil")):
        value = getattr(ou, attribute)
        if value:
            value = value.strftime("%Y-%m-%d")
        output_element(writer, value, element)

    for kind, lang, element in ((ou.NAME_LONG, "no", "navnBokmal"),
                                (ou.NAME_LONG, "nb", "navnBokmal"),
                                (ou.NAME_LONG, "en", "navnEngelsk")):
        tmp = ou.get_name_with_lang(kind, lang)
        output_element(writer, tmp, element)

    nsd = ou.get_id(ou.NO_NSD)
    if nsd:
        output_element(writer, str(nsd), "NSDKode")

    output_element(writer, ou.get_name_with_lang(ou.NAME_ACRONYM, "no",
                   "nb", "nn", "en"),
                   "akronym")

    # Grab the first available address
    for kind in (DataAddress.ADDRESS_BESOK, DataAddress.ADDRESS_POST):
        addr = ou.get_address(kind)
        if addr:
            output_element(writer, addr.street, "postadresse")
            output_element(writer, (addr.zip + " " + addr.city).strip(),
                           "postnrOgPoststed")
            output_element(writer, addr.country, "land")
            break

    output_contact(writer, ou,
                   (DataContact.CONTACT_PHONE, "telefonnr"),
                   (DataContact.CONTACT_FAX, "telefaxnr"),
                   (DataContact.CONTACT_EMAIL, "epost"),
                   (DataContact.CONTACT_URL, "URLBokmal"))

    writer.endElement("enhet")


def output_OUs(writer, sysname, oufile):
    """Run through all OUs and publish the interesting ones.

    An OU is interesting to FRIDA, if:

      - the OU is supposed to be published (marked as such in the data source)
      - it has been less than a year since the OU has been terminated.

    """

    # First we build an ID cache.
    ou_cache = dict()
    parser = system2parser(sysname)(oufile, logger, False)
    for ou in parser.iter_ou():
        sko = ou.get_id(ou.NO_SKO, None)
        if sko:
            ou_cache[sko] = ou

    logger.info("Cached info on %d OUs from %s", len(ou_cache), oufile)

    result = set()
    writer.startElement("organisasjon")
    for sko in ou_cache:
        publishable_sko = find_publishable_sko(sko, ou_cache)
        if not publishable_sko:
            logger.debug("Cannot find publishable sko starting from %s", sko)
            continue

        if publishable_sko in result:
            continue

        output_OU(writer, ou_cache[publishable_sko])
        result.add(publishable_sko)

    writer.endElement("organisasjon")
    return ou_cache


def output_assignments(writer, sequence, ou_cache, blockname, elemname, attrs):
    """Output tilsetting/gjest information.

    The format is:

      <blockname>
        <elemname>
          <k1>x.v1</k1>
          <k2>x.v2</k2>
        </elemname>
      </blockname>

    ... where attrs is a mapping from k1 -> v1 and sequence contains the x's
    to be output.

    Parameters:

    :param xmliprinter writer: Helper class to generate XML output
    :param iter sequence: A sequence of objects that we want to output. each
        object can be indexed as a dictionary.
    :param dict ou_cache: OU mappings registered for this import. Used to
        locate publishable OUs (generated by `output_OUs`).
    :param str blockname: XML element name for a grouping represented by
        sequence.
    :param str elemname: XML element name for each element of sequence.
    :param dict attrs: A dictionary-like object key->xmlname, where key can be
        used to extract values from each member of sequence.

    """

    # if there is nothing to output we are done
    if not sequence:
        return

    if blockname:
        writer.startElement(blockname)

    for item in sequence:
        sko = item["place"]
        publishable_sko = find_publishable_sko(sko, ou_cache)
        if not publishable_sko:
            logger.debug("Cannot locate publishable sko starting from %s", sko)
            continue

        writer.startElement(elemname)
        for value, xmlelement in (
                (cereconf.DEFAULT_INSTITUSJONSNR, "institusjonsnr"),
                (publishable_sko[0], "avdnr"),
                (publishable_sko[1], "undavdnr"),
                (publishable_sko[2], "gruppenr")):
            output_element(writer, value, xmlelement)

        for key, xmlelement in attrs.iteritems():
            # The key is among the names passed to us, but since it is output
            # specially, no action should be taken here.
            if key == "place":
                continue
            value = item[key]
            # FIXME: DateTime hack. SIGTHTBABW
            if hasattr(value, "strftime"):
                value = value.strftime("%Y-%m-%d")
            output_element(writer, value, xmlelement)

        writer.endElement(elemname)

    if blockname:
        writer.endElement(blockname)


def output_account_info(writer, person_db):
    """Output primary account and e-mail informatino for person_db."""

    primary_account = person_db.get_primary_account()
    if primary_account is None:
        logger.info("Person %s has no accounts", person_db.entity_id)
        return

    account_db = Factory.get("Account")(cerebrum_db)
    account_db.find(primary_account)
    output_element(writer, account_db.get_account_name(), "brukernavn")

    try:
        primary_email = account_db.get_primary_mailaddress()
        output_element(writer, primary_email, "epost")
    except Errors.NotFoundError:
        logger.info("person %s has no primary e-mail address",
                    person_db.entity_id)


def output_employments(writer, person, ou_cache):
    """Output <ansettelser>-element."""

    employments = [x for x in person.iteremployment()
                   if x.kind in (x.HOVEDSTILLING, x.BISTILLING) and
                   x.is_active()]

    # Mapping from employment attribute to xml element name.
    names = dict((("code", "stillingskode"),
                  ("start", "datoFra"),
                  ("end", "datoTil"),
                  ("percentage", "stillingsandel"),))
    languages = ("nb", "nn", "en")

    output_sequence = list()
    for employment in employments:
        values = dict((key, getattr(employment, key))
                      for key in names)
        # grab sko
        try:
            values["place"] = employment.place[1]
        except TypeError:
            # Some employments, like 8;50, does not come with a placecode. It
            # is perfectly natural to skip them at this stage.
            continue
        # grab title
        values["title"] = employment.get_name_with_lang(employment.WORK_TITLE,
                                                        *languages)
        output_sequence.append(values)

    # Register the keys that needed special processing.
    names["title"] = "stillingsbetegnelse"
    names["place"] = None
    return output_assignments(writer, output_sequence, ou_cache,
                              "ansettelser", "ansettelse", names)


def output_person(writer, person, phd_cache, ou_cache):
    """Output all information pertinent to a particular person.

    Each <person> is described thus:

    <person fnr="..." reservert="X">
      <etternavn>...</etternavn>
      <fornavn>...</fornavn>
      <brukernavn>...</brukernavn>  <!-- primary user account -->
      <telefonnr>...</telefonnr>
      <telefaxnr>...</telefaxnr>
      <epost>...</epost>            <!-- primary user account? -->
      <URL>...</URL>                <!-- ?? -->
      <personligTittel>...</...>    <!-- ?? -->
      <ansettelser>
        ...
      </ansettelser>
      <gjester>
        ...
      </gjester>
    <person>

    """
    reserved = {True: "J",
                False: "N",
                None: "N", }[person.reserved]
    fnr = person.get_id(person.NO_SSN)

    if not fnr:
        logger.info("Skipping person without fnr. person=%s", str(person))
        return

    writer.startElement("person", {"fnr": fnr,
                                   "reservert": reserved, })
    for attribute, element in ((person.NAME_LAST, "etternavn"),
                               (person.NAME_FIRST, "fornavn")):
        name = person.get_name(attribute, None)
        if name:
            name = name[0].value
        output_element(writer, name, element)

    title = person.get_name_with_lang(person.NAME_TITLE, "nb", "en")
    if title:
        output_element(writer, title, "personligTittel")

    phds = list()
    try:
        person_db.clear()
        person_db.find_by_external_id(constants.externalid_fodselsnr, fnr)
        phds = phd_cache.get(int(person_db.entity_id), list())
        if phds:
            del phd_cache[int(person_db.entity_id)]
    except Errors.NotFoundError:
        logger.error("Person %s is in the datafile, but not in Cerebrum",
                     list(person.iterids()))
    except Errors.TooManyRowsError:
        logger.error("Found more than one person with NO_SSN=%s", fnr)
    else:
        output_account_info(writer, person_db)

    output_contact(writer, person,
                   (DataContact.CONTACT_PHONE, "telefonnr"),
                   (DataContact.CONTACT_FAX, "telefaxnr"),
                   (DataContact.CONTACT_URL, "URL"))

    output_employments(writer, person, ou_cache)

    guests = filter(lambda x: x.kind == x.GJEST and x.is_active(),
                    person.iteremployment())
    if guests or phds:
        writer.startElement("gjester")
        names = dict((("start", "datoFra"),
                      ("end", "datoTil"),
                      ("code", "gjestebetegnelse"),
                      ("place", None)))
        output_assignments(writer, [xml2dict(x, names) for x in guests],
                           ou_cache, None, "gjest", names)

        output_assignments(writer, phds, ou_cache, None, "gjest", names)
        writer.endElement("gjester")

    writer.endElement("person")


def cache_phd_students():
    """Load all PhD students from cerebrum and return a set of their IDs"""

    result = dict()
    person = Factory.get("Person")(cerebrum_db)
    ou_db = Factory.get("OU")(cerebrum_db)

    for row in person.list_affiliations(
            status=constants.affiliation_status_student_drgrad):
        key = int(row["person_id"])

        try:
            ou_db.clear()
            ou_db.find(row["ou_id"])
        except Errors.NotFoundError:
            logger.warn("OU with ou_id %s does not exist. This cannot happen",
                        row["ou_id"])
            continue

        value = {"start": row["create_date"],
                 "end": row["deleted_date"],
                 "code": "DOKTORGRADSSTUDENT",
                 "place": (ou_db.fakultet, ou_db.institutt, ou_db.avdeling)}
        result.setdefault(key, list()).append(value)

    return result


def output_phd_students(writer, sysname, phd_students, ou_cache):
    """Output information about PhD students based on Cerebrum only.

    There may be phd students who have no employment/guest records at
    all. However, they still need access to FRIDA and we need to gather as
    much information as possible about them.
    """
    # name constant -> xml element for that name constant
    name_kinds = dict(((int(constants.name_last), "etternavn"),
                       (int(constants.name_first), "fornavn")))
    # contact constant -> xml element for that contact constant
    contact_kinds = dict(((int(constants.contact_phone), "telefonnr"),
                          (int(constants.contact_fax), "telefaxnr"),
                          (int(constants.contact_url), "URL")))
    # person_id -> public reservation status
    reservations = dict(
        (row['entity_id'], row['numval']) for row in
        person_db.list_traits(code=constants.trait_public_reservation))

    for person_id, phd_records in phd_students.iteritems():
        try:
            person_db.clear()
            person_db.find(person_id)
            # We can be a bit lenient here.
            fnr = person_db.get_external_id(
                id_type=constants.externalid_fodselsnr)
            if fnr:
                fnr = fnr[0]["external_id"]
            else:
                logger.warn("No fnr for person_id %s", person_id)
                continue
        except Errors.NotFoundError:
            logger.warn(
                "Cached id %s not found in the database. This cannot happen",
                person_id)
            continue

        res_status = 'J' if reservations.get(person_id, True) else 'N'
        writer.startElement("person", {"fnr": fnr, "reservert": res_status})

        names = extract_names(person_db, name_kinds)
        for variant, xmlname in name_kinds.iteritems():
            value = names.get(variant)
            if value:
                output_element(writer, value, xmlname)
        title = person_db.get_name_with_language(
            name_variant=constants.personal_title,
            name_language=constants.language_nb,
            default="")
        if title:
            output_element(writer, title, "personligTittel")

        output_account_info(writer, person_db)

        for contact_kind in contact_kinds:
            value = person_db.get_contact_info(source_system, contact_kind)
            if value:
                value = value[0]["contact_value"]
                output_element(writer, value, contact_kinds[contact_kind])

        names = dict((("start", "datoFra"),
                      ("end", "datoTil"),
                      ("code", "gjestebetegnelse"),
                      ("place", None)))
        output_assignments(writer, phd_records, ou_cache, "gjester", "gjest",
                           names)
        writer.endElement("person")


def should_export_person(person):
    """ Test to decide whether a person should be exported.

    Returns True by default, unless some exception rule matches (i.e. any
    person from the SAP import file is exported, unless a filter rule applies).

    NOTE: Any person filtered out by this method can still get exported, if the
    person has a PhD-affiliation in Cerebrum. PhD-students gets processed
    separately.

    """
    # This step is added for clarity in the logs.
    # Filter out any person that has no employment record.
    employments = [e for e in person.iteremployment()]
    if not employments:
        logger.debug2("Skipping, person_id %s has no employment records",
                      list(person.iterids()))
        return False

    # All employments that are *NOT* MG/MUG 4;04
    # Filters out persons that *only* has 4;04 employment records
    employments = filter(lambda x: not (x.mg == 4 and x.mug == 4),
                         person.iteremployment())
    if not employments:
        logger.debug2("Skipping, person_id %s only has MG/MUG 404 records",
                      list(person.iterids()))
        return False

    # Filter out people that have 8;50 as a HOVEDSTILLING, unless they have a
    # GJEST role of appropriate type:
    assignments = filter(lambda x: x.kind in [DataEmployment.HOVEDSTILLING],
                         person.iteremployment())
    assignments_8_50 = filter(lambda x: x.mg == 8 and x.mug == 50,
                              assignments)

    guest_roles = filter(lambda x: (x.kind == DataEmployment.GJEST and
                                    x.code in ['EF-FORSKER',
                                               'EF-STIP',
                                               'EMERITUS',
                                               'ASSOSIERT',
                                               'GJ-FORSKER']),
                         person.iteremployment())

    if (assignments_8_50 and assignments_8_50 == assignments and
            not guest_roles):
        logger.debug2("Skipping, person_id %s only has MG/MUG 8;50 records and"
                      " has no applicable role", list(person.iterids()))
        return False

    # Filters out persons that has no *active* employment of types
    # 'Hovedstilling', 'Bistilling' or 'Gjest'.
    active = filter(lambda x: (x.is_active() and x.kind in (x.HOVEDSTILLING,
                                                            x.BISTILLING,
                                                            x.GJEST)),
                    person.iteremployment())
    if not (active):
        logger.debug2(
            "Skipping, person_id %s has no active tils/gjest records",
            list(person.iterids()))
        return False

    # Future filters?

    return True


def output_people(writer, sysname, personfile, ou_cache):
    """Output information about all interesting people.

    A person is interesting for FRIDA, if it has active employments
    (tilsetting) or active guest records (gjest). A record is considered
    active, if it has a start date in the past (compared to the moment when
    the script is run) and the end date is either unknown or in the future.

    """
    logger.info("extracting people from %s", personfile)

    phd_students = cache_phd_students()
    logger.info("cached PhD students (%d people)", len(phd_students))

    writer.startElement("personer")
    parser = system2parser(sysname)(personfile, logger, fetchall=False)
    for person in parser.iter_person(filter_out_sko_0000=False,
                                     require_ou_for_assignments=False):
        if not should_export_person(person):
            continue

        # NB! phd_students is updated destructively
        output_person(writer, person, phd_students, ou_cache)

    # process whatever is left of phd-students
    output_phd_students(writer, sysname, phd_students, ou_cache)
    writer.endElement("personer")


def output_xml(output_file, sysname, personfile, oufile):
    """Output the data from sysname source."""

    output_stream = AtomicFileWriter(output_file, "w")
    writer = xmlprinter.xmlprinter(output_stream,
                                   indent_level=2,
                                   data_mode=True,
                                   input_encoding="latin1")

    # Hardcoded headers
    writer.startDocument(encoding="iso8859-1")

    writer.startElement("fridaImport")

    writer.startElement("beskrivelse")
    output_element(writer, "UIO", "kilde")
    # ISO8601 style -- the *only* right way :)
    output_element(writer, time.strftime("%Y-%m-%d %H:%M:%S"), "dato")
    output_element(writer, "UiO-FRIDA", "mottager")
    writer.endElement("beskrivelse")

    writer.startElement("institusjon")
    output_element(writer, cereconf.DEFAULT_INSTITUSJONSNR, "institusjonsnr")
    output_element(writer, "Universitetet i Oslo", "navnBokmal")
    output_element(writer, "University of Oslo", "navnEngelsk")
    output_element(writer, "UiO", "akronym")
    output_element(writer, "1110", "NSDKode")
    writer.endElement("institusjon")

    # Dump all OUs
    ou_cache = output_OUs(writer, sysname, oufile)

    # Dump all people
    output_people(writer, sysname, personfile, ou_cache)

    writer.endElement("fridaImport")
    writer.endDocument()
    output_stream.close()


def usage(exitcode=0):
    print """Usage: generate_frida_export.py [options]

    -o, --output-file  FILE  The ePhorte XML export file
    -s, --source-spec  SPEC  The source data spec. Format:

    The input SPEC is on the format <system>:<person-file>:<ou-file>, where
      - system is the source system
      - person-file is the person source xml file
      - ou-file is the OU source xml file
    """
    sys.exit(exitcode)


def main():
    logger.info("Generating FRIDA export")

    try:
        options, rest = getopt.getopt(sys.argv[1:],
                                      "o:s:", ["output-file=",
                                               "source-spec=", ])
    except getopt.GetoptError:
        usage(1)

    output_file = "frida.xml"

    for option, value in options:
        if option in ("-o", "--output-file"):
            output_file = value
        elif option in ("-s", "--source-spec"):
            sysname, personfile, oufile = value.split(":")

    global source_system
    source_system = getattr(constants, sysname)
    output_xml(output_file, sysname, personfile, oufile)


if __name__ == "__main__":
    main()
