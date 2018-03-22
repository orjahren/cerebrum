# -*- coding: utf-8 -*-
#
# Copyright 2004-2018 University of Oslo, Norway
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
""" example job config.

This is an example of scheduling settings that can be used in a
cerebrum installation.  See the documentation for job_runner for
details.
"""

from Cerebrum.modules.job_runner.job_actions import Action, System
from Cerebrum.modules.job_runner.times import When, Time


def get_jobs():
    sbin = '/cerebrum/sbin'
    ypsrc = '/cerebrum/yp/src'

    return {
        'import_from_lt': Action(
            call=System('%s/import_from_LT.py' % sbin),
            max_freq=6*60*60
        ),
        'import_ou': Action(
            pre=['import_from_lt'],
            call=System('%s/import_OU.py' % sbin),
            max_freq=6*60*60
        ),
        'import_lt': Action(
            pre=['import_ou', 'import_from_lt'],
            call=System('%s/import_LT.py' % sbin),
            max_freq=6*60*60
        ),
        'import_from_fs': Action(
            call=System('%s/import_from_FS.py' % sbin),
            max_freq=6*60*60
        ),
        'import_fs': Action(
            pre=['import_from_fs'],
            call=System('%s/import_FS.py' % sbin),
            max_freq=6*60*60,
        ),
        'process_students': Action(
            pre=['import_fs'],
            call=System('%s/process_students.py' % sbin),
            max_freq=5*60,
        ),
        'backup': Action(
            call=System('%s/backup.py' % sbin),
            max_freq=23*60*60,
        ),
        'rotate_logs': Action(
            call=System('%s/rotate_logs.py' % sbin),
            max_freq=23*60*60,
        ),
        'daily': Action(
            pre=['import_lt', 'import_fs', 'process_students'],
            call=None,
            when=When(time=[Time(min=[10], hour=[1])]),
            post=['backup', 'rotate_logs'],
        ),
        'generate_passwd': Action(
            call=System(
                '%s/generate_nismaps.py' % sbin,
                params=[
                    '--user_spread', 'NIS_user@uio',
                    '-p', '%s/passwd' % ypsrc,
                ]
            ),
            max_freq=5*60),
        'generate_group': Action(
            call=System(
                '%s/generate_nismaps.py' % sbin,
                params=[
                    '--group_spread', 'NIS_fg@ifi',
                    '-g', '%s/group' % ypsrc,
                ]
            ),
            max_freq=15*60
        ),
        'convert_ypmap': Action(
            call=System(
                'make',
                params=['-s', '-C', '/var/yp'],
                stdout_ok=1
            ),
            multi_ok=1
        ),
        'dist_passwords': Action(
            pre=['generate_passwd', 'convert_ypmap'],
            call=System('%s/passdist.pl' % sbin),
            max_freq=5*60,
            when=When(freq=10*60)
        ),
        'dist_groups': Action(
            pre=['generate_group', 'convert_ypmap'],
            call=System('%s/passdist.pl' % sbin),
            max_freq=5*60,
            when=When(freq=30*60)
        )
    }
