#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

# Copyright 2003 University of Oslo, Norway
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

import cerebrum_path

import getopt
import xml.sax
import sys
from Cerebrum.Utils import XMLHelper
from Cerebrum.utils.atomicfile import SimilarSizeWriter


class CollectParser(xml.sax.ContentHandler):
    def __init__(self, filename, results, hash_keys, append_file=False):
        self.results = results
        self.level = 0
        self.hash_keys = hash_keys
        self.append_file = append_file
        xml.sax.parse(filename, self)
        
    def startElement(self, name, attrs):
        self.level += 1
        if self.level > 1:
            tmp = {}
            hash_key = "�".join([attrs[x].encode('iso8859-1') for x in self.hash_keys])
            if self.append_file and hash_key not in self.results:
                return
            for k in attrs.keys():
                if k not in self.hash_keys:
                    tmp[k.encode('iso8859-1')] = attrs[k].encode('iso8859-1')
            tmp['TagName'] = name.encode('iso8859-1')
            self.results.setdefault(hash_key, []).append(tmp)
                        
    def endElement(self, name):
        self.level -= 1
        pass

def usage(exitcode=0):
    print """Usage: [options]

Merges data from several XML files into one big XML file.  The XML
files should look something like:

  <data><tag-to-merge common_key1="foo" common_key2="bar"></data>

For entities on level 2 (tag-to-merge above), the common_key(s)
are used as a key in an internal hash (with attributes as value),
which will contain data from all processed XML files.  Once all
files are parsed, the new XML file is written from this hash.

-t | -tag tag: name of tag in output file
-d | -delim delim: name of attribute(s) to use as common_key separated by :
-f | -file file: file to parse
-a | -append file: file to append
-o | -out file: file to write

-d and -f can be repeated.  The last -d is used as attribute names for
the -t tag.

Note: If you wish to append data from a file, the option '-a' must be
preceeded by the file you wish to append it to (orelse the result will
be empty).

Example:
merge_xml_files.py -d fodselsdato:personnr -f person_file.xml -f regkort.xml -t person -o out.dat

Note that memory usage may equal the total size of all XML files."""
    sys.exit(exitcode)

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'd:f:o:t:a:', ['delim=', 'file=', 'out=', 'tag=', 'append='])
    except getopt.GetoptError:
        usage(2)
        
    big_xml = {}
    for opt, val in opts:
        if opt in ('-t', '--tag'):
            tag = val
        elif opt in ('-d', '--delim'):
            delim = val.split(":")
        elif opt in ('-f', '--file'):
            CollectParser(val, big_xml, delim)
        elif opt in ('-a', '--append'):
            CollectParser(val, big_xml, delim, True)
        elif opt in ('-o', '--out'):
            f = SimilarSizeWriter(val, "w")
            f.set_size_change_limit(10)
            xml = XMLHelper()
            f.write(xml.xml_hdr + "<data>\n")
            for bx_key in big_xml.keys():
                bx_delim = bx_key.split("�")
                f.write("<%s %s>\n" % (
                    tag, " ".join(["%s=%s" % (
                    delim[n], xml.escape_xml_attr(bx_delim[n])) for n in range(len(delim))])))
                for tmp_tag in big_xml[bx_key]:
                    tmp = tmp_tag['TagName']
                    del(tmp_tag['TagName'])

                    f.write("  <%s %s/>\n" % (
                        tmp, " ".join(["%s=%s" % (
                        tk, xml.escape_xml_attr(tmp_tag[tk])) for tk in tmp_tag.keys()])))

                f.write("</%s>\n" % tag)
            f.write("</data>\n")
            f.close()

if __name__ == '__main__':
    main()

