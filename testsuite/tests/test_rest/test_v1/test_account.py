#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" Tests for api.v1.account """

from __future__ import unicode_literals

import pytest
import json
import string
import random

from flask import url_for


@pytest.fixture
def cereconf(cereconf):
    # Password rules for testing
    cereconf.PASSWORD_CHECKS = {
        'rigid': (
            ('simple_entropy_calculator',
             {'min_required_entropy': 32,
              'min_groups': 3,
              'min_chars_per_group': 2}),
        ),
    }
    return cereconf


def random_string(length=32):
    return ''.join(random.choice(string.ascii_letters + string.digits + ' ')
                   for _ in range(length))


VALID_PASSWORD = random_string() + 'æøå' + '🐛' + 'опитайтова'
INVALID_PASSWORD = 'too short'


def test_get_account(client, auth_header, account_foo, person_foo):
    assert account_foo.account_name
    res = client.get(url_for('api_v1.account',
                             name=account_foo.account_name),
                     headers=auth_header)
    assert res.json.get('name') == account_foo.account_name
    assert res.json.get('owner').get('id') == person_foo.entity_id


def test_account_set_and_verify_valid_password(client, auth_header,
                                               account_foo):
    """ Sets a valid password. Verifies new credentials internally and
    against the REST API. """
    password = VALID_PASSWORD
    data = {'password': password}
    post = client.post(url_for('api_v1.account-password',
                               name=account_foo.account_name),
                       data=json.dumps(data),
                       content_type="application/json",
                       headers=auth_header)
    assert post.status_code == 200
    assert account_foo.verify_auth(password)
    post = client.post(url_for('api_v1.account-password-verify',
                               name=account_foo.account_name),
                       data=json.dumps(data),
                       content_type="application/json",
                       headers=auth_header)
    assert post.status_code == 200
    assert post.json.get('verified') is True


def test_account_set_and_verify_invalid_passowrd(client, auth_header,
                                                 account_foo):
    """ Attempts to set an invalid passwords. Makes sure password did not
    change. """
    password = INVALID_PASSWORD
    data = {'password': password}
    post = client.post(url_for('api_v1.account-password',
                               name=account_foo.account_name),
                       data=json.dumps(data),
                       content_type="application/json",
                       headers=auth_header)
    assert post.status_code == 400
    assert not account_foo.verify_auth(password)
    post = client.post(url_for('api_v1.account-password-verify',
                               name=account_foo.account_name),
                       data=json.dumps(data),
                       content_type="application/json",
                       headers=auth_header)
    assert post.status_code == 200
    assert post.json.get('verified') is False


def test_account_check_password(client, auth_header, account_foo):
    """ Check a valid and invalid password against the password rules. """
    data = {'password': VALID_PASSWORD}
    post = client.post(url_for('api_v1.account-password-check',
                               name=account_foo.account_name),
                       data=json.dumps(data),
                       content_type="application/json",
                       headers=auth_header)
    assert post.status_code == 200
    assert post.json.get('passed') is True
    data = {'password': INVALID_PASSWORD}
    post = client.post(url_for('api_v1.account-password-check',
                               name=account_foo.account_name),
                       data=json.dumps(data),
                       content_type="application/json",
                       headers=auth_header)
    assert post.status_code == 200
    assert post.json.get('passed') is False
