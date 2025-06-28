# Create Cognito App Client Script
# Usage: .\create_cognito_client.ps1 -UserPoolId "your-user-pool-id"

param(
    [Parameter(Mandatory=$true)]
    [string]$UserPoolId
)

Write-Host "Creating Cognito App Client for User Pool: $UserPoolId" -ForegroundColor Green

# Create the app client
$appClientName = "taxless-app-client"

try {
    $result = aws cognito-idp create-user-pool-client `
        --user-pool-id $UserPoolId `
        --client-name $appClientName `
        --no-generate-secret `
        --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH ALLOW_USER_SRP_AUTH `
        --supported-identity-providers COGNITO `
        --allowed-o-auth-flows code implicit `
        --allowed-o-auth-scopes email openid profile `
        --allowed-o-auth-flows-user-pool-client

    if ($LASTEXITCODE -eq 0) {
        Write-Host "App Client created successfully!" -ForegroundColor Green
        
        # Parse the JSON response to get the client ID
        $clientData = $result | ConvertFrom-Json
        $clientId = $clientData.UserPoolClient.ClientId
        
        Write-Host "Your COGNITO_CLIENT_ID is: $clientId" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Add this to your .env file:" -ForegroundColor Cyan
        Write-Host "COGNITO_CLIENT_ID=$clientId" -ForegroundColor White
    } else {
        Write-Host "Failed to create app client" -ForegroundColor Red
    }
} catch {
    Write-Host "Error creating app client: $_" -ForegroundColor Red
} 