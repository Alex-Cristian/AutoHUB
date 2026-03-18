from twilio.rest import Client
from dotenv import load_dotenv
import os

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
from_number = os.getenv("TWILIO_PHONE_NUMBER")

print("SID:", account_sid)
print("TOKEN EXISTS:", bool(auth_token))
print("FROM:", from_number)

client = Client(account_sid, auth_token)

message = client.messages.create(
    body="Salut! Test AutoHub",
    from_=from_number,
    to="+40751347420"
)

print("SMS trimis:", message.sid)