#!/usr/bin/env python3
"""IMAP test cases"""

import unittest
import logging
import os
import glob

from dotenv import load_dotenv

import imap
import redmine
import test_utils


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestMessages(unittest.TestCase):
    """Test suite for IMAP functions"""

    def setUp(self):
        self.redmine: redmine.Client = redmine.Client.fromenv()
        self.imap: imap.Client = imap.Client()

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
        self.assertEqual(first, "Fred")
        self.assertEqual(last, "Example")
        self.assertEqual(addr, "freddy@example.com")

    # disabled so I don't flood the system with files
    def test_upload(self):
        with open("test/message-161.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            self.redmine.upload_attachments("philion", message.attachments)


    def test_doctype_head(self):
        # NOTING for future: This doc shows a need for much better HTML stripping, but I'm not
        # rewriting that this afternoon, this tests the fix for the actual bug (ignoring DOCTYPE)
        with open("test/message-doctype.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            #log.info(f"### message: {message}")
            self.assertFalse(message.note.startswith("<!doctype html>"))


    def test_more_recent_ticket(self):
        ticket = self.redmine.most_recent_ticket_for("philion")
        self.assertIsNotNone(ticket)


    def test_email_address_parsing2(self):
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
        # make sure neither the email or subject exist
        # note: these are designed to fail-fast, because trying to manage the user and subject as part of the test failed.
        test_email = "philion@acmerocket.com"
        user = self.redmine.lookup_user(test_email)
        self.assertIsNone(user, "Found existing user: {test_email}")

        subject = "Search for subject match in email threading"
        tickets = self.redmine.match_subject(subject)
        self.assertEqual(0, len(tickets), "Found ticket matching: '{subject}' - {tickets[0].id}, please delete.")

        with open("test/message-190.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            log.debug(f"loaded message: {message}")
            self.imap.handle_message("test", message)

        user = self.redmine.lookup_user(test_email)
        self.assertIsNotNone(user, f"Couldn't find user for {test_email}")
        self.assertEqual(test_email, user.mail)

        # validate the ticket created by message-190
        #subject = "Search for subject match in email threading"
        tickets = self.redmine.match_subject(subject)
        self.assertEqual(1, len(tickets))
        self.assertEqual(subject, tickets[0].subject)
        self.assertEqual(user.id, tickets[0].author.id)

        # remove the ticket
        self.redmine.remove_ticket(tickets[0].id)

        # remove the user after the test
        self.redmine.user_mgr.remove(user)


    def test_subject_search(self):
        # create a new ticket with unique subject
        tag = test_utils.tagstr()
        user = self.redmine.user_mgr.get_by_name("admin") # FIXME: create_test_user in test_utils
        self.assertIsNotNone(user)
        subject = f"Test {tag} {tag} {tag}"
        ticket = self.redmine.create_ticket(user, subject, f"This for {self.id}-{tag}")
        self.assertIsNotNone(ticket)

        # search for the ticket
        tickets = self.redmine.match_subject(subject)
        for check in tickets:
            log.debug(f"### tickets: {check.subject}")
        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(ticket.id, tickets[0].id)

        tickets = self.redmine.search_tickets(tag)
        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(ticket.id, tickets[0].id)

        # clean up
        self.redmine.remove_ticket(ticket.id)


    def test_ticket_query(self):
        # FIXME move to test_redmine.py

        # create a ticket with the tag in the body, not the subject
        tag = test_utils.tagstr()
        user = self.redmine.user_mgr.get_by_name("admin")
        self.assertIsNotNone(user)
        body = f"Body with {self.id} and {tag}"
        ticket = self.redmine.create_ticket(user, "Boring test ticket", body)
        self.assertIsNotNone(ticket)

        # search for the ticket
        tickets = self.redmine.search_tickets(tag)

        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(ticket.id, tickets[0].id)

        # clean up
        self.redmine.remove_ticket(ticket.id)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="{asctime} {levelname:<8s} {name:<16} {message}", style='{')
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)

    unittest.main()
