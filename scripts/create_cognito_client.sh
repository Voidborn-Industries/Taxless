#!/bin/bash

# Create Cognito App Client Script
# Usage: ./create_cognito_client.sh "your-user-pool-id"

if [ $# -eq 0 ]; then
    echo "Usage: $0 <user-pool-id>"
    echo "Example: $0 us-east-1_abcdef123"
    exit 1
fi

USER_POOL_ID=$1
APP_CLIENT_NAME="taxless-app-client"

echo "Creating Cognito App Client for User Pool: $USER_POOL_ID"

# Create the app client
result=$(aws cognito-idp create-user-pool-client \
    --user-pool-id "$USER_POOL_ID" \
    --client-name "$APP_CLIENT_NAME" \
    --no-generate-secret \
    --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH ALLOW_USER_SRP_AUTH \
    --supported-identity-providers COGNITO \
    --allowed-o-auth-flows code implicit \
    --allowed-o-auth-scopes email openid profile \
    --allowed-o-auth-flows-user-pool-client 2>&1)

if [ $? -eq 0 ]; then
    echo "App Client created successfully!"
    
    # Extract the client ID from the JSON response
    client_id=$(echo "$result" | jq -r '.UserPoolClient.ClientId')
    
    echo "Your COGNITO_CLIENT_ID is: $client_id"
    echo ""
    echo "Add this to your .env file:"
    echo "COGNITO_CLIENT_ID=$client_id"
else
    echo "Failed to create app client:"
    echo "$result"
fi 