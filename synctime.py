#!/usr/bin/env python3
"""A collection of utilities to help manage time"""

import logging
import datetime as dt

import humanize


log = logging.getLogger(__name__)


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def now_millis() -> int:
    return int(now().timestamp()*1000.0)

def parse_millis(timestamp:int) -> dt.datetime:
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc)

def parse_str(timestamp:str) -> dt.datetime:
    if timestamp is not None and len(timestamp) > 0:
        return dt.datetime.fromisoformat(timestamp)
    else:
        return None

def age(time:dt.datetime) -> dt.timedelta:
    return now() - time

def age_str(time:dt.datetime) -> str:
    return humanize.naturaldelta(age(time))


class SyncRecord():
    """encapulates the record of the last ticket syncronization"""
    def __init__(self, ticket_id: int, channel_id: int, last_sync: dt.datetime):
        assert last_sync.tzinfo is dt.timezone.utc # make sure TZ is set and correct
        self.ticket_id = ticket_id
        self.channel_id = channel_id
        self.last_sync = last_sync


    @classmethod
    def from_token(cls, ticket_id: int, token: str):
        """Parse a custom field token into a SyncRecord.
        If the token is legacy, channel=0 is returned with legacy sync.
        If the token is empty, channel=0 is returned with last_sync=0 (epoch).
        If the token is invalid, it's treated as empty and a new token is
        returned
        """
        if '|' in token:
            # token format {channel_id}|{last_sync_ms}, where
            # channel_id is the ID of the Discord Thread
            # last_sync is the ms-since-utc-epoch sunce the last
            parts = token.split('|')
            try:
                channel_id = int(parts[0])
            except ValueError:
                log.exception(f"error parsing {token}: -> {parts[0]}")
                channel_id = 0

            last_sync = parse_str(parts[1])

            return cls(ticket_id, channel_id, last_sync)
        else:
            # legacy token - assume UTC ZULU
            last_sync = parse_str(token)
            return cls(ticket_id, 0, last_sync)


    def age(self) -> dt.timedelta:
        age(self.last_sync)

    def token_str(self) -> str:
        return f"{self.channel_id}|{self.last_sync}"

    def __str__(self) -> str:
        return f"SYNC #{self.ticket_id} <-> {self.channel_id}, {age_str(self.last_sync)}"
