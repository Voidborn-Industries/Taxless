from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class TaxProfileType(str, Enum):
    PERSONAL = "personal"
    BUSINESS = "business"


class ExpenseCategory(str, Enum):
    MEALS_ENTERTAINMENT = "MEALS_ENTERTAINMENT"
    TRAVEL = "TRAVEL"
    OFFICE_SUPPLIES = "OFFICE_SUPPLIES"
    VEHICLE = "VEHICLE"
    HOME_OFFICE = "HOME_OFFICE"
    PROFESSIONAL_DEVELOPMENT = "PROFESSIONAL_DEVELOPMENT"
    INSURANCE = "INSURANCE"
    UTILITIES = "UTILITIES"
    RENT = "RENT"
    EQUIPMENT = "EQUIPMENT"
    SOFTWARE = "SOFTWARE"
    MARKETING = "MARKETING"
    LEGAL = "LEGAL"
    OTHER = "OTHER"


class TaxEligibility(str, Enum):
    FULLY_DEDUCTIBLE = "FULLY_DEDUCTIBLE"
    PARTIALLY_DEDUCTIBLE = "PARTIALLY_DEDUCTIBLE"
    NOT_DEDUCTIBLE = "NOT_DEDUCTIBLE"
    PERSONAL = "PERSONAL"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class Currency(str, Enum):
    CAD = "CAD"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


# Base Models
class BaseEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('updated_at', pre=True, always=True)
    def set_updated_at(cls, v):
        return datetime.utcnow()


# User Models
class UserCreate(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class User(BaseEntity):
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    is_active: bool = True


# Tax Profile Models
class TaxProfileCreate(BaseModel):
    name: str = Field(..., description="Profile name (e.g., 'Personal', 'Company ABC')")
    profile_type: TaxProfileType
    default_currency: Currency = Currency.CAD
    tax_year: int = Field(..., ge=2020, le=2030)
    business_number: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None


class TaxProfileUpdate(BaseModel):
    name: Optional[str] = None
    profile_type: Optional[TaxProfileType] = None
    default_currency: Optional[Currency] = None
    business_number: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None


class TaxProfile(BaseEntity):
    user_id: str
    name: str
    profile_type: TaxProfileType
    default_currency: Currency
    tax_year: int
    business_number: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None


class TaxProfileResponse(BaseModel):
    id: str
    name: str
    profile_type: TaxProfileType
    default_currency: Currency
    tax_year: int
    business_number: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Location Models
class Location(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    source: str = Field(..., description="Source of location data: exif, ocr, ip, manual")


# Receipt Models
class ReceiptAnalysis(BaseModel):
    merchant_name: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[Currency] = None
    date: Optional[datetime] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
    tax_amount: Optional[float] = None
    subtotal: Optional[float] = None
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    raw_text: str = Field(..., description="Raw OCR text from receipt")


class Receipt(BaseEntity):
    user_id: str
    expense_id: Optional[str] = None
    file_key: str = Field(..., description="S3 key for the receipt image")
    file_size: int
    content_type: str
    analysis: Optional[ReceiptAnalysis] = None
    is_processed: bool = False
    processing_error: Optional[str] = None


# Expense Models
class ExpenseCreate(BaseModel):
    profile_id: str = Field(..., description="Tax profile ID")
    amount: float = Field(..., gt=0, description="Expense amount")
    currency: Currency = Currency.CAD
    description: str = Field(..., description="Expense description")
    category: ExpenseCategory
    date: datetime = Field(default_factory=datetime.utcnow)
    location: Optional[Location] = None
    tax_eligibility: TaxEligibility = TaxEligibility.REQUIRES_REVIEW
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    receipt_ids: List[str] = Field(default_factory=list)


class ExpenseUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    currency: Optional[Currency] = None
    description: Optional[str] = None
    category: Optional[ExpenseCategory] = None
    date: Optional[datetime] = None
    location: Optional[Location] = None
    tax_eligibility: Optional[TaxEligibility] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    receipt_ids: Optional[List[str]] = None


class Expense(BaseEntity):
    user_id: str
    profile_id: str
    amount: float
    currency: Currency
    description: str
    category: ExpenseCategory
    date: datetime
    location: Optional[Location] = None
    tax_eligibility: TaxEligibility
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    receipt_ids: List[str] = Field(default_factory=list)
    is_verified: bool = False
    llm_analysis: Optional[Dict[str, Any]] = None


class ExpenseResponse(BaseModel):
    id: str
    profile_id: str
    amount: float
    currency: Currency
    description: str
    category: ExpenseCategory
    date: datetime
    location: Optional[Location] = None
    tax_eligibility: TaxEligibility
    notes: Optional[str] = None
    tags: List[str]
    receipt_ids: List[str]
    is_verified: bool
    created_at: datetime
    updated_at: datetime


# Report Models
class ExpenseFilter(BaseModel):
    profile_ids: Optional[List[str]] = None
    categories: Optional[List[ExpenseCategory]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    tax_eligibility: Optional[List[TaxEligibility]] = None
    tags: Optional[List[str]] = None
    is_verified: Optional[bool] = None


class ExpenseSummary(BaseModel):
    total_expenses: int
    total_amount: float
    currency: Currency
    by_category: Dict[str, float]
    by_month: Dict[str, float]
    by_tax_eligibility: Dict[str, float]
    average_amount: float


class TaxReport(BaseModel):
    profile_id: str
    tax_year: int
    summary: ExpenseSummary
    expenses: List[ExpenseResponse]
    flagged_expenses: List[ExpenseResponse] = Field(default_factory=list)
    llm_analysis: Optional[Dict[str, Any]] = None


# API Response Models
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


# Authentication Models
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None 