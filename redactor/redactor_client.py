#!/usr/bin/env python3
"""
HTTP client for calling the remote LLM redaction API
Used by threader on redmine2 to call llm server
"""

import logging
import requests
import time
from typing import Optional

log = logging.getLogger(__name__)

# API configuration
LLM_API_URL = "http://172.16.20.64:8000"
MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds

class RedactedText:
    """Same interface as local redactor"""
    def __init__(self, text: str, fields: dict):
        self.text = text
        self.fields = fields
    
    def __str__(self):
        return self.text
    
    def unredact(self) -> str:
        """Restore original PII"""
        import re
        pattern = re.compile(r"\[(\w+)\]")
        restored_text = self.text
        
        for match in pattern.finditer(self.text):
            placeholder_with_brackets = match.group(0)  # [LastName1]
            key = match.group(1)  # LastName1
            
            if key not in self.fields:
                log.error(f"Expected field, {key}, not provided.")
                continue
            
            value = self.fields[key]
            restored_text = restored_text.replace(placeholder_with_brackets, value)
        
        return restored_text


class RedactorClient:
    """HTTP client for remote redaction API"""
    
    def __init__(self, api_url: str = LLM_API_URL):
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Test connection
        try:
            response = self.session.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                log.info(f"Connected to LLM API at {self.api_url}")
            else:
                log.warning(f"LLM API health check failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to LLM API at {self.api_url}: {e}")
            raise RuntimeError(f"LLM API unavailable: {e}")
    
    def redact_text(self, text: str) -> RedactedText:
        """
        Redact PII from text using remote API
        
        Args:
            text: Original text to redact
            
        Returns:
            RedactedText object with redacted text and PII mapping
            
        Raises:
            RuntimeError: If API call fails after retries
        """
        if not text or not text.strip():
            return RedactedText("", {})
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info(f"Calling LLM API (attempt {attempt}/{MAX_RETRIES})...")
                
                response = self.session.post(
                    f"{self.api_url}/redact",
                    json={"text": text},
                    timeout=1800  # 30 minutes (was 1200)
                )
                
                if response.status_code == 200:
                    data = response.json()
                    log.info(f"Redaction complete ({data['processing_time']:.1f}s)")
                    
                    return RedactedText(
                        text=data["redacted_text"],
                        fields=data["properties_redacted"]
                    )
                
                elif response.status_code == 503:
                    # Server busy, retry
                    log.warning(f"LLM API busy, retrying in {RETRY_DELAY}s...")
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY)
                        continue
                    else:
                        raise RuntimeError("LLM API busy after max retries")
                
                else:
                    raise RuntimeError(f"API returned status {response.status_code}: {response.text}")
            
            except requests.exceptions.Timeout:
                log.error(f"API timeout on attempt {attempt}")
                if attempt < MAX_RETRIES:
                    log.info(f"Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    raise RuntimeError("API timeout after max retries")
            
            except requests.exceptions.RequestException as e:
                log.error(f"API request failed: {e}")
                if attempt < MAX_RETRIES:
                    log.info(f"Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    raise RuntimeError(f"API request failed after max retries: {e}")
        
        raise RuntimeError("Redaction failed after all retries")


# For compatibility with existing code
class Redactor(RedactorClient):
    """Alias for backward compatibility"""
    pass


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    
    client = RedactorClient()
    
    test_text = "Contact John Smith at john.smith@example.com or call 555-123-4567"
    result = client.redact_text(test_text)
    
    print(f"Original: {test_text}")
    print(f"Redacted: {result.text}")
    print(f"Fields: {result.fields}")
    print(f"Unredacted: {result.unredact()}")
