import json
import os
import boto3
from typing import Dict, Any
from datetime import datetime

# Import shared modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config import settings
from shared.database import db, DynamoKeys
from shared.ai_services import rekognition_service, llm_service, location_service


def handler(event, context):
    """Process uploaded images for OCR and analysis"""
    try:
        # Parse S3 event
        s3_event = event['Records'][0]['s3']
        bucket_name = s3_event['bucket']['name']
        object_key = s3_event['object']['key']
        
        print(f"Processing image: {object_key} from bucket: {bucket_name}")
        
        # Download image from S3
        s3_client = boto3.client('s3', region_name=settings.aws_region)
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        image_bytes = response['Body'].read()
        
        # Extract user_id and receipt_id from the key
        # Expected format: uploads/{user_id}/{date}/{filename}
        key_parts = object_key.split('/')
        if len(key_parts) < 4:
            raise Exception(f"Invalid object key format: {object_key}")
        
        user_id = key_parts[1]
        filename = key_parts[-1]
        
        # Find receipt record by file_key
        result = db.scan_items(
            filter_expression="#file_key = :file_key",
            expression_attribute_names={"#file_key": "file_key"},
            expression_attribute_values={":file_key": object_key}
        )
        
        if not result['items']:
            raise Exception(f"No receipt record found for file_key: {object_key}")
        
        receipt = result['items'][0]
        receipt_id = receipt['id']
        
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
            raise Exception(f"OCR failed: {ocr_result.get('error', 'Unknown error')}")
        
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
            pk=DynamoKeys.user_key(user_id),
            sk=DynamoKeys.receipt_key(user_id, receipt_id),
            updates={
                'analysis': analysis.dict(),
                'is_processed': True,
                'processed_at': datetime.utcnow().isoformat()
            }
        )
        
        # If location was found, update the receipt
        if location:
            db.update_item(
                pk=DynamoKeys.user_key(user_id),
                sk=DynamoKeys.receipt_key(user_id, receipt_id),
                updates={
                    'location': location.dict()
                }
            )
        
        print(f"Successfully processed receipt {receipt_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'receipt_id': receipt_id,
                'analysis': analysis.dict(),
                'location': location.dict() if location else None
            })
        }
        
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        
        # Update receipt with error
        try:
            if 'receipt_id' in locals() and 'user_id' in locals():
                db.update_item(
                    pk=DynamoKeys.user_key(user_id),
                    sk=DynamoKeys.receipt_key(user_id, receipt_id),
                    updates={
                        'is_processed': False,
                        'processing_error': str(e),
                        'processed_at': datetime.utcnow().isoformat()
                    }
                )
        except Exception as update_error:
            print(f"Error updating receipt with error: {str(update_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        } 