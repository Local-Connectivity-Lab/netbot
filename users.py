#!/usr/bin/env python3
"""redmine client"""

import datetime as dt
import logging

from dataclasses import dataclass


log = logging.getLogger(__name__)


DISCORD_ID_FIELD = "Discord ID"


@dataclass
class CustomField():
    """A redmine custom field"""
    id: int
    name: str
    value: str

@dataclass
class User():
    """Encapsulates a redmine user"""
    id: int
    login: str
    mail: str
    custom_fields: dict
    admin: bool
    firstname: str
    lastname: str
    mail: str
    created_on: dt.datetime
    updated_on: dt.datetime
    last_login_on: dt.datetime
    passwd_changed_on: dt.datetime
    twofa_scheme: str
    api_key: str = ""
    status: int = ""
    custom_fields: list[CustomField]


    def __post_init__(self):
        self.custom_fields = [CustomField(**field) for field in self.custom_fields]
        self.discord_id = self.get_custom_field(DISCORD_ID_FIELD)


    def get_custom_field(self, name: str) -> str:
        for field in self.custom_fields:
            if field.name == name:
                return field.value

        return None

@dataclass
class UserResult:
    """Encapsulates a set of users"""
    users: list[User]
    total_count: int
    limit: int
    offset: int

    def __post_init__(self):
        self.users = [User(**user) for user in self.users]
