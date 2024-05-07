# Netbot Usage

Netbot provides a series of slash-commands to support tickets and users in Redmine.

The commands are grouped:
* `/tickets` provides ticket management and queries
* `/scn` provides commands to manages users and organization in Redmine

## Use Cases


### Create A New Ticket

To create a new ticket to capture

For example, to create a new ticket to "Change the water filter":

    /ticket new Change the water filter

[screen shot]

This will create a new ticket with the title "Change the water filter", and create a new Discord thread to manage discussion of the ticket.

-> creating in specific channels

-> mappings for teams


### Find Tickets

#### Finding *Your* Tickets
Query, based on "me", teams, etc.

    /ticket query me

[screen shot]

This will offer a list of tickets, based on the teams you are part of and tickets that are assigned to you directly.

#### Finding Other Tickets
Query, based on a specific term related to the tickets you're interested in, for example "water"

    /ticket query water

[screen shot]

This will return an ticket related that contain the term "water".


### Work On A Ticket

Once you've selected a ticket to work on, assign it to yourself with:

    /ticket assign 42

This will assign ticket ID 42 to you (the Discord user).

When you're ready to start work:

    /ticket progress 42

This will mark ticket "42" in-progress.

Assuming this ticket was created via the Discord bot, there will be an associated Discord thread: "Ticket 42: Change the water filter". Any comments in this thread will be reflected back to the redmine ticket, so it can be easy way to update progress especially with the Discord app on your smartphone.

In this example, you might might updates like:
* Confirmed the filter model we need and that we have one on hand.
* Starting install. Water will be off for a few minutes.
* Install complete. Water is running and new filter is operating as expecting.

Once the work is done and everything checks out, resolve the ticket:

    /ticket resolve 42

This will mark the ticket "resolved", so everyone knows the work is taken care of.

NOTE: All the /ticket commands for one ticket could be derived from the threat name.


## Ticket Commands

The `/ticket` slash command is used to information about tickets in Redmine. A number of commands are provided:
* query
* details
* new
* thread
* assign
* unassign
* progress
* resolve


### `/ticket query me` - Query my tickets

The the list of tickets for *me* (you, the reader) to work on.

```
/ticket query me
```

### `/ticket query [term]` - Query tickets about *term*

*term* can be a user, a team or any term that will be used for a full text search for tickets (open and closed) that match the *term*.

```
/ticket query test
```
will return any tickets that reference the term "test".

### `/ticket details [ticket-id]` - Show details about a specific ticket

Show ticket *ticket-id* with full details.

```
/ticket details 787
```
will display all the ticket information for ticket ID 787

### `/ticket new [title]` - Create a new ticket

Create a new ticket, with the associated title. This will also create a new Discord thread for the ticket. If the command is issued in an existing thread, that thread is used and synched with redmine.

```
/ticket new Upgrade the server to the v1.62 LTS
```
Will create a new ticket with the title "Upgrade the server to the v1.62 LTS", and a thread for the new ticket in Discord.

### `/ticket thread [ticket-id]` - Create a Discord thread for a ticket

Create a new discord thread from an existing ticket *ticket-id*, using the ticket title as the thread title. The thread is created in the channel it is invoked in, and all notes from the existing ticket are copied into the thread.
```
/ticket thread 787
```
will create a new thread for ticket 787 in the current Discord channel.

If a Discord thread has already been created for that ticket, a note with a link to that thread will be displayed.

If an existing *ticket thread* has been deleted, it can be recreated in any channel with the same command.

To move a *ticket thread* to a new channel:
1. Delete the existing *ticket thread* using the Discord UI. NOTE: The relevant comments are already synced to Redmine.
2. Create the *ticket thread* in the new channel with (you guessed it): `/thread ticket [id]`

`/ticket thread` is designed to be forgiving: If no *ticket thread* exists or syncdata is old, incomplete or invalid, a new valid *ticket thread* will be created and synchroized. Otherwise, an existing *ticket thread* is associated with that ticket ID and a link to it will be displayed.


### `/ticket assign [ticket-id]` - Assign a ticket

Assign ticket *ticket-id* to yourself (the invoking user).

```
/ticket assign 787
```
will assign ticket 787 to you.

### `/ticket unassign [ticket-id]` - Unassign a ticket

Mark ticket *ticket-id* new and unassigned, so it can be assigned for someone else to work on.

```
/ticket unassign 787
```
will unassign (you) from ticker 787 and set it's status to "new" and it's owner to "intake".

### `/ticket progress [ticket-id]` - Set a ticket to in-progress

Mark ticket *ticket-id* to in-progress and assign it to yourself.

```
/ticket progress 787
```
will set the status of ticket 787 to in-progress and assign it to you.

### `/ticket resolve [ticket-id]` - Resolve a ticket

Mark ticket *ticket-id* resolved.

```
/ticket thread 787
```
will mark ticket 787 resolved. Well done!


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
