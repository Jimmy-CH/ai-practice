"""创建管理员用户。可重复运行（用户名已存在则跳过）。"""
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, sync_engine
from app.users.models import User, Role
from app.auth.service import hash_password
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_EMAIL = "admin@example.com"


def create_admin():
    with Session(sync_engine) as session:
        # 查找 admin 角色
        result = session.execute(select(Role).where(Role.name == "admin"))
        admin_role = result.scalar_one_or_none()
        if admin_role is None:
            logger.error("admin 角色不存在，请先运行 seed_data.py")
            return

        # 检查是否已有管理员
        result = session.execute(select(User).where(User.username == ADMIN_USERNAME))
        existing = result.scalar_one_or_none()
        if existing:
            # 升级为 admin
            if existing.role_id != admin_role.id:
                existing.role_id = admin_role.id
                session.commit()
                logger.info(f"用户 {ADMIN_USERNAME} 已升级为 admin")
            else:
                logger.info(f"用户 {ADMIN_USERNAME} 已经是 admin")
            return

        # 创建管理员
        user = User(
            username=ADMIN_USERNAME,
            hashed_password=hash_password(ADMIN_PASSWORD),
            email=ADMIN_EMAIL,
            role_id=admin_role.id,
        )
        session.add(user)
        session.commit()
        logger.info(f"管理员已创建: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")


if __name__ == "__main__":
    create_admin()
