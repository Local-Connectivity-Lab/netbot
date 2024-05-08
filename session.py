#!/usr/bin/env python3
"""redmine client"""

import os
import logging
from urllib3.exceptions import ConnectTimeoutError
import requests
from requests.exceptions import ConnectTimeout

import dotenv

log = logging.getLogger(__name__)


TIMEOUT = 5 # seconds


class RedmineException(Exception):
    """redmine exception"""
    def __init__(self, message: str, request_id: str) -> None:
        super().__init__(message + ", req_id=" + request_id)
        self.request_id = request_id


class RedmineSession():
    """RedmineSession"""
    url: str
    token: str
    session: requests.Session

    """redmine session"""
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.session = requests.Session()


    @classmethod
    def fromenv(cls):
        url = os.getenv('REDMINE_URL')
        if url is None:
            raise RedmineException("REDMINE_URL not set in environment", __name__)

        token = os.getenv('REDMINE_TOKEN')
        if token is None:
            raise RedmineException("Unable to load REDMINE_TOKEN", "__init__")

        return cls(url, token)

    @classmethod
    def fromenvfile(cls):
        dotenv.load_dotenv()
        return cls.fromenv()

    def get_headers(self, impersonate_id:str|None=None):
        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/json',
            'X-Redmine-API-Key': self.token,
        }
        # insert the impersonate_id to impersonate another user
        if impersonate_id:
            headers['X-Redmine-Switch-User'] = impersonate_id
            log.debug(f"setting redmine impersonation flag for user={impersonate_id}")

        return headers


    def get(self, query_str:str, impersonate_id:str|None=None):
        """run a query against a redmine instance"""
        headers = self.get_headers(impersonate_id)
        try:
            r = self.session.get(f"{self.url}{query_str}", headers=headers, timeout=TIMEOUT)

            if r.ok:
                return r.json()
            else:
                log.info(f"GET {r.reason}/{r.status_code} url={r.request.url}, reqid={r.headers.get('X-Request-Id','')}")
        except (TimeoutError, ConnectTimeoutError, ConnectTimeout, ConnectionError):
            # ticket-509: Handle timeout gracefully
            log.warning(f"TIMEOUT ({TIMEOUT}s) during {query_str}")
        except Exception as ex:
            log.exception(f"{type(ex)} during {query_str}: {ex}")

        return None


    def put(self, resource: str, data:str, impersonate_id:str|None=None) -> None:
        r = self.session.put(f"{self.url}{resource}",
                             data=data,
                             timeout=TIMEOUT,
                             headers=self.get_headers(impersonate_id))
        if r.ok:
            log.debug(f"PUT {resource}: {data}")
        else:
            raise RedmineException(f"PUT {resource} by {impersonate_id} failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    def post(self, resource: str, data:str, user_login: str|None = None, files: list|None = None) -> dict|None:
        r = self.session.post(f"{self.url}{resource}",
                              data=data,
                              files=files,
                              timeout=TIMEOUT,
                              headers=self.get_headers(user_login))
        if r.status_code == 201:
            #log.debug(f"POST {resource}: {data} - {vars(r)}")
            return r.json()
        elif r.status_code == 204:
            return None
        else:
            raise RedmineException(f"POST failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    def delete(self, resource: str) -> None:
        r = self.session.delete(
            url=f"{self.url}{resource}",
            timeout=TIMEOUT,
            headers=self.get_headers())

        if not r.ok:
            raise RedmineException(f"DELETE failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    def upload_file(self, user_login:str, data, filename:str, content_type:str):
        """Upload a file to redmine"""
        # POST /uploads.json?filename=image.png
        # Content-Type: application/octet-stream
        # (request body is the file content)

        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/octet-stream', # <-- VERY IMPORTANT
            'X-Redmine-API-Key': self.token,
            'X-Redmine-Switch-User': user_login, # Make sure the comment is noted by the correct user
        }

        r = self.session.post(
            url=f"{self.url}/uploads.json?filename={filename}",
            timeout=TIMEOUT,
            files={ 'upload_file': (filename, data, content_type) },
            headers=headers)

        # 201 response: {"upload":{"token":"7167.ed1ccdb093229ca1bd0b043618d88743"}}
        if r.status_code == 201:
            # all good, get token
            #root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
            token = r.json()['upload']['token']
            log.info(f"Uploaded {filename} {content_type}, got token={token}")
            return token
        else:
            raise RedmineException(f"UPLOAD {r.request.url} {r.reason}/{r.status_code} - {filename}/{content_type}", r.headers['X-Request-Id'])
