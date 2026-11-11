from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, Dict
from core.auth import authenticate_user, create_access_token, decode_access_token
from core.config import USERS_DB

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

def get_current_user_dependency(authorization: Optional[str] = Header(None)) -> Dict:
    """Dependency for protected endpoints."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autorização ausente")
    
    parts = authorization.split(" ")
    token = parts[1] if len(parts) == 2 else parts[0]
    user_payload = decode_access_token(token)
    if not user_payload:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    return user_payload

@router.post("/login")
def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas. Verifique seu usuário e senha.")
    
    token = create_access_token(user)
    return {
        "success": True,
        "token": token,
        "user": user
    }

@router.get("/me")
def get_me(user: Dict = Depends(get_current_user_dependency)):
    return {
        "authenticated": True,
        "user": user
    }

@router.get("/demo-accounts")
def get_demo_accounts():
    """Returns available demo credentials to make testing instantaneous."""
    demo_list = []
    for username, data in USERS_DB.items():
        # Clean default sample password
        pwd = "admin123" if "admin" in username else ("gestor123" if "gestor" in username else "analista123")
        demo_list.append({
            "username": username,
            "password": pwd,
            "name": data["name"],
            "role": data["role"],
            "role_title": data["role_title"],
            "avatar": data["avatar"]
        })
    return demo_list
