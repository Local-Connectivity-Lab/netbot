#!/usr/bin/env python3

import unittest
import logging
import os, glob
import datetime as dt

from dotenv import load_dotenv

import imap
import redmine


#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.DEBUG, 
#    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
#logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestMessages(unittest.TestCase):
    
    def setUp(self):
        #load_dotenv()
        self.redmine = redmine.Client()
        self.imap = imap.Client()
        
    def test_messages_examples(self):
        # open 
        for filename in glob.glob('test/*.eml'):
            with open(os.path.join(os.getcwd(), filename), 'rb') as file:
                message = self.imap.parse_message(file.read())
                self.assertNotIn("------ Forwarded message ---------", message.note)
                self.assertNotIn("wrote:", message.note, f"Found 'wrote:' after processing {filename}")
                self.assertNotIn("https://voice.google.com", message.note)
                
    def test_email_address_parsing(self):
        from_address =  "Esther Jang <infrared@cs.washington.edu>"
        first, last, addr = self.imap.parse_email_address(from_address)
        self.assertEqual(first, "Esther")
        self.assertEqual(last, "Jang")
        self.assertEqual(addr, "infrared@cs.washington.edu")

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
        self.assertEqual(test_email, user.mail)
        self.assertTrue(self.redmine.is_user_in_team(user.login, "users"))
        
        self.redmine.remove_user(user.id) # remove the user, for testing
        self.redmine.reindex_users()
        self.assertIsNone(self.redmine.find_user(test_email))

    def test_subject_search(self):
        # find expected tickets, based on subject
        items = [
            {"subject": "Search for subject match in email threading", "id": "218"}
        ]
        
        for item in items:
            tickets = self.redmine.search_tickets(item["subject"])
            
            self.assertEqual(1, len(tickets))
            self.assertEqual(int(item["id"]), tickets[0].id)


if __name__ == '__main__':
    unittest.main()