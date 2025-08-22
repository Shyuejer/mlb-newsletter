#emailer.py
import os
import smtplib
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader, select_autoescape

def render_template(template_name: str, **ctx) -> str:
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html", "xml"])
    )
    tpl = env.get_template(template_name)
    return tpl.render(**ctx)

def send_email(subject: str, html: str, recipients: list[str]):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, pwd)
        s.sendmail(user, recipients, msg.as_string())
