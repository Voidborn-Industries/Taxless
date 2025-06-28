import json
import os
import boto3
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Import shared modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.config import settings
from shared.database import db, DynamoKeys
from shared.ai_services import llm_service


def handler(event, context):
    """Batch analyze expenses for tax eligibility and optimization"""
    try:
        print("Starting batch expense analysis")
        
        # Get all unverified expenses from the last 30 days
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        
        result = db.scan_items(
            filter_expression="#is_verified = :is_verified AND #created_at >= :date_from",
            expression_attribute_names={
                "#is_verified": "is_verified",
                "#created_at": "created_at"
            },
            expression_attribute_values={
                ":is_verified": False,
                ":date_from": thirty_days_ago
            }
        )
        
        expenses = result['items']
        print(f"Found {len(expenses)} unverified expenses to analyze")
        
        processed_count = 0
        error_count = 0
        
        for expense in expenses:
            try:
                # Analyze expense for tax eligibility
                analysis_result = llm_service.analyze_expense_tax_eligibility(expense)
                
                # Update expense with analysis
                updates = {
                    'tax_eligibility': analysis_result['tax_eligibility'],
                    'is_verified': True,
                    'llm_analysis': analysis_result,
                    'analyzed_at': datetime.utcnow().isoformat()
                }
                
                # Update category if suggested
                if analysis_result.get('category_suggestion'):
                    updates['category'] = analysis_result['category_suggestion']
                
                db.update_item(
                    pk=expense['pk'],
                    sk=expense['sk'],
                    updates=updates
                )
                
                processed_count += 1
                print(f"Processed expense {expense['id']}")
                
            except Exception as e:
                error_count += 1
                print(f"Error processing expense {expense.get('id', 'unknown')}: {str(e)}")
                
                # Update expense with error
                try:
                    db.update_item(
                        pk=expense['pk'],
                        sk=expense['sk'],
                        updates={
                            'is_verified': False,
                            'llm_analysis': {
                                'error': str(e),
                                'processed_at': datetime.utcnow().isoformat()
                            }
                        }
                    )
                except Exception as update_error:
                    print(f"Error updating expense with error: {str(update_error)}")
        
        # Generate summary report
        summary = generate_summary_report()
        
        print(f"Batch analysis completed. Processed: {processed_count}, Errors: {error_count}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'processed_count': processed_count,
                'error_count': error_count,
                'summary': summary
            })
        }
        
    except Exception as e:
        print(f"Error in batch analysis: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


def generate_summary_report() -> Dict[str, Any]:
    """Generate a summary report of all expenses"""
    try:
        # Get all expenses from the current year
        current_year = datetime.now().year
        year_start = f"{current_year}-01-01T00:00:00"
        year_end = f"{current_year}-12-31T23:59:59"
        
        result = db.scan_items(
            filter_expression="#created_at BETWEEN :start_date AND :end_date",
            expression_attribute_names={"#created_at": "created_at"},
            expression_attribute_values={
                ":start_date": year_start,
                ":end_date": year_end
            }
        )
        
        expenses = result['items']
        
        # Calculate totals
        total_expenses = len(expenses)
        total_amount = sum(expense.get('amount', 0) for expense in expenses)
        
        # By category
        by_category = {}
        for expense in expenses:
            category = expense.get('category', 'OTHER')
            by_category[category] = by_category.get(category, 0) + expense.get('amount', 0)
        
        # By tax eligibility
        by_eligibility = {}
        for expense in expenses:
            eligibility = expense.get('tax_eligibility', 'REQUIRES_REVIEW')
            by_eligibility[eligibility] = by_eligibility.get(eligibility, 0) + expense.get('amount', 0)
        
        # By month
        by_month = {}
        for expense in expenses:
            try:
                date = datetime.fromisoformat(expense.get('created_at', ''))
                month_key = date.strftime('%Y-%m')
                by_month[month_key] = by_month.get(month_key, 0) + expense.get('amount', 0)
            except:
                pass
        
        # Flag potential issues
        flagged_expenses = []
        for expense in expenses:
            issues = []
            
            # Check for high amounts
            if expense.get('amount', 0) > 1000:
                issues.append("High amount - may need documentation")
            
            # Check for personal expenses
            if expense.get('tax_eligibility') == 'PERSONAL':
                issues.append("Marked as personal expense")
            
            # Check for unverified expenses
            if not expense.get('is_verified', False):
                issues.append("Not yet verified by AI")
            
            if issues:
                flagged_expenses.append({
                    'id': expense.get('id'),
                    'amount': expense.get('amount'),
                    'description': expense.get('description'),
                    'issues': issues
                })
        
        return {
            'year': current_year,
            'total_expenses': total_expenses,
            'total_amount': total_amount,
            'by_category': by_category,
            'by_eligibility': by_eligibility,
            'by_month': by_month,
            'flagged_expenses': flagged_expenses,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Error generating summary report: {str(e)}")
        return {
            'error': str(e),
            'generated_at': datetime.utcnow().isoformat()
        } 