"""
streamlit_app.py
Social Media Agent — Using OpenRouter (gpt-oss-20b free model)

Features:
- Streamlit UI
- Collect email + content interests
- Uses OpenRouter API to generate Social Media Plan
- Emails the generated plan daily at 07:00 IST
- Manual test run + scheduler log
"""

import streamlit as st
import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
import threading
from openai import OpenAI

# -------------------------------------------------------
# Load secrets: Streamlit Secrets → .env → default
# -------------------------------------------------------
load_dotenv()

def get_secret(key: str, default=None):
    """Load variable from Streamlit secrets → .env → default."""
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key, default)

# OpenRouter + SMTP credentials
OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY")
SMTP_SERVER = get_secret("SMTP_SERVER")
SMTP_PORT = int(get_secret("SMTP_PORT", 587))
SMTP_USERNAME = get_secret("SMTP_USERNAME")
SMTP_PASSWORD = get_secret("SMTP_PASSWORD")
SENDER_EMAIL = get_secret("SENDER_EMAIL")

if not OPENROUTER_API_KEY:
    st.error("Missing OPENROUTER_API_KEY. Add it to Streamlit Secrets.")
    st.stop()

# File paths
CONFIG_FILE = "sma_config.json"
LOG_FILE = "sma_last_run.json"

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# -------------------------------------------------------
# Content interest list
# -------------------------------------------------------
CONTENT_INTERESTS = [
    "Tech & Gadgets", "AI / ML", "Startup", "Entrepreneurship", "Marketing",
    "Digital Marketing", "Social Media Tips", "Productivity", "Career Advice",
    "Interview Tips", "Finance & Personal Finance", "Investing", "Cryptocurrency",
    "Health & Wellness", "Fitness", "Yoga", "Meditation", "Nutrition",
    "Food & Recipes", "Travel", "Photography", "Education", "Exam Tips",
    "Coding & Tutorials", "Programming (Python)", "Web Development",
    "Android Development", "Cloud Computing", "Cybersecurity",
    "Design & UX", "Art & Illustration", "Music", "Movies & TV",
    "Books & Reading", "Science & Space", "Environment & Sustainability",
    "Sports", "Fashion", "Beauty", "Parenting", "Lifestyle",
    "Business News", "E-commerce", "Real Estate", "Automotive",
    "Gaming", "Memes / Humor", "Motivation / Self-help"
]

# -------------------------------------------------------
# Scheduler setup
# -------------------------------------------------------
scheduler = BackgroundScheduler()
scheduler_lock = threading.Lock()


def save_config(email, interests):
    data = {"email": email, "interests": interests}
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None


# -------------------------------------------------------
# Prompt builder
# -------------------------------------------------------
def build_prompt(interests):
    interest_text = ", ".join(interests)

    return f"""
You are a social media strategist. Create a JSON response only.

Inputs:
- Content Interests: {interest_text}

Output JSON must include:
- "instagram": {{"content_ideas":[], "daily_captions":{{}}, "weekly_plan":[]}}
- "facebook": same structure
- "linkedin": same structure

Requirements:
- 6 content idea titles
- 7 daily captions (Mon–Sun)
- 7-day weekly plan (day, post_type, idea, cta)
- Keep JSON valid. No explanations outside JSON.
"""


# -------------------------------------------------------
# OpenRouter Call
# -------------------------------------------------------
def generate_content(interests):
    try:
        prompt = build_prompt(interests)

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b:free",
            messages=[{"role": "user", "content": prompt}]
        )

        output = response.choices[0].message.content

        # Remove ``` if model adds them
        if output.startswith("```"):
            output = "\n".join(output.split("\n")[1:-1])

        # Try parsing JSON normally
        try:
            return json.loads(output)
        except:
            # Fallback: extract JSON with regex
            import re
            match = re.search(r"\{(.|\n)*\}", output)
            if match:
                return json.loads(match.group(0))
            raise Exception("Model did not return valid JSON.")

    except Exception as e:
        raise Exception(f"OpenRouter Error: {str(e)}")


