# Netbot Usage

FIXME - expand into use cases, this is a cheatsheet.
FIXME - add block

The following Discord commands are implemented:

```
/scn add [login]    - Map current discord userid to redmine [login]
/scn join [team]    - discord user joins [team] (and maps user id)
/scn leave [team]   - discord user leaves [team]
/scn reindex        - rebuild the bot's index of users, teams and other metadata.
                      Use after adding new users and teams to Redmine.

/tickets me         - (default) tickets assigned to me or my teams
/tickets [team]     - tickets assigned to team [team]
/tickets [user]     - tickets assigned to a specific [user]
/tickets [query]    - tickets that match the term [query]

/ticket # show      - (default) show ticket info for ticket #
/ticket # details   - show ticket # with all notes (in a decent format)

/ticket # assign    - Assign ticket n to the specified user - not yet implemented
/ticket # unassign  - Mark ticket n new and unassigned.
/ticket # progress  - Assign the ticket to yourself and set it yourself.
/ticket # resolve   - Mark the ticket resolved.

/new [title]        - Create a new ticket with the title [title]
```
