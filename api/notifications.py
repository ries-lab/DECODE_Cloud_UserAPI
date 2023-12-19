import abc
import time
from fastapi import HTTPException


class EmailSender(abc.ABC):
    @abc.abstractmethod
    def send_email(self, to: str, subject: str, body: str):
        raise NotImplementedError()


class DummyEmailSender(EmailSender):
    def send_email(self, to: str, subject: str, body: str):
        pass


class MailjetEmailSender(EmailSender):
    def __init__(self, api_key, api_secret, sender_address):
        import mailjet_rest

        self.mailjet = mailjet_rest.Client(auth=(api_key, api_secret), version="v3.1")
        self.sender_address = sender_address

    def send_email(self, to: str, subject: str, body: str):
        data = {
            "Messages": [
                {
                    "From": {"Email": self.sender_address},
                    "To": [{"Email": to}],
                    "Subject": subject,
                    "HTMLPart": body,
                }
            ]
        }

        retries = 0
        while True:
            result = self.mailjet.send.create(data=data)
            if str(result.status_code).startswith("2"):
                break
            elif result.status_code == 429 and retries < 5:
                retries += 1
                time.sleep(30)
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to send email: {result.status_code} {result.text}",
                )
