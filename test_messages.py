#!/usr/bin/env python3

import unittest
import logging
import os, glob
import datetime as dt

from dotenv import load_dotenv

import imap
import redmine

#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, 
    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
log = logging.getLogger(__name__)

load_dotenv()
client = redmine.Client()
imap = imap.Client()

class TestMessages(unittest.TestCase):
    #@unittest.skip
    def test_messages_examples(self):
        # open 
        for filename in glob.glob('test/*.eml'):
            with open(os.path.join(os.getcwd(), filename), 'rb') as file:
                message = imap.parse_message(file.read())
                #print(message.subject_cleaned())
                #if "Forwarded message" in message.note:
                #    print(f"Found: {filename}")
                tag = "------ Forwarded message ---------"
                idx = message.note.find(tag)
                self.assertEquals(-1, idx)
                
    @unittest.skip
    def test_email_address_parsing(self):
        from_address =  "Esther Jang <infrared@cs.washington.edu>"
        first, last, addr = imap.parse_email_address(from_address)
        self.assertEqual(first, "Esther")
        self.assertEqual(last, "Jang")
        self.assertEqual(addr, "infrared@cs.washington.edu")

    # disabled so I don't flood the system with files
    @unittest.skip
    def test_upload(self):

        with open("test/message-161.eml", 'rb') as file:
            message = imap.parse_message(file.read())
            #print(message)
            client.upload_attachments("philion", message.attachments)

    @unittest.skip
    def test_more_recent_ticket(self):
        ticket = client.most_recent_ticket_for("philion")
        self.assertIsNotNone(ticket)
        #print(ticket)

    @unittest.skip
    def test_recent_notes(self):
        now = dt.datetime.utcnow().astimezone(dt.timezone.utc)
        notes = client.get_notes_since(106, now)
        self.assertEqual(0, len(notes))

        notes = client.get_notes_since(106)
        self.assertEqual(2, len(notes))

    @unittest.skip
    def test_teams(self):
        username = "philion"
        teamname = "test-group"

        team = client.find_team(teamname)
        self.assertEqual(67, team.id)
        self.assertEqual(teamname, team.name)

        client.join_team(username, teamname)

        # assert in team
        self.assertTrue(client.is_user_in_team(username, teamname))

        client.leave_team(username, teamname)

        # assert in team
        self.assertFalse(client.is_user_in_team(username, teamname))

    @unittest.skip
    def test_subject_threading(self):
        # find expected tickets, based on subject
        items = [
            {"subject": "Search for subject match in email threading", "id": "193"}
        ]
        
        for item in items:
            tickets = client.search_tickets(item["subject"])
            
            self.assertEqual(1, len(tickets))
            self.assertEqual(int(item["id"]), tickets[0].id)


    # note about python date time and utc: Stop using utcnow and utcfromtimestamp
    # https://blog.ganssle.io/articles/2019/11/utcnow.html
    @unittest.skip
    def test_datetime(self):
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
        #print(f"{note.created_on} -> {created} tz={created.tzinfo}, LOCAL={created.astimezone().isoformat()}")
        # confirming that redmine is giving standard UTC time here.

        #print(f"note {note.id} created: {created}/{note.created_on} diff={created - timestamp} ts:{timestamp}")
        # 2023-11-19T20:42:09Z -> 2023-11-19 20:42:09+00:00 tz=UTC, LOCAL=2023-11-19T12:42:09-08:00


        # THIS IS THE CORRECT ANSWER : dt.datetime.now(dt.timezone.utc)
        

        client.update_syncdata(106, timestamp)

        ticket = client.get_ticket(106)

        last_sync = client.get_field(ticket, "sync")
        #print(f"last_sync - after {last_sync}, {last_sync.timestamp()} tz={last_sync.tzname()}")

        self.assertEqual(timestamp.timestamp(), last_sync.timestamp())

    @unittest.skip
    def test_email_address_parsing(self):
        addr = 'philion <philion@gmail.com>'
        
        first, last, email = imap.parse_email_address(addr)
        self.assertEqual("philion", first)
        self.assertEqual("", last)
        self.assertEqual("philion@gmail.com", email)
        
        addr2 = 'Paul Philion <philion@acmerocket.com>'
        
        first, last, email = imap.parse_email_address(addr2)
        self.assertEqual("Paul", first)
        self.assertEqual("Philion", last)
        self.assertEqual("philion@acmerocket.com", email)

    @unittest.skip
    def test_new_account(self):
        test_email = "philion@acmerocket.com"
        
        user = client.find_user(test_email)
        log.info(f"found {user} for {test_email}")
        #if user:
        #    client.remove_user(user.id) # remove the user, for testing
        #    
        #    client.reindex_users()
        #    log.info(f"removed user id={user.id} and reindexed")
        
        email = "test/message-190.eml"
        with open("test/message-190.eml", 'rb') as file:
            message = imap.parse_message(file.read())
            imap.handle_message("test", message)
        
        client.reindex_users()
        user = client.find_user(test_email)
        print(user)
        self.assertEqual(test_email, user.mail)
        # check if part of a project? how?
        self.assertTrue(client.is_user_in_team(user.login, "users"))
        
        #client.remove_user(user.id) # remove the user, for testing
        #client.reindex_users()
        #self.assertIsNone(client.find_user(test_email))
                        
        
    @unittest.skip
    def test_project_add(self):
        user = client.find_user("philion@acmerocket.com")
        self.assertIsNotNone(user)
        
        client.join_project(user.login, "scn")
        
        
        #self.assertTrue(client.is_user_in_team(user.login, "users"))

if __name__ == '__main__':
    unittest.main()