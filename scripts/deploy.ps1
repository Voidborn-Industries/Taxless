# Taxless Deployment Script for Windows
# This script deploys both the backend and frontend components

param(
    [string]$Stage = "dev"
)

Write-Host "🚀 Starting Taxless deployment..." -ForegroundColor Blue

# Function to print colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check if required tools are installed
function Check-Prerequisites {
    Write-Status "Checking prerequisites..."
    
    # Check Node.js
    try {
        $nodeVersion = node --version
        Write-Status "Node.js version: $nodeVersion"
    }
    catch {
        Write-Error "Node.js is not installed. Please install Node.js 16+"
        exit 1
    }
    
    # Check npm
    try {
        $npmVersion = npm --version
        Write-Status "npm version: $npmVersion"
    }
    catch {
        Write-Error "npm is not installed. Please install npm"
        exit 1
    }
    
    # Check Python
    try {
        $pythonVersion = python --version
        Write-Status "Python version: $pythonVersion"
    }
    catch {
        Write-Error "Python is not installed. Please install Python 3.9+"
        exit 1
    }
    
    # Check AWS CLI
    try {
        $awsVersion = aws --version
        Write-Status "AWS CLI version: $awsVersion"
    }
    catch {
        Write-Error "AWS CLI is not installed. Please install AWS CLI"
        exit 1
    }
    
    # Check Flutter
    try {
        $flutterVersion = flutter --version
        Write-Status "Flutter is installed"
    }
    catch {
        Write-Error "Flutter is not installed. Please install Flutter SDK"
        exit 1
    }
    
    Write-Success "All prerequisites are installed"
}

# Deploy backend
function Deploy-Backend {
    Write-Status "Deploying backend..."
    
    Set-Location backend
    
    # Install Serverless Framework if not installed
    try {
        $serverlessVersion = serverless --version
        Write-Status "Serverless Framework version: $serverlessVersion"
    }
    catch {
        Write-Status "Installing Serverless Framework..."
        npm install -g serverless
    }
    
    # Install Python dependencies
    Write-Status "Installing Python dependencies..."
    pip install -r requirements.txt
    
    # Check if .env file exists
    if (-not (Test-Path ".env")) {
        Write-Warning ".env file not found. Please create one based on env.example"
        Write-Status "Copying env.example to .env..."
        Copy-Item "env.example" ".env"
        Write-Warning "Please edit .env file with your actual values before deploying"
        Set-Location ..
        exit 1
    }
    
    # Deploy using Serverless Framework
    Write-Status "Deploying to AWS..."
    serverless deploy --stage $Stage
    
    # Get the API Gateway URL
    $serverlessInfo = serverless info --stage $Stage
    $apiUrl = ($serverlessInfo | Select-String "endpoints:" -Context 0,1 | Select-Object -Last 1) -split " " | Select-Object -Last 1
    
    Write-Success "Backend deployed successfully!"
    Write-Status "API Gateway URL: $apiUrl"
    
    Set-Location ..
    return $apiUrl
}

# Deploy frontend
function Deploy-Frontend {
    Write-Status "Deploying frontend..."
    
    Set-Location frontend
    
    # Get dependencies
    Write-Status "Getting Flutter dependencies..."
    flutter pub get
    
    # Build for web
    Write-Status "Building for web..."
    flutter build web --release
    
    # Build for Android
    Write-Status "Building for Android..."
    flutter build apk --release
    
    Write-Success "Frontend built successfully!"
    Write-Status "Web build: build/web/"
    Write-Status "Android build: build/app/outputs/flutter-apk/app-release.apk"
    
    Set-Location ..
}

# Update API configuration
function Update-ApiConfig {
    param([string]$ApiUrl)
    
    Write-Status "Updating API configuration..."
    
    if ($ApiUrl) {
        # Update the API URL in the Flutter config
        $configFile = "frontend/lib/config/app_config.dart"
        $content = Get-Content $configFile -Raw
        $updatedContent = $content -replace "https://your-api-gateway-url\.amazonaws\.com/dev", $ApiUrl
        Set-Content $configFile $updatedContent
        Write-Success "API configuration updated"
    }
    else {
        Write-Warning "Could not get API URL. Please update frontend/lib/config/app_config.dart manually"
    }
}

# Main deployment function
function Main {
    Write-Status "Starting Taxless deployment..."
    
    # Check prerequisites
    Check-Prerequisites
    
    # Deploy backend
    $apiUrl = Deploy-Backend
    
    # Update API configuration
    Update-ApiConfig -ApiUrl $apiUrl
    
    # Deploy frontend
    Deploy-Frontend
    
    Write-Success "🎉 Deployment completed successfully!"
    Write-Status ""
    Write-Status "Next steps:"
    Write-Status "1. Configure your AWS Cognito User Pool"
    Write-Status "2. Set up your OpenAI/Anthropic API keys"
    Write-Status "3. Test the application"
    Write-Status "4. Deploy to production when ready"
}

# Run main function
Main 