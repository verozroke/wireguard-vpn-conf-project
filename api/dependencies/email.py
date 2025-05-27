import os
import smtplib

def send_email(to_email: str, subject: str, body: str):
    email_address = os.getenv("EMAIL_HOST_ADDRESS")
    email_password = os.getenv("EMAIL_HOST_PASSWORD")

    if not email_address or not email_password:
        raise ValueError("Email credentials are not set in environment variables.")

    message = f"Subject: {subject}\n\n{body}"

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(email_address, email_password)
        smtp.sendmail(email_address, to_email, message)
