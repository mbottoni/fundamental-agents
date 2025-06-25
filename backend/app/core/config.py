from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    FINANCIAL_MODELING_PREP_API_KEY: str
    NEWS_API_KEY: str
    DATABASE_URL: str
    SECRET_KEY: str = "a_very_secret_key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str
    FRONTEND_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

settings = Settings()
