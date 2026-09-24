import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, User
from app.schemas import CompanyCreate, CompanyOut
from app.auth import get_current_user

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=list[CompanyOut])
def list_companies(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return db.query(Company).filter(Company.user_id == current_user.id).order_by(Company.name).all()


@router.post("/", response_model=CompanyOut, status_code=201)
def create_company(
    payload: CompanyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    company = Company(**payload.model_dump(), user_id=current_user.id)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _get_owned_company(company_id: uuid.UUID, current_user: User, db: Session) -> Company:
    company = db.query(Company).filter(
        Company.id == company_id, Company.user_id == current_user.id
    ).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return _get_owned_company(company_id, current_user, db)


@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    company = _get_owned_company(company_id, current_user, db)
    db.delete(company)
    db.commit()
