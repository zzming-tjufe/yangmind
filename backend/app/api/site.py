from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.cms import ContentBlock, PageConfig
from app.models.user import User

router = APIRouter(prefix="/api/v1/site", tags=["site"])


class PageOut(BaseModel):
    page_key: str
    title: str
    subtitle: str
    status: str
    sort_order: int


class ContentOut(BaseModel):
    block_key: str
    title: str
    body: str
    version: int


@router.get("/pages", response_model=list[PageOut])
def list_visible_pages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """参与端导航用：仅返回已发布页面。管理员可看全部（含草稿）。"""
    q = db.query(PageConfig).order_by(PageConfig.sort_order, PageConfig.id)
    rows = q.all()
    if current_user.role != "admin":
        rows = [r for r in rows if r.status == "published"]
    return [
        PageOut(
            page_key=r.page_key,
            title=r.title,
            subtitle=r.subtitle,
            status=r.status,
            sort_order=r.sort_order,
        )
        for r in rows
    ]


@router.get("/content", response_model=list[ContentOut])
def list_content(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = db.query(ContentBlock).order_by(ContentBlock.block_key).all()
    return [
        ContentOut(block_key=r.block_key, title=r.title, body=r.body, version=r.version)
        for r in rows
    ]
