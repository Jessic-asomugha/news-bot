# ─────────────────────────────────────────────
# agent/waitlist_checker.py
# Manages the news waitlist — saving, loading,
# checking for matches, and sending notifications
# ─────────────────────────────────────────────

import json
import os
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# PATHS & SETTINGS
# ─────────────────────────────────────────────
WAITLIST_FILE   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "waitlist.json")
CHECK_INTERVAL_HOURS = 2
MATCH_THRESHOLD = 0.35

# Gmail SMTP settings
GMAIL_SENDER   = os.getenv("GMAIL_SENDER")    # Your Gmail address
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")  # Gmail App Password (not your login password)


# ─────────────────────────────────────────────
# WAITLIST STORAGE
# ─────────────────────────────────────────────
def load_waitlist() -> list:
    """Load all waitlist items from disk."""
    if not os.path.exists(WAITLIST_FILE):
        return []
    try:
        with open(WAITLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_waitlist(items: list):
    """Save all waitlist items to disk."""
    try:
        with open(WAITLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[WAITLIST] Could not save waitlist: {e}")


def add_to_waitlist(description: str, notify_email: str) -> dict:
    """
    Adds a new item to the waitlist.
    Returns the created item dict.
    """
    items = load_waitlist()

    # Check for duplicates
    for item in items:
        if item["description"].lower() == description.lower():
            return {"success": False, "reason": "This description is already on your waitlist."}

    new_item = {
        "id":           int(time.time()),         # Unix timestamp as unique ID
        "description":  description.strip(),
        "notify_email": notify_email.strip(),
        "added_at":     datetime.now().isoformat(),
        "last_checked": None,
        "status":       "pending",                # pending | matched
        "matches":      [],                       # filled when match is found
    }

    items.append(new_item)
    save_waitlist(items)

    return {"success": True, "item": new_item}


def remove_from_waitlist(item_id: int):
    """Remove a waitlist item by ID."""
    items = load_waitlist()
    items = [i for i in items if i["id"] != item_id]
    save_waitlist(items)


def get_pending_items() -> list:
    """Return all items that haven't been matched yet."""
    return [i for i in load_waitlist() if i["status"] == "pending"]


def get_matched_items() -> list:
    """Return all items that have been matched."""
    return [i for i in load_waitlist() if i["status"] == "matched"]


def is_due_for_check(item: dict) -> bool:
    """
    Returns True if the item hasn't been checked recently
    and is due for another check based on CHECK_INTERVAL_HOURS.
    """
    if item["last_checked"] is None:
        return True
    last = datetime.fromisoformat(item["last_checked"])
    due  = last + timedelta(hours=CHECK_INTERVAL_HOURS)
    return datetime.now() >= due


# ─────────────────────────────────────────────
# EMAIL NOTIFICATION
# ─────────────────────────────────────────────
def send_match_email(to_email: str, description: str, matches: list) -> bool:
    """
    Sends a Gmail notification when a waitlist match is found.
    Uses Gmail App Password — must be set in .env file.

    To get a Gmail App Password:
    1. Go to myaccount.google.com/security
    2. Enable 2-Step Verification
    3. Go to App Passwords and generate one for PULSE
    4. Add it to your .env as GMAIL_APP_PASSWORD
    """
    if not GMAIL_SENDER or not GMAIL_PASSWORD:
        print("[EMAIL] Gmail credentials not set in .env — skipping email notification.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"⚡ PULSE — Match found: {description[:50]}"
        msg["From"]    = GMAIL_SENDER
        msg["To"]      = to_email

        # Build match list for email body
        match_lines = ""
        for article, score in matches[:3]:  # Top 3 matches only
            confidence = int(score * 100)
            match_lines += f"""
            <div style="margin-bottom:16px; padding:14px; background:#0D1626;
                        border-left:3px solid #00DCFF; border-radius:4px;">
                <div style="font-size:13px; color:#aaa; margin-bottom:4px;">
                    {article.get('source','Unknown')} &nbsp;·&nbsp;
                    {article.get('published','')} &nbsp;·&nbsp;
                    <span style="color:#00DCFF;">{confidence}% match</span>
                </div>
                <div style="font-size:15px; font-weight:600; color:#fff; margin-bottom:8px;">
                    {article.get('title','No title')}
                </div>
                <a href="{article.get('link','#')}"
                   style="font-size:13px; color:#00DCFF; text-decoration:none;">
                    Read article →
                </a>
            </div>
            """

        html = f"""
        <html>
        <body style="background:#080E1A; color:#E8EDF5; font-family:Arial,sans-serif;
                     padding:32px; max-width:600px; margin:auto;">
            <div style="font-size:11px; letter-spacing:2px; color:#00DCFF;
                        text-transform:uppercase; margin-bottom:8px;">
                ⚡ PULSE News Intelligence
            </div>
            <h1 style="font-size:24px; color:#fff; margin:0 0 8px;">
                Match found
            </h1>
            <p style="color:#7A8BA8; font-size:14px; margin:0 0 24px;">
                A news story matching your waitlist description has been detected.
            </p>
            <div style="background:#0D1626; border:1px solid rgba(0,220,255,0.15);
                        border-radius:8px; padding:16px; margin-bottom:24px;">
                <div style="font-size:11px; color:#3D5068; text-transform:uppercase;
                             letter-spacing:1px; margin-bottom:4px;">Your description</div>
                <div style="font-size:15px; color:#E8EDF5;">"{description}"</div>
            </div>
            <div style="font-size:11px; color:#3D5068; text-transform:uppercase;
                         letter-spacing:1px; margin-bottom:12px;">Top matches</div>
            {match_lines}
            <p style="color:#2A3A50; font-size:12px; margin-top:32px; text-align:center;">
                Sent by PULSE · Open the app to manage your waitlist
            </p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_SENDER, to_email, msg.as_string())

        print(f"[EMAIL] Notification sent to {to_email}")
        return True

    except Exception as e:
        print(f"[EMAIL] Failed to send notification: {e}")
        return False


# ─────────────────────────────────────────────
# MAIN CHECKER
# Called every time the app opens
# ─────────────────────────────────────────────
def run_waitlist_check():
    """
    Checks all pending waitlist items that are due.
    Called on app startup — runs silently in the background.
    Returns a list of newly matched items for in-app notification.
    """
    # Import here to avoid circular imports
    from sources.feeds import get_all_articles
    from agent.nlp_utils import find_best_matches, extract_keywords

    pending = get_pending_items()
    if not pending:
        return []

    newly_matched = []
    all_items     = load_waitlist()

    for item in pending:
        if not is_due_for_check(item):
            continue

        print(f"[WAITLIST] Checking: '{item['description']}'")

        # Extract keywords to use as the search query
        keywords  = extract_keywords(item["description"])
        query     = " ".join(kw for kw, _ in keywords[:3])  # Top 3 keywords as query

        # Fetch articles for this description
        try:
            articles = get_all_articles(topic=query)
        except Exception as e:
            print(f"[WAITLIST] Fetch failed for '{item['description']}': {e}")
            continue

        # Score matches
        matches = find_best_matches(
            description=item["description"],
            articles=articles,
            threshold=MATCH_THRESHOLD,
        )

        # Update last_checked timestamp
        for i, stored in enumerate(all_items):
            if stored["id"] == item["id"]:
                all_items[i]["last_checked"] = datetime.now().isoformat()

                if matches:
                    # Mark as matched and store top results
                    all_items[i]["status"]     = "matched"
                    all_items[i]["matched_at"] = datetime.now().isoformat()
                    all_items[i]["matches"]    = [
                        {
                            "title":     article.get("title", ""),
                            "source":    article.get("source", ""),
                            "published": article.get("published", ""),
                            "link":      article.get("link", ""),
                            "score":     score,
                        }
                        for article, score in matches[:3]
                    ]

                    newly_matched.append(all_items[i])

                    # Send email notification
                    if item.get("notify_email"):
                        send_match_email(
                            to_email=item["notify_email"],
                            description=item["description"],
                            matches=matches,
                        )

                    print(f"[WAITLIST] Match found for: '{item['description']}'")
                else:
                    print(f"[WAITLIST] No match yet for: '{item['description']}'")
                break

    save_waitlist(all_items)
    return newly_matched