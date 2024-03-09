"""
contains all the dataclass and models for redmine
"""

import re

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

    def upload(self, client, user):
        self.token = client.upload_file(user, self.payload, self.name, self.content_type)

    def set_token(self, token):
        self.token = token


class Message():
    """email message"""
    from_address: str
    to: str
    cc: str
    subject:str
    attachments: list[Attachment]
    note: str

    def __init__(self, from_addr:str, subject:str, to:str = None, cc:str = None):
        self.from_address = from_addr
        self.subject = subject
        self.to = to
        self.cc = cc
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

    def to_cc_str(self) -> str | None:
        if not self.cc:
            return self.to
        elif not self.to:
            return self.cc
        else:
            return '//'.join([self.to, self.cc])
