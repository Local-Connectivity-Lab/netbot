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

The `/ticket` command is used to information about tickets in Redmine

### /ticket query me
- The the list of tickets for *me* (you, the reader) to work on

### /ticket query [term]
- *term* can be a user, a team or any term that will be used for a full text search for tickets (open and closed) that match the *term*.

### /ticket details [ticket-id]
- Show ticket *ticket-id* with full details.

### /ticket new [title]
- Create a new ticket, with the associated title. This will also create a new Discord thread for the ticket. If the command is issued in an existing thread, that thread is used and synched with redmine.

### /ticket thread [ticket-id]
- Create a new discord thread from an existing ticket *ticket-id*, using the ticket title as the thread title. The thread is created in the channel it is invoked in, and all notes from the existing ticket are copied into the thread.

### /ticket assign [ticket-id]
- Assign ticket *ticket-id* to yourself (the invoking user)

### /ticket unassign [ticket-id]
- Mark ticket *ticket-id* new and unassigned.

### /ticket progress [ticket-id]
-  Mark ticket *ticket-id* to in-progress and assign it to yourself.

### /ticket resolve [ticket-id]
- Mark ticket *ticket-id* resolved.
