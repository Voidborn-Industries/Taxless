import boto3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from botocore.exceptions import ClientError
from .config import settings, DynamoKeys
from .models import BaseEntity


class DynamoDBClient:
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb', region_name=settings.aws_region)
        self.table = self.dynamodb.Table(settings.dynamodb_table)
        self.client = boto3.client('dynamodb', region_name=settings.aws_region)
    
    def _serialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Python types to DynamoDB format"""
        def serialize_value(value):
            if isinstance(value, datetime):
                return value.isoformat()
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(v) for v in value]
            elif isinstance(value, (int, float, str, bool)) or value is None:
                return value
            else:
                return str(value)
        
        return serialize_value(item)
    
    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB format to Python types"""
        def deserialize_value(value):
            if isinstance(value, dict):
                return {k: deserialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [deserialize_value(v) for v in value]
            elif isinstance(value, str):
                # Try to parse as datetime
                try:
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    return value
            else:
                return value
        
        return deserialize_value(item)
    
    def create_item(self, pk: str, sk: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new item in DynamoDB"""
        item = {
            'pk': pk,
            'sk': sk,
            **item_data
        }
        
        # Add timestamps if not present
        if 'created_at' not in item:
            item['created_at'] = datetime.utcnow().isoformat()
        if 'updated_at' not in item:
            item['updated_at'] = datetime.utcnow().isoformat()
        
        serialized_item = self._serialize_item(item)
        
        try:
            self.table.put_item(Item=serialized_item)
            return self._deserialize_item(serialized_item)
        except ClientError as e:
            raise Exception(f"Failed to create item: {str(e)}")
    
    def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """Get an item by primary key"""
        try:
            response = self.table.get_item(Key={'pk': pk, 'sk': sk})
            item = response.get('Item')
            if item:
                return self._deserialize_item(item)
            return None
        except ClientError as e:
            raise Exception(f"Failed to get item: {str(e)}")
    
    def update_item(self, pk: str, sk: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing item"""
        update_expression_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        # Add updated_at timestamp
        updates['updated_at'] = datetime.utcnow().isoformat()
        
        for key, value in updates.items():
            if value is not None:  # Only update non-None values
                attr_name = f"#{key}"
                attr_value = f":{key}"
                
                update_expression_parts.append(f"{attr_name} = {attr_value}")
                expression_attribute_names[attr_name] = key
                expression_attribute_values[attr_value] = self._serialize_item({key: value})[key]
        
        if not update_expression_parts:
            return self.get_item(pk, sk)
        
        update_expression = "SET " + ", ".join(update_expression_parts)
        
        try:
            response = self.table.update_item(
                Key={'pk': pk, 'sk': sk},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )
            return self._deserialize_item(response['Attributes'])
        except ClientError as e:
            raise Exception(f"Failed to update item: {str(e)}")
    
    def delete_item(self, pk: str, sk: str) -> bool:
        """Delete an item"""
        try:
            self.table.delete_item(Key={'pk': pk, 'sk': sk})
            return True
        except ClientError as e:
            raise Exception(f"Failed to delete item: {str(e)}")
    
    def query_items(self, pk: str, sk_prefix: Optional[str] = None, 
                   sk_condition: Optional[str] = None, sk_value: Optional[str] = None,
                   limit: Optional[int] = None, 
                   start_key: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Query items by partition key with optional sort key conditions"""
        query_params = {
            'KeyConditionExpression': 'pk = :pk',
            'ExpressionAttributeValues': {':pk': pk}
        }
        
        if sk_prefix:
            query_params['KeyConditionExpression'] += ' AND begins_with(sk, :sk_prefix)'
            query_params['ExpressionAttributeValues'][':sk_prefix'] = sk_prefix
        elif sk_condition and sk_value:
            if sk_condition == 'begins_with':
                query_params['KeyConditionExpression'] += ' AND begins_with(sk, :sk_value)'
            elif sk_condition == '=':
                query_params['KeyConditionExpression'] += ' AND sk = :sk_value'
            elif sk_condition == '>=':
                query_params['KeyConditionExpression'] += ' AND sk >= :sk_value'
            elif sk_condition == '<=':
                query_params['KeyConditionExpression'] += ' AND sk <= :sk_value'
            
            query_params['ExpressionAttributeValues'][':sk_value'] = sk_value
        
        if limit:
            query_params['Limit'] = limit
        
        if start_key:
            query_params['ExclusiveStartKey'] = start_key
        
        try:
            response = self.table.query(**query_params)
            items = [self._deserialize_item(item) for item in response.get('Items', [])]
            
            return {
                'items': items,
                'count': response.get('Count', 0),
                'scanned_count': response.get('ScannedCount', 0),
                'last_evaluated_key': response.get('LastEvaluatedKey'),
                'has_more': 'LastEvaluatedKey' in response
            }
        except ClientError as e:
            raise Exception(f"Failed to query items: {str(e)}")
    
    def query_gsi(self, gsi_name: str, gsi_pk: str, gsi_sk_prefix: Optional[str] = None,
                  limit: Optional[int] = None, 
                  start_key: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Query items using a Global Secondary Index"""
        query_params = {
            'IndexName': gsi_name,
            'KeyConditionExpression': 'gsi1pk = :gsi_pk',
            'ExpressionAttributeValues': {':gsi_pk': gsi_pk}
        }
        
        if gsi_sk_prefix:
            query_params['KeyConditionExpression'] += ' AND begins_with(gsi1sk, :gsi_sk_prefix)'
            query_params['ExpressionAttributeValues'][':gsi_sk_prefix'] = gsi_sk_prefix
        
        if limit:
            query_params['Limit'] = limit
        
        if start_key:
            query_params['ExclusiveStartKey'] = start_key
        
        try:
            response = self.table.query(**query_params)
            items = [self._deserialize_item(item) for item in response.get('Items', [])]
            
            return {
                'items': items,
                'count': response.get('Count', 0),
                'scanned_count': response.get('ScannedCount', 0),
                'last_evaluated_key': response.get('LastEvaluatedKey'),
                'has_more': 'LastEvaluatedKey' in response
            }
        except ClientError as e:
            raise Exception(f"Failed to query GSI: {str(e)}")
    
    def scan_items(self, filter_expression: Optional[str] = None,
                  expression_attribute_names: Optional[Dict[str, str]] = None,
                  expression_attribute_values: Optional[Dict[str, Any]] = None,
                  limit: Optional[int] = None,
                  start_key: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Scan items with optional filtering"""
        scan_params = {}
        
        if filter_expression:
            scan_params['FilterExpression'] = filter_expression
        
        if expression_attribute_names:
            scan_params['ExpressionAttributeNames'] = expression_attribute_names
        
        if expression_attribute_values:
            scan_params['ExpressionAttributeValues'] = expression_attribute_values
        
        if limit:
            scan_params['Limit'] = limit
        
        if start_key:
            scan_params['ExclusiveStartKey'] = start_key
        
        try:
            response = self.table.scan(**scan_params)
            items = [self._deserialize_item(item) for item in response.get('Items', [])]
            
            return {
                'items': items,
                'count': response.get('Count', 0),
                'scanned_count': response.get('ScannedCount', 0),
                'last_evaluated_key': response.get('LastEvaluatedKey'),
                'has_more': 'LastEvaluatedKey' in response
            }
        except ClientError as e:
            raise Exception(f"Failed to scan items: {str(e)}")
    
    def batch_get_items(self, keys: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Get multiple items by their keys"""
        try:
            response = self.client.batch_get_item(
                RequestItems={
                    settings.dynamodb_table: {
                        'Keys': keys
                    }
                }
            )
            
            items = response['Responses'].get(settings.dynamodb_table, [])
            return [self._deserialize_item(item) for item in items]
        except ClientError as e:
            raise Exception(f"Failed to batch get items: {str(e)}")
    
    def batch_write_items(self, items: List[Dict[str, Any]], operation: str = 'put') -> Dict[str, Any]:
        """Write multiple items in batch"""
        if operation not in ['put', 'delete']:
            raise ValueError("Operation must be 'put' or 'delete'")
        
        batch_items = []
        for item in items:
            if operation == 'put':
                batch_items.append({
                    'PutRequest': {
                        'Item': self._serialize_item(item)
                    }
                })
            else:  # delete
                batch_items.append({
                    'DeleteRequest': {
                        'Key': {
                            'pk': item['pk'],
                            'sk': item['sk']
                        }
                    }
                })
        
        # DynamoDB batch operations are limited to 25 items
        results = []
        for i in range(0, len(batch_items), 25):
            batch = batch_items[i:i+25]
            
            try:
                response = self.client.batch_write_item(
                    RequestItems={
                        settings.dynamodb_table: batch
                    }
                )
                results.append(response)
            except ClientError as e:
                raise Exception(f"Failed to batch write items: {str(e)}")
        
        return {'results': results}


# Global database client instance
db = DynamoDBClient() 