import boto3
import json
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
import google.generativeai as genai
from .config import settings
from .models import ReceiptAnalysis, Currency, Location


class RekognitionService:
    def __init__(self):
        self.client = boto3.client('rekognition', region_name=settings.aws_region)
    
    def detect_text(self, image_bytes: bytes) -> Dict[str, Any]:
        """Detect text in an image using AWS Rekognition"""
        try:
            response = self.client.detect_text(
                Image={'Bytes': image_bytes}
            )
            
            # Extract all detected text
            text_blocks = []
            for text_detection in response.get('TextDetections', []):
                if text_detection['Type'] == 'LINE':
                    text_blocks.append({
                        'text': text_detection['DetectedText'],
                        'confidence': text_detection['Confidence'],
                        'geometry': text_detection.get('Geometry', {})
                    })
            
            return {
                'success': True,
                'text_blocks': text_blocks,
                'raw_response': response
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'text_blocks': []
            }
    
    def analyze_document(self, image_bytes: bytes) -> Dict[str, Any]:
        """Analyze document structure using AWS Textract-like features"""
        try:
            # For now, we'll use detect_text as the base
            # In production, you might want to use AWS Textract for better document analysis
            text_result = self.detect_text(image_bytes)
            
            if not text_result['success']:
                return text_result
            
            # Extract structured information from text blocks
            structured_data = self._extract_structured_data(text_result['text_blocks'])
            
            return {
                'success': True,
                'text_blocks': text_result['text_blocks'],
                'structured_data': structured_data,
                'raw_response': text_result['raw_response']
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'text_blocks': [],
                'structured_data': {}
            }
    
    def _extract_structured_data(self, text_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract structured data from text blocks"""
        full_text = ' '.join([block['text'] for block in text_blocks])
        
        # Basic pattern matching for common receipt elements
        structured_data = {
            'merchant_name': None,
            'total_amount': None,
            'currency': None,
            'date': None,
            'items': [],
            'tax_amount': None,
            'subtotal': None
        }
        
        # Look for currency symbols and amounts
        import re
        
        # Currency patterns
        currency_patterns = {
            r'\$(\d+\.?\d*)': 'USD',
            r'CAD\s*(\d+\.?\d*)': 'CAD',
            r'(\d+\.?\d*)\s*CAD': 'CAD',
            r'€(\d+\.?\d*)': 'EUR',
            r'£(\d+\.?\d*)': 'GBP'
        }
        
        for pattern, currency in currency_patterns.items():
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                # Try to find the largest amount as total
                amounts = [float(match) for match in matches]
                structured_data['total_amount'] = max(amounts)
                structured_data['currency'] = currency
                break
        
        # Look for date patterns
        date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, full_text)
            if matches:
                # Use the first match as date
                structured_data['date'] = matches[0]
                break
        
        return structured_data


class LLMService:
    def __init__(self):
        self.model = None
        
        if settings.google_api_key:
            genai.configure(api_key=settings.google_api_key)
            self.model = genai.GenerativeModel(settings.llm_model)
    
    def analyze_receipt(self, ocr_text: str, image_metadata: Optional[Dict[str, Any]] = None) -> ReceiptAnalysis:
        """Analyze receipt text using Google Gemini to extract structured information"""
        if not self.model:
            raise Exception("Google API key not configured")
        
        prompt = self._create_receipt_analysis_prompt(ocr_text, image_metadata)
        
        try:
            response = self._call_gemini(prompt)
            return self._parse_receipt_analysis_response(response)
        except Exception as e:
            # Fallback to basic analysis
            return self._fallback_analysis(ocr_text)
    
    def analyze_expense_tax_eligibility(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze expense for tax eligibility using Google Gemini"""
        if not self.model:
            raise Exception("Google API key not configured")
        
        prompt = self._create_tax_eligibility_prompt(expense_data)
        
        try:
            response = self._call_gemini(prompt)
            return self._parse_tax_eligibility_response(response)
        except Exception as e:
            return {
                'tax_eligibility': 'REQUIRES_REVIEW',
                'confidence': 0.0,
                'reasoning': f"LLM analysis failed: {str(e)}",
                'suggestions': []
            }
    
    def filter_expenses_for_tax(self, expenses: List[Dict[str, Any]], 
                               tax_year: int, profile_type: str) -> Dict[str, Any]:
        """Filter and categorize expenses for tax purposes using Google Gemini"""
        if not self.model:
            raise Exception("Google API key not configured")
        
        prompt = self._create_expense_filtering_prompt(expenses, tax_year, profile_type)
        
        try:
            response = self._call_gemini(prompt)
            return self._parse_expense_filtering_response(response)
        except Exception as e:
            return {
                'flagged_expenses': [],
                'summary': f"LLM filtering failed: {str(e)}",
                'suggestions': []
            }
    
    def _create_receipt_analysis_prompt(self, ocr_text: str, 
                                      image_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create prompt for receipt analysis"""
        prompt = f"""
You are an expert at analyzing receipt images and extracting structured information for expense tracking.

Please analyze the following OCR text from a receipt and extract the following information in JSON format:

OCR Text:
{ocr_text}

{self._format_image_metadata(image_metadata)}

Please return a JSON object with the following structure:
{{
    "merchant_name": "Name of the business/merchant",
    "total_amount": 123.45,
    "currency": "CAD",
    "date": "2024-01-15T12:30:00",
    "items": [
        {{
            "description": "Item description",
            "quantity": 1,
            "unit_price": 10.00,
            "total_price": 10.00
        }}
    ],
    "tax_amount": 12.34,
    "subtotal": 111.11,
    "confidence_score": 0.85,
    "notes": "Any additional observations or uncertainties"
}}

Guidelines:
- If a field cannot be determined, use null
- For currency, use standard codes (CAD, USD, EUR, GBP)
- For dates, use ISO format
- Confidence score should be between 0.0 and 1.0
- Be conservative with confidence scores if information is unclear
"""
        return prompt
    
    def _create_tax_eligibility_prompt(self, expense_data: Dict[str, Any]) -> str:
        """Create prompt for tax eligibility analysis"""
        prompt = f"""
You are a tax expert analyzing business expenses for tax deduction eligibility in Canada.

Please analyze the following expense and determine its tax eligibility:

Expense Details:
{json.dumps(expense_data, indent=2)}

Please return a JSON object with the following structure:
{{
    "tax_eligibility": "FULLY_DEDUCTIBLE|PARTIALLY_DEDUCTIBLE|NOT_DEDUCTIBLE|PERSONAL|REQUIRES_REVIEW",
    "confidence": 0.85,
    "reasoning": "Detailed explanation of the determination",
    "suggestions": [
        "Specific suggestions for improving tax compliance"
    ],
    "category_suggestion": "SUGGESTED_CATEGORY",
    "notes": "Additional tax-related notes"
}}

Tax Eligibility Guidelines:
- FULLY_DEDUCTIBLE: 100% deductible business expense
- PARTIALLY_DEDUCTIBLE: 50% deductible (e.g., meals and entertainment)
- NOT_DEDUCTIBLE: Not eligible for deduction
- PERSONAL: Personal expense, not business-related
- REQUIRES_REVIEW: Needs human review

Consider:
- Business purpose and necessity
- Personal vs business use
- CRA guidelines and restrictions
- Documentation requirements
"""
        return prompt
    
    def _create_expense_filtering_prompt(self, expenses: List[Dict[str, Any]], 
                                       tax_year: int, profile_type: str) -> str:
        """Create prompt for expense filtering and categorization"""
        prompt = f"""
You are a tax expert reviewing a list of expenses for {profile_type} tax filing for the year {tax_year}.

Please analyze the following expenses and provide tax-related insights:

Expenses:
{json.dumps(expenses, indent=2)}

Please return a JSON object with the following structure:
{{
    "flagged_expenses": [
        {{
            "expense_id": "id",
            "issue": "Description of the issue",
            "severity": "HIGH|MEDIUM|LOW",
            "suggestion": "How to address the issue"
        }}
    ],
    "summary": "Overall summary of the expense list for tax purposes",
    "suggestions": [
        "General suggestions for tax optimization"
    ],
    "categories_analysis": {{
        "category": "Analysis of this category"
    }}
}}

Focus on:
- Expenses that may not be deductible
- Missing documentation
- Potential audit risks
- Tax optimization opportunities
- Compliance with CRA guidelines
"""
        return prompt
    
    def _format_image_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        """Format image metadata for the prompt"""
        if not metadata:
            return ""
        
        metadata_text = "\nImage Metadata:\n"
        for key, value in metadata.items():
            metadata_text += f"- {key}: {value}\n"
        return metadata_text
    
    def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini API"""
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            raise Exception(f"Gemini API call failed: {str(e)}")
    
    def _parse_receipt_analysis_response(self, response: str) -> ReceiptAnalysis:
        """Parse Gemini response into ReceiptAnalysis object"""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)
            
            return ReceiptAnalysis(
                merchant_name=data.get('merchant_name'),
                total_amount=data.get('total_amount'),
                currency=data.get('currency'),
                date=datetime.fromisoformat(data['date']) if data.get('date') else None,
                items=data.get('items', []),
                tax_amount=data.get('tax_amount'),
                subtotal=data.get('subtotal'),
                confidence_score=data.get('confidence_score', 0.5),
                raw_text=response
            )
        except Exception as e:
            # Fallback to basic analysis
            return self._fallback_analysis(response)
    
    def _parse_tax_eligibility_response(self, response: str) -> Dict[str, Any]:
        """Parse tax eligibility response"""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)
            
            return {
                'tax_eligibility': data.get('tax_eligibility', 'REQUIRES_REVIEW'),
                'confidence': data.get('confidence', 0.5),
                'reasoning': data.get('reasoning', ''),
                'suggestions': data.get('suggestions', []),
                'category_suggestion': data.get('category_suggestion'),
                'notes': data.get('notes', '')
            }
        except Exception as e:
            return {
                'tax_eligibility': 'REQUIRES_REVIEW',
                'confidence': 0.0,
                'reasoning': f"Failed to parse response: {str(e)}",
                'suggestions': []
            }
    
    def _parse_expense_filtering_response(self, response: str) -> Dict[str, Any]:
        """Parse expense filtering response"""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)
            
            return {
                'flagged_expenses': data.get('flagged_expenses', []),
                'summary': data.get('summary', ''),
                'suggestions': data.get('suggestions', []),
                'categories_analysis': data.get('categories_analysis', {})
            }
        except Exception as e:
            return {
                'flagged_expenses': [],
                'summary': f"Failed to parse response: {str(e)}",
                'suggestions': []
            }
    
    def _fallback_analysis(self, ocr_text: str) -> ReceiptAnalysis:
        """Fallback analysis when LLM fails"""
        return ReceiptAnalysis(
            merchant_name=None,
            total_amount=None,
            currency=None,
            date=None,
            items=[],
            tax_amount=None,
            subtotal=None,
            confidence_score=0.1,
            raw_text=ocr_text
        )


