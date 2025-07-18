#!/usr/bin/env python3
"""redmine client"""

import datetime as dt
import logging
import json


from redmine.model import Team, User, UserResult, NamedId, DISCORD_ID_FIELD
from redmine.session import RedmineSession, RedmineException


log = logging.getLogger(__name__)


USER_RESOURCE = "/users.json"
TEAM_RESOURCE = "/groups.json"
BLOCKED_TEAM_NAME = "blocked"


class UserCache():
    """cache of user data"""
    def __init__(self):
        self.users: dict[str, int] = {}
        self.user_ids: dict[int, User] = {}
        self.user_emails: dict[str, int]  = {}
        self.discord_ids: dict[str, int]  = {}
        self.teams: dict[str, Team] = {}


    def clear(self):
        # reset the indices
        self.users.clear()
        self.user_ids.clear()
        self.user_emails.clear()
        self.discord_ids.clear()


    def cache_user(self, user: User) -> None:
        """add the user to the cache"""
        #log.debug(f"caching: {user.id} {user.login} {user.discord_id}")

        self.user_ids[user.id] = user
        self.users[user.login] = user.id
        self.user_emails[user.mail] = user.id
        if user.discord_id:
            self.discord_ids[user.discord_id.name] = user.id


    def cache_team(self, team: Team) -> None:
        """add the team to the cache"""
        self.teams[team.name] = team


    def get(self, user_id:int):
        """get a user by ID"""
        return self.user_ids.get(user_id)


    def get_by_name(self, username:str) -> User:
        return self.find(username)


    def find(self, name):
        """find a user by name"""
        # check if name is int, raw user id. then look up in userids
        # check the indicies
        if name in self.user_emails:
            return self.get(self.user_emails[name])
        if name in self.users:
            return self.get(self.users[name])
        if name in self.discord_ids:
            return self.get(self.discord_ids[name])
        if name in self.teams:
            return self.teams[name] #ugly. put groups in user collection?

        return None


    def get_team_by_name(self, name:str) -> Team:
        if name in self.teams:
            return self.teams[name]
        return None


    def find_discord_user(self, discord_user_id:str) -> User:
        """find a user by their discord ID"""
        if discord_user_id is None:
            return None

        if discord_user_id in self.discord_ids:
            user_id = self.discord_ids[discord_user_id]
            return self.user_ids[user_id]

        return None


    #def is_user_or_group(self, name:str) -> bool:
    #    return name in self.users or name in self.teams


    def is_team(self, name:str) -> bool:
        return name in self.teams


    def get_teams(self) -> list[Team]:
        return self.teams.values()


    def is_user_in_team(self, user:User, teamname:str) -> bool:
        if user is None or teamname is None:
            return False

        team = self.get_team_by_name(teamname)

        if team:
            for team_user in team.users:
                if team_user.id == user.id:
                    return True

        return False


