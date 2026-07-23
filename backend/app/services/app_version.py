"""站点展示版本号（登录页等），与代码包版本无关。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.cms import ContentBlock

APP_VERSION_BLOCK_KEY = "lab.app_version"
DEFAULT_APP_DISPLAY_VERSION = "v0.4.1"


def normalize_app_version(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return DEFAULT_APP_DISPLAY_VERSION
    if not text.lower().startswith("v"):
        text = f"v{text}"
    return text[:32]


def ensure_app_version_block(db: Session) -> ContentBlock:
    row = (
        db.query(ContentBlock)
        .filter(ContentBlock.block_key == APP_VERSION_BLOCK_KEY)
        .first()
    )
    if row is None:
        row = ContentBlock(
            block_key=APP_VERSION_BLOCK_KEY,
            title="平台显示版本号",
            body=DEFAULT_APP_DISPLAY_VERSION,
            locale="zh-CN",
            version=1,
        )
        db.add(row)
        db.flush()
    elif not (row.body or "").strip():
        row.body = DEFAULT_APP_DISPLAY_VERSION
        db.flush()
    return row


def get_app_display_version(db: Session) -> str:
    row = ensure_app_version_block(db)
    return normalize_app_version(row.body or DEFAULT_APP_DISPLAY_VERSION)


def set_app_display_version(db: Session, version: str) -> str:
    row = ensure_app_version_block(db)
    value = normalize_app_version(version)
    row.body = value
    row.title = row.title or "平台显示版本号"
    row.version = (row.version or 1) + 1
    db.flush()
    return value
