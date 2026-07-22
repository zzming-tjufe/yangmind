from pydantic_settings import BaseSettings, SettingsConfigDict

# 开发默认值；生产环境（APP_ENV=production）禁止使用
DEFAULT_SECRET_KEY = "yangmind-dev-secret-change-me-before-production"


class Settings(BaseSettings):
    """应用配置。以后换 PostgreSQL 只改 database_url 即可。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "YangMind Lab API"
    # development | production
    app_env: str = "development"
    # 开发用密钥；生产必须通过环境变量 SECRET_KEY 覆盖为随机长串
    secret_key: str = DEFAULT_SECRET_KEY
    access_token_expire_minutes: int = 60 * 24  # 24 小时
    # SQLite 本地文件，或 Postgres：postgresql+psycopg://user:pass@host:5432/dbname
    # Render/Heroku 常给 postgres://，启动时会自动改成 postgresql+psycopg://
    database_url: str = "postgresql+psycopg://yangmind:yangmind@127.0.0.1:5432/yangmind"
    # 逗号分隔；公网部署时务必加上前端域名，例如 https://zzming-tjufe.github.io
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    # 唯一管理员：登录可用别名 admin；邮箱存库用完整地址
    seed_admin_email: str = "admin@yangmind.cn"
    seed_admin_password: str = "1234asdF"
    seed_admin_nickname: str = "管理员"
    seed_admin_login: str = "admin"

    # 调试账号 sudo（权限高于总管）。密码务必用环境变量 SUDO_PASSWORD，勿提交真实密码。
    enable_sudo: bool = False
    sudo_nickname: str = "sudo"
    sudo_email: str = "sudo@yangmind.local"
    sudo_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    def validate_security(self) -> None:
        """生产环境拒绝默认 / 过短密钥；开发环境仅告警。"""
        using_default = self.secret_key == DEFAULT_SECRET_KEY
        too_short = len(self.secret_key) < 32
        if self.is_production:
            if using_default or too_short:
                raise RuntimeError(
                    "生产环境必须设置足够长的 SECRET_KEY（至少 32 字符），"
                    "且不能使用默认开发密钥。请设置环境变量 SECRET_KEY 与 APP_ENV=production。"
                )
            if self.enable_sudo and not self.sudo_password.strip():
                raise RuntimeError(
                    "生产环境启用 ENABLE_SUDO 时必须设置 SUDO_PASSWORD。"
                )
        elif using_default:
            print(
                "[yangmind] 警告: 正在使用默认 SECRET_KEY。"
                "上线前请设置环境变量 SECRET_KEY，并将 APP_ENV=production。"
            )


settings = Settings()
