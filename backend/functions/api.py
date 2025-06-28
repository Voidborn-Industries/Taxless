import json
import os
import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from datetime import datetime, timedelta

# Import shared modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config import settings
from shared.models import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    TaxProfileCreate, TaxProfileUpdate, TaxProfileResponse,
    ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseFilter,
    ExpenseSummary, TaxReport, APIResponse, PaginatedResponse
)
from shared.database import db, DynamoKeys
from shared.auth import auth_service
from shared.ai_services import rekognition_service, llm_service, location_service

# Create FastAPI app
app = FastAPI(
    title="Taxless API",
    description="AI-powered expense tracking for tax purposes",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get current user from token
async def get_current_user(authorization: str = Query(..., description="Bearer token")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.split(" ")[1]
    token_data = auth_service.verify_token(token)
    
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return token_data


# Authentication endpoints
@app.post("/auth/register", response_model=APIResponse)
async def register_user(user_data: UserCreate):
    """Register a new user"""
    try:
        # Create user in Cognito
        user_id = auth_service.create_user_cognito(user_data)
        if not user_id:
            raise HTTPException(status_code=400, detail="Failed to create user")
        
        # Create user record in DynamoDB
        user_record = {
            'id': user_id,
            'email': user_data.email,
            'first_name': user_data.first_name,
            'last_name': user_data.last_name,
            'phone': user_data.phone,
            'is_active': True
        }
        
        db.create_item(
            pk=DynamoKeys.user_key(user_id),
            sk=DynamoKeys.user_key(user_id),
            item_data=user_record
        )
        
        return APIResponse(
            success=True,
            message="User registered successfully",
            data={"user_id": user_id}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/login", response_model=APIResponse)
async def login_user(login_data: UserLogin):
    """Login user and return tokens"""
    try:
        # Authenticate with Cognito
        auth_result = auth_service.authenticate_user_cognito(login_data.email, login_data.password)
        if not auth_result:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Get user info
        user_info = auth_service.get_user_cognito(login_data.email)
        if not user_info:
            raise HTTPException(status_code=404, detail="User not found")
        
        return APIResponse(
            success=True,
            message="Login successful",
            data={
                "access_token": auth_result['access_token'],
                "refresh_token": auth_result['refresh_token'],
                "expires_in": auth_result['expires_in'],
                "user": user_info
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/refresh", response_model=APIResponse)
async def refresh_token(refresh_token: str = Form(...)):
    """Refresh access token"""
    try:
        result = auth_service.refresh_token_cognito(refresh_token)
        if not result:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        return APIResponse(
            success=True,
            message="Token refreshed successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Tax Profile endpoints
@app.get("/profiles", response_model=APIResponse)
async def get_tax_profiles(current_user = Depends(get_current_user)):
    """Get all tax profiles for the current user"""
    try:
        result = db.query_items(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk_prefix="PROFILE#"
        )
        
        profiles = []
        for item in result['items']:
            profiles.append(TaxProfileResponse(**item))
        
        return APIResponse(
            success=True,
            message="Tax profiles retrieved successfully",
            data=profiles
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/profiles", response_model=APIResponse)
async def create_tax_profile(
    profile_data: TaxProfileCreate,
    current_user = Depends(get_current_user)
):
    """Create a new tax profile"""
    try:
        profile_record = {
            'id': profile_data.id,
            'user_id': current_user.user_id,
            'name': profile_data.name,
            'profile_type': profile_data.profile_type,
            'default_currency': profile_data.default_currency,
            'tax_year': profile_data.tax_year,
            'business_number': profile_data.business_number,
            'address': profile_data.address,
            'description': profile_data.description
        }
        
        db.create_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.profile_key(current_user.user_id, profile_data.id),
            item_data=profile_record
        )
        
        return APIResponse(
            success=True,
            message="Tax profile created successfully",
            data=TaxProfileResponse(**profile_record)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/profiles/{profile_id}", response_model=APIResponse)
async def update_tax_profile(
    profile_id: str,
    profile_data: TaxProfileUpdate,
    current_user = Depends(get_current_user)
):
    """Update a tax profile"""
    try:
        updates = profile_data.dict(exclude_unset=True)
        
        result = db.update_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.profile_key(current_user.user_id, profile_id),
            updates=updates
        )
        
        return APIResponse(
            success=True,
            message="Tax profile updated successfully",
            data=TaxProfileResponse(**result)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/profiles/{profile_id}", response_model=APIResponse)
async def delete_tax_profile(
    profile_id: str,
    current_user = Depends(get_current_user)
):
    """Delete a tax profile"""
    try:
        db.delete_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.profile_key(current_user.user_id, profile_id)
        )
        
        return APIResponse(
            success=True,
            message="Tax profile deleted successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Expense endpoints
@app.get("/expenses", response_model=APIResponse)
async def get_expenses(
    profile_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_user)
):
    """Get expenses with optional filtering"""
    try:
        # Build filter expression
        filter_parts = []
        expression_attrs = {}
        expression_values = {}
        
        if profile_id:
            filter_parts.append("#profile_id = :profile_id")
            expression_attrs["#profile_id"] = "profile_id"
            expression_values[":profile_id"] = profile_id
        
        if category:
            filter_parts.append("#category = :category")
            expression_attrs["#category"] = "category"
            expression_values[":category"] = category
        
        if date_from:
            filter_parts.append("#date >= :date_from")
            expression_attrs["#date"] = "date"
            expression_values[":date_from"] = date_from
        
        if date_to:
            filter_parts.append("#date <= :date_to")
            expression_attrs["#date"] = "date"
            expression_values[":date_to"] = date_to
        
        filter_expression = " AND ".join(filter_parts) if filter_parts else None
        
        result = db.scan_items(
            filter_expression=filter_expression,
            expression_attribute_names=expression_attrs,
            expression_attribute_values=expression_values,
            limit=page_size,
            start_key=None  # Add pagination support
        )
        
        expenses = [ExpenseResponse(**item) for item in result['items']]
        
        return APIResponse(
            success=True,
            message="Expenses retrieved successfully",
            data=PaginatedResponse(
                items=expenses,
                total=result['count'],
                page=page,
                page_size=page_size,
                has_next=result['has_more'],
                has_prev=page > 1
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/expenses", response_model=APIResponse)
async def create_expense(
    expense_data: ExpenseCreate,
    current_user = Depends(get_current_user)
):
    """Create a new expense"""
    try:
        expense_record = {
            'id': expense_data.id,
            'user_id': current_user.user_id,
            'profile_id': expense_data.profile_id,
            'amount': expense_data.amount,
            'currency': expense_data.currency,
            'description': expense_data.description,
            'category': expense_data.category,
            'date': expense_data.date.isoformat(),
            'location': expense_data.location.dict() if expense_data.location else None,
            'tax_eligibility': expense_data.tax_eligibility,
            'notes': expense_data.notes,
            'tags': expense_data.tags,
            'receipt_ids': expense_data.receipt_ids,
            'is_verified': False
        }
        
        db.create_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.expense_key(current_user.user_id, expense_data.id),
            item_data=expense_record
        )
        
        return APIResponse(
            success=True,
            message="Expense created successfully",
            data=ExpenseResponse(**expense_record)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/expenses/{expense_id}", response_model=APIResponse)
async def update_expense(
    expense_id: str,
    expense_data: ExpenseUpdate,
    current_user = Depends(get_current_user)
):
    """Update an expense"""
    try:
        updates = expense_data.dict(exclude_unset=True)
        
        # Convert datetime to string if present
        if 'date' in updates and updates['date']:
            updates['date'] = updates['date'].isoformat()
        
        # Convert location to dict if present
        if 'location' in updates and updates['location']:
            updates['location'] = updates['location'].dict()
        
        result = db.update_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.expense_key(current_user.user_id, expense_id),
            updates=updates
        )
        
        return APIResponse(
            success=True,
            message="Expense updated successfully",
            data=ExpenseResponse(**result)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/expenses/{expense_id}", response_model=APIResponse)
async def delete_expense(
    expense_id: str,
    current_user = Depends(get_current_user)
):
    """Delete an expense"""
    try:
        db.delete_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.expense_key(current_user.user_id, expense_id)
        )
        
        return APIResponse(
            success=True,
            message="Expense deleted successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Receipt upload and analysis endpoints
@app.post("/expenses/upload", response_model=APIResponse)
async def upload_receipt(
    file: UploadFile = File(...),
    profile_id: str = Form(...),
    current_user = Depends(get_current_user)
):
    """Upload a receipt image for analysis"""
    try:
        # Validate file type
        if file.content_type not in settings.supported_image_types:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Read file content
        file_content = await file.read()
        
        if len(file_content) > settings.max_file_size_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large")
        
        # Generate file key
        file_key = f"uploads/{current_user.user_id}/{datetime.utcnow().strftime('%Y/%m/%d')}/{file.filename}"
        
        # Upload to S3
        import boto3
        s3_client = boto3.client('s3', region_name=settings.aws_region)
        s3_client.put_object(
            Bucket=settings.s3_bucket,
            Key=file_key,
            Body=file_content,
            ContentType=file.content_type
        )
        
        # Create receipt record
        receipt_record = {
            'id': str(uuid.uuid4()),
            'user_id': current_user.user_id,
            'file_key': file_key,
            'file_size': len(file_content),
            'content_type': file.content_type,
            'is_processed': False
        }
        
        db.create_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.receipt_key(current_user.user_id, receipt_record['id']),
            item_data=receipt_record
        )
        
        return APIResponse(
            success=True,
            message="Receipt uploaded successfully",
            data={
                "receipt_id": receipt_record['id'],
                "file_key": file_key
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/expenses/analyze", response_model=APIResponse)
async def analyze_receipt(
    receipt_id: str = Form(...),
    current_user = Depends(get_current_user)
):
    """Analyze a receipt using OCR and LLM"""
    try:
        # Get receipt record
        receipt = db.get_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.receipt_key(current_user.user_id, receipt_id)
        )
        
        if not receipt:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        # Download from S3
        import boto3
        s3_client = boto3.client('s3', region_name=settings.aws_region)
        response = s3_client.get_object(
            Bucket=settings.s3_bucket,
            Key=receipt['file_key']
        )
        image_bytes = response['Body'].read()
        
        # Extract EXIF data
        import exifread
        from PIL import Image
        import io
        
        image = Image.open(io.BytesIO(image_bytes))
        exif_data = {}
        if hasattr(image, '_getexif') and image._getexif():
            exif_data = exifread.process_file(io.BytesIO(image_bytes))
        
        # Extract location from EXIF
        location = location_service.extract_location_from_exif(exif_data)
        
        # Perform OCR
        ocr_result = rekognition_service.detect_text(image_bytes)
        if not ocr_result['success']:
            raise HTTPException(status_code=500, detail="OCR failed")
        
        # Extract text
        ocr_text = ' '.join([block['text'] for block in ocr_result['text_blocks']])
        
        # Analyze with LLM
        analysis = llm_service.analyze_receipt(ocr_text, {
            'file_size': receipt['file_size'],
            'content_type': receipt['content_type'],
            'exif_data': exif_data
        })
        
        # Update receipt with analysis
        db.update_item(
            pk=DynamoKeys.user_key(current_user.user_id),
            sk=DynamoKeys.receipt_key(current_user.user_id, receipt_id),
            updates={
                'analysis': analysis.dict(),
                'is_processed': True
            }
        )
        
        return APIResponse(
            success=True,
            message="Receipt analyzed successfully",
            data={
                "receipt_id": receipt_id,
                "analysis": analysis.dict(),
                "location": location.dict() if location else None
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Reporting endpoints
@app.get("/reports/summary", response_model=APIResponse)
async def get_expense_summary(
    profile_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user = Depends(get_current_user)
):
    """Get expense summary for reporting"""
    try:
        # Get expenses with filters
        filter_parts = []
        expression_attrs = {}
        expression_values = {}
        
        if profile_id:
            filter_parts.append("#profile_id = :profile_id")
            expression_attrs["#profile_id"] = "profile_id"
            expression_values[":profile_id"] = profile_id
        
        if date_from:
            filter_parts.append("#date >= :date_from")
            expression_attrs["#date"] = "date"
            expression_values[":date_from"] = date_from
        
        if date_to:
            filter_parts.append("#date <= :date_to")
            expression_attrs["#date"] = "date"
            expression_values[":date_to"] = date_to
        
        filter_expression = " AND ".join(filter_parts) if filter_parts else None
        
        result = db.scan_items(
            filter_expression=filter_expression,
            expression_attribute_names=expression_attrs,
            expression_attribute_values=expression_values
        )
        
        # Calculate summary
        total_expenses = len(result['items'])
        total_amount = sum(item['amount'] for item in result['items'])
        currency = result['items'][0]['currency'] if result['items'] else 'CAD'
        
        by_category = {}
        by_month = {}
        by_tax_eligibility = {}
        
        for item in result['items']:
            # By category
            category = item['category']
            by_category[category] = by_category.get(category, 0) + item['amount']
            
            # By month
            date = datetime.fromisoformat(item['date'])
            month_key = date.strftime('%Y-%m')
            by_month[month_key] = by_month.get(month_key, 0) + item['amount']
            
            # By tax eligibility
            eligibility = item['tax_eligibility']
            by_tax_eligibility[eligibility] = by_tax_eligibility.get(eligibility, 0) + item['amount']
        
        summary = ExpenseSummary(
            total_expenses=total_expenses,
            total_amount=total_amount,
            currency=currency,
            by_category=by_category,
            by_month=by_month,
            by_tax_eligibility=by_tax_eligibility,
            average_amount=total_amount / total_expenses if total_expenses > 0 else 0
        )
        
        return APIResponse(
            success=True,
            message="Expense summary retrieved successfully",
            data=summary.dict()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reports/filter", response_model=APIResponse)
async def filter_expenses_for_tax(
    filter_data: ExpenseFilter,
    current_user = Depends(get_current_user)
):
    """Use LLM to filter and analyze expenses for tax purposes"""
    try:
        # Get expenses with filters
        filter_parts = []
        expression_attrs = {}
        expression_values = {}
        
        if filter_data.profile_ids:
            filter_parts.append("#profile_id IN (:profile_ids)")
            expression_attrs["#profile_id"] = "profile_id"
            expression_values[":profile_ids"] = filter_data.profile_ids
        
        if filter_data.categories:
            filter_parts.append("#category IN (:categories)")
            expression_attrs["#category"] = "category"
            expression_values[":categories"] = filter_data.categories
        
        if filter_data.date_from:
            filter_parts.append("#date >= :date_from")
            expression_attrs["#date"] = "date"
            expression_values[":date_from"] = filter_data.date_from.isoformat()
        
        if filter_data.date_to:
            filter_parts.append("#date <= :date_to")
            expression_attrs["#date"] = "date"
            expression_values[":date_to"] = filter_data.date_to.isoformat()
        
        filter_expression = " AND ".join(filter_parts) if filter_parts else None
        
        result = db.scan_items(
            filter_expression=filter_expression,
            expression_attribute_names=expression_attrs,
            expression_attribute_values=expression_values
        )
        
        # Use LLM to analyze expenses
        llm_result = llm_service.filter_expenses_for_tax(
            result['items'],
            tax_year=datetime.now().year,
            profile_type="business"  # This should come from the profile
        )
        
        return APIResponse(
            success=True,
            message="Expenses filtered successfully",
            data=llm_result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Create Mangum handler for AWS Lambda
handler = Mangum(app) 