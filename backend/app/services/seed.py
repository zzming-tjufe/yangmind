from sqlalchemy.orm import Session

from app.data.bfi44_seed import (
    BFI44_ITEMS,
    INSTRUMENT_CODE,
    INSTRUMENT_TITLE,
    INSTRUMENT_VERSION,
)
from app.data.cms_seed import DEFAULT_CONTENT_BLOCKS, DEFAULT_PAGES
from app.data.stag_hunt_seed import (
    ROUNDS_PER_SCENE,
    STAG_HUNT_CODE,
    STAG_HUNT_TITLE,
    STAG_SCENES,
)
from app.models.cms import ContentBlock, PageConfig
from app.models.game import Experiment, ExperimentScene
from app.models.survey import SurveyInstrument, SurveyItem
from app.models.user import User
from app.core.config import settings
from app.core.security import hash_password


def seed_bfi44_if_needed(db: Session) -> None:
    """若库里还没有 BFI-44，就写入题库。"""
    exists = db.query(SurveyInstrument).filter(SurveyInstrument.code == INSTRUMENT_CODE).first()
    if exists:
        return

    instrument = SurveyInstrument(
        code=INSTRUMENT_CODE,
        version=INSTRUMENT_VERSION,
        title=INSTRUMENT_TITLE,
        item_count=len(BFI44_ITEMS),
    )
    db.add(instrument)
    db.flush()

    for row in BFI44_ITEMS:
        db.add(
            SurveyItem(
                instrument_id=instrument.id,
                item_no=row["item_no"],
                stem=row["stem"],
                dimension=row["dimension"],
                reverse_scored=row["reverse_scored"],
                sort_order=row["item_no"],
            )
        )
    db.commit()


def seed_stag_hunt_if_needed(db: Session) -> None:
    """若库里还没有猎鹿博弈，就写入实验与场景。"""
    exists = db.query(Experiment).filter(Experiment.code == STAG_HUNT_CODE).first()
    if exists:
        return

    experiment = Experiment(
        code=STAG_HUNT_CODE,
        title=STAG_HUNT_TITLE,
        status="active",
        sort_order=1,
        rounds_per_scene=ROUNDS_PER_SCENE,
    )
    db.add(experiment)
    db.flush()

    for row in STAG_SCENES:
        db.add(
            ExperimentScene(
                experiment_id=experiment.id,
                scene_key=row["scene_key"],
                no=row["no"],
                title=row["title"],
                short_desc=row["short_desc"],
                option_a=row["option_a"],
                option_b=row["option_b"],
                option_a_text=row["option_a_text"],
                option_b_text=row["option_b_text"],
                required=row["required"],
                sort_order=row["sort_order"],
                enabled=True,
            )
        )
    db.commit()


def seed_cms_if_needed(db: Session) -> None:
    """写入默认页面配置与内容块（仅补缺失项，不覆盖已有编辑）。"""
    existing_pages = {p.page_key for p in db.query(PageConfig).all()}
    for row in DEFAULT_PAGES:
        if row["page_key"] in existing_pages:
            continue
        db.add(PageConfig(**row))

    existing_blocks = {b.block_key for b in db.query(ContentBlock).all()}
    for row in DEFAULT_CONTENT_BLOCKS:
        if row["block_key"] in existing_blocks:
            continue
        db.add(ContentBlock(**row))

    db.commit()


def seed_admin_if_needed(db: Session) -> None:
    """确保唯一总管账号；旧 role=admin 迁移为 super_admin；保留已有 sub_admin。"""
    from app.core.roles import ROLE_ADMIN_LEGACY, ROLE_SUPER

    email = settings.seed_admin_email.lower().strip()
    admin = db.query(User).filter(User.email == email).first()
    if admin is None:
        count = db.query(User).count()
        admin = User(
            public_id=f"U-{1001 + count}",
            email=email,
            password_hash=hash_password(settings.seed_admin_password),
            nickname=settings.seed_admin_nickname,
            role=ROLE_SUPER,
            status="active",
        )
        db.add(admin)
    else:
        admin.role = ROLE_SUPER
        admin.status = "active"
        admin.nickname = settings.seed_admin_nickname
        admin.password_hash = hash_password(settings.seed_admin_password)

    # 其它遗留 admin 升为总管角色名统一，避免出现第二个总管：降为 participant
    others = (
        db.query(User)
        .filter(User.role.in_([ROLE_ADMIN_LEGACY, ROLE_SUPER]), User.email != email)
        .all()
    )
    for u in others:
        # 明确是子管的不碰；仅清理误标的总管/旧 admin
        if u.role == ROLE_ADMIN_LEGACY or u.role == ROLE_SUPER:
            u.role = "participant"

    db.commit()


def seed_all(db: Session) -> None:
    seed_bfi44_if_needed(db)
    seed_stag_hunt_if_needed(db)
    seed_cms_if_needed(db)
    seed_admin_if_needed(db)
