#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for Cerebrum.auth """
from __future__ import unicode_literals

import logging
import unittest

import Cerebrum.auth

from Cerebrum.auth import all_auth_methods
from Cerebrum.Utils import Factory
from Cerebrum.Account import Account

from datasource import BasicAccountSource, BasicPersonSource
from dbtools import DatabaseTools

logger = logging.getLogger(__name__)

# TODO:
#
# Not imploemented tests for
#  - Account/AccountType
#  - Account/AccountHome


class BaseAccountTest(unittest.TestCase):
    """
    This is a testcase for Cerebrum.Account class.

    No subclass or mixin should cause this test to fail, so the test is valid
    for other setups as well.
    Mixins and subclasses can subclass this test in order to perform additional
    setup and tests.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up this TestCase module.

        This setup code sets up shared objects between each tests. This is done
        *once* before running any of the tests within this class.
        """

        # TODO: We might want this basic class setup in other TestCases. Maybe
        #       set up a generic TestCase class to inherit common stuff from?
        cls._db = Factory.get('Database')()
        cls._db.cl_init(change_program='nosetests')
        cls._db.commit = cls._db.rollback  # Let's try not to screw up the db

        cls._ac = Factory.get('Account')(cls._db)
        cls._ac = Account(cls._db)
        cls._co = Factory.get('Constants')(cls._db)

        # Data sources
        cls.account_ds = BasicAccountSource()
        cls.person_ds = BasicPersonSource()

        # Tools for creating and destroying temporary db items
        cls.db_tools = DatabaseTools(cls._db)
        cls.db_tools._ac = cls._ac

    @classmethod
    def tearDownClass(cls):
        """ Clean up this TestCase class. """
        cls.db_tools.clear_groups()
        cls.db_tools.clear_accounts()
        cls.db_tools.clear_persons()
        cls.db_tools.clear_constants()
        cls._db.rollback()


class SimpleAuthImplementationTest(BaseAccountTest):
    """ This is a test case for simple SHA-1 hashing implementation. """

    def test_auth_ssha(self):
        auth_methods = self._co.get_auth_crypt_methods()
        method_name = "SSHA"
        if method_name not in map(lambda x: str(x), auth_methods):
            return
        auth_impl = all_auth_methods[str(method_name)]()
        _hash = auth_impl.encrypt("hesterbest", salt="ABCDEFGI")
        self.assertEqual(
            _hash, "qBVr/e8BtH7dw2h09V8WL0jxEaxBQkNERUZHSQ==")

    def test_auth_sha256(self):
        auth_methods = self._co.get_auth_crypt_methods()
        method_name = "SHA-256-crypt"
        if method_name not in map(lambda x: str(x), auth_methods):
            return
        auth_impl = all_auth_methods[str(method_name)]()
        _hash = auth_impl.encrypt("hesterbest", salt="$5$ABCDEFGI")
        self.assertEqual(
            _hash, "$5$ABCDEFGI$wRL35zTjgAhecyc9CWv5Id.qsz5RZqXvDD3EXmlkUJ4")

    def test_auth_sha512(self):
        auth_methods = self._co.get_auth_crypt_methods()
        method_name = "SHA-512-crypt"
        if method_name not in map(lambda x: str(x), auth_methods):
            return
        auth_impl = all_auth_methods[str(method_name)]()
        _hash = auth_impl.encrypt("hesterbest", salt="$6$ABCDEFGI")
        self.assertEqual(
            _hash, "$6$ABCDEFGI$s5rS3hTF2FJrqxToloyKaOcmUwFMVvEft"
            "Yen3WjaetYz726AFZQkI572G0o/bO9BWC86Sae1QjMUe7TZYBeYg1")

    def test_auth_md5(self):
        auth_methods = self._co.get_auth_crypt_methods()
        method_name = "MD5-crypt"
        if method_name not in map(lambda x: str(x), auth_methods):
            return
        auth_impl = all_auth_methods[str(method_name)]()
        _hash = auth_impl.encrypt("hesterbest", salt="$1$ABCDEFGI")
        self.assertEqual(
            _hash, "$1$ABCDEFGI$iO4CKjwcmvejNZ7j1MEW./")

    def test_auth_md4_nt(self):
        auth_methods = self._co.get_auth_crypt_methods()
        method_name = "MD4-NT"
        if method_name not in map(lambda x: str(x), auth_methods):
            return
        auth_impl = all_auth_methods[str(method_name)]()
        _hash = auth_impl.encrypt("hesterbest", salt="ABC")
        self.assertEqual(
            _hash, "5DDE3A6B19D3DEB6B63E304A5574A193")

    def test_ha1md5_encrypt():
        name = 'olanordmann'
        realm = 'myorg'
        passwd = 'hesterbest'

        _hash = Cerebrum.auth.encrypt_ha1_md5(name, realm, passwd)
        assert _hash == "05f96542dbba4d8c53dc83635985df97"

    def test_ha1md5_verify():
        name = 'olanordmann'
        realm = 'myorg'
        right_passwd = 'hesterbest'
        wrong_passwd = 'hesterverst'
        _hash = Cerebrum.auth.encrypt_ha1_md5(name, realm, right_passwd)

        assert Cerebrum.auth.verify_ha1_md5(name, realm, right_passwd, _hash)
        assert not Cerebrum.auth.verify_ha1_md5(name, realm, wrong_passwd, _hash)
