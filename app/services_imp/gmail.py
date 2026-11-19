
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from cryptography.fernet import Fernet
from app.config import settings
from app.database import SessionLocal
from app.models import Application, Company, JobPosting, SyncJob
from app.services_imp.LLM import get_llm
from app.services_imp.pydantic_op_models import EmailClassification, UpdateApplicationFromEmail, AddJobPostingFromEmail
import uuid
from bs4 import BeautifulSoup
import re
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

fernet = Fernet(settings.FERNET_KEY.encode())


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def build_gmail_service(cred):

    try:
        refresh_token = fernet.decrypt(
            cred.refresh_token_enc.encode()
        ).decode()
        print("1. Refresh token decrypted successfully")

    except Exception as e:
        print("Decryption failed:", repr(e))
        raise

    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=SCOPES,
        )
        print("2. Credentials object created successfully")

    except Exception as e:
        print("Credentials construction failed:", repr(e))
        raise

    try:
        credentials.refresh(Request())
        print("3. Access token refreshed successfully")

    except Exception as e:
        print("Token refresh failed:", repr(e))
        raise

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
        logging.info(f"Email classified as job application. Extracting application update info for user {user_id}") 
        applications =  db.query(Application).filter(Application.user_id == user_id).all()
        company_map = {app.id : (app.job_posting.role,app.job_posting.company.name,app.job_posting_id) for app in applications}
        
        try :
            llm = llm.with_structured_output(UpdateApplicationFromEmail,method='json_schema',include_raw=False)
            update_data = llm.invoke(
                f"""
                Extract the  information about a current job application from the email ,company_map( which maps application IDs to their corresponding company names ,roles and job_posting_ids) and also the list of companies which the user has applied. :
               Here is the email info :
                Subject: {email['subject']}
                Body: {email['body']}
                Here is the company map: {company_map}
                """)
            update_data = UpdateApplicationFromEmail(**update_data)
            if update_data.application_id  == "<UNKNOWN>":
               return 
            logging.info(f"Recieved this data from job application : {update_data}")
        except Exception as e:
            print("Exception:", repr(e))
            print("Error body:", getattr(e, "body", None))
            raise
        application = db.query(Application).filter(Application.id == update_data.application_id).first()
        application.status = update_data.status
        application.follow_up_date = update_data.follow_up_date
        application.notes = update_data.notes
        db.commit()
        db.refresh(application)
    else :
        logging.info(f"Email classified as job posting. Extracting job posting info for user {user_id}")
        # If the email is related to a job posting, we can extract the company name and role from the email
        try : 
            job_postings = db.query(JobPosting).filter(JobPosting.user_id == user_id).all()
            company_names = [posting.company.name for posting in job_postings]
            llm = llm.with_structured_output(AddJobPostingFromEmail,method='json_schema',include_raw=False)
            update_data = llm.invoke(
                f"""
                Extract all the information about a job posting from the email and by using company_names which is a list of company names already present in the user's job postings database .
                Here is the list of company names: {company_names}
                Here is the email content:
                Subject: {email['subject']}
                Body: {email['body']}
                """)
            logging.info(f"Recieved this data from job posting  LLm{update_data}")
            update_data = AddJobPostingFromEmail(**update_data)
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
        except Exception as e:
            print("Exception:", repr(e))
            print("Error body:", getattr(e, "body", None))
            raise


import traceback
 

def classify_email(email:dict)-> EmailClassification:
    logging.info(f"Classifying email: {email['subject']} from {email['from']}")
    llm = get_llm()
    llm2 = llm.with_structured_output(schema=EmailClassification,method='json_schema',include_raw=False)

    try :
        logging.info(f"hello Using LLM: {llm}")
        logging.info(f"Invoking LLM for classification with email subject: {email['subject']}")
        result = llm2.invoke(
            f"""
            Determine whether the email is related to a job posting
            or a job application. Note : An email is related to a job posting or job application only if it has a company name and a role.
            Here is the contents of email : 
            Subject: {email['subject']}
            Body: {email['body']}
            Return job_category as:
            - True if related to a job posting or application.
            - False otherwise.
            """
        )
    except Exception as e:
        logging.info(f"Error during email classification: {repr(e)}")
        logging.info(f"Error body: {e}")
        traceback.print_exc()
        print("Error body:", getattr(e, "body", None))
        raise
    logging.info(f"Classification result: {result}")
    logging.info(f"Classification type : {type(result)}")
    return EmailClassification.model_validate(result)



def extract_email_body_2(html_content):

    soup = BeautifulSoup(html_content, "html.parser")

    # Remove unnecessary HTML elements
    for element in soup(["style", "script", "head", "meta", "title"]):
        element.decompose()

    # Extract readable text
    text = soup.get_text(separator="\n")

    # Remove excessive whitespace and blank lines
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)

    return text.strip()
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
        "body": extract_email_body_2(extract_email_body(msg.get("payload", {}))),
    }
    
    return email


def process_email(db, job, msg):
    
    # 1. Parse Gmail's response into a clean dictionary
    email = parse_email(msg)
    logging.info(f"Processing email: {email['subject']} from {email['from']}")
    
    # 2. Classify the email

    classification = classify_email(email)
    logging.info(f"CLASSIFICATION OBJECT TYPE : {type(classification)}")
    if not classification.email_category:
        return 
    update_application_from_email(db, job.user_id, email, classification)
    # 5. Return processing information
    

def mark_job_failed(job_id : uuid.UUID, error_message):
    logging.error("in mark_job_failed: job_id=%s, error_message=%s", job_id, error_message)
    db = SessionLocal()
    job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
    job.status = "failed"
    job.error = error_message
    db.commit()