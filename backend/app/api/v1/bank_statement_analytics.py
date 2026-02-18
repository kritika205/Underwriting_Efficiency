"""
Bank Statement Analytics API Endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.bank_statement_analytics_service import bank_statement_analytics_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/account/{account_number}")
async def analyze_by_account_number(account_number: str):
    """
    Analyze bank statement by account number
    
    - **account_number**: Account number to analyze
    """
    try:
        result = await bank_statement_analytics_service.analyze_bank_statement(
            account_number=account_number
        )
        return result
    except Exception as e:
        logger.error(f"Bank statement analytics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document/{document_id}")
async def analyze_by_document_id(document_id: str):
    """
    Analyze bank statement by document ID
    
    - **document_id**: Document ID of bank statement
    """
    try:
        result = await bank_statement_analytics_service.analyze_bank_statement(
            document_id=document_id
        )
        return result
    except Exception as e:
        logger.error(f"Bank statement analytics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}")
async def analyze_by_user_id(user_id: str):
    """
    Analyze bank statement by user ID
    
    - **user_id**: User ID to analyze
    """
    try:
        result = await bank_statement_analytics_service.analyze_bank_statement(
            user_id=user_id
        )
        return result
    except Exception as e:
        logger.error(f"Bank statement analytics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
