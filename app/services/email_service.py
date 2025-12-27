import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, body: str):
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            server = smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT)
            server.starttls()
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            text = msg.as_string()
            server.sendmail(settings.MAIL_FROM, to_email, text)
            server.quit()
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False

    @staticmethod
    def send_verification_email(to_email: str, token: str):
        # Fix: Ensure link points to the correct API endpoint
        link = f"http://localhost:8000/api/v1/auth/verify-email?token={token}"
        subject = "Verify your Class-Kit Account"
        body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                    <h2 style="color: #4285f4;">Welcome to Class-Kit!</h2>
                    <p>Thank you for signing up. Please verify your email address to activate your account.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{link}" style="background-color: #4285f4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold;">Verify Email</a>
                    </div>
                    <p>Or click this link: <a href="{link}">{link}</a></p>
                    <p style="font-size: 0.8em; color: #777;">This link will expire in 24 hours.</p>
                </div>
            </body>
        </html>
        """
        return EmailService.send_email(to_email, subject, body)
