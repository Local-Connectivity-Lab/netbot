import google.generativeai as genai
import dspy
import requests
import re
from datetime import datetime
import json
import re

import logging
from requests.exceptions import RequestException, ConnectionError, Timeout, HTTPError

# check signal for details
# genai.configure(api_key="TBDTBDTBD")

class PIIRedactionModule(dspy.Module):
    def __init__(self):
        super().__init__()

    def forward(self, text, pii_entities):
        pii_list = "\n".join([f"- {entity}: {label}" for entity, label in pii_entities.items()])

        prompt = f"""
        You are a **privacy compliance officer** responsible for redacting **personally identifiable information (PII)** from **Redmine support tickets** before they are shared on public platforms like Discord.

        Your primary goal is to **remove PII while preserving ticket clarity and structure** so that it remains **useful for troubleshooting and public discussion.**
        ALWAYS REMEMBER: never summarize a ticket. redact per instructions but never summarize or shorten excessively

        ---

        ## **Strict Redaction Rules:**
        Apply these redaction rules carefully:

        ### **1. Names** 
        Replace all personal names with placeholders **original firstname [LastNameN]**, where **N** is a unique number per name within the ticket.

        - Example:
        - **Original:** *Chris Caputo reported an issue with network latency.*
        - **Redacted:** *Chris [LastName1] reported an issue with network latency.*

        - Example (Multiple people):
        - **Original:** *Esther Jang contacted Alice about the issue.*
        - **Redacted:** *Esther [LastName1] contacted Alice about the issue.*

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

        ## **Example Redacted Ticket:**
        **Original Ticket (ID: 1591)**  
        **Subject:** *MacBook Air 2023 Laptop donation*  
        **Description:**  
        ```
        Hi Shannon,

        I saw your message on Meetup! Are you still down to donate your laptop?

        Thanks,  
        -Esther  
        1280 AFA4 DD14 589B <https://keybase.io/infrared>  
        Seattle Community Network <https://seattlecommunitynetwork.org/>  
        Join SCN on Discord <https://discord.gg/DYckq6hTy4>  
        Note: I have flexible working hours, so my emails may come at unusual times. Please do not feel obligated to respond outside of your usual hours. Thank you!!

        shannonhoffman007@gmail.com
        ```

        **Redacted Version:**  
        **Subject:** *[FirstName1] [LastName1] donating a MacBook Air 2023 Laptop*  
        **Description:**  
        ```
        Hi [FirstName2],

        I saw your message on [MeetupN]! Are you still willing to donate your laptop?

        Thanks,  
        -[FirstName1]  
        [PublicKey1] <[Keybase Link]>  
        Seattle Community Network <https://seattlecommunitynetwork.org/>  
        Join SCN on Discord <[Discord Link]>  
        Note: I have flexible working hours, so my emails may come at unusual times. Please do not feel obligated to respond outside of your usual hours. Thank you!!

        [Email1]

        ALWAYS REMEMBER: never summarize a ticket. redact per instructions but never summarize or shorten excessively
        ``` 

        Detected PII:
        {pii_list}
        
        Original text:
        {text}
        
        Return JSON output:
        {{
          "redacted_text": "Formatted, cleaned, and redacted output."
        }}
        """

        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = model.generate_content(prompt)

        if response and response.text:
            return dspy.Prediction(redacted_text=response.text)
        else:
            return dspy.Prediction(redacted_text=text)


