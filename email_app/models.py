from django.db import models
import smtplib
import imaplib
import email as python_email
import time
from datetime import datetime
from cryptography.fernet import Fernet
import base64
import logging
import traceback
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from email.utils import parseaddr


# temporar key for test
ENCRYPT_KEY = b'HLEPa2zpsEr0JvKaDbGypeB2iIqQzFIPdE7RUdLJOIQ='

class Contact(models.Model):
    name = models.CharField(max_length=500, null=True,blank=True)
    email = models.EmailField()

class EmailAccount(models.Model):
    email = models.EmailField()
    password = models.CharField(max_length=500)
    smtp_server = models.CharField(max_length=256)
    smtp_port = models.IntegerField()
    imap_server = models.CharField(max_length=256)
    imap_port = models.IntegerField()

    def save(self, *args, **kwargs):
        # Hash the password before saving
        self.password = self.encrypt(self.password)
        super().save(*args, **kwargs)

    def read_emails(self):
        # Connect to the IMAP server
        mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        mail.login(self.email, self.decrypt(self.password))

        # Select the inbox folder
        mail.select("inbox")

        # Keep checking for new messages in a loop
        while True:
            print(datetime.now())
            # Search for new messages that haven't been read yet
            status, messages = mail.search(None, "UNSEEN")

            # Iterate through the messages
            for num in messages[0].split():
                # Fetch the message data
                status, msg_data = mail.fetch(num, "(RFC822)")

                # Parse the message into an email object
                msg = python_email.message_from_bytes(msg_data[0][1])

                # Get the email address
                if msg["From"]:
                    email = msg["From"]
                else:
                    email = "unknown"

                # Print the subject and sender of the message
                print("Subject:", msg["Subject"])
                print("From:", email)
                print("To:", msg["To"])
                print("-" * 30)

                # Get the email content
                content = msg.get_payload(decode=True)

                # Print the email content
                print("Content:")
                print(content)
                print("-" * 30)

            # Wait for 10 seconds before checking for new messages again
            time.sleep(1)

        # Close the mailbox and logout
        mail.close()
        mail.logout()

    def send_email(self, to, subject, body):
        # Connect to the SMTP server
        smtp_server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        smtp_server.ehlo()
        smtp_server.starttls()
        smtp_server.login(self.email, self.decrypt(self.password))

        # Create the email message
        message = email.message.Message()
        message["To"] = to
        message["From"] = self.email
        message["Subject"] = subject
        message.set_payload(body)

        # Send the email message
        smtp_server.sendmail(self.email, to, message.as_string())

        # Close the SMTP connection
        smtp_server.quit()
    def encrypt(self, pas):
        cipher_pass = Fernet(ENCRYPT_KEY)
        encod_pass = cipher_pass.encrypt(pas.encode())
        return base64.urlsafe_b64encode(encod_pass).decode("ascii")

    def decrypt(self, pas):
        try:
            pas = base64.urlsafe_b64decode(pas.encode())
            cipher_pass = Fernet(ENCRYPT_KEY)
            decod_pass = cipher_pass.decrypt(pas).decode("ascii")
            return decod_pass
        except Exception as e:
            logging.getLogger("error_logger").error(traceback.format_exc())
            return None

    def get_password(self):
        return self.decrypt(self.password)

    def set_password(self, raw_password):
        self.password = self.encrypt(raw_password)

    def delete(self, *args, **kwargs):
        # Delete the encrypted password file when deleting the email account
        encrypted_password_file_path = os.path.join(settings.ENCRYPTED_PASSWORDS_DIR, f"{self.id}.txt")
        if os.path.exists(encrypted_password_file_path):
            os.remove(encrypted_password_file_path)
        super().delete(*args, **kwargs)

    def save_contacts(self):
        # Connect to the IMAP server
        mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        mail.login(self.email, self.decrypt(self.password))

        # Select the INBOX folder
        mail.select("INBOX")

        # Search for all messages in the INBOX folder
        status, messages = mail.search(None, "ALL")

        # Iterate through the messages
        for num in messages[0].split():
            try:
                # Fetch the message data
                status, msg_data = mail.fetch(num, "(RFC822)")

                # Parse the message into an email object
                msg = python_email.message_from_bytes(msg_data[0][1])

                # Get the email address
                email = parseaddr(msg["From"])[1]

                # Validate the email address
                if email:
                    try:
                        validate_email(email)
                    except ValidationError:
                        email = None

                # Get the contact name
                name = None
                if msg["From"]:
                    name = parseaddr(msg["From"])[0]

                # Save the contact to the database
                if email != None:
                    try:
                        Contact.objects.create(name=name, email=email)
                    except IntegrityError:
                        pass
            except Exception:
                # Log the error and continue to the next message
                logging.getLogger("error_logger").error(traceback.format_exc())

        # Close the mailbox and logout
        mail.close()
        mail.logout()

    class Meta:
        abstract = False
