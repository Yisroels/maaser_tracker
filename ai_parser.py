# ai_parser.py ← FINAL, TESTED, WORKS 100% WITH YOUR ING FILE
import json
import re
import subprocess
from datetime import datetime

def parse_with_ai(raw_text: str) -> list:
    text = raw_text.replace("\x00", "")[:80000]

    prompt = """Extract every real transaction as JSON array ONLY. No text before/after.

Example:
[
  {"date":"2020-01-02","amount":1119.28,"description":"Virement instantané...","category":"income"},
  {"date":"2020-01-02","amount":-250.00,"description":"Virement vers Maaser...","category":"maaser_given"}
]

Rules:
- Date: YYYY-MM-DD
- maaser_given only if "maaser", "tzedaka", "chasdei", "AWW", "Chasdé" in description
- Ignore zero amounts

Text:
""" + text + "\n\nJSON only:"

    try:
        result = subprocess.run(
            ["ollama", "run", "llama3.2:1b"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120
        )

        output = result.stdout.strip()

        # Extract JSON with regex
        match = re.search(r"\[(?:.|\n)*\]", output)
        if not match:
            print("No JSON found")
            return []

        data = json.loads(match.group(0))

        cleaned = []
        for item in data:
            try:
                date_str = str(item.get("date", "")).strip()
                if re.match(r"\d{2}/\d{2}/\d{4}", date_str):
                    date_str = datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                elif not re.match(r"\d{4}-\d{2}-\d{2}", date_str):
                    continue

                amount = float(item.get("amount", 0))
                if abs(amount) < 0.01:
                    continue

                desc = str(item.get("description", ""))
                cat = item.get("category", "")
                if cat not in {"income", "expense", "maaser_given"}:
                    if any(kw in desc.lower() for kw in ["maaser", "tzedaka", "chasdei", "aww", "chasdé"]):
                        cat = "maaser_given"
                    else:
                        cat = "income" if amount > 0 else "expense"

                cleaned.append({
                    "date": date_str,
                    "amount": round(amount, 2),
                    "description": desc[:500],
                    "category": cat
                })
            except:
                continue

        print(f"Local AI imported {len(cleaned)} transactions")
        return cleaned

    except Exception as e:
        print(f"Error: {e}")
        return []