from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from room_booking.core.dependencies import CurrentUser, SessionDep
from room_booking.users import service
from room_booking.users.models import User
from room_booking.users.schemas import Token, UserCreate, UserRead

router = APIRouter(tags=["Users"])


@router.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: SessionDep) -> User:
    return service.register(session, payload)


@router.post("/auth/token", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep) -> Token:
    """Use your email address as the OAuth2 username."""
    return Token(access_token=service.authenticate(session, form.username, form.password))


@router.get("/users/me", response_model=UserRead)
def get_profile(user: CurrentUser) -> User:
    return user