class UserManager():
    """manage redmine users"""
    session: RedmineSession
    cache: UserCache


    def __init__(self, session: RedmineSession):
        self.session = session
        self.cache = UserCache()

        self.reindex()

    def get_all(self) -> list[User]:
        jresp = self.session.get(f"{USER_RESOURCE}?status=1,2&limit=100")
        if jresp:
            user_result = UserResult(**jresp)
            user_buffer = user_result.users

            #for user in user_buffer:
            #    log.info(f"{user.status}, {user.login}, {user.discord_id}")

            if user_result.total_count > user_result.limit:
                offset = user_result.limit
                while offset < user_result.total_count:
                    next_req = f"{USER_RESOURCE}?status=1,2&offset={offset}&limit={user_result.limit}"
                    log.debug(f"next request: {next_req}")
                    next_resp = self.session.get(next_req)
                    next_result = UserResult(**next_resp)
                    user_buffer.extend(next_result.users)
                    offset += next_result.limit

            return user_buffer
        log.warning("No users from get_all_users")
        return []

    def get_registered(self) -> list[User]:
        resp = self.session.get(f"{USER_RESOURCE}?status=2") # NOTE: 2 is the "registered" status
        if resp:
            user_result = UserResult(**resp)
            return user_result.users

        log.debug("no pending registered users")
        return []

    def update(self, user:User, fields:dict) -> User:
        """update a user record in redmine"""
        # PUT a simple JSON structure
        data = {}
        data['user'] = fields

        # put the updated date
        self.session.put(f"/users/{user.id}.json", json.dumps(data))

        # get and return the updated user
        user = self.get(user.id)
        log.debug(f"updated id={user.id}: user: {user}")
        return user


    def get_by_name(self, username:str) -> User:
        """Get a user based on name, directly from redmine"""
        if username is None or len(username) == 0:
            log.debug("Empty user ID")
            return None

        response = self.session.get(f"{USER_RESOURCE}?name={username}")
        if response:
            result = UserResult(**response)
            log.debug(f"lookup_user: {username} -> {result.users}")

            if result.total_count == 1:
                return result.users[0]
            if result.total_count > 1:
                log.warning(f"Too many results for {username}: {result.users}")
                return result.users[0]

            log.debug(f"Unknown user: {username}")
            return None
        return None


    def create(self, email:str, first:str, last:str, user_login:str|None) -> User:
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

        r = self.session.post(USER_RESOURCE, json.dumps(data), user_login)

        # check status
        if r:
            user = User(**r['user'])

            log.info(f"created user: {user.id} {user.login} {user.mail}")

            return user
        else:
            raise RedmineException(f"create_user {email} failed", r.headers['X-Request-Id'])


    def register(self, login:str, email:str, first:str, last:str) -> User:
        """register a new redmine user"""
        data = {
            'user': {
                'login': login,
                'firstname': first,
                'lastname': last,
                'mail': email,
                'status': 2, # registered
            }
        }

        r = self.session.post(USER_RESOURCE, json.dumps(data))

        # check status
        if r:
            user = User(**r['user'])

            log.info(f"registered user: {user.id} {user.login} {user.mail}")

            return user
        else:
            raise RedmineException(f"register {email} failed", r.headers['X-Request-Id'])


    def approve(self, user:User) -> User:
        """Update the approved flag to approve the user"""
        fields = {
            "status": 1, # approved status
        }
        # set the flag
        updated = self.update(user, fields)

        # cache the user
        self.cache.cache_user(updated)

        return updated


    def find(self, name: str) -> User:
        """get a user by ID"""
        if not name:
            return None

        # check cache first
        user = self.cache.find(name)
        if not user:
            # not found in cache, try a name search
            user = self.get_by_name(name)
            if user:
                log.info(f"found uncached user for {name}: {user.login}, caching")
                self.cache.cache_user(user)
        return user


    def find_discord_user(self, discord_user_id:str) -> User:
        # just a proxy
        return self.cache.find_discord_user(discord_user_id)

    #def is_user_or_group(self, term:str):
    #    return self.cache.is_user_or_group(term)

    def is_team(self, name:str):
        return self.cache.is_team(name)

    def get(self, user_id:int):
        """get a user by ID, directly from redmine"""
        jresp = self.session.get(f"/users/{user_id}.json")
        if jresp:
            #log.info(f"^^^ {jresp['user']}")
            return User(**jresp['user'])


    # used only in testing
    def remove(self, user: User):
        """remove user frmo redmine. used for testing"""
        # DELETE to /users/{user_id}.json
        r = self.session.delete(f"/users/{user.id}.json")

        # check status
        if r:
            log.info(f"deleted user {user.id}")


    def create_discord_mapping(self, user:User, discord_id: int, discord_name:str) -> User:
        named = NamedId(id=discord_id, name=discord_name)
        fields = {
            "custom_fields": [
                {
                    "id": 2, # Currently, get_custom_field() is in ticket_mgr
                    "name": DISCORD_ID_FIELD,
                    "value": named.as_token()
                }
            ]
        }
        updated = self.update(user, fields)
        # cache updated user, based on now-or-changed discord id.
        self.cache.cache_user(updated)
        return updated

    # for testing
    def remove_discord_mapping(self, user:User) -> User:
        field_id = 2 ## FIXME "Discord ID"search for me in cached custom fields
        fields = {
            "custom_fields": [
                { "id": field_id, "value": "" }
            ]
        }
        return self.update(user, fields)

    def get_all_teams(self, include_users: bool = True) -> dict[str, Team]:
        resp = self.session.get(f"{TEAM_RESOURCE}?limit=100")
        # list of id, name
        if resp:
            teams = {}
            for team_rec in resp['groups']:
                # create dict mapping team name -> full team record
                # calling "get_team" here, as it's the only way to get users in the team
                if include_users:
                    teams[team_rec['name']] = self.get_team(team_rec['id']) # requires an additional API call
                else:
                    teams[team_rec['name']] = Team(**team_rec)

            return teams
        else:
            log.warning("No teams from get_all_teams")
            return []


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


    def get_team(self, team_id: int) -> Team:
        """get a full team record from redmine. only way to get team membership"""
        # as per https://www.redmine.org/projects/redmine/wiki/Rest_Groups#GET-2
        # GET /groups/20.json?include=users
        response = self.session.get(f"/groups/{team_id}.json?include=users")
        if response:
            return Team(**response['group'])
        else:
            #TODO exception?
            return None


    def get_team_by_name(self, name:str) -> Team:
        # need to get all team, which builds a dicts of names
        teams = self.get_all_teams(include_users=False)
        log.debug(f"teams: {teams}")
        if name in teams:
            return self.get_team(teams[name].id)


    def is_user_in_team(self, user: User, teamname:str) -> bool:
        if user is None or teamname is None:
            return False

        team = self.get_team_by_name(teamname)
        return self.is_user_in(user, team)


    def is_user_in(self, user: User, team:Team) -> bool:
        if user and team:
            for team_user in team.users:
                if team_user.id == user.id:
                    return True

        return False


    def is_blocked(self, user:User) -> bool:
        if self.is_user_in_team(user, BLOCKED_TEAM_NAME):
            return True
        else:
            return False


    def block(self, user) -> None:
        # check if the blocked team exists
        blocked_team = self.get_team_by_name(BLOCKED_TEAM_NAME)
        if blocked_team is None:
            # create blocked team
            self.create_team(BLOCKED_TEAM_NAME)

        self.join_team(user, BLOCKED_TEAM_NAME)


    def unblock(self, user) -> None:
        self.leave_team(user, BLOCKED_TEAM_NAME)


    def join_team(self, user: User, teamname:str) -> None:
        # map teamname to team
        team = self.get_team_by_name(teamname)
        if team is None:
            raise RedmineException(f"Unknown team name: {teamname}", "[n/a]")

        # calling POST when the user is already in the team results in a
        # 422 Unprocessable Entity error, so checking first.
        # Expected behavior is idempotent: if already in the team, return as expected (no exception)
        if self.is_user_in(user, team):
            return # already done

        # POST to /group/ID/users.json
        data = {
            "user_id": user.id
        }

        self.session.post(f"/groups/{team.id}/users.json", data=json.dumps(data))


    def leave_team(self, user: User, teamname:str):
        # map teamname to team
        team = self.get_team_by_name(teamname)
        if team is None:
            log.warning(f"Unknown team name: {teamname}")
            return

        # DELETE to /groups/{team-id}/users/{user_id}.json
        self.session.delete(f"/groups/{team.id}/users/{user.id}.json") # encapsulation
        # raises an exception if there's a problem


    # python method sync?
    def reindex_users(self):
        # rebuild the indicies
        # looking over issues in redmine and specifically https://www.redmine.org/issues/16069
        # it seems that redmine has a HARD CODED limit of 100 responses per request.
        all_users = self.get_all()
        if all_users:
            self.cache.clear()

            for user in all_users:
                self.cache.cache_user(user) # several internal indicies

            log.debug(f"indexed {len(all_users)} users")
            log.debug(f"discord users: {self.cache.discord_ids}")
        else:
            log.warning("No users to index")


    def reindex_teams(self):
        all_teams = self.get_all_teams()
        if all_teams and len(all_teams) > 0:
            self.cache.teams = all_teams # replace all the cached teams
            log.debug(f"TEAMs {self.cache.teams}")
        else:
            log.warning("No teams to index")


    def reindex(self):
        start = dt.datetime.now()
        self.reindex_users()
        self.reindex_teams()
        log.info(f"reindex took {dt.datetime.now() - start}")
