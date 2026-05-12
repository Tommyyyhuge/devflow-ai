from fastapi import APIRouter

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/")
def list_users():
    return {"users": []}
