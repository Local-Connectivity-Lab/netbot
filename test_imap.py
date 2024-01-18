#!/usr/bin/env python3

import unittest
import logging
import os, glob
import datetime as dt

from dotenv import load_dotenv

import imap
import redmine
import test_utils


#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
#logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestMessages(unittest.TestCase):
    
    def setUp(self):
        #load_dotenv()
        self.redmine = redmine.Client()
        self.imap = imap.Client()
        
    def test_messages_stripping(self):
        # open 
        for filename in glob.glob('test/*.eml'):
            with open(os.path.join(os.getcwd(), filename), 'rb') as file:
                message = self.imap.parse_message(file.read())
                self.assertNotIn("------ Forwarded message ---------", message.note)
                self.assertNotIn("wrote:", message.note, f"Found 'wrote:' after processing {filename}")
                self.assertNotIn("https://voice.google.com", message.note)
                
    def test_google_stripping(self):
        with open("test/New text message from 5551212.eml", 'rb') as file:
                message = self.imap.parse_message(file.read())
                self.assertNotIn("Forwarded message", message.note)
                self.assertNotIn("https://voice.google.com", message.note)
                self.assertNotIn("YOUR ACCOUNT", message.note)
                self.assertNotIn("https://support.google.com/voice#topic=3D1707989", message.note)
                self.assertNotIn("https://productforums.google.com/forum/#!forum/voice", message.note)
                self.assertNotIn("This email was sent to you because you indicated that you'd like to receive", message.note)
                self.assertNotIn("email notifications for text messages. If you don't want to receive such", message.note)
                self.assertNotIn("emails in the future, please update your email notification settings", message.note)
                self.assertNotIn("https://voice.google.com/settings#messaging", message.note)
                self.assertNotIn("Google LLC", message.note)
                self.assertNotIn("1600 Amphitheatre Pkwy", message.note)
                self.assertNotIn("Mountain View CA 94043 USA", message.note)
                
    def test_email_address_parsing(self):
        from_address =  "Fred Example <freddy@example.com>"
        first, last, addr = self.imap.parse_email_address(from_address)
        self.assertEqual(first, "Esther")
        self.assertEqual(last, "Chae")
        self.assertEqual(addr, "freddy@example.com")

    # disabled so I don't flood the system with files
    @unittest.skip
    def test_upload(self):

        with open("test/message-161.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            #print(message)
            self.redmine.upload_attachments("philion", message.attachments)

    def test_more_recent_ticket(self):
        ticket = self.redmine.most_recent_ticket_for("philion")
        self.assertIsNotNone(ticket)
        #print(ticket)

    def test_email_address_parsing(self):
        addr = 'philion <philion@gmail.com>'
        
        first, last, email = self.imap.parse_email_address(addr)
        self.assertEqual("philion", first)
        self.assertEqual("", last)
        self.assertEqual("philion@gmail.com", email)
        
        addr2 = 'Paul Philion <philion@acmerocket.com>'
        
        first, last, email = self.imap.parse_email_address(addr2)
        self.assertEqual("Paul", first)
        self.assertEqual("Philion", last)
        self.assertEqual("philion@acmerocket.com", email)


    def test_new_account_from_email(self):
        test_email = "philion@acmerocket.com"
        
        user = self.redmine.find_user(test_email)
        log.info(f"found {user} for {test_email}")
        if user:
            self.redmine.remove_user(user.id) # remove the user, for testing
            self.redmine.reindex_users()
            log.info(f"removed user id={user.id} and reindexed for test")
        
        email = "test/message-190.eml"
        with open("test/message-190.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            self.imap.handle_message("test", message)
        
        self.redmine.reindex_users()
        user = self.redmine.find_user(test_email)
        self.assertIsNotNone(user, f"Couldn't find user for {test_email}")
        self.assertEqual(test_email, user.mail)
        self.assertTrue(self.redmine.is_user_in_team(user.login, "users"))
        
        self.redmine.remove_user(user.id) # remove the user, for testing
        self.redmine.reindex_users()
        self.assertIsNone(self.redmine.find_user(test_email))

    def test_subject_search(self):
        # create a new ticket with unique subject
        tag = test_utils.tagstr()
        user = self.redmine.find_user("philion") # FIXME: create a relaible test_user
        self.assertIsNotNone(user)
        subject = f"New ticket with unique marker {tag}"
        ticket = self.redmine.create_ticket(user, subject, f"This for {self.id}-{tag}")
        self.assertIsNotNone(ticket)

        # search for the ticket
        tickets = self.redmine.match_subject(subject)
        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(ticket.id, tickets[0].id)
        
        tickets = self.redmine.search_tickets(tag)
        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(ticket.id, tickets[0].id)
        
        # clean up
        self.redmine.remove_ticket(ticket.id)


if __name__ == '__main__':
    unittest.main()