# Taxless Setup Guide

This guide will help you set up and deploy the Taxless expense tracking application.

## Prerequisites

Before you begin, ensure you have the following installed:

### Required Software
- **Node.js 18+** - [Download here](https://nodejs.org/)
- **Python 3.9+** - [Download here](https://www.python.org/downloads/)
- **AWS CLI** - [Download here](https://aws.amazon.com/cli/)
- **Flutter SDK 3.0+** - [Download here](https://flutter.dev/docs/get-started/install)
- **Git** - [Download here](https://git-scm.com/)

### AWS Account Setup
1. Create an AWS account if you don't have one
2. Configure AWS CLI with your credentials:
   ```bash
   aws configure
   ```
3. Ensure you have appropriate permissions for:
   - Lambda
   - API Gateway
   - DynamoDB
   - S3
   - Cognito
   - Rekognition

### Google Cloud Account
1. **Google AI Studio** - [Sign up here](https://makersuite.google.com/app/apikey)
   - Get your API key from the dashboard

## Quick Start

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd Taxless
```

### 2. Backend Setup

#### Install Dependencies
```bash
cd backend
pip install -r requirements.txt
npm install -g serverless
```

#### Configure Environment Variables
1. Copy the environment template:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` with your actual values:
   ```env
   # AWS Configuration
   AWS_REGION=us-east-1
   DYNAMODB_TABLE=taxless-expenses
   S3_BUCKET=taxless-receipts

   # Cognito Configuration
   COGNITO_USER_POOL_ID=your-user-pool-id
   COGNITO_CLIENT_ID=your-client-id

   # AI Services - Google Gemini
   GOOGLE_API_KEY=your-google-api-key-here

   # Security
   JWT_SECRET="your-jwt-secret-key-here"
   JWT_ALGORITHM=HS256
   JWT_EXPIRATION_HOURS=24

   # Application Settings
   DEFAULT_CURRENCY=CAD
   MAX_FILE_SIZE_MB=10
   SUPPORTED_IMAGE_TYPES=image/jpeg,image/png,image/heic

   # LLM Settings
   LLM_MODEL=gemini-2.0-flash-exp
   MAX_TOKENS=2000
   ```

#### Deploy Backend
```bash
# Deploy to AWS
serverless deploy

# Or use the deployment script
../scripts/deploy.sh  # Linux/macOS
../scripts/deploy.ps1 # Windows
```

### 3. Frontend Setup

#### Install Dependencies
```bash
cd frontend
flutter pub get
```

#### Update API Configuration
After backend deployment, update the API URL in `lib/config/app_config.dart`:
```dart
class AppConfig {
  static const String apiBaseUrl = 'https://your-api-gateway-url.amazonaws.com/dev';
  static const String region = 'us-east-1';
  static const String userPoolId = 'your-user-pool-id';
  static const String clientId = 'your-client-id';
}
```

#### Build and Run
```bash
# For web
flutter run -d chrome

# For Android
flutter run -d android

# For iOS (macOS only)
flutter run -d ios
```

## Detailed Setup

### AWS Cognito Setup

1. **Create User Pool**:
   ```bash
   aws cognito-idp create-user-pool \
     --pool-name "TaxlessUserPool" \
     --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=false}" \
     --auto-verified-attributes email \
     --username-attributes email
   ```

2. **Create User Pool Client**:
   ```bash
   aws cognito-idp create-user-pool-client \
     --user-pool-id YOUR_USER_POOL_ID \
     --client-name "TaxlessClient" \
     --no-generate-secret \
     --explicit-auth-flows ADMIN_NO_SRP_AUTH
   ```

3. **Update your `.env` file** with the User Pool ID and Client ID.

### DynamoDB Setup

The DynamoDB table will be created automatically by the Serverless Framework, but you can also create it manually:

```bash
aws dynamodb create-table \
  --table-name taxless-expenses \
  --attribute-definitions AttributeName=pk,AttributeType=S AttributeName=sk,AttributeType=S \
  --key-schema AttributeName=pk,KeyType=HASH AttributeName=sk,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

### S3 Setup

The S3 bucket will be created automatically, but you can also create it manually:

```bash
aws s3 mb s3://taxless-receipts
```

## Deployment Scripts

### Windows (PowerShell)
```powershell
.\scripts\deploy.ps1
```

### Linux/macOS (Bash)
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

## Testing the Application

### 1. Create a Test User
Use the registration endpoint or create a user directly in Cognito:
```bash
aws cognito-idp admin-create-user \
  --user-pool-id YOUR_USER_POOL_ID \
  --username test@example.com \
  --user-attributes Name=email,Value=test@example.com Name=email_verified,Value=true \
  --temporary-password TestPass123!
```

### 2. Test API Endpoints
```bash
# Login
curl -X POST https://your-api-url/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!"}'

# Get profiles
curl -X GET https://your-api-url/profiles \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Test Frontend
1. Open the Flutter app
2. Register a new account or login with test credentials
3. Create a tax profile
4. Add an expense manually
5. Upload a receipt image
6. View reports

## Troubleshooting

### Common Issues

#### Backend Deployment Fails
- **Issue**: Serverless Framework not installed
- **Solution**: `npm install -g serverless`

- **Issue**: AWS credentials not configured
- **Solution**: Run `aws configure`

- **Issue**: Insufficient IAM permissions
- **Solution**: Ensure your AWS user has Lambda, API Gateway, DynamoDB, S3, and Cognito permissions

#### Frontend Build Fails
- **Issue**: Flutter not installed
- **Solution**: Install Flutter SDK and add to PATH

- **Issue**: Dependencies not installed
- **Solution**: Run `flutter pub get`

- **Issue**: API URL not configured
- **Solution**: Update `lib/config/app_config.dart` with correct API Gateway URL

#### OCR/AI Analysis Fails
- **Issue**: Google Gemini API key not configured
- **Solution**: Add valid Google Gemini API key to `.env`

- **Issue**: AWS Rekognition permissions
- **Solution**: Ensure Lambda has Rekognition permissions

### Logs and Debugging

#### Backend Logs
```bash
# View Lambda logs
serverless logs -f api
serverless logs -f image-processor
serverless logs -f expense-analyzer
```

#### Frontend Debugging
```bash
# Run in debug mode
flutter run --debug

# Check Flutter doctor
flutter doctor
```

## Production Deployment

### 1. Environment Variables
Update `.env` for production:
```env
AWS_REGION=us-east-1
DYNAMODB_TABLE=taxless-expenses-prod
S3_BUCKET=taxless-receipts-prod
# ... other production values
```

### 2. Deploy Backend
```bash
serverless deploy --stage prod
```

### 3. Deploy Frontend
```bash
# Build for production
flutter build web --release
flutter build apk --release
flutter build ios --release

# Deploy web build to your hosting service
# Upload APK to Google Play Store
# Upload iOS build to App Store Connect
```

### 4. Domain and SSL
- Configure custom domain for API Gateway
- Set up SSL certificates
- Update CORS settings for your domain

## Security Considerations

### 1. Environment Variables
- Never commit `.env` files to version control
- Use AWS Secrets Manager for production secrets
- Rotate API keys regularly

### 2. AWS Permissions
- Use least privilege principle
- Create dedicated IAM roles for the application
- Enable CloudTrail for audit logging

### 3. Data Protection
- Enable encryption at rest for DynamoDB
- Enable encryption in transit for S3
- Implement proper data retention policies

## Monitoring and Maintenance

### 1. CloudWatch Monitoring
- Set up CloudWatch alarms for Lambda errors
- Monitor API Gateway metrics
- Track DynamoDB performance

### 2. Cost Optimization
- Monitor Lambda execution times
- Optimize DynamoDB read/write capacity
- Review S3 storage usage

### 3. Regular Updates
- Keep dependencies updated
- Monitor security advisories
- Update Flutter SDK regularly

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review AWS CloudWatch logs
3. Check Flutter console output
4. Create an issue in the repository

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 