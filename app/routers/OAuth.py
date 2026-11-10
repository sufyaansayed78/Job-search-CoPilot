from google_auth_oauthlib.flow import Flow
from app.config import settings
from app.auth import get_current_user
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from itsdangerous import URLSafeSerializer
from app.models import GmailCredential
from cryptography.fernet import Fernet
from app.services_imp.gmail import fernet

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

router = APIRouter(prefix="/oauth", tags=["oauth"])

def sign_state(user_id: str) -> str:
    """Sign the state parameter to prevent CSRF attacks."""
    serializer = URLSafeSerializer(settings.SECRET_KEY)
    return serializer.dumps(user_id)

def verify_state(state: str) -> str:
    "Verify the state parameter to prevent CSRF attacks."
    serializer = URLSafeSerializer(settings.SECRET_KEY)
    return serializer.loads(state)

def make_flow():
    return Flow.from_client_secrets_file(
        "client_secret.json", scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )

@router.get("/gmail/connect")
def connect(user=Depends(get_current_user)):
    flow = make_flow()
    url, state = flow.authorization_url(
        access_type="offline", prompt="consent", state=sign_state(user.id)
    )
    return RedirectResponse(url)

@router.get("/gmail/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    user_id = verify_state(state)  # protects against CSRF
    flow = make_flow()
    flow.fetch_token(code=code)
    cred = db.get(GmailCredential, user_id) or GmailCredential(user_id=user_id)
    cred.refresh_token_enc = fernet.encrypt(flow.credentials.refresh_token.encode()).decode()
    db.add(cred); db.commit()
    return RedirectResponse("/applications?gmail=connected")