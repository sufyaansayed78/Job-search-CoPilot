from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cryptography.fernet import Fernet
from app.config import settings
from app.models import Application, Company, JobPosting
from app.services_imp.LLM import get_llm
from app.services_imp.pydantic_op_models import EmailClassification, UpdateApplicationFromEmail, AddJobPostingFromEmail
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

import re

def normalize_company_name(name: str) -> str:

    name = name.lower()
    # Remove common legal suffixes
    name = re.sub(
        r"\b(inc|incorporated|ltd|limited|llc|plc|corp|corporation)\b",
        "",
        name
    )
    # Remove punctuation and extra whitespace
    name = re.sub(r"[^a-z0-9\s]", "", name)

    name = re.sub(r"\s+", " ", name).strip()

    return name

def update_application_from_email(db,user_id ,email,classification):
    llm = get_llm()

    
    #comp_name = normalize_company_name(email['from'])
    if classification.job_category == "job_application":   
        applications =  db.query(Application).filter(Application.user_id == user_id).all()
        company_map = {app.id : (app.job_posting.role,app.job_posting.company.name) for app in applications}
        llm = llm.with_structured_output(UpdateApplicationFromEmail)
        update_data = llm.invoke(
            f"""
            Extract the following information about a current job application from the email and by using company_map which maps application IDs to their corresponding company names and roles. :
            - status: The new status of the application, if applicable
            - follow_up_date: The follow-up date and time mentioned in the email, in ISO 8601 format. Return null if not mentioned.
            - Notes: Any additional notes or information extracted from the email that may be relevant to the application. Return null if not applicable.
            - application ID: The UUID of the matching job application. Use the company_map to find the correct application id based on the company name and role extracted from the email. Return null if not applicable.
            Here is the email content:
            Subject: {email['subject']}
            Body: {email['body']}
            Here is the company map: {company_map}
            """)
        
        application = db.query(Application).filter(Application.id == update_data.application_id).first()
        application.status = update_data.status
        application.follow_up_date = update_data.follow_up_date
        application.notes = update_data.notes
        db.commit()
        db.refresh(application)
    else :
        # If the email is related to a job posting, we can extract the company name and role from the email
        job_postings = db.query(JobPosting).filter(JobPosting.user_id == user_id).all()
        company_names = [posting.company.name for posting in job_postings]
        llm = llm.with_structured_output(UpdateApplicationFromEmail)
        update_data = llm.invoke(
            f"""
            Extract the following information about a job posting from the email and by using company_names which is a list of company names already present in the user's job postings database :
            - company_name: The company name extracted from the email of the job posting
            - role: The role or position extracted from the email
            - title: The title of the job posting extracted from the email
            - url: The URL of the job posting extracted from the email
            - raw_description: The raw description of the job posting extracted from the email
            Here is the list of company names: {company_names}
            Here is the email content:
            Subject: {email['subject']}
            Body: {email['body']}
            """)
        company = db.query(Company).filter(Company.user_id == user_id, Company.name == update_data.company_name).first()
        if not company:
            company = Company(user_id=user_id, name=update_data.company_name)
            db.add(company)
            db.commit()
            db.refresh(company)
        db.add(JobPosting(
            user_id=user_id,
            company_id=company.id,
            title=update_data.title,
            url=update_data.url,
            raw_description=update_data.raw_description,
            role=update_data.role,
            source="email",
            analysis_status="not_started"

        ))
        db.commit()


    

def classify_email(email):

    llm = get_llm()
    llm = llm.with_structured_output(EmailClassification)
    result = llm.invoke(
        f"""
        Determine whether the email is related to a job posting
        or a job application.
        Subject: {email['subject']}
        Body: {email['body']}
        Return job_category as:
        - True if related to a job posting or application.
        - False otherwise.
        """
    )

    return result

def parse_email(msg):
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    email = {
        "gmail_id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "body": extract_email_body(msg.get("payload", {})),
    }

    return email


def process_email(db, job, msg):

    # 1. Parse Gmail's response into a clean dictionary
    email = parse_email(msg)

    # 2. Classify the email
    classification = classify_email(email)
    if not classification.email_category:
        return 
    update_application_from_email(db, job.user_id, email, classification)
    # 5. Return processing information
    