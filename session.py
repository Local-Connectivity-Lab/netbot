
#!/usr/bin/env python3
"""redmine client"""

import os
import logging

import requests


log = logging.getLogger(__name__)


TIMEOUT = 10 # seconds


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


    def get_headers(self, impersonate_id:str=None):
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


    def get(self, query_str:str, user:str=None):
        """run a query against a redmine instance"""

        headers = self.get_headers(user)

        try:
            r = self.session.get(f"{self.url}{query_str}", headers=headers, timeout=TIMEOUT)

            if r.ok:
                return r.json()
            else:
                log.error(f"GET {r.status_code} for {r.request.url}, reqid={r.headers['X-Request-Id']}: {r}")
        except TimeoutError as toe:
            # ticket-509: Handle timeout gracefully
            log.warning(f"Timeout during {query_str}: {toe}")
        except Exception as ex:
            log.exception(f"Exception during {query_str}: {ex}")

        return None


    # data=json.dumps(data),
    def put(self, resource: str, data, user_login: str = None) -> bool:
        r = self.session.put(f"{self.url}{resource}", data=data, timeout=TIMEOUT,
                         headers=self.get_headers(user_login))
        if r.ok:
            log.debug(f"PUT {resource}: {data} - {r}")
            return True
        else:
            raise RedmineException(f"POST failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    def post(self, resource: str, data, user_login: str = None):
        r = self.session.post(f"{self.url}{resource}", data=data, timeout=TIMEOUT,
                          headers=self.get_headers(user_login))
        if r.status_code == 201:
            #log.debug(f"POST {resource}: {data} - {vars(r)}")
            return r.json()
        elif r.status_code == 204:
            return None
        else:
            raise RedmineException(f"POST failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    def delete(self, resource: str) -> bool:
        r = self.session.delete(
            url=f"{self.url}{resource}",
            timeout=TIMEOUT,
            headers=self.get_headers())

        if r.ok:
            return True
        else:
            raise RedmineException(f"DELETE failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    def upload_file(self, user_id, data, filename, content_type):
        """Upload a file to redmine"""
        # POST /uploads.json?filename=image.png
        # Content-Type: application/octet-stream
        # (request body is the file content)

        headers = {
            'User-Agent': 'netbot/0.0.1', # TODO update to project version, and add version management
            'Content-Type': 'application/octet-stream', # <-- VERY IMPORTANT
            'X-Redmine-API-Key': self.token,
            'X-Redmine-Switch-User': user_id, # Make sure the comment is noted by the correct user
        }

        r = self.session.post(
            url=f"{self.url}/uploads.json?filename={filename}",
            timeout=TIMEOUT,
            files={ 'upload_file': (filename, data, content_type) },
            headers=headers)

        # 201 response: {"upload":{"token":"7167.ed1ccdb093229ca1bd0b043618d88743"}}
        if r.ok:
            # all good, get token
            #root = json.loads(r.text, object_hook= lambda x: SimpleNamespace(**x))
            token = r.json()['upload']['token']
            log.info(f"Uploaded {filename} {content_type}, got token={token}")
            return token
        else:
            raise RedmineException(f"UPLOAD failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])
