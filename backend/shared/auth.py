import boto3
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from .config import settings
from .models import TokenData, User, UserCreate, UserResponse


class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.cognito_client = None
        
        if settings.cognito_user_pool_id:
            self.cognito_client = boto3.client('cognito-idp', region_name=settings.aws_region)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
        
        to_encode.update({"exp": expire})
        
        if not settings.jwt_secret:
            raise Exception("JWT secret not configured")
        
        encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode a JWT token"""
        try:
            if not settings.jwt_secret:
                raise Exception("JWT secret not configured")
            
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            
            if user_id is None:
                return None
            
            token_data = TokenData(user_id=user_id, email=email)
            return token_data
        except jwt.PyJWTError:
            return None
    
    def authenticate_user_cognito(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user using AWS Cognito"""
        if not self.cognito_client:
            raise Exception("Cognito not configured")
        
        try:
            response = self.cognito_client.admin_initiate_auth(
                UserPoolId=settings.cognito_user_pool_id,
                ClientId=settings.cognito_client_id,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password
                }
            )
            
            if response.get('AuthenticationResult'):
                return {
                    'access_token': response['AuthenticationResult']['AccessToken'],
                    'refresh_token': response['AuthenticationResult']['RefreshToken'],
                    'expires_in': response['AuthenticationResult']['ExpiresIn']
                }
            else:
                return None
        except Exception as e:
            print(f"Cognito authentication error: {e}")
            return None
    
    def create_user_cognito(self, user_data: UserCreate) -> Optional[str]:
        """Create a new user in Cognito"""
        if not self.cognito_client:
            raise Exception("Cognito not configured")
        
        try:
            response = self.cognito_client.admin_create_user(
                UserPoolId=settings.cognito_user_pool_id,
                Username=user_data.email,
                UserAttributes=[
                    {
                        'Name': 'email',
                        'Value': user_data.email
                    },
                    {
                        'Name': 'email_verified',
                        'Value': 'true'
                    },
                    {
                        'Name': 'given_name',
                        'Value': user_data.first_name
                    },
                    {
                        'Name': 'family_name',
                        'Value': user_data.last_name
                    }
                ],
                TemporaryPassword=user_data.password,
                MessageAction='SUPPRESS'
            )
            
            # Set permanent password
            self.cognito_client.admin_set_user_password(
                UserPoolId=settings.cognito_user_pool_id,
                Username=user_data.email,
                Password=user_data.password,
                Permanent=True
            )
            
            return response['User']['Username']
        except Exception as e:
            print(f"Cognito user creation error: {e}")
            return None
    
    def get_user_cognito(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information from Cognito"""
        if not self.cognito_client:
            raise Exception("Cognito not configured")
        
        try:
            response = self.cognito_client.admin_get_user(
                UserPoolId=settings.cognito_user_pool_id,
                Username=user_id
            )
            
            user_attributes = {}
            for attr in response['UserAttributes']:
                user_attributes[attr['Name']] = attr['Value']
            
            return {
                'id': response['Username'],
                'email': user_attributes.get('email'),
                'first_name': user_attributes.get('given_name'),
                'last_name': user_attributes.get('family_name'),
                'phone': user_attributes.get('phone_number'),
                'is_active': response['UserStatus'] == 'CONFIRMED',
                'created_at': response.get('UserCreateDate'),
                'updated_at': response.get('UserLastModifiedDate')
            }
        except Exception as e:
            print(f"Cognito get user error: {e}")
            return None
    
    def refresh_token_cognito(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh Cognito access token"""
        if not self.cognito_client:
            raise Exception("Cognito not configured")
        
        try:
            response = self.cognito_client.initiate_auth(
                ClientId=settings.cognito_client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={
                    'REFRESH_TOKEN': refresh_token
                }
            )
            
            if response.get('AuthenticationResult'):
                return {
                    'access_token': response['AuthenticationResult']['AccessToken'],
                    'expires_in': response['AuthenticationResult']['ExpiresIn']
                }
            else:
                return None
        except Exception as e:
            print(f"Cognito token refresh error: {e}")
            return None
    
    def change_password_cognito(self, access_token: str, old_password: str, new_password: str) -> bool:
        """Change user password in Cognito"""
        if not self.cognito_client:
            raise Exception("Cognito not configured")
        
        try:
            self.cognito_client.change_password(
                AccessToken=access_token,
                OldPassword=old_password,
                NewPassword=new_password
            )
            return True
        except Exception as e:
            print(f"Cognito password change error: {e}")
            return False
    
    def forgot_password_cognito(self, email: str) -> bool:
        """Initiate forgot password flow in Cognito"""
        if not self.cognito_client:
            raise Exception("Cognito not configured")
        
        try:
            self.cognito_client.forgot_password(
                ClientId=settings.cognito_client_id,
                Username=email
            )
            return True
        except Exception as e:
            print(f"Cognito forgot password error: {e}")
            return False
    
    def confirm_forgot_password_cognito(self, email: str, confirmation_code: str, new_password: str) -> bool:
        """Confirm forgot password in Cognito"""
        if not self.cognito_client:
            raise Exception("Cognito not configured")
        
        try:
            self.cognito_client.confirm_forgot_password(
                ClientId=settings.cognito_client_id,
                Username=email,
                ConfirmationCode=confirmation_code,
                Password=new_password
            )
            return True
        except Exception as e:
            print(f"Cognito confirm forgot password error: {e}")
            return False


# Global auth service instance
auth_service = AuthService() 