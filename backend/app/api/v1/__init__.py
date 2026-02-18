from fastapi import APIRouter
from . import documents, classify, ocr_extract, users, cross_validation, risk_analysis, applications, bank_statement_analytics, admin

router = APIRouter()

router.include_router(documents.router, prefix="/documents", tags=["Documents"])
router.include_router(classify.router, prefix="/classify", tags=["Classification"])
router.include_router(ocr_extract.router, prefix="/ocr-extract", tags=["OCR & Extraction"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(cross_validation.router, prefix="/cross-validate", tags=["Cross-Validation"])
router.include_router(risk_analysis.router, prefix="/risk-analysis", tags=["Risk Analysis"])
router.include_router(applications.router, prefix="/applications", tags=["Applications"])
router.include_router(bank_statement_analytics.router, prefix="/bank-statement-analytics", tags=["Bank Statement Analytics"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])





