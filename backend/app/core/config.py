from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。以后换 PostgreSQL 只改 database_url 即可。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "YangMind Lab API"
    # 开发用密钥；上线前必须改成随机长字符串，并放进环境变量
    secret_key: str = "yangmind-dev-secret-change-me-before-production"
    access_token_expire_minutes: int = 60 * 24  # 24 小时
    # SQLite：数据存在 backend/yangmind.db 文件里
    database_url: str = "sqlite:///./yangmind.db"


settings = Settings()
