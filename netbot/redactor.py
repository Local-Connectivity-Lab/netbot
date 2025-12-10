"""Simple PII redactor"""

import json
import logging
import sys
from mlx_lm import load, generate
from redmine.model import Ticket


log = logging.getLogger(__name__)

REDACTOR_MODEL = "mlx-community/Llama-3.2-1B-Instruct-4bit"

REDACTOR_PROMPT = """You are a privacy compliance officer. Redact PII and output JSON:
{
  "redacted_text": "text with [LastNameN], [EmailN], [PhoneN], [AddressN], [IPN] placeholders",
  "properties_redacted": {"lastname1": "original", "email1": "original", ...}
}"""

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
        restored_text = self.text
        # FIXME: Replace tags in text with values from fields-map
        return restored_text


class Redactor:
    def __init__(self, path: str = "finetuning/adapters/pii-redactor"): # relative to current module
        log.info("Loading model from {path}")
        self.model, self.tokenizer = load(REDACTOR_MODEL, adapter_path=path)


    def redact_text(self, text: str) -> RedactedText:
        text = text.strip()
        messages = [
            {"role": "system", "content": REDACTOR_PROMPT},
            {"role": "user", "content": f"Redact all PII from this text and output in JSON format:\n\n{text}"}
        ]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        result = generate(self.model, self.tokenizer, prompt=prompt, max_tokens=512)
        # Cleanup result str
        if result.startswith("Outstanding JSON output:"):
            result = result[24:]
        result = result.strip()
        log.error(f"result: '{result}'")

        return RedactedText.from_json(result.strip())


    def redact_ticket(self, ticket: Ticket) -> Ticket:
        pass


def main():
    redactor = Redactor()
    redacted = redactor.redact_text("Paul is trying out the redactor.")
    print(redacted)


# Run the IMAP sync process
if __name__ == '__main__':
    main()
