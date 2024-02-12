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
    return dt.datetime.fromisoformat(timestamp)

def age(time:dt.datetime) -> dt.timedelta:
    return now() - time

def age_str(time:dt.datetime) -> str:
    return humanize.naturaldelta(age(time))


class SyncRecord():
    """encapulates the record of the last ticket syncronization"""
    def __init__(self, ticket_id: int, channel_id: int, last_sync: dt.datetime):
        self.ticket_id = ticket_id
        self.channel_id = channel_id
        self.last_sync = last_sync


    @classmethod
    def from_token(cls, ticket_id: int, token: str, expected_channel: int):
        if '|' in token:
            # token format {channel_id}|{last_sync_ms}, where
            # channel_id is the ID of the Discord Thread
            # last_sync is the ms-since-utc-epoch sunce the last
            parts = token.split('|')
            channel_id = int(parts[0])
            last_sync = int(parts[1])

            if channel_id != expected_channel:
                log.info(f"skipping mismatched thread ID: expected={expected_channel}, got={channel_id}")
                return None
            else:
                return cls(ticket_id, channel_id, last_sync)
        else:
            # legacy token - assume UTC ZULU
            last_sync = parse_str(token)
            return cls(ticket_id, expected_channel, last_sync)


    def age(self) -> dt.timedelta:
        age(self.last_sync)

    def token_str(self) -> str:
        return f"{self.channel_id}|{self.last_sync}"

    def __str__(self) -> str:
        return f"SYNC #{self.ticket_id} <-> {self.channel_id}, {age_str(self.last_sync)}"
