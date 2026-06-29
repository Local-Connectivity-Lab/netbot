#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IMAP module - uses remote LLM API for redaction"""

import os
import logging
import email
import email.policy
import re
import traceback

from io import StringIO
from html.parser import HTMLParser

from imapclient import IMAPClient, SEEN, DELETED
from dotenv import load_dotenv

from redmine.model import Attachment, Message
from redmine import redmine

# Import HTTP client instead of local redactor
from redactor.redactor_client import RedactorClient

log = logging.getLogger(__name__)


class MLStripper(HTMLParser):
    """strip HTML from a string"""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs= True
        self.text = StringIO()
    def handle_data(self, data):
        self.text.write(data + '\n') # force a newline
    def get_data(self):
        return self.text.getvalue()


class Client(): ## imap.Client()
    """IMAP Client"""

    def __init__(self):
        self.host = os.getenv('IMAP_HOST')
        self.user = os.getenv('IMAP_USER')
        self.passwd = os.getenv('IMAP_PASSWORD')
        self.redmine:redmine.Client = redmine.Client.fromenv()

        redactor_url = os.getenv('REDACTOR_URL')
        if redactor_url:
            # Initialize HTTP client for remote redaction
            try:
                self.redactor = RedactorClient(redactor_url)
                log.info("Connected to remote LLM API for redaction")
            except Exception as e:
                log.error(f"Failed to connect to LLM API: {e}")
                log.error("Emails will NOT be redacted!")
                self.redactor = None
        else:
            log.warning("Redactor is not configured. If redaction is needed, please configure REDACTOR_URL env var.")
            log.warning("Emails will NOT be redacted!")
            self.redactor = None


    def parse_email_address(self, email_addr):
        regex_str = r"(.*)<(.*)>"
        m = re.match(regex_str, email_addr)
        first = last = addr = ""
        if m:
            name = m.group(1).strip()
            if ' ' in name:
                first, last = name.rsplit(None, 1)
            else:
                first = name
                last = "-"
            addr = m.group(2)
            return first, last, addr
        else:
            return "", "", email_addr

    def is_html_doc(self, payload: str) -> bool:
        tags = [ "<html>", "<!doctype html>" ]
        head = payload[:20].strip().lower()
        for tag in tags:
            if head.startswith(tag):
                return True
        return False

    def parse_message(self, data):
        root = email.message_from_bytes(data, policy=email.policy.default)

        from_address = root.get("From")
        subject = root.get("Subject")
        to_header = root.get("To")
        cc_header = root.get("Cc")
        message = Message(from_address, subject, to_header, cc_header)
        payload = ""

        for part in root.walk():
            content_type = part.get_content_type()
            if part.is_attachment():
                message.add_attachment( Attachment(
                    name=part.get_filename(),
                    content_type=content_type,
                    payload=part.get_payload(decode=True)))
                log.debug(f"Added attachment: {part.get_filename()} {content_type}")
            elif content_type == 'text/plain':
                payload = part.get_payload(decode=True).decode('UTF-8')

        if payload == "":
            payload = root.get_body().get_content()
            if self.is_html_doc(payload):
                payload = self.strip_html_tags(payload)
                log.debug(f"HTML payload after: {payload}")

        payload = self.strip_forwards(payload)
        message.set_note(payload)
        log.debug(f"Setting note: {payload}")

        return message

    def strip_html_tags(self, text:str) -> str:
        s = MLStripper()
        s.feed(text)
        return s.get_data()

    skip_strs = [
        "<https://voice.google.com>",
        "YOUR ACCOUNT <https://voice.google.com> HELP CENTER",
        "<https://support.google.com/voice#topic=1707989> HELP FORUM",
        "<https://productforums.google.com/forum/#!forum/voice>",
        "This email was sent to you because you indicated that you'd like to receive",
        "email notifications for text messages. If you don't want to receive such",
        "emails in the future, please update your email notification settings",
        "<https://voice.google.com/settings#messaging>.",
        "Google LLC",
        "1600 Amphitheatre Pkwy",
        "Mountain View CA 94043 USA",
    ]

    def strip_forwards(self, text:str) -> str:
        forward_tag = "------ Forwarded message ---------"
        idx = text.find(forward_tag)
        if idx > -1:
            text = text[0:idx]

        p = re.compile(r"^On .* <.*>\s+wrote:", flags=re.MULTILINE|re.DOTALL|re.IGNORECASE)
        match = p.search(text)
        if match:
            text = text[0:match.start()]

        buffer = ""
        for line in text.splitlines():
            skip = False
            for skip_str in self.skip_strs:
                if line.startswith(skip_str):
                    skip = True
                    break
            if skip:
                log.debug(f"skipping {line}")
            else:
                buffer += line + '\n'

        return buffer.strip()

    def handle_message(self, msg_id:str, message:Message):
        first, last, addr = self.parse_email_address(message.from_address)
        subject = message.subject_cleaned()
        log.debug(f'uid:{msg_id} - from:{last}, {first}, email:{addr}, subject:{subject}')

        # NOTE: Might need a setting to override "search for matching ticket"
        # Simplyfying assumption: If the subject has a valid tracker tag -> [Valid-Tracker-Name]
        # Then skip the searches in first, next.

        # Redact message using remote API
        original_note = message.note

        if self.redactor:
            try:
                log.info(f"Redacting PII from message {msg_id} via LLM API...")
                redacted = self.redactor.redact_text(original_note)
                log.info(f"Redaction complete for message {msg_id}")
            except Exception as e:
                log.error(f"Redaction failed for message {msg_id}: {e}")
                log.warning("Creating ticket WITHOUT redaction")
                redacted = None
        else:
            log.warning("No redactor available, creating ticket WITHOUT redaction")
            redacted = None

        # Get user
        user = self.redmine.user_mgr.get_by_name(addr)
        if user is None:
            log.debug(f"Unknown email address, no user found: {addr}, {message.from_address}")
            user = self.redmine.user_mgr.create(addr, first, last, user_login=None)
            log.info(f"Unknown user: {addr}, created new account.")

        self.redmine.user_mgr.join_team(user, "users")

        # Upload attachments
        self.redmine.ticket_mgr.upload_attachments(user, message.attachments)

        # Check for existing ticket
        tickets = self.redmine.ticket_mgr.match_subject(subject)

        if len(tickets) == 1:
            ticket = tickets[0]
            log.debug(f"found ticket id={ticket.id} for subject: {subject}")
        elif len(tickets) >= 2:
            log.warning(f"subject query returned {len(tickets)} results, using first: {subject}")
            ticket = tickets[0]

        # next, find ticket using the subject, if possible
        if ticket is None:
            # this uses a simple REGEX '#\d+' to match ticket numbers
            ticket = self.redmine.find_ticket_from_str(subject)

        # get user id from from_address
        user = self.redmine.user_mgr.get_by_name(addr)
        if user is None:
            log.debug(f"Unknown email address, no user found: {addr}, {message.from_address}")
            # create new user
            user = self.redmine.user_mgr.create(addr, first, last, user_login=None)
            log.info(f"Unknow user: {addr}, created new account.")
        # make sure user is in users group
        self.redmine.user_mgr.join_team(user, "users")

        #  upload any attachments
        self.redmine.ticket_mgr.upload_attachments(user, message.attachments)

        if ticket:
            # Update existing ticket
            # self.redmine.ticket_mgr.append_message(ticket.id, user.login, message.note, message.attachments) TODO: CHANGE LATER 2/9
            # Use API key account (admin) instead of impersonating sender
            # This avoids 403 permission errors for external users
            attributed_note = f"**From:** {user.name} ({user.mail})\n\n{message.note}"
            self.redmine.ticket_mgr.append_message(ticket.id, None, attributed_note, message.attachments)
            log.info(f"Updated ticket #{ticket.id} with message from {user.login} and {len(message.attachments)} attachments")
        else:
            if redacted:
                # Store REDACTED in description (public facing)
                message.note = redacted.text
                ticket = self.redmine.create_ticket(user, message)

                # Store ORIGINAL in unredacted custom field (PII admin only)
                unredacted_cf = self.redmine.ticket_mgr.get_custom_field("unredacted")
                if unredacted_cf:
                    fields = {
                        "custom_fields": [
                            {"id": unredacted_cf.id, "value": original_note}
                        ]
                    }
                    self.redmine.ticket_mgr.update(ticket.id, fields)
                    log.info(f"Stored original in unredacted CF for ticket #{ticket.id}")
                else:
                    log.error("Custom field 'unredacted' not found!")
            else:
                # No redaction available, store original in description only
                message.note = original_note
                ticket = self.redmine.create_ticket(user, message)
            log.info(f"Created new ticket for: {ticket}, with {len(message.attachments)} attachments")

    def synchronize(self):
        """Process ONE email, then return. Returns number of emails processed (0 or 1)."""
        processed_count = 0
        try:
            with IMAPClient(host=self.host, ssl=True) as server:
                server.login(self.user, self.passwd)
                server.select_folder("INBOX", readonly=False)
                log.info(f'logged into imap {self.host}')

                messages = server.search("UNSEEN")
                log.info(f"processing {len(messages)} new messages from {self.host}")

                if not messages:
                    # No emails to process
                    log.info("done. processed 0 messages")
                    return 0

                # Process ONLY the first email
                uid = messages[0]  # Get first unread email
                message_data = server.fetch([uid], "RFC822")

                try:
                    data = message_data[uid][b"RFC822"]
                    message = self.parse_message(data)
                    self.handle_message(uid, message)
                    server.add_flags(uid, [SEEN, DELETED])
                    processed_count = 1
                    log.info("done. processed 1 message")
                except Exception as e:
                    log.error(f"Message {uid} can not be processed: {e}")
                    traceback.print_exc()
                    with open(f"message-err-{uid}.eml", "wb") as file:
                        file.write(data)
                    server.add_flags(uid, [SEEN])
                    processed_count = 0

        except Exception as ex:
            log.error(f"caught exception syncing IMAP: {ex}")
            traceback.print_exc()

        return processed_count

    # def process_edit_job(self, job: dict):
    #     #Process a ticket edit job from the queue
    #     from redaction_queue import RedactionQueue

    #     ticket_id = job["ticket_id"]
    #     new_description = job["description"]
    #     user_info = job["user"]

    #     log.info(f"Processing edit for ticket #{ticket_id}")

    #     queue = RedactionQueue()

    #     try:
    #         # Lock the ticket
    #         queue.lock_ticket(ticket_id, "edit")

    #         # Get ticket
    #         ticket = self.redmine.ticket_mgr.get(ticket_id)
    #         if not ticket:
    #             raise Exception(f"Ticket #{ticket_id} not found")

    #         # Redact the new description
    #         if self.redactor:
    #             log.info(f"Redacting new description for ticket #{ticket_id}")
    #             redacted = self.redactor.redact_text(new_description)
    #             log.info(f"Redaction complete for ticket #{ticket_id}")
    #         else:
    #             log.warning("No redactor available")
    #             redacted = None

    #         # Update ticket in Redmine
    #         if redacted:
    #             # Store ORIGINAL in description (admin-only)
    #             fields = {"description": new_description}
    #             self.redmine.ticket_mgr.update(ticket_id, fields)

    #             # Store REDACTED in custom field (public)
    #             redacted_cf = self.redmine.ticket_mgr.get_custom_field("redacted")
    #             if redacted_cf:
    #                 fields = {
    #                     "custom_fields": [
    #                         {"id": redacted_cf.id, "value": redacted.text}
    #                     ]
    #                 }
    #                 self.redmine.ticket_mgr.update(ticket_id, fields)
    #                 log.info(f"Updated redacted field for ticket #{ticket_id}")
    #         else:
    #             # No redaction, just update description
    #             fields = {"description": new_description}
    #             self.redmine.ticket_mgr.update(ticket_id, fields)

    #         log.info(f"Successfully updated ticket #{ticket_id}")

    #     finally:
    #         # Always unlock ticket
    #         queue.unlock_ticket(ticket_id)


    def process_edit_job(self, job: dict):
        #process a ticket edit job from the queue
        from redaction_queue import RedactionQueue

        ticket_id = job["ticket_id"]
        new_description = job["description"]
        user_info = job.get("user", {})

        queue = RedactionQueue()

        try:
            queue.lock_ticket(ticket_id, "edit")

            log.info(f"Processing edit for ticket #{ticket_id}")

            # Get ticket
            # ticket = self.redmine.ticket_mgr.get(ticket_id)
            # Only ticket_id is needed.

            # Redact description
            log.info(f"Redacting new description for ticket #{ticket_id}")
            if self.redactor:
                redacted = self.redactor.redact_text(new_description)
            else:
                redacted = None

            # Update Redmine
            if redacted:
                # Redacted in description (public facing)
                # Original in unredacted CF (PII admin only)
                unredacted_cf = self.redmine.ticket_mgr.get_custom_field("unredacted")
                if unredacted_cf:
                    fields = {
                        "description": redacted.text,
                        "custom_fields": [
                            {"id": unredacted_cf.id, "value": new_description}
                        ],
                        "notes": f"Ticket description updated and redacted by {user_info.get('name', 'user')}"
                    }
                    self.redmine.ticket_mgr.update(ticket_id, fields)
                    log.info(f"Updated description (redacted) and unredacted CF for ticket #{ticket_id}")
                else:
                    log.error("Custom field 'unredacted' not found!")
                    self.redmine.ticket_mgr.update(ticket_id, {
                        "description": redacted.text,
                        "notes": f"Ticket description updated and redacted by {user_info.get('name', 'user')}"
                    })
            else:
                # No redaction available - store original in description
                params = {
                    "description": new_description,
                    "notes": f"Ticket description updated (no redaction) by {user_info.get('name', 'user')}"
                }
                self.redmine.ticket_mgr.update(ticket_id, params)
            log.info(f"Successfully updated ticket #{ticket_id}")

        finally:
            queue.unlock_ticket(ticket_id)


if __name__ == '__main__':
    log.info('initializing IMAP threader')
    load_dotenv()
    Client().synchronize()