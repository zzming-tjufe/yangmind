from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.roles import is_super_admin
from app.models.cms import Announcement, ContentBlock, PageConfig
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


class AnnouncementOut(BaseModel):
    id: int
    kind: str
    title: str
    body: str
    pinned: bool
    published_at: datetime | None = None
    updated_at: datetime | None = None


@router.get("/pages", response_model=list[PageOut])
def list_visible_pages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """参与端导航用：仅返回已发布页面。管理员可看全部（含草稿）。"""
    q = db.query(PageConfig).order_by(PageConfig.sort_order, PageConfig.id)
    rows = q.all()
    if not is_super_admin(current_user):
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


@router.get("/announcements", response_model=list[AnnouncementOut])
def list_announcements(
    kind: str | None = Query(default=None, description="notice | changelog"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """参与端公告栏：仅已发布条目。"""
    q = db.query(Announcement).filter(Announcement.status == "published")
    if kind in ("notice", "changelog"):
        q = q.filter(Announcement.kind == kind)
    rows = q.order_by(
        Announcement.pinned.desc(),
        Announcement.published_at.desc().nullslast(),
        Announcement.id.desc(),
    ).all()
    return [
        AnnouncementOut(
            id=r.id,
            kind=r.kind,
            title=r.title,
            body=r.body,
            pinned=r.pinned,
            published_at=r.published_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
