import abc
import time

import mailjet_rest  # type: ignore
from fastapi import HTTPException
from requests import Response


class EmailSender(abc.ABC):
    """Abstract email sender for user notifications."""

    @abc.abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError()


class DummyEmailSender(EmailSender):
    """Dummy email sender for testing and when notifications are not required."""

    def send_email(self, to: str, subject: str, body: str) -> None:
        pass


class MailjetEmailSender(EmailSender):
    """Email sender using Mailjet."""

    def __init__(self, api_key: str, secret_key: str, sender_address: str):
        self.mailjet = mailjet_rest.Client(auth=(api_key, secret_key), version="v3.1")
        self.sender_address = sender_address

    def send_email(self, to: str, subject: str, body: str) -> None:
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
            result: Response = self.mailjet.send.create(data=data)
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
