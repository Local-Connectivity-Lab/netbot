#!/usr/bin/env python3

import os
import logging
import email
import email.policy
import re
import traceback

import redmine

from imapclient import IMAPClient, SEEN, DELETED
from dotenv import load_dotenv


# imapclient docs: https://imapclient.readthedocs.io/en/3.0.0/index.html
# source code: https://github.com/mjs/imapclient


## logging ##
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


# Parsing compound forwarded emails messages is more complex than expected, so
# Message will represent everything needed for creating and updating tickets,
# including attachments.
class Attachment():
    def __init__(self, name:str, type:str, payload):
        self.name = name
        self.content_type = type
        self.payload = payload

    def upload(self, client, user_id):
        self.token = client.upload_file(user_id, self.payload, self.name, self.content_type)

    def set_token(self, token):
        self.token = token


class Message():
    def __init__(self, from_addr:str, subject:str):
        self.from_address = from_addr
        self.subject = subject
        self.attachments = []

    # Note: note containts the text of the message, the body of the email
    def set_note(self, note:str):
        self.note = note

    def add_attachment(self, attachment:Attachment):
        self.attachments.append(attachment)

    def __str__(self):
        return f"from:{self.from_address}, subject:{self.subject}, attached:{len(self.attachments)}; {self.note[0:20]}" 


def parse_message(data):
    # NOTE this policy setting is important, default is "compat-mode"
    root = email.message_from_bytes(data, policy=email.policy.default)

    from_address = root.get("From")
    subject = root.get("Subject")

    message = Message(from_address, subject)

    for part in root.walk():
        content_type = part.get_content_type()
        if part.is_attachment():
            message.add_attachment( Attachment(
                name=part.get_filename(), 
                type=content_type,
                payload=part.get_payload(decode=True)))
            log.debug(f"Added attachment: {part.get_filename()} {content_type}")
        elif content_type == 'text/plain': # FIXME std const?
            payload = part.get_payload(decode=True).decode('UTF-8')
            message.set_note(payload)
            log.debug(f"Set note, size={len(payload)}: {payload[0:20]}...")

    return message

# note: not happy with this method of dealing with complex email address
# but I don't see a better way. open to suggestions
def parse_email_address(email_addr):
    #regex_str = r"(.*)<(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)>"
    regex_str = r"(.*)<(.*)>"
    m = re.match(regex_str, email_addr)
    first = last = addr = ""
    if m:
        first, last = m.group(1).strip().rsplit(' ', 1)
        addr = m.group(2)
    else:
        log.error(f"Unable to parse email str: {email_addr}")

    return first, last, addr


class Client(): ## imap.Client()
    def __init__(self):
        self.host = os.getenv('IMAP_HOST')
        self.user = os.getenv('IMAP_USER')
        self.passwd = os.getenv('IMAP_PASSWORD')
        self.port = 993
        self.redmine = redmine.Client()


    def handle_message(self, uid:str, message:Message):
        first, last, addr = parse_email_address(message.from_address)
        log.info(f'uid:{uid} - from:{last}, {first}, email:{addr}, subject:{message.subject}')

        # get user id from from_address
        user = self.redmine.find_user(addr)
        if user == None:
            log.error(f"Unknown email address, no user found: {addr}, {message.from_address}")
            # TODO throw EX or create user
            # create new user if needed -> always new ticket
            # TODO try parsing first and last from from_address
            # user = redmine.create_user(addr, first, last)
            # self.redmine.create_ticket(user.login, subject, body)
            return
 
        # find ticket using the subject, if possible
        # this uses a simple REGEX '#\d+' to match ticket numbers
        ticket = self.redmine.find_ticket_from_str(message.subject)
        
        # if there is not ticket number found,
        # query "most recently updated open ticket by userid", if any
        if user and (ticket is None):
            ticket = self.redmine.most_recent_ticket_for(user.login)

        if ticket:
            # found a ticket, append the message

            # first, upload any attachments
            for attachment in message.attachments:
                # uploading the attachment this way
                # puts the token in the attachment
                attachment.upload(self.redmine, user.login)

            self.redmine.append_message(ticket.id, user.login, message.note, message.attachments)
            log.info(f"Updated ticket #{ticket.id} with message from {user.login}")
        else:
            # no open tickets, create new ticket for the email message
            self.redmine.create_ticket(user.login, message.subject, message.body)
            ## FIXME get ticket #, add attachments
            log.info(f"Created new ticket from: {user.login}")


    def check_unseen(self):
        with IMAPClient(host=self.host, port=self.port, ssl=True) as server:
            server.login(self.user, self.passwd)
            server.select_folder("INBOX", readonly=False)
            log.info(f'logged into imap {self.host}')

            messages = server.search("UNSEEN")
            for uid, message_data in server.fetch(messages, "RFC822").items():
                data = message_data[b"RFC822"]
                
                # log the file
                #with open(f"message-{uid}.eml", "wb") as file:
                #    file.write(data)

                # process each message returned by the query
                try:
                    # decode the message
                    message = parse_message(data)

                    # handle the message
                    self.handle_message(uid, message)

                    #  mark msg uid seen and deleted, as per redmine imap.rb
                    server.add_flags(uid, [SEEN, DELETED])

                except Exception as e:
                    log.error(f"Message {uid} can not be processed: {e}")
                    traceback.print_exc()
                    server.add_flags(uid, [SEEN])


# this behavior mirrors that of threader.py, for now.
# in the furute, this will run the imap threading, while
# threader.py will coordinate all the threaders.
if __name__ == '__main__':
    log.info('initializing IMAP threader')

    # load credentials 
    load_dotenv()

    # construct the client and run the email check
    Client().check_unseen()

    #with open("test_messages/message-126.eml", 'rb') as file:
    #    message = parse_message(file.read())
    #    Client().handle_message("126", message)
