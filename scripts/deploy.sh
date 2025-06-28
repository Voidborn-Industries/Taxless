#!/bin/bash

# Taxless Deployment Script
# This script deploys both the backend and frontend components

set -e

echo "🚀 Starting Taxless deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if required tools are installed
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js 16+"
        exit 1
    fi
    
    # Check npm
    if ! command -v npm &> /dev/null; then
        print_error "npm is not installed. Please install npm"
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.9+"
        exit 1
    fi
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install AWS CLI"
        exit 1
    fi
    
    # Check Flutter
    if ! command -v flutter &> /dev/null; then
        print_error "Flutter is not installed. Please install Flutter SDK"
        exit 1
    fi
    
    print_success "All prerequisites are installed"
}

# Deploy backend
deploy_backend() {
    print_status "Deploying backend..."
    
    cd backend
    
    # Install Serverless Framework if not installed
    if ! command -v serverless &> /dev/null; then
        print_status "Installing Serverless Framework..."
        npm install -g serverless
    fi
    
    # Install Python dependencies
    print_status "Installing Python dependencies..."
    pip install -r requirements.txt
    
    # Check if .env file exists
    if [ ! -f .env ]; then
        print_warning ".env file not found. Please create one based on env.example"
        print_status "Copying env.example to .env..."
        cp env.example .env
        print_warning "Please edit .env file with your actual values before deploying"
        exit 1
    fi
    
    # Deploy using Serverless Framework
    print_status "Deploying to AWS..."
    serverless deploy --stage dev
    
    # Get the API Gateway URL
    API_URL=$(serverless info --stage dev | grep "endpoints:" -A 1 | tail -n 1 | awk '{print $2}')
    
    print_success "Backend deployed successfully!"
    print_status "API Gateway URL: $API_URL"
    
    cd ..
}

# Deploy frontend
deploy_frontend() {
    print_status "Deploying frontend..."
    
    cd frontend
    
    # Get dependencies
    print_status "Getting Flutter dependencies..."
    flutter pub get
    
    # Build for web
    print_status "Building for web..."
    flutter build web --release
    
    # Build for Android
    print_status "Building for Android..."
    flutter build apk --release
    
    # Build for iOS (macOS only)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        print_status "Building for iOS..."
        flutter build ios --release --no-codesign
    else
        print_warning "Skipping iOS build (macOS required)"
    fi
    
    print_success "Frontend built successfully!"
    print_status "Web build: build/web/"
    print_status "Android build: build/app/outputs/flutter-apk/app-release.apk"
    
    cd ..
}

# Update API configuration
update_api_config() {
    print_status "Updating API configuration..."
    
    # Get the API Gateway URL from backend deployment
    cd backend
    API_URL=$(serverless info --stage dev | grep "endpoints:" -A 1 | tail -n 1 | awk '{print $2}')
    cd ..
    
    if [ -n "$API_URL" ]; then
        # Update the API URL in the Flutter config
        sed -i "s|https://your-api-gateway-url.amazonaws.com/dev|$API_URL|g" frontend/lib/config/app_config.dart
        print_success "API configuration updated"
    else
        print_warning "Could not get API URL. Please update frontend/lib/config/app_config.dart manually"
    fi
}

# Main deployment function
main() {
    print_status "Starting Taxless deployment..."
    
    # Check prerequisites
    check_prerequisites
    
    # Deploy backend
    deploy_backend
    
    # Update API configuration
    update_api_config
    
    # Deploy frontend
    deploy_frontend
    
    print_success "🎉 Deployment completed successfully!"
    print_status ""
    print_status "Next steps:"
    print_status "1. Configure your AWS Cognito User Pool"
    print_status "2. Set up your OpenAI/Anthropic API keys"
    print_status "3. Test the application"
    print_status "4. Deploy to production when ready"
}

# Run main function
main "$@" 