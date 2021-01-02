from email.mime.text import MIMEText
from subprocess import Popen, PIPE


def send_notification(mail_from, mail_to, subject, msg):
    msg = MIMEText(msg)
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = subject

    p = Popen(["/usr/bin/sendmail", "-t", "-oi"], stdin=PIPE)
    p.communicate(msg.as_bytes())