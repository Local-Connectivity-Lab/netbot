"""Simple PII redactor"""

import re
import json
import logging
import sys
from mlx_lm import load, generate
from redmine.model import Ticket

log = logging.getLogger(__name__)

default_model_file = "finetuning/adapters/pii-redactor-3b-varied"
model_name = "mlx-community/Llama-3.2-3B-Instruct-4bit"
system_prompt = """You are a **privacy compliance officer** responsible for redacting **personally identifiable information (PII)** from **Redmine support tickets** before they are shared on public platforms like Discord.

        Your primary goal is to **remove PII while preserving ticket clarity and structure** so that it remains **useful for troubleshooting and public discussion.**
        ALWAYS REMEMBER: never summarize a ticket. redact per instructions but never summarize or shorten excessively

        ---

        ## **Strict Redaction Rules:**
        Apply these redaction rules carefully:

        ### **1. Names**
        Replace all personal names with placeholders
        Note: If there's only a first name, leave as is. If both first and last names are present, redact the last name only.
        using **original firstname [LastNameN]**, where **N** is a unique number per name within the ticket.

        - Example:
        - **Original:** *Chris Caputo reported an issue with network latency.*
        - **Redacted:** *Chris [LastName1] reported an issue with network latency.*

        - Example:
        - **Original:** *John reported an issue with network latency.*
        - **Redacted:** *John reported an issue with network latency.*

        - Example (Multiple people):
        - **Original:** *Esther Jang contacted Alice about the issue.*
        - **Redacted:** *Esther [LastName1] contacted Alice about the issue.*

        - Example (Multiple people):
        - **Original:** *Esther Jang contacted Alice Beatrice about the issue.*
        - **Redacted:** *Esther [LastName1] contacted Alice [LastName2] about the issue.*

        ### **2. Emails**
        Replace all email addresses with **[EmailN]**, ensuring correct numbering within the ticket.

        - Example:
        - **Original:** *Please contact john.doe@example.com for assistance.*
        - **Redacted:** *Please contact [Email1] for assistance.*

        - **Original:** *infrared@cs.washington.edu requested access to the document.*
        - **Redacted:** *[Email2] requested access to the document.*

        ### **3. Phone Numbers**
        Replace all phone numbers with **[PhoneN]**.

        - Example:
        - **Original:** *Call us at +1 (555) 123-4567 for support.*
        - **Redacted:** *Call us at [Phone1] for support.*

        ### **4. Physical Addresses**
        Replace all physical addresses (including partial ones) with **[AddressN]**.

        - Example:
        - **Original:** *The router is located at 1234 Elm St, Seattle, WA 98101.*
        - **Redacted:** *The router is located at [Address1].*

        ### **5. IP & MAC Addresses**
        Replace all IP addresses (both IPv4 and IPv6) and MAC addresses with **[IPN]** and **[MACN]**, respectively.

        - Example:
        - **Original:** *Router IP: 192.168.1.100, IPv6: 2001:db8::ff00:42:8329.*
        - **Redacted:** *Router IP: [IP1], IPv6: [IP2].*

        - **Original:** *Device MAC: AA:BB:CC:DD:EE:FF.*
        - **Redacted:** *Device MAC: [MAC1].*

        ### **6. Public Keys & Login Credentials**
        Replace cryptographic keys (such as SSH, PGP, and API keys) with **[PublicKeyN]**.

        - Example:
        - **Original:** *PGP Key: 1280 AFA4 DD14 589B.*
        - **Redacted:** *PGP Key: [PublicKey1].*

        Replace **any login credentials** (usernames and passwords) with **[UsernameN]** and **[PasswordN]**.

        - Example:
        - **Original:** *Username: admin, Password: pass123!*
        - **Redacted:** *Username: [Username1], Password: [Password1].*

        ### **7. Links & URLs**
        - Replace **personal document-sharing links** with **[Document Link]**.
        - Keep **institutional URLs** **(such as Seattle Community Network pages and PeeringDB links)** intact.

        - Example:
        - **Original:** *Google Doc: https://docs.google.com/document/d/xyz123.*
        - **Redacted:** *Google Doc: [Document Link].*

        - **Original:** *Seattle IX route servers: https://www.seattleix.net/route-servers.*
        - **Redacted:** *Seattle IX route servers: https://www.seattleix.net/route-servers.* (Kept because it is public knowledge)

        ### **8. Message Context Preservation**
        - **DO NOT** modify technical details, ticket metadata, or non-PII network-related content.
        - **DO NOT** over-redact information that is **public knowledge or operationally relevant**.

        ---

        ## **Handling Multi-User Interactions**
        When a ticket has **multiple users**, assign **unique placeholders per person** to maintain readability:

        - **Original:**
```
        Chris Caputo: Please fix this issue.
        Esther Jang: I have escalated this to IT.
        Chris Caputo: Thank you!
```
        - **Redacted:**
```
        [FirstName1] [LastName1]: Please fix this issue.
        [FirstName2] [LastName2]: I have escalated this to IT.
        [FirstName1] [LastName1]: Thank you!
```

        ---

        ALWAYS REMEMBER: never summarize a ticket. redact per instructions but never summarize or shorten excessively

You must output in JSON format with:
{
  "redacted_text": "the fully redacted text",
  "properties_redacted": {
     "lastname1": "original last name",
     "email1": "original email",
     "ip1": "original IP",
     ...
  }
}
Rules:
Use snake_case consistently for all keys, inside both "redacted_text" and "properties_redacted"
Do not include empty fields.
In "properties_redacted", include only properties that were actually found and redacted.
Do not add any text outside the JSON object.
"""


class RedactedText:
    def __init__(self, text: str, fields: dict[str,str]):
        self.text = text
        self.fields = fields


    @classmethod
    def from_json(cls, json_str: str):
        result = json.loads(json_str)
        return cls(text=result['redacted_text'], fields=result['properties_redacted'])


    def __str__(self):
        return self.text


    def unredact(self) -> str:
        # retacted text format: Some text [aValue] more text [anotherValue]
        # match all [], iterate over matches
        pattern = re.compile(r"\[(\w+)\]")

        restored_text = self.text

        # this is all about managing UpperCase vs lowercase keys
        for match in pattern.finditer(self.text):
            key = match.group(1)
            lookup_key = key
            if lookup_key not in self.fields:
                lookup_key = lookup_key.lower()
            if lookup_key not in self.fields:
                log.error(f"Expected field, {key}, not provided.")
                continue
            value = self.fields[lookup_key]
            restored_text = restored_text.replace('[' + key + ']', value)

        return restored_text


class Redactor:
    def __init__(self, path: str = default_model_file): # relative to current module
        log.info("Loading model from {path}")
        self.model, self.tokenizer = load(model_name, adapter_path=path)


    def redact_text(self, text: str) -> RedactedText:
        text = text.strip()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Redact all PII from this text and output in JSON format:\n\n{text}"}
        ]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        result = generate(self.model, self.tokenizer, prompt=prompt, max_tokens=1024)

        # Extract JSON only
        if '{' in result:
            json_start = result.find('{')
            json_end = result.rfind('}') + 1
            result = result[json_start:json_end]

        return RedactedText.from_json(result.strip())


    def redact_ticket(self, ticket: Ticket) -> Ticket:
        pass


def main():
    # Get input
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read().strip()

    redactor = Redactor()
    redacted = redactor.redact_text(text)
    print("Input:", text)
    print("Redacted:", redacted)
    print("Fields:", redacted.fields)
    print("Unredacted:", redacted.unredact())




# Run the IMAP sync process
if __name__ == '__main__':
    main()
