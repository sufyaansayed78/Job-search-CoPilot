from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cryptography.fernet import Fernet
from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

fernet = Fernet(settings.FERNET_KEY.encode())

def build_gmail_service(cred):
    # 1. Decrypt the refresh token from the database
    refresh_token = fernet.decrypt(
        cred.refresh_token_enc.encode()
    ).decode()

    # 2. Create Google OAuth credentials
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )

    # 3. Exchange refresh token for a fresh access token
    credentials.refresh(Request())

    # 4. Build a Gmail API client
    service = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )

    return service





def fetch_job_emails(service, since):

    # Convert datetime into Unix timestamp (seconds)
    timestamp = int(since.timestamp())

    # Gmail search query
    query = f"after:{timestamp}"

    page_token = None

    while True:

        # 1. Ask Gmail for a batch of message IDs
        response = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=100,
            pageToken=page_token,
        ).execute()

        messages = response.get("messages", [])

        # 2. Retrieve the complete contents of each message
        for message in messages:

            email = service.users().messages().get(
                userId="me",
                id=message["id"],
                format="full",
            ).execute()

            yield email

        # 3. Check whether another page exists
        page_token = response.get("nextPageToken")

        if not page_token:
            break

import base64


def decode_body(data):
    if not data:
        return ""

    # Gmail returns URL-safe Base64
    padded_data = data + "=" * (-len(data) % 4)

    decoded = base64.urlsafe_b64decode(padded_data)

    return decoded.decode("utf-8", errors="replace")


def extract_email_body(payload):

    # Check whether this part contains the actual body
    body_data = payload.get("body", {}).get("data")

    if body_data:
        return decode_body(body_data)

    # Emails can contain multiple MIME parts
    for part in payload.get("parts", []):
        body = extract_email_body(part)

        if body:
            return body

    return ""


def classify_email(email):

    text = (
        email["subject"] + " " + email["snippet"] + " " + email["body"]
    ).lower()

    if any(word in text for word in [
        "interview invitation",
        "schedule an interview",
        "technical interview",
        "interview round",
    ]):
        return "interview"

    if any(word in text for word in [
        "unfortunately",
        "not moving forward",
        "regret to inform",
        "not selected",
    ]):
        return "rejection"

    if any(word in text for word in [
        "application received",
        "thank you for applying",
        "application confirmation",
    ]):
        return "application_confirmation"

    if any(word in text for word in [
        "offer letter",
        "pleased to offer",
        "employment offer",
    ]):
        return "job_offer"

    return "other"


def process_email(db, job, msg):

    # 1. Parse Gmail's response into a clean dictionary
    email = parse_email(msg)

    # 2. Classify the email
    classification = classify_email(email)

    # 3. Find which job application this email belongs to
    application = match_application(
        db=db,
        user_id=job.user_id,
        email=email,
    )

    # 4. If we found a matching application, update it
    if application:
        apply_email_update(
            db=db,
            application=application,
            email=email,
            classification=classification,
        )

    # 5. Return processing information
    return {
        "gmail_id": email["gmail_id"],
        "classification": classification,
        "matched": application is not None,
    }