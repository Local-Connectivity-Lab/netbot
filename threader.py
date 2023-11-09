#!/usr/bin/env python3

from dotenv import load_dotenv
import imap


# load credentials 
load_dotenv()

# construct the client
imap_client = imap.Client()

# process unseen emails
imap_client.check_unseen()