class LocationService:
    def __init__(self):
        self.geoip_client = None
        # You could integrate with a geolocation service here
    
    def extract_location_from_exif(self, exif_data: Dict[str, Any]) -> Optional[Location]:
        """Extract location from EXIF data"""
        try:
            if 'GPSInfo' in exif_data:
                gps_info = exif_data['GPSInfo']
                
                # Extract latitude and longitude
                lat = self._convert_gps_to_decimal(gps_info.get('GPSLatitude'), gps_info.get('GPSLatitudeRef'))
                lon = self._convert_gps_to_decimal(gps_info.get('GPSLongitude'), gps_info.get('GPSLongitudeRef'))
                
                if lat and lon:
                    return Location(
                        latitude=lat,
                        longitude=lon,
                        source="exif"
                    )
        except Exception as e:
            print(f"Error extracting EXIF location: {e}")
        
        return None
    
    def _convert_gps_to_decimal(self, gps_coords: List[float], ref: str) -> Optional[float]:
        """Convert GPS coordinates to decimal format"""
        if not gps_coords or len(gps_coords) != 3:
            return None
        
        degrees, minutes, seconds = gps_coords
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        
        if ref in ['S', 'W']:
            decimal = -decimal
        
        return decimal
    
    def get_location_from_ip(self, ip_address: str) -> Optional[Location]:
        """Get location from IP address"""
        # This would integrate with a geolocation service
        # For now, return None
        return None
    
    def parse_location_from_text(self, text: str) -> Optional[Location]:
        """Parse location from text (OCR or manual input)"""
        # Basic location parsing - in production, you'd use a more sophisticated approach
        import re
        
        # Look for common location patterns
        patterns = [
            r'(\d+\.\d+),\s*(\d+\.\d+)',  # lat,lon
            r'(\w+),\s*(\w+),\s*(\w+)',   # city, province, country
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                match = matches[0]
                if len(match) == 2 and '.' in match[0] and '.' in match[1]:
                    # Likely coordinates
                    try:
                        lat, lon = float(match[0]), float(match[1])
                        return Location(
                            latitude=lat,
                            longitude=lon,
                            source="ocr"
                        )
                    except ValueError:
                        pass
                elif len(match) >= 2:
                    # Likely address components
                    return Location(
                        city=match[0] if len(match) > 0 else None,
                        province=match[1] if len(match) > 1 else None,
                        country=match[2] if len(match) > 2 else None,
                        source="ocr"
                    )
        
        return None


# Global service instances
rekognition_service = RekognitionService()
llm_service = LLMService()
location_service = LocationService() 