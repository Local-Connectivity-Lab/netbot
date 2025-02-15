"""
mock_session: For testing
"""

import json
import logging
from urllib.parse import urlparse

from redmine.session import RedmineSession
from redmine.model import User, Ticket, TicketsResult

TEST_DATA = "data" # dir with test data

log = logging.getLogger(__name__)

def load_file(filename:str):
    log.debug(f"loading file {TEST_DATA + filename}")
    with open(TEST_DATA + filename, 'r', encoding="utf-8") as file:
        return file.read()

class MockSession(RedmineSession):
    """Magic session handling for test"""
    def __init__(self, token:str):
        super().__init__("http://example.com", token)
        self.test_cache = {}
        self.ticket_count = 1000


    def _next_id(self) -> int:
        self.ticket_count += 1
        return self.ticket_count


    def _get(self, resource:str) -> dict:
        try:
            path = urlparse(resource).path
            # check cache, assumed to be str
            cached = self.test_cache.get(path, None)
            if not cached:
                log.debug(f"checking path={path}")
                cached = load_file(path)
                self.test_cache[path] = cached
            else:
                log.debug(f"cache hit: {path}")

            return json.loads(cached)
        except FileNotFoundError as e:
            log.warning(f"404: not found {e.filename}")
            return None
            #super().get(query, impersonate_id)


    def _cache(self, resource:str, item):
        self.test_cache[resource] = json.dumps(item, indent=4, default=str)


    def cache_user(self, user:User):
        data = {
            'user': user.asdict()
        }
        self._cache(f"/users/{user.id}.json", data)


    def cache_ticket(self, ticket:Ticket):
        data = {
            'issue': ticket.asdict()
        }
        log.info(data)
        self._cache(f"/issues/{ticket.id}.json", data)


    def cache_results(self, tickets:list[Ticket]):
        result = TicketsResult(
            total_count=len(tickets),
            limit=25,
            offset=0,
            issues=tickets)
        self._cache("/issues.json", result.asdict())


    def get(self, query:str, impersonate_id:str|None=None):
        log.debug(f"GET {query}, id={impersonate_id}")
        try:
            return self._get(query)
        except FileNotFoundError:
            return None #super().get(query, impersonate_id)
        except Exception as ex:
            log.error(f"GET error {query}", exc_info=ex)
            return None


    def put(self, resource:str, data:str, impersonate_id:str|None=None) -> None:
        log.info(f"PUT {resource}, data={data} impersonate={impersonate_id}")

        item = self._get(resource)
        data_dict = json.loads(data)
        for k, v in data_dict.items():
            item[k].update(v)

        path = urlparse(resource).path
        self.test_cache[path] = json.dumps(item)
        log.debug(f"PUT {path} -> {item}")


    # def post(self, resource: str, data:str, user_login: str|None = None, files: list|None = None) -> dict|None:
    #     log.info(f"POST {resource}, data={data} user_login={user_login}")
    #     item_id = self._next_id()

    #     path = urlparse(resource).path

    #     name_a = path.rsplit('.', 1)
    #     path = f"{name_a[0]}/{item_id}.{name_a[1]}"

    #     data_dict = json.loads(data)
    #     for _, v in data_dict.items():
    #         v['id'] = item_id
    #     value = json.dumps(data_dict)
    #     log.debug(f"POST {path} -> {value}")
    #     self.test_cache[path] = value

    #     return data_dict
    #     #raise RedmineException(f"POST failed, status=[{r.status_code}] {r.reason}", r.headers['X-Request-Id'])


    def delete(self, resource: str) -> None:
        log.info(f"DELETE {resource}")
        path = urlparse(resource).path
        if path in self.test_cache:
            log.debug(f"deleted {path}")
            del self.test_cache[path]
