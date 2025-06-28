# Taxless - AI-Powered Expense Tracking for Tax Purposes

A comprehensive expense tracking application that uses AI to automatically record receipts and expenses for tax deduction purposes. Supports multiple tax profiles (personal and business) with intelligent OCR, LLM processing, and tax compliance filtering.

## Features

### Core Functionality
- **User Management**: Secure registration and login with CRUD operations
- **Tax Profile Management**: Multiple tax profiles per user (personal, company 1, company 2, etc.)
- **Expense Recording**: 
  - AI-powered receipt scanning with AWS Rekognition OCR
  - LLM-powered expense detail extraction and categorization
  - Manual expense input with optional receipt attachment
  - Unified interface for both automatic and manual entry
- **Smart Data Capture**:
  - Automatic location detection (EXIF, OCR, IP geolocation, manual)
  - Currency detection with CAD default
  - Timestamp and metadata preservation
- **Tax Intelligence**:
  - LLM-powered expense filtering and categorization
  - Tax eligibility flagging
  - Custom date range reporting
  - Structured numerical summaries

### Tech Stack
- **Backend**: AWS Lambda (Python)
- **Frontend**: Flutter (Cross-platform: Web, Android, iOS)
- **Database**: Amazon DynamoDB
- **Object Storage**: Amazon S3
- **AI Services**: AWS Rekognition, OpenAI/Anthropic LLM
- **Authentication**: AWS Cognito

## Project Structure
```
taxless/
├── backend/                 # Python Lambda functions
│   ├── functions/          # Individual Lambda functions
│   ├── shared/             # Shared utilities and models
│   ├── requirements.txt    # Python dependencies
│   └── serverless.yml      # Serverless framework config
├── frontend/               # Flutter application
│   ├── lib/               # Dart source code
│   ├── assets/            # Images, fonts, etc.
│   ├── pubspec.yaml       # Flutter dependencies
│   └── android/           # Android-specific config
├── infrastructure/         # AWS infrastructure as code
│   ├── terraform/         # Terraform configurations
│   └── cloudformation/    # CloudFormation templates
├── docs/                  # Documentation
└── scripts/               # Deployment and utility scripts
```

## Setup Instructions

### Prerequisites
- Python 3.9+
- Flutter SDK 3.0+
- AWS CLI configured
- Node.js (for Serverless Framework)

### Backend Setup
1. Navigate to `backend/`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables (see `.env.example`)
4. Deploy: `serverless deploy`

### Frontend Setup
1. Navigate to `frontend/`
2. Install dependencies: `flutter pub get`
3. Configure API endpoints in `lib/config/api_config.dart`
4. Run: `flutter run`

## Environment Variables

Create a `.env` file in the backend directory with:
```
AWS_REGION=us-east-1
DYNAMODB_TABLE=taxless-expenses
S3_BUCKET=taxless-receipts
COGNITO_USER_POOL_ID=your-user-pool-id
COGNITO_CLIENT_ID=your-client-id
OPENAI_API_KEY=your-openai-key
```

## API Documentation

### Authentication Endpoints
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Token refresh

### Tax Profile Endpoints
- `GET /profiles` - List user tax profiles
- `POST /profiles` - Create new tax profile
- `PUT /profiles/{id}` - Update tax profile
- `DELETE /profiles/{id}` - Delete tax profile

### Expense Endpoints
- `GET /expenses` - List expenses with filters
- `POST /expenses` - Create new expense
- `PUT /expenses/{id}` - Update expense
- `DELETE /expenses/{id}` - Delete expense
- `POST /expenses/upload` - Upload receipt image
- `POST /expenses/analyze` - Analyze receipt with AI

### Reporting Endpoints
- `GET /reports/summary` - Get expense summary
- `GET /reports/tax-ready` - Get tax-ready report
- `POST /reports/filter` - LLM-powered expense filtering

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details 