"""Session-based auth helpers for page/API protection."""

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

_SESSION_USER_ID_KEY = "user_id"


def get_session_user_id(request: Request) -> int | None:
    """Return logged-in user id from session, or None."""
    value = request.session.get(_SESSION_USER_ID_KEY)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_session_user_id(request: Request, user_id: int) -> None:
    request.session[_SESSION_USER_ID_KEY] = int(user_id)


def clear_session_user_id(request: Request) -> None:
    request.session.pop(_SESSION_USER_ID_KEY, None)


def require_page_user(request: Request) -> int | RedirectResponse:
    """Return user id for pages, or a redirect response when unauthenticated."""
    user_id = get_session_user_id(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    return user_id


def require_api_user_id(request: Request) -> int:
    """Return user id for API routes, raising 401 when unauthenticated."""
    user_id = get_session_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id
