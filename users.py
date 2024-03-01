#!/usr/bin/env python3
"""redmine client"""

import datetime as dt
import logging
import json

from dataclasses import dataclass

from session import RedmineSession, RedmineException

log = logging.getLogger(__name__)

USER_RESOURCE = "/users.json"
TEAM_RESOURCE = "/groups.json"
DISCORD_ID_FIELD = "Discord ID"
BLOCKED_TEAM_NAME = "blocked"


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


@dataclass
class Team:
    """Encapsulates a team"""
    id: int
    name: str


class UserManager():
    """manage redmine users"""
    session: RedmineSession


    def __init__(self, session: RedmineSession):
        self.session = session


    def get_all(self) -> list[User]:
        jresp = self.session.get(f"{USER_RESOURCE}?limit=100")
        if jresp:
            user_result = UserResult(**jresp)
            user_buffer = user_result.users
            if user_result.total_count > user_result.limit:
                offset = user_result.limit
                while offset < user_result.total_count:
                    next_req = f"{USER_RESOURCE}?offset={offset}&limit={user_result.limit}"
                    log.debug(f"next request: {next_req}")
                    next_resp = self.session.get(next_req)
                    next_result = UserResult(**next_resp)
                    user_buffer.extend(next_result.users)
                    offset += next_result.limit

            return user_buffer
        else:
            log.warning("No users from get_all_users")
            return []


    def update(self, user:User, fields:dict):
        """update a user record in redmine"""
        # PUT a simple JSON structure
        data = {}
        data['user'] = fields

        response = self.session.put(f"/users/{user.id}.json",json.dumps(data))

        log.debug(f"update user: [{response.status_code}] {response.request.url}, fields: {fields}")

        # check status
        if response.ok:
            # TODO get and return the updated user
            return user
        else:
            raise RedmineException(
                f"update failed, status=[{response.status_code}] {response.reason}",
                response.headers['X-Request-Id'])



    def search(self, username:str) -> User:
        """Get a user based on ID, directly from redmine"""
        if username is None or len(username) == 0:
            log.debug("Empty user ID")
            return None

        response = self.session.get(f"{USER_RESOURCE}?name={username}")
        if response:
            result = UserResult(**response)
            log.debug(f"lookup_user: {username} -> {result.users}")

            if result.total_count == 1:
                return result.users[0]
            elif result.total_count > 1:
                log.warning(f"Too many results for {username}: {result.users}")
                return result.users[0]
            else:
                log.debug(f"Unknown user: {username}")
                return None


    def is_blocked(self, user) -> bool:
        if self.is_user_in_team(user.login, BLOCKED_TEAM_NAME):
            return True
        else:
            return False


    def block(self, user) -> None:
        # check if the blocked team exists
        blocked_team = self.find_team(BLOCKED_TEAM_NAME)
        if blocked_team is None:
            # create blocked team
            self.create_team(BLOCKED_TEAM_NAME)

        self.join_team(user.login, BLOCKED_TEAM_NAME)


    def unblock(self, user) -> None:
        self.leave_team(user.login, BLOCKED_TEAM_NAME)


    def create(self, email:str, first:str, last:str):
        """create a new redmine user"""
        # TODO: Generate JSON from User object
        data = {
            'user': {
                'login': email,
                'firstname': first,
                'lastname': last,
                'mail': email,
            }
        }
        # on create, assign watcher: sender?

        r = self.session.post(USER_RESOURCE, json.dumps(data))

        # check status
        if r:
            user = User(**r['user'])

            log.info(f"created user: {user.id} {user.login} {user.mail}")

            return user
        else:
            raise RedmineException(f"create_user {email} failed", r.headers['X-Request-Id'])


    # used only in testing
    def remove(self, user: User):
        """remove user frmo redmine. used for testing"""
        # DELETE to /users/{user_id}.json
        r = self.session.delete(f"/users/{user.id}.json")

        # check status
        if r:
            log.info(f"deleted user {user.id}")
        else:
            log.error(f"Error removing user status={r.status_code}, url={r.request.url}, req_id={r.headers['X-Request-Id']}")
            # exception?


    def create_discord_mapping(self, redmine_login:str, discord_name:str):
        user = self.search(redmine_login)

        field_id = 2 ## "Discord ID"search for me in cached custom fields
        fields = {
            "custom_fields": [
                { "id": field_id, "value": discord_name } # cf_4, custom field syncdata
            ]
        }
        self.update(user, fields)


    def get_all_teams(self) -> dict:
        # this needs to be cached!
        resp = self.session.get(f"{TEAM_RESOURCE}?limit=100")
        # list of id, name
        if resp:
            teams = {}
            for team in resp['groups']:
                teams[team['name']] = Team(**team)

            return teams
        else:
            log.warning("No users from get_all_users")
            return []


    def find_team(self, name:str) -> int:
        return self.get_all_teams().get(name, None)


    def create_team(self, teamname:str):
        if teamname is None or len(teamname.strip()) == 0:
            raise RedmineException(f"Invalid team name: '{teamname}'", __name__)

        # POST to /groups.json
        data = {
            "group": {
                "name": teamname,
            }
        }

        response = self.session.post(TEAM_RESOURCE, json.dumps(data))

        # check status
        if response:
            log.info(f"OK create_team {teamname}")
        else:
            raise RedmineException(f"create_team {teamname} failed", response.headers['X-Request-Id'])


    def join_team(self, user: User, teamname:str) -> None:
        # look up user ID
        #user = self.find_user(username)
        #if user is None:
        #    raise RedmineException(f"Unknown user name: {username}", "[n/a]")

        # map teamname to team
        team_id = self.find_team(teamname)
        if team_id is None:
            raise RedmineException(f"Unknown team name: {teamname}", "[n/a]")

        # POST to /group/ID/users.json
        data = {
            "user_id": user.id
        }

        response = self.session.post(f"/groups/{team_id}/users.json", data=json.dumps(data))

        # check status
        if response.ok:
            log.info(f"OK join_team {user.login}, {teamname}")
        else:
            raise RedmineException(f"join_team failed, status=[{response.status_code}] {response.reason}", response.headers['X-Request-Id'])


    def leave_team(self, user: User, teamname:str):
        # look up user ID
        #user = self.find_user(username)
        #if user is None:
        #    log.warning(f"Unknown user name: {username}")
        #    return None

        # map teamname to team
        team_id = self.find_team(teamname)
        if team_id is None:
            log.warning(f"Unknown team name: {teamname}")
            return

        # DELETE to /groups/{team-id}/users/{user_id}.json
        r = self.session.delete(f"/groups/{team_id}/users/{user.id}.json")

        # check status
        if not r:
            log.error(f"Error removing {user.login} from {teamname}")


    def get_team(self, teamname:str):
        team_id = self.find_team(teamname)
        if team_id is None:
            log.debug(f"Unknown team name: {teamname}")
            return None

        # as per https://www.redmine.org/projects/redmine/wiki/Rest_Groups#GET-2
        # GET /groups/20.json?include=users
        response = self.session.get(f"/groups/{team_id}.json?include=users")
        if response:
            return response.group
        else:
            #TODO exception?
            return None


    def is_user_in_team(self, user: User, teamname:str) -> bool:
        if user is None or teamname is None:
            return False

        team = self.get_team(teamname)

        if team:
            for team_user in team.users:
                if team_user.id == user.id:
                    return True

        return False


