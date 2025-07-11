#!/usr/bin/env python3
"""IMAP test cases"""

import unittest
import logging
import os
import glob

from dotenv import load_dotenv

from redmine.model import Message
from threader import imap
from tests import test_utils


log = logging.getLogger(__name__)


@unittest.skipUnless(load_dotenv(), "ENV settings not available")
class TestMessages(test_utils.RedmineTestCase):
    """Test suite for IMAP functions"""

    def setUp(self):
        self.imap: imap.Client = imap.Client()


    def test_messages_stripping(self):
        # open
        for filename in glob.glob('data/*.eml'):
            with open(os.path.join(os.getcwd(), filename), 'rb') as file:
                message = self.imap.parse_message(file.read())
                self.assertNotIn("------ Forwarded message ---------", message.note)
                self.assertNotIn("wrote:", message.note, f"Found 'wrote:' after processing {filename}")
                self.assertNotIn("https://voice.google.com", message.note)


    def test_google_stripping(self):
        with open("data/New text message from 5551212.eml", 'rb') as file:
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
        with open("data/message-161.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            user = self.redmine.user_mgr.get_by_name('admin')
            self.redmine.ticket_mgr.upload_attachments(user, message.attachments)


    def test_doctype_head(self):
        # NOTING for future: This doc shows a need for much better HTML stripping, but I'm not
        # rewriting that this afternoon, this tests the fix for the actual bug (ignoring DOCTYPE)
        with open("data/message-doctype.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            self.assertFalse(message.note.startswith("<!doctype html>"))


    def test_more_recent_ticket(self):
        user = self.redmine.user_mgr.get_by_name('admin')
        ticket = self.redmine.ticket_mgr.most_recent_ticket_for(user)
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

        addr3 = 'no-reply@accounts.google.com'
        first, last, email = self.imap.parse_email_address(addr3)
        self.assertEqual("", first)
        self.assertEqual("", last)
        self.assertEqual(addr3, email)


    @unittest.skip # failing because user exists, but I can't find the user!
    def test_new_account_from_email(self):
        # make sure neither the email or subject exist
        # note: these are designed to fail-fast, because trying to manage the user and subject as part of the test failed.
        tickets = []
        try:
            test_email = "philion@acmerocket.com"
            user = self.redmine.user_mgr.get_by_name(test_email)
            self.assertIsNone(user, f"Found existing user: {test_email}")

            subject = "Search for subject match in email threading"
            tickets = self.redmine.ticket_mgr.match_subject(subject)
            self.assertEqual(0, len(tickets), f"Found ticket matching: '{subject}' - {tickets}, please delete.")

            with open("data/message-190.eml", 'rb') as file:
                message = self.imap.parse_message(file.read())
                log.debug(f"loaded message: {message}")
                self.imap.handle_message("test", message)

            user = self.redmine.user_mgr.find(test_email)
            self.assertIsNotNone(user, f"Couldn't find user for {test_email}")
            self.assertEqual(test_email, user.mail)

            # validate the ticket created by message-190
            tickets = self.redmine.ticket_mgr.match_subject(subject)
            self.assertEqual(1, len(tickets))
            self.assertTrue(tickets[0].subject.endswith(subject))
            self.assertEqual(user.id, tickets[0].author.id)
        finally:
            if tickets:
                # remove the ticket
                self.redmine.ticket_mgr.remove(tickets[0].id)
            if user:
                # remove the user after the test
                self.redmine.user_mgr.remove(user)


    def test_subject_search(self):
        # create a new ticket with unique subject
        tag = test_utils.tagstr()
        user = self.redmine.user_mgr.get_by_name("test-user")
        self.assertIsNotNone(user)
        subject = f"Test {tag} {tag} {tag}"
        message = Message(user.mail, subject, f"to-{tag}@example.com", f"cc-{tag}@example.com")
        ticket = self.redmine.create_ticket(user, message)
        self.assertIsNotNone(ticket)

        # search for the ticket
        tickets = self.redmine.ticket_mgr.match_subject(subject)
        #for check in tickets:
        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(ticket.id, tickets[0].id)

        tickets = self.redmine.ticket_mgr.search(tag)
        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(ticket.id, tickets[0].id)

        # clean up
        self.redmine.ticket_mgr.remove(ticket.id)


    def test_handle_message(self):
        subject = f"TEST {self.tag} {unittest.TestCase.id(self)}"
        message = Message(
            f"Test {self.tag} <{self.user.mail}>",
            subject,
            f"to-{self.tag}@example.com",
            f"cc-{self.tag}@example.com")
        self.imap.handle_message(self.tag, message)

        tickets = self.redmine.ticket_mgr.match_subject(subject)
        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        self.assertEqual(subject, tickets[0].subject)

        # clean up
        self.redmine.ticket_mgr.remove(tickets[0].id)


    def test_find_tracker(self):
        checks = [
            "[Research] More of the test.",
            "[Yoyo] All good things",
            "[Software-Dev]    Yo!!!",
            "[Infra-Config] This is more text.",
            "[Admin]",
        ]

        expect = [
            "Research",
            "External-Comms-Intake",
            "Software-Dev",
            "Infra-Config",
            "Admin",
        ]

        for i, check in enumerate(checks):
            tracker = self.redmine.find_tracker(check)
            self.assertEqual(tracker.name, expect[i])


    def test_handle_message_tracker(self):
        with open("data/with-tracker.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            self.imap.handle_message(self.tag, message)

            tickets = self.redmine.ticket_mgr.match_subject(message.subject)
            self.assertIsNotNone(tickets)
            self.assertEqual(1, len(tickets))
            ticket = tickets[0]

            # clean up
            self.redmine.ticket_mgr.remove(ticket.id)

            self.assertEqual(ticket.tracker.name, "Research")
            self.assertEqual(ticket.subject, "test_handle_message_tracker")


    def test_to_cc(self):
        subject = f"TEST {self.tag} {unittest.TestCase.id(self)}"
        to_addr = f"to-{self.tag}@example.com"
        cc_addr = f"cc-{self.tag}@example.com"
        message = Message(
            f"Test {self.tag} <{self.user.mail}>",
            subject,
            to_addr,
            cc_addr)

        self.imap.handle_message(self.tag, message)

        tickets = self.redmine.ticket_mgr.match_subject(subject)
        self.assertIsNotNone(tickets)
        self.assertEqual(1, len(tickets))
        ticket = tickets[0]

        self.assertEqual(subject, ticket.subject)
        self.assertEqual(to_addr, ticket.to[0])
        self.assertEqual(cc_addr, ticket.cc[0])

        # clean up
        self.redmine.ticket_mgr.remove(tickets[0].id)


    def test_known_user(self):
        # Found a problem where redmine was rejecting
        # requests to create new tickets from email for
        # known email addrs.
        # This is an attempt to recreate (to fix)
        # Update: origin email is now blocked, and invokes
        # differnt logic.
        # email = "no-reply@accounts.google.com"
        email = "philion@gmail.com"

        user = self.redmine.user_mgr.get_by_name(email)
        self.assertIsNotNone(user, f"Couldn't find user for {email}")
        self.assertEqual(email, user.mail)
        log.info(f"Found user for {email}: {user}")

        subject = f"{self.tag}.{unittest.TestCase.id(self)}"
        message = Message(email, subject)
        self.imap.handle_message(unittest.TestCase.id(self), message)

        # validate the ticket created
        tickets = self.redmine.ticket_mgr.match_subject(subject)
        self.assertEqual(1, len(tickets))
        self.assertEqual(subject, tickets[0].subject)
        self.assertEqual(user.id, tickets[0].author.id)

        # remove the ticket
        self.redmine.ticket_mgr.remove(tickets[0].id)


    def test_strip_forwards(self):
        with open("data/message-err-4920.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())
            for line in message.note.splitlines():
                self.assertFalse(line.strip().startswith(">"), "found a line that starts with '>'")


    def test_err_4920(self):
        with open("data/message-err-4920.eml", 'rb') as file:
            message = self.imap.parse_message(file.read())

            self.assertEqual(message.from_address, "Vorpal George <zapbran@uw.edu>")

            # handle the message
            self.imap.handle_message(unittest.TestCase.id(self), message)

            tickets = self.redmine.ticket_mgr.match_subject(message.subject)
            self.assertEqual(1, len(tickets))
            self.assertEqual(message.subject, tickets[0].subject)
            #self.assertEqual(user.id, tickets[0].author.id)


    def test_add_note(self):
        test_ticket_id = 182
        ticket = self.redmine.ticket_mgr.get(test_ticket_id)
        user = self.redmine.user_mgr.get_by_name("test-known-user")
        self.assertIsNotNone(user)

        message = Message(f"{user.name} <{user.mail}>", "RE: " + ticket.subject)
        note = f"TEST {self.tag} {unittest.TestCase.id(self)}"
        message.set_note(note)
        self.imap.handle_message(self.tag, message)

        ticket = self.redmine.ticket_mgr.get(test_ticket_id, include="journals")
        self.assertIsNotNone(ticket)

        last_note = ticket.get_notes()[-1]
        self.assertEqual(last_note.user.id, user.id)
        self.assertEqual(last_note.notes, note)
