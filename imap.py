#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IMAP module"""

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

import redmine


# imapclient docs: https://imapclient.readthedocs.io/en/3.0.0/index.html
# source code: https://github.com/mjs/imapclient


log = logging.getLogger(__name__)


# Parsing compound forwarded emails messages is more complex than expected, so
# Message will represent everything needed for creating and updating tickets,
# including attachments.
class Attachment():
    """email attachment"""
    def __init__(self, name:str, content_type:str, payload):
        self.name = name
        self.content_type = content_type
        self.payload = payload
        self.token = None

    def upload(self, client, user_id):
        self.token = client.upload_file(user_id, self.payload, self.name, self.content_type)

    def set_token(self, token):
        self.token = token


class Message():
    """email message"""
    def __init__(self, from_addr:str, subject:str):
        self.from_address = from_addr
        self.subject = subject
        self.attachments = []
        self.note = ""

    # Note: note containts the text of the message, the body of the email
    def set_note(self, note:str):
        self.note = note

    def add_attachment(self, attachment:Attachment):
        self.attachments.append(attachment)

    def subject_cleaned(self) -> str:
        # strip any re: and forwarded from a subject line
        # from: https://stackoverflow.com/questions/9153629/regex-code-for-removing-fwd-re-etc-from-email-subject
        p = re.compile(r'^([\[\(] *)?(RE?S?|FYI|RIF|I|FS|VB|RV|ENC|ODP|PD|YNT|ILT|SV|VS|VL|AW|WG|ΑΠ|ΣΧΕΤ|ΠΡΘ|תגובה|הועבר|主题|转发|FWD?) *([-:;)\]][ :;\])-]*|$)|\]+ *$', re.IGNORECASE)
        return p.sub('', self.subject).strip()

    def __str__(self):
        return f"from:{self.from_address}, subject:{self.subject}, attached:{len(self.attachments)}; {self.note[0:20]}"


# from https://stackoverflow.com/questions/753052/strip-html-from-strings-in-python
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
        self.redmine = redmine.Client()

    # note: not happy with this method of dealing with complex email address
    # but I don't see a better way. open to suggestions
    def parse_email_address(self, email_addr):
        #regex_str = r"(.*)<(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)>"
        regex_str = r"(.*)<(.*)>"
        m = re.match(regex_str, email_addr)
        first = last = addr = ""
        if m:
            name = m.group(1).strip()
            if ' ' in name:
                first, last = name.rsplit(None, 1)
            else:
                first = name
                last = ""
            addr = m.group(2)
        else:
            log.error(f"Unable to parse email str: {email_addr}")

        return first, last, addr


    def is_html_doc(self, payload: str) -> bool:
        # check the first few chars to see if they contain any HTML tags
        tags = [ "<html>", "<!doctype html>" ]
        head = payload[:20].strip().lower()
        for tag in tags:
            if head.startswith(tag):
                return True
        # no html tag found
        return False


    def parse_message(self, data):
        # NOTE this policy setting is important, default is "compat-mode" amd we need "default"
        root = email.message_from_bytes(data, policy=email.policy.default)

        from_address = root.get("From")
        subject = root.get("Subject")
        message = Message(from_address, subject)
        payload = ""

        for part in root.walk():
            content_type = part.get_content_type()
            if part.is_attachment():
                message.add_attachment( Attachment(
                    name=part.get_filename(),
                    content_type=content_type,
                    payload=part.get_payload(decode=True)))
                log.debug(f"Added attachment: {part.get_filename()} {content_type}")
            elif content_type == 'text/plain': # FIXME std const?
                payload = part.get_payload(decode=True).decode('UTF-8')

        # http://10.10.0.218/issues/208
        if payload == "":
            payload = root.get_body().get_content()
            # search for HTML
            if self.is_html_doc(payload):
                # strip HTML
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
        # strip any forwarded messages
        # from ^>
        forward_tag = "------ Forwarded message ---------"
        idx = text.find(forward_tag)
        if idx > -1:
            text = text[0:idx]

        # search for "On ... wrote:"
        p = re.compile(r"^On .* <.*>\s+wrote:", flags=re.MULTILINE)
        match = p.search(text)
        if match:
            text = text[0:match.start()]

        # TODO search for --

        # look for google content, as in http://10.10.0.218/issues/323
        buffer = ""
        for line in text.splitlines():
            skip = False
            # search for skip_strs
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

        ticket = None
        # first, search for a matching subject
        tickets = self.redmine.match_subject(subject)
        if len(tickets) == 1:
            # as expected
            ticket = tickets[0]
            log.debug(f"found ticket id={ticket.id} for subject: {subject}")
        elif len(tickets) >= 2:
            # more than expected
            log.warning(f"subject query returned {len(tickets)} results, using first: {subject}")
            ticket = tickets[0]

        # next, find ticket using the subject, if possible
        if ticket is None:
            # this uses a simple REGEX '#\d+' to match ticket numbers
            ticket = self.redmine.find_ticket_from_str(subject)

        # get user id from from_address
        user = self.redmine.find_user(addr)
        if user is None:
            log.debug(f"Unknown email address, no user found: {addr}, {message.from_address}")
            # create new user
            user = self.redmine.create_user(addr, first, last)
            log.info(f"Unknow user: {addr}, created new account.")

        #  upload any attachments
        for attachment in message.attachments:
            # uploading the attachment this way
            # puts the token in the attachment
            attachment.upload(self.redmine, user.login)

        if ticket:
            # found a ticket, append the message
            self.redmine.append_message(ticket.id, user.login, message.note, message.attachments)
            log.info(f"Updated ticket #{ticket.id} with message from {user.login} and {len(message.attachments)} attachments")
        else:
            # no open tickets, create new ticket for the email message
            self.redmine.create_ticket(user, subject, message.note, message.attachments)
            log.info(f"Created new ticket for: {user.login}, {subject}, with {len(message.attachments)} attachments")


    def synchronize(self):
        try:
            with IMAPClient(host=self.host, ssl=True) as server:
                # https://imapclient.readthedocs.io/en/3.0.1/api.html#imapclient.IMAPClient.oauthbearer_login
                # NOTE: self.user -> IMAP_USER -> identity, self.user -> IMAP_PASSWD -> token
                server.login(self.user, self.passwd)
                #server.oauthbearer_login(self.user, self.passwd)
                #server.oauth2_login(self.user, self.passwd)

                server.select_folder("INBOX", readonly=False)
                log.info(f'logged into imap {self.host}')

                messages = server.search("UNSEEN")
                log.info(f"processing {len(messages)} new messages from {self.host}")

                for uid, message_data in server.fetch(messages, "RFC822").items():
                    # process each message returned by the query
                    try:
                        # decode the message
                        data = message_data[b"RFC822"]
                        message = self.parse_message(data)

                        # handle the message
                        self.handle_message(uid, message)

                        #  mark msg uid seen and deleted, as per redmine imap.rb
                        server.add_flags(uid, [SEEN, DELETED])

                    except Exception as e:
                        log.error(f"Message {uid} can not be processed: {e}")
                        traceback.print_exc()
                        # save the message data in a file
                        with open(f"message-err-{uid}.eml", "wb") as file:
                            file.write(data)
                        server.add_flags(uid, [SEEN])

                log.info(f"done. processed {len(messages)} messages")
        except Exception as ex:
            log.error(f"caught exception syncing IMAP: {ex}")
            traceback.print_exc()


# Run the IMAP sync process
if __name__ == '__main__':
    log.info('initializing IMAP threader')

    # load credentials
    load_dotenv()

    # construct the client and run the email check
    Client().synchronize()
