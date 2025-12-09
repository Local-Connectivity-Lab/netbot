# PII Redactor - Setup & Usage

## Installation

# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/pii-redactor.git
cd pii-redactor

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install mlx mlx-lm

## Usage

# Basic usage
./redact.py "Contact John Doe at john@example.com or call 555-123-4567"

# From stdin
echo "Server at 192.168.1.100" | ./redact.py

# From file
cat ticket.txt | ./redact.py

## Expected Output

Input:
"Contact John Doe at john@example.com or call 555-123-4567"

Output:
{
  "redacted_text": "Contact John [LastName1] at [Email2] or call [Phone3]",
  "properties_redacted": {
    "lastname1": "Doe",
    "email2": "john@example.com",
    "phone3": "555-123-4567"
  }
}

## Requirements

- Mac with Apple Silicon (M1/M2/M3/M4)
- Python 3.9+
- 8GB+ RAM

## First Run

- Downloads base model (~700MB) - takes 2-3 minutes
- Subsequent runs are instant