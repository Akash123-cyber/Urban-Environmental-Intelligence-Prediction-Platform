import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://urban:urban_dev_password@postgres:5432/urban")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "")
    S3_RAW_BUCKET: str = os.getenv("S3_RAW_BUCKET", "urban-raw")
    S3_PROCESSED_BUCKET: str = os.getenv("S3_PROCESSED_BUCKET", "urban-processed")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
