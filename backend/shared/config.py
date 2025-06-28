import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AWS Configuration
    aws_region: str = "us-east-1"
    dynamodb_table: str = "taxless-expenses"
    s3_bucket: str = "taxless-receipts"
    
    # Cognito Configuration
    cognito_user_pool_id: Optional[str] = None
    cognito_client_id: Optional[str] = None
    
    # AI Services - Google Gemini
    google_api_key: Optional[str] = None
    
    # Security
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Application Settings
    default_currency: str = "CAD"
    max_file_size_mb: int = 10
    supported_image_types: list = ["image/jpeg", "image/png", "image/heic"]
    
    # LLM Settings
    llm_model: str = "gemini-2.0-flash-exp"  # Google Gemini 2.0 Flash
    max_tokens: int = 2000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

# DynamoDB Key Patterns
class DynamoKeys:
    USER_PREFIX = "USER#"
    PROFILE_PREFIX = "PROFILE#"
    EXPENSE_PREFIX = "EXPENSE#"
    RECEIPT_PREFIX = "RECEIPT#"
    
    @staticmethod
    def user_key(user_id: str) -> str:
        return f"{DynamoKeys.USER_PREFIX}{user_id}"
    
    @staticmethod
    def profile_key(user_id: str, profile_id: str) -> str:
        return f"{DynamoKeys.PROFILE_PREFIX}{user_id}#{profile_id}"
    
    @staticmethod
    def expense_key(user_id: str, expense_id: str) -> str:
        return f"{DynamoKeys.EXPENSE_PREFIX}{user_id}#{expense_id}"
    
    @staticmethod
    def receipt_key(user_id: str, receipt_id: str) -> str:
        return f"{DynamoKeys.RECEIPT_PREFIX}{user_id}#{receipt_id}"
    
    @staticmethod
    def user_profiles_sk(user_id: str) -> str:
        return f"PROFILES#{user_id}"
    
    @staticmethod
    def user_expenses_sk(user_id: str) -> str:
        return f"EXPENSES#{user_id}"
    
    @staticmethod
    def expense_by_date_sk(date: str) -> str:
        return f"DATE#{date}"


# Expense Categories for tax purposes
EXPENSE_CATEGORIES = {
    "MEALS_ENTERTAINMENT": "Meals and Entertainment",
    "TRAVEL": "Travel Expenses",
    "OFFICE_SUPPLIES": "Office Supplies",
    "VEHICLE": "Vehicle Expenses",
    "HOME_OFFICE": "Home Office",
    "PROFESSIONAL_DEVELOPMENT": "Professional Development",
    "INSURANCE": "Insurance",
    "UTILITIES": "Utilities",
    "RENT": "Rent",
    "EQUIPMENT": "Equipment",
    "SOFTWARE": "Software and Subscriptions",
    "MARKETING": "Marketing and Advertising",
    "LEGAL": "Legal and Professional Services",
    "OTHER": "Other"
}

# Tax eligibility flags
TAX_ELIGIBILITY_FLAGS = {
    "FULLY_DEDUCTIBLE": "Fully deductible",
    "PARTIALLY_DEDUCTIBLE": "Partially deductible (50%)",
    "NOT_DEDUCTIBLE": "Not deductible",
    "PERSONAL": "Personal expense",
    "REQUIRES_REVIEW": "Requires review"
} 