# -------------------------------------------------------
# Email sender
# -------------------------------------------------------
def send_email(recipient, subject, html_content):
    msg = MIMEMultipart("alternative")
    msg["To"] = recipient
    msg["From"] = SENDER_EMAIL
    msg["Subject"] = subject

    msg.attach(MIMEText("View this email in HTML.", "plain"))
    msg.attach(MIMEText(html_content, "html"))

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    server.sendmail(SENDER_EMAIL, recipient, msg.as_string())
    server.quit()


# -------------------------------------------------------
# HTML formatter
# -------------------------------------------------------
def format_html(content, interests):
    now = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M")

    html = f"""
    <h2>Daily Social Media Plan</h2>
    <p><b>Interests:</b> {", ".join(interests)}</p>
    <p><b>Generated at:</b> {now} IST</p>
    <hr>
    """

    for platform in ["instagram", "facebook", "linkedin"]:
        if platform not in content:
            continue

        p = content[platform]

        html += f"<h3>{platform.capitalize()}</h3>"

        # Content Ideas
        html += "<b>Content Ideas:</b><ul>"
        for idea in p.get("content_ideas", []):
            html += f"<li>{idea}</li>"
        html += "</ul>"

        # Daily Captions
        html += "<b>Daily Captions:</b><ul>"
        for day, caption in p.get("daily_captions", {}).items():
            html += f"<li><b>{day.capitalize()}:</b> {caption}</li>"
        html += "</ul>"

        # Weekly Plan
        html += "<b>Weekly Plan:</b><ol>"
        for d in p.get("weekly_plan", []):
            html += f"<li><b>{d['day']}:</b> ({d['post_type']}) {d['idea']} — CTA: {d['cta']}</li>"
        html += "</ol>"

    return html


# -------------------------------------------------------
# Job execution
# -------------------------------------------------------
def job_run(email, interests):
    run_log = {
        "email": email,
        "interests": interests,
        "started_at": datetime.now().isoformat()
    }

    try:
        content = generate_content(interests)
        html = format_html(content, interests)
        subject = f"Daily Social Media Plan — {', '.join(interests)}"
        send_email(email, subject, html)

        run_log["status"] = "success"

    except Exception as e:
        run_log["status"] = "error"
        run_log["error"] = str(e)

    finally:
        run_log["ended_at"] = datetime.now().isoformat()
        with open(LOG_FILE, "w") as f:
            json.dump(run_log, f, indent=2)


# -------------------------------------------------------
# Scheduler
# -------------------------------------------------------
def start_scheduler(config):
    with scheduler_lock:
        scheduler.remove_all_jobs()

        scheduler.add_job(
            job_run,
            CronTrigger(hour=7, minute=0, timezone=pytz.timezone("Asia/Kolkata")),
            args=[config["email"], config["interests"]],
            id="daily_job"
        )

        if not scheduler.running:
            scheduler.start()


# -------------------------------------------------------
# STREAMLIT UI
# -------------------------------------------------------
st.set_page_config(page_title="Social Media Agent", layout="centered")
st.title("💬 Social Media Agent (OpenRouter Version)")
st.write("Automatically generate and email daily social media plans using **gpt-oss-20b free model**.")

config = load_config()

email = st.text_input("Email to send daily content:", value=config["email"] if config else "")
interests = st.multiselect("Select content interests:", CONTENT_INTERESTS,
                           default=config["interests"] if config else [])

if st.button("Save & Schedule Daily Emails"):
    if not email or not interests:
        st.error("Email and interests are required.")
    else:
        cfg = save_config(email, interests)
        start_scheduler(cfg)
        st.success("Settings saved. Scheduler activated for 07:00 AM IST.")

if st.button("Run Now (Send Content Immediately)"):
    if not email or not interests:
        st.error("Fill details first.")
    else:
        st.info("Generating... please wait...")
        job_run(email, interests)
        st.success("Email sent successfully!")

if os.path.exists(LOG_FILE):
    st.subheader("📄 Last Run Log")
    with open(LOG_FILE) as f:
        st.code(f.read(), language="json")