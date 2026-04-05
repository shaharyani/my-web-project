import smtplib
import threading
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailManager:
    def __init__(self):
        # אתחול ללא ערכים קבועים
        pass

    def send_custom_email(self, server_config, recipient_email, subject, body_html):
        """
        server_config: דיקשיונרי המכיל host, port, user, password
        """
        try:
            msg = MIMEMultipart()
            msg['From'] = server_config['user']
            msg['To'] = recipient_email
            msg['Subject'] = subject

            # עיצוב בסיסי לעברית
            html_content = f"""
            <div dir="rtl" style="font-family: 'Segoe UI', sans-serif; text-align: right;">
                {body_html}
            </div>
            """
            msg.attach(MIMEText(html_content, 'html'))

            # התחברות לשרת Outlook/Office365
            server = smtplib.SMTP(server_config['host'], server_config['port'], timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(server_config['user'], server_config['password'])
            server.send_message(msg)
            server.quit()

            logging.info(f"Email sent from {server_config['user']} to {recipient_email}")
            return True
        except Exception as e:
            logging.error(f"SMTP Error (Sender: {server_config.get('user')}): {e}")
            return False

    def send_async(self, server_config, recipient_email, subject, body_html):
        """שליחה ברקע מבלי לעצור את ה-Route"""
        thread = threading.Thread(
            target=self.send_custom_email,
            args=(server_config, recipient_email, subject, body_html)
        )
        thread.start()