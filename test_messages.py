#!/usr/bin/env python3

import unittest
import logging
import os, glob
import datetime as dt

from dotenv import load_dotenv

import imap
import redmine

logging.basicConfig(level=logging.DEBUG, 
    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
#log = logging.getLogger(__name__)

class TestMessages(unittest.TestCase):
    def test_messages_examples(self):
        # open 
        for filename in glob.glob('test_messages/*.eml'):
            with open(os.path.join(os.getcwd(), filename), 'rb') as file:
                message = imap.parse_message(file.read())
                #print(message)

    def test_email_address_parsing(self):
        from_address =  "Esther Jang <infrared@cs.washington.edu>"
        first, last, addr = imap.parse_email_address(from_address)
        self.assertEqual(first, "Esther")
        self.assertEqual(last, "Jang")
        self.assertEqual(addr, "infrared@cs.washington.edu")

    # disabled so I don't flood the system with files
    def xxtest_upload(self):
        load_dotenv()
        client = redmine.Client()

        with open("test/message-161.eml", 'rb') as file:
            message = imap.parse_message(file.read())
            #print(message)
            client.upload_attachments("philion", message.attachments)


    def test_more_recent_ticket(self):
        load_dotenv()
        client = redmine.Client()

        ticket = client.most_recent_ticket_for("philion")
        self.assertIsNotNone(ticket)
        #print(ticket)

    def XXXtest_recent_notes(self):
        load_dotenv()
        client = redmine.Client()

        now = dt.datetime.utcnow().astimezone(dt.timezone.utc)
        notes = client.get_notes_since(106, now)
        self.assertEqual(0, len(notes))

        notes = client.get_notes_since(106)
        self.assertEqual(2, len(notes))


    def test_teams(self):
        username = "philion"
        teamname = "test-group"
        load_dotenv()
        client = redmine.Client()

        team = client.find_team(teamname)
        self.assertEqual(67, team.id)
        self.assertEqual(teamname, team.name)

        client.join_team(username, teamname)

        # assert in team
        self.assertTrue(client.is_user_in_team(username, teamname))

        client.leave_team(username, teamname)

        # assert in team
        self.assertFalse(client.is_user_in_team(username, teamname))


    # note about python date time and utc: Stop using utcnow and utcfromtimestamp
    # https://blog.ganssle.io/articles/2019/11/utcnow.html
    def test_datetime(self):
        load_dotenv()
        client = redmine.Client()

        login = "philion"
        ticket_id = 106

        # create a note
        # get the note
        # tell me how old it is
        # get rid is those pesky microseconds that mess up compares
        timestamp = dt.datetime.now().replace(microsecond=0).astimezone(dt.timezone.utc)

        client.append_message(ticket_id, login, f"This is a test note at {timestamp}")
        all_notes = client.get_notes_since(ticket_id) # get all
        note = all_notes[-1] #last note
        created = dt.datetime.fromisoformat(note.created_on)
        print(f"{note.created_on} -> {created} tz={created.tzinfo}, LOCAL={created.astimezone().isoformat()}")
        # confirming that redmine is giving standard UTC time here.

        #print(f"note {note.id} created: {created}/{note.created_on} diff={created - timestamp} ts:{timestamp}")
        # 2023-11-19T20:42:09Z -> 2023-11-19 20:42:09+00:00 tz=UTC, LOCAL=2023-11-19T12:42:09-08:00


        # THIS IS THE CORRECT ANSWER : dt.datetime.now(dt.timezone.utc)
        

        client.update_syncdata(106, timestamp)

        ticket = client.get_ticket(106)

        last_sync = client.get_field(ticket, "sync")
        #print(f"last_sync - after {last_sync}, {last_sync.timestamp()} tz={last_sync.tzname()}")

        self.assertEqual(timestamp.timestamp(), last_sync.timestamp())



if __name__ == '__main__':
    unittest.main()