class RedmineProcessor:
    def __init__(self, api_key: str, redmine_url: str):
        self.api_key = api_key
        self.redmine_url = redmine_url.rstrip("/")
        # self.base = redmine_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "netbot/0.0.1",
            "Content-Type": "application/json",
            "X-Redmine-API-Key": api_key,
        })

    def fetch_ticket_by_id(self, ticket_id: int):
        """Fetch a Redmine ticket by ID and flatten the JSON result."""
        url = f"{self.redmine_url}/issues/{ticket_id}.json?include=children,watchers"
        print(f"[DEBUG] Fetching ticket {ticket_id} from {url}")
        resp = self.session.get(url, timeout=10)
        print(f"[DEBUG] Response status: {resp.status_code}")
        if not resp.ok:
            logging.warning(f"Failed to fetch ticket #{ticket_id}: {resp.status_code}")
            return {}

        data = resp.json()
        issue = data.get("issue", {})
        print(f"[DEBUG] Keys in issue: {list(issue.keys())}")

        if "red_description" in issue:
            print(f"[DEBUG] red_description directly in issue: {issue['red_description'][:80]!r}")
        else:
            print("[DEBUG] red_description not found directly; checking custom_fields")

        flat_issue = {**issue}

        if "custom_fields" in issue:
            for cf in issue["custom_fields"]:
                if cf.get("name") == "red_description":
                    flat_issue["red_description"] = cf.get("value")
                    print(f"[DEBUG] Found red_description in custom_fields: {cf.get('value')[:80]!r}")
        return flat_issue

    def update_ticket(self, ticket_id: int, fields: dict) -> dict:
        """Update a ticket via Redmine REST API."""
        payload = {"issue": fields}
        r = self.session.put(
            f"{self.redmine_url}/issues/{ticket_id}.json",
            data=json.dumps(payload),
            timeout=10,
        )
        if r.status_code not in (200, 201, 204):
            r.raise_for_status()
        try:
            return (r.json() or {}).get("issue", {})
        except ValueError:
            return {}



    def clean_text(self, text):
        return re.sub(r"\s+", " ", text).strip()

    def redact_pii(self, text, pii_entities):
        redactor = PIIRedactionModule()
        result = redactor.forward(text, pii_entities)
        return self.clean_text(result.redacted_text)


    def process_ticket(self, ticket_id):
        try:
            ticket = self.fetch_ticket_by_id(ticket_id)
            if not ticket:
                log.error(f"Ticket #{ticket_id} not found.")
                self.logger.warning(f"Could not retrieve ticket {ticket_id}")
                return None

            title = self.clean_text(ticket.get("subject", ""))
            description = self.clean_text(ticket.get("description", ""))
            print(f"[DEBUG] Ticket fetched: id={ticket.get('id')} subject={ticket.get('subject')}")
            print(f"[DEBUG] red_description={ticket.get('red_description')}")
            if not ticket.get("red_description"):
                redacted_title = self.redact_pii(title, {})
                redacted_description = self.redact_pii(description, {})
                
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", redacted_description.strip(), flags=re.DOTALL)
                try:
                    payload = json.loads(cleaned)
                    redacted_description = payload.get("redacted_text", cleaned)
                except json.JSONDecodeError:
                    redacted_description = cleaned

                self.update_ticket(ticket_id, {"red_description": redacted_description})
                self.logger.info(f"Updating red_description for ticket #{ticket_id}: {redacted_description}")

                return {
                    "id": ticket["id"],
                    "redacted_subject": redacted_title,
                    "redacted_description": redacted_description,
                    "original_subject": title,
                    "original_description": description
                }
            else:
                return {
                    "id": ticket["id"],
                    "redacted_subject": ticket.get("redacted_subject", ""),
                    "redacted_description": ticket["red_description"],
                    "original_subject": title,
                    "original_description": description
                }

        except Exception as e:
            self.logger.error(f"Unexpected error processing ticket {ticket_id}: {e}")
            return None

if __name__ == "__main__":
    try:
        API_KEY = "8e9f6efeac50a11afc26d0c7bead709f0dfce25b"
        REDMINE_URL = "http://localhost:80"  # Updated IP

        processor = RedmineProcessor(API_KEY, REDMINE_URL)
        TICKET_ID = 11735
        final_ticket = processor.process_ticket(TICKET_ID)

        if final_ticket:
            print("\nFinal Processed Ticket:\n")
            print(f"ID: {final_ticket['id']}\n")

            print("\nRedacted Description:")
            json_str = final_ticket["redacted_description"]
            json_match = re.search(r'```json\s*({.*})\s*```', json_str, re.DOTALL)

            if json_match:
                try:
                    json_data = json.loads(json_match.group(1))
                    print(json_data["redacted_text"])
                except json.JSONDecodeError as e:
                    print(f"JSON Decode Error: {e}")
            else:
                print("No JSON found in the string")
        else:
            print(f"Failed to process ticket {TICKET_ID}")

    except Exception as e:
        print(f"Critical error in main execution: {e}")