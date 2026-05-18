"""
Authentication routes - Login, Register, and user management
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
import traceback
from backend.database import SessionLocal
from backend.models import User
from backend.security import hash_password, verify_password, is_hashed_password
from backend.session_auth import clear_session_user_id, set_session_user_id

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register")
def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    """Register a new user."""
    db = SessionLocal()
    try:
        username = (username or "").strip()
        email = (email or "").strip().lower()
        password = password or ""

        if not username or not email or len(password) < 6:
            return {"error": "Username, email, and a 6+ char password are required"}

        if db.query(User).filter(User.username == username).first():
            return {"error": "Username already exists"}

        if db.query(User).filter(User.email == email).first():
            return {"error": "Email already exists"}

        user = User(username=username, email=email, password=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        set_session_user_id(request, user.id)

        return RedirectResponse("/site", status_code=303)

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

    finally:
        db.close()


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Authenticate user login."""
    db = SessionLocal()
    try:
        email = (email or "").strip().lower()
        password = password or ""
        user = db.query(User).filter(User.email == email).first()

        if not user or not verify_password(password, user.password):
            return {"error": "Invalid credentials"}

        # Upgrade old plain-text passwords after a successful login.
        if user.password and not is_hashed_password(user.password):
            user.password = hash_password(password)
            db.commit()

        set_session_user_id(request, user.id)

        return RedirectResponse("/site", status_code=303)

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

    finally:
        db.close()


@router.get("/logout")
def logout(request: Request):
    """Clear login session and redirect to login page."""
    clear_session_user_id(request)
    return RedirectResponse("/login", status_code=303)
