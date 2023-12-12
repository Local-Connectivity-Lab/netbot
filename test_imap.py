#!/usr/bin/env python3

import unittest
import logging
import os, glob
import datetime as dt

from dotenv import load_dotenv

import imap
import redmine

logging.basicConfig(level=logging.ERROR)

#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.DEBUG, 
#    format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
#logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

log = logging.getLogger(__name__)

load_dotenv()
client = redmine.Client()
imap = imap.Client()

class TestMessages(unittest.TestCase):
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
                self.assertEqual(-1, idx)
                
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

    def test_more_recent_ticket(self):
        ticket = client.most_recent_ticket_for("philion")
        self.assertIsNotNone(ticket)
        #print(ticket)


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


if __name__ == '__main__':
    unittest.main()