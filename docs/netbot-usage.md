# Netbot Usage

Netbot provides a series of slash-commands to support tickets and users in Redmine.

The commands are grouped:
* `/scn` provides commands to manages users and organization in Redmine
* `/tickets` provides ticket management and queries


## SCN Commands

Any SCN commands that manage users allow for "self-management", and come in parallel forms:
* `/scn <command> <options>` and
* `/scn <command> <options> @member`

The first form assumes the @member is the person executing the command. The second form assumes the invoker is an established Redmine user with admin priviledges, and is executing the command on behalf of the member.

For example, if a normal user @bob was to invoke `/scn join nu-team` it would result in Bob joining nu-team in Redmine. If an @admin user invoked `/scn join nu-team @bob` it would also result in Bob joining the team.

### `/scn add` - Add a Discord user to Redmine

This command creates a linkage between a Discord user ID and a Redmine user ID. Any commands issued by a links Discord user will be executed on Redmine as if they were performed by that user.

To add you own Discord user, use:
```
/scn add [redmine-login]
```

If the user [redmine-login] exists in Redmine, the Discord member invoking the command will be associated with it.

If the user [redmine-login] does not exist in Redmine, a modal dialog will popup in Discord to create a new user, requesting first name, last name and email. A new Redmine user will be created with these parameters and linked to the invoking Discord user.

An administrator can also use `/scn add` to add other Discord users to Redmine:
```
/scn add [redmine-login] @member
```

This will behave as above, except that all operations will be performed as if by @member.

### `/scn teams` - List teams

To list all the teams, and their members, configured on Redmine:
```
/scn teams
```

To display only a single team `teamname`
```
/scn teams teamname
```

### `/scn join` - Join a team

To join the team `teamname` yourself:
```
/scn join teamname
```

An admin can add other people to teams, for example adding @blanche to `teamname`:
```
/scn join teamname @blanche
```

### `/scn leave` - Leave a team

To leave team `teamname`:
```
/scn leave teamname
```

An admin can remove people from teams:
```
/scn leave teamname @blanche
```

### `/scn block` - Block a user

This command is designed to manage external users, not Discord users.

SCN Redmine supports a "block" function that will reject (but still record) all tickets from a specific email.

This command exposes the "block" function in Discord. To block the user with email `spam@example.com`, use:
```
/scn block spam@example.com
```

### `/scn unblock` - Unblock a user

This command is designed to manage external users, not Discord users.

To unblock a user with email spam@example.com:
```
/scn unblock spam@example.com
```

> [!NOTE]
> This will remove the user from the blocked team, but will not "unreject" the tickets created by that email. New email will create normal tickets.

### `/scn blocked` - List the blocked users

List the blocked users.

Should be the same as `/scn teams blocked`.

## Ticket Commands

The `/tickets` command is used to information about tickets in Redmine

### /tickets
- My tickets

### /tickets team
- Tickets assigned to team [team]

### /tickets user
- Tickets assigned to a specific [user]

### /tickets query-term
- Full text search for all tickets (open and closed) that match the query-term

### /ticket 42
- Show ticket info for ticket 42

### /ticket 42 details
- Show ticket 42 with all notes (in a decent format)

### /ticket 42 assign
- Assign ticket 42 to yourself (the invoking user)
- `/ticket 42 assign @bob` would assign ticket 42 to Bob.

### /ticket 42 unassign
- Mark ticket 42 new and unassigned.

### /ticket 42 progress
-  Set ticket 42 it to in-progress.

### /ticket 42 resolve
- Mark the ticket resolved.

### /new Title of a new ticket to be created
- Create a new ticket with the supplied title.
- FUTURE: Will popup a modal dialog to collect ...
- OR just supply params with default values for tracker, etc.
