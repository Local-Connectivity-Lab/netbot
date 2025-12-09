"""Simple PII redactor"""
import sys
from mlx_lm import load, generate

print("Loading model...", file=sys.stderr)
model, tokenizer = load(
    "mlx-community/Llama-3.2-1B-Instruct-4bit",
    adapter_path="adapters/pii-redactor"
)

if len(sys.argv) > 1:
    text = " ".join(sys.argv[1:])
else:
    text = sys.stdin.read().strip()

system_prompt = """You are a privacy compliance officer. Redact PII and output JSON:
{
  "redacted_text": "text with [LastNameN], [EmailN], [PhoneN], [AddressN], [IPN] placeholders",
  "properties_redacted": {"lastname1": "original", "email1": "original", ...}
}"""

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": f"Redact all PII from this text and output in JSON format:\n\n{text}"}
]

prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

result = generate(model, tokenizer, prompt=prompt, max_tokens=512)

print(result)
