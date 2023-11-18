#!/usr/bin/env python3

import unittest
import logging
import os, glob
import datetime as dt

from dotenv import load_dotenv

import imap
import redmine

#logging.basicConfig(level=logging.DEBUG)
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

    def test_recent_notes(self):
        load_dotenv()
        client = redmine.Client()

        now = dt.datetime.utcnow().astimezone(dt.timezone.utc)
        notes = client.get_notes_since(106, now)
        self.assertEqual(0, len(notes))

        notes = client.get_notes_since(106)
        self.assertEqual(2, len(notes))

if __name__ == '__main__':
    unittest.main()