class UserCache():
    """cache of user data"""
    def __init__(self, mgr:UserManager):
        self.mgr = mgr

        self.users = {}
        self.user_ids = {}
        self.user_emails = {}
        self.discord_users = {}
        self.teams = {}
        self.reindex()


    def get_user(self, user_id:int):
        """get a user by ID"""
        if user_id:
            return self.user_ids[user_id]


    def find_user(self, name):
        """find a user by name"""
        # check if name is int, raw user id. then look up in userids
        # check the indicies
        if name in self.user_emails:
            return self.get_user(self.user_emails[name])
        elif name in self.users:
            return self.get_user(self.users[name])
        elif name in self.discord_users:
            return self.get_user(self.discord_users[name])
        elif name in self.teams:
            return self.teams[name] #ugly. put groups in user collection?
        else:
            return None


    def find_team(self, name:str) -> int:
        if name in self.teams:
            return self.teams[name]


    def find_discord_user(self, discord_user_id:str):
        """find a user by their discord ID"""
        if discord_user_id is None:
            return None

        if discord_user_id in self.discord_users:
            user_id = self.discord_users[discord_user_id]
            return self.user_ids[user_id]
        else:
            return None


    def is_user_or_group(self, name:str) -> bool:
        if name in self.users:
            return True
        elif name in self.teams:
            return True
        else:
            return False


    # python method sync?
    def reindex_users(self):
        # rebuild the indicies
        # looking over issues in redmine and specifically https://www.redmine.org/issues/16069
        # it seems that redmine has a HARD CODED limit of 100 responses per request.
        all_users = self.mgr.get_all()
        if all_users:
            # reset the indices
            self.users.clear()
            self.user_ids.clear()
            self.user_emails.clear()
            self.discord_users.clear()

            for user in all_users:
                self.users[user.login] = user.id
                self.user_ids[user.id] = user
                self.user_emails[user.mail] = user.id

                #discord_id = user.get_discord_id(user)
                if user.discord_id:
                    self.discord_users[user.discord_id] = user.id
            log.debug(f"indexed {len(self.users)} users")
            log.debug(f"discord users: {self.discord_users}")
        else:
            log.error("No users to index")


    def get_teams(self):
        return self.teams.keys()


    # TODO: Add a dataclass for Team, and page-unrolling for "all teams"
    def reindex_teams(self):
        # rebuild the group index
        self.teams = self.mgr.get_all_teams()


    def is_user_in_team(self, username:str, teamname:str) -> bool:
        if username is None or teamname is None:
            return False

        user = self.mgr.search(username)
        if user:
            user_id = user.id
            team = self.mgr.get_team(teamname) # requires an API call

            if team:
                for team_user in team.users:
                    if team_user.id == user_id:
                        return True

        return False


    def reindex(self):
        start = dt.datetime.now()
        self.reindex_users()
        self.reindex_teams()
        log.debug(f"reindex took {dt.datetime.now() - start}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    # load credentials
    from dotenv import load_dotenv
    load_dotenv()

    users = UserManager(RedmineSession.fromenv())
    print(len(users.get_all()))
