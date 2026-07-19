from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.games import router as games_router
from app.api.leaderboard import router as leaderboard_router
from app.api.survey import router as survey_router
from app.core.database import Base, SessionLocal, engine
from app.models import User  # noqa: F401
from app.models import admin_extra as _admin_extra_models  # noqa: F401
from app.models import cms as _cms_models  # noqa: F401
from app.models import game as _game_models  # noqa: F401
from app.models import match as _match_models  # noqa: F401
from app.models import survey as _survey_models  # noqa: F401
from app.api.pvp import router as pvp_router
from app.api.site import router as site_router
from app.core.config import settings
from app.services.seed import seed_all

app = FastAPI(
    title="YangMind Lab API",
    description="人格与合作博弈实验平台 · 后端",
    version="0.1.0",
)

# 允许前端跨域访问 API（本地 + 公网域名，见 CORS_ORIGINS）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """启动时校验密钥、建表、修补旧库，并写入题库 / 实验种子数据。"""
    settings.validate_security()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.services.db_fixes import (
            cleanup_duplicate_survey_responses,
            ensure_rbac_schema,
            ensure_survey_response_unique_index,
        )

        ensure_rbac_schema(engine)
        cleanup_duplicate_survey_responses(db)
        ensure_survey_response_unique_index(engine)
        seed_all(db)
    finally:
        db.close()


app.include_router(auth_router)
app.include_router(survey_router)
app.include_router(games_router)
app.include_router(pvp_router)
app.include_router(leaderboard_router)
app.include_router(site_router)
app.include_router(admin_router)


@app.get("/health")
def health():
    return {"ok": True, "service": "yangmind-api", "version": "0.1.0"}


@app.get("/")
def root():
    return {
        "message": "YangMind Lab API is running",
        "docs": "/docs",
        "health": "/health",
        "auth": {
            "register": "POST /api/v1/auth/register",
            "login": "POST /api/v1/auth/login",
            "me": "GET /api/v1/auth/me",
        },
        "surveys": {
            "bfi44": "GET /api/v1/surveys/bfi-44",
            "submit": "POST /api/v1/surveys/bfi-44/submit",
        },
        "games": {
            "scenes": "GET /api/v1/experiments/stag-hunt/scenes",
            "play": "POST /api/v1/sessions/{id}/rounds",
        },
        "leaderboard": "GET /api/v1/leaderboard",
        "admin": {
            "stats": "GET /api/v1/admin/stats/overview",
            "users": "GET /api/v1/admin/users",
            "personality": "GET /api/v1/admin/users/{id}/personality",
        },
    }
