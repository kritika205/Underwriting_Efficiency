"""
Risk Analysis API Endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.risk_analysis_service import risk_analysis_service
from app.services.validation_service import validation_service
from app.services.user_aggregation_service import user_aggregation_service
from app.core.database import get_database
from app.models.document import DocumentType
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class RiskAnalysisRequest(BaseModel):
    document_id: str
    include_llm_reasoning: bool = True

class RiskAnalysisResponse(BaseModel):
    document_id: str
    document_type: str
    risk_score: float
    risk_level: str
    anomalies: Dict[str, Any]
    llm_reasoning: Optional[Dict[str, Any]] = None
    recommendations: list
    analysis_timestamp: str

@router.post("/", response_model=RiskAnalysisResponse)
async def analyze_risk(request: RiskAnalysisRequest):
    """
    Perform risk analysis on a document
    
    - **document_id**: Document identifier
    - **include_llm_reasoning**: Whether to include LLM reasoning (default: True)
    """
    try:
        # Get document from database
        db = await get_database()
        doc = await db.documents.find_one({"document_id": request.document_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get extraction result
        extraction = await db.extraction_results.find_one(
            {"document_id": request.document_id},
            sort=[("extraction_timestamp", -1)]
        )
        
        if not extraction:
            raise HTTPException(
                status_code=400,
                detail="Document has not been extracted yet. Please run OCR extraction first."
            )
        
        extracted_data = extraction["extracted_fields"]
        document_type = DocumentType(doc["document_type"])
        user_id = doc.get("user_id")
        application_id = doc.get("application_id")
        
        # Get validation result (re-validate if needed)
        validation_result = await validation_service.validate_extracted_data(
            extracted_data,
            document_type,
            user_id=user_id,
            validate_against_profile=True
        )
        
        # Get all user documents for cross-document analysis
        all_user_documents = None
        if user_id:
            try:
                all_user_documents = await user_aggregation_service.get_user_aggregation(user_id)
            except:
                logger.warning(f"Could not fetch user documents for cross-document analysis: {user_id}")
        
        # Perform risk analysis
        risk_result = await risk_analysis_service.analyze_risk(
            extracted_data=extracted_data,
            document_type=document_type,
            validation_result=validation_result,
            user_id=user_id,
            all_user_documents=all_user_documents,
            document_id=request.document_id
        )
        
        # Validate and prepare risk score for storage
        risk_score = risk_result["risk_score"]
        try:
            risk_score = float(risk_score)
            # Ensure risk score is in valid range
            risk_score = max(0.0, min(100.0, risk_score))
        except (ValueError, TypeError):
            logger.error(f"Invalid risk_score from analysis: {risk_result['risk_score']}, using 0")
            risk_score = 0.0
        
        risk_level = risk_result["risk_level"]
        # Ensure risk level is valid
        if risk_level not in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            logger.warning(f"Invalid risk_level: {risk_level}, defaulting to MEDIUM")
            risk_level = "MEDIUM"
        
        # Save risk analysis result to database
        risk_record = {
            "document_id": request.document_id,
            "user_id": user_id,
            "application_id": application_id,
            "document_type": document_type.value,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "anomalies": risk_result["anomalies"],
            "llm_reasoning": risk_result.get("llm_reasoning"),
            "recommendations": risk_result["recommendations"],
            "analysis_timestamp": risk_result["analysis_timestamp"]
        }
        
        # Store in risk_analyses collection
        await db.risk_analyses.insert_one(risk_record)
        
        # Update document with risk score
        await db.documents.update_one(
            {"document_id": request.document_id},
            {"$set": {
                "risk_score": risk_score,
                "risk_level": risk_level
            }}
        )
        
        logger.info(f"Risk analysis completed: {request.document_id}, Risk: {risk_level}, Score: {risk_score}")
        
        return RiskAnalysisResponse(
            document_id=request.document_id,
            document_type=document_type.value,
            risk_score=risk_score,
            risk_level=risk_level,
            anomalies=risk_result["anomalies"],
            llm_reasoning=risk_result.get("llm_reasoning"),
            recommendations=risk_result["recommendations"],
            analysis_timestamp=risk_result["analysis_timestamp"].isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Risk analysis failed: {str(e)}")

@router.get("/{document_id}")
async def get_risk_analysis(document_id: str):
    """Get risk analysis result for a document"""
    try:
        db = await get_database()
        
        # Get latest risk analysis
        risk_analysis = await db.risk_analyses.find_one(
            {"document_id": document_id},
            sort=[("analysis_timestamp", -1)]
        )
        
        if not risk_analysis:
            raise HTTPException(
                status_code=404,
                detail="Risk analysis not found. Please run risk analysis first."
            )
        
        risk_analysis.pop("_id", None)
        return risk_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get risk analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/application/{application_id}/summary")
async def get_application_risk_summary(application_id: str):
    """Get risk summary for all documents of an application"""
    try:
        db = await get_database()
        
        # First, get all documents for this application
        application_docs = await db.documents.find(
            {"application_id": application_id}
        ).to_list(length=None)
        
        if not application_docs:
            return {
                "application_id": application_id,
                "total_documents": 0,
                "average_risk_score": 0.0,
                "max_risk_score": 0.0,
                "weighted_risk_score": 0.0,
                "final_risk_score": 0.0,
                "risk_level_distribution": {},
                "total_anomalies": 0,
                "most_recent_analysis_timestamp": None,
                "risk_summary": {},
                "message": "No documents found for this application"
            }
        
        # Get document IDs
        document_ids = [doc["document_id"] for doc in application_docs]
        
        # Get all risk analyses for these documents (query by document_id to handle cases where application_id might not be set in risk_analyses)
        cursor = db.risk_analyses.find({"document_id": {"$in": document_ids}}).sort("analysis_timestamp", -1)
        analyses = await cursor.to_list(length=None)
        
        if not analyses:
            return {
                "application_id": application_id,
                "total_documents": len(document_ids),
                "average_risk_score": 0.0,
                "max_risk_score": 0.0,
                "weighted_risk_score": 0.0,
                "final_risk_score": 0.0,
                "risk_level_distribution": {},
                "total_anomalies": 0,
                "most_recent_analysis_timestamp": None,
                "risk_summary": {},
                "message": f"No risk analyses found for this application. {len(document_ids)} document(s) found but risk analysis not yet completed."
            }
        
        # Calculate summary statistics (same logic as user summary)
        total = len(analyses)
        risk_levels = {}
        avg_risk_score = 0.0
        max_risk_score = 0.0
        weighted_score = 0.0
        total_anomalies = 0
        
        total_critical_anomalies = 0
        total_high_anomalies = 0
        total_medium_anomalies = 0
        total_low_anomalies = 0

        for analysis in analyses:
            risk_level = analysis.get("risk_level", "UNKNOWN")
            risk_level = risk_level.upper() if risk_level else "UNKNOWN"
            risk_levels[risk_level] = risk_levels.get(risk_level, 0) + 1
            
            risk_score = analysis.get("risk_score", 0)
            try:
                risk_score = float(risk_score)
                risk_score = max(0.0, min(100.0, risk_score))
            except (ValueError, TypeError):
                risk_score = 0.0
            
            avg_risk_score += risk_score
            max_risk_score = max(max_risk_score, risk_score)
            
            anomalies = analysis.get("anomalies", {})
            if not isinstance(anomalies, dict):
                anomalies = {}
            
            critical_count = len(anomalies.get("critical_anomalies", []))
            high_count = len(anomalies.get("high_anomalies", []))
            medium_count = len(anomalies.get("medium_anomalies", []))
            low_count = len(anomalies.get("low_anomalies", []))
            
            total_critical_anomalies += critical_count
            total_high_anomalies += high_count
            total_medium_anomalies += medium_count
            total_low_anomalies += low_count
            
            anomaly_count = anomalies.get("anomaly_count")
            if anomaly_count is None or not isinstance(anomaly_count, (int, float)):
                anomaly_count = critical_count + high_count + medium_count + low_count
            
            anomaly_count = int(anomaly_count) if anomaly_count else 0
            total_anomalies += anomaly_count
        
        if total > 0:
            avg_risk_score = avg_risk_score / total
            avg_risk_score = round(max(0.0, min(100.0, avg_risk_score)), 2)
        else:
            avg_risk_score = 0.0
        
        if total_anomalies > 0:
            for analysis in analyses:
                risk_score = analysis.get("risk_score", 0)
                try:
                    risk_score = float(risk_score)
                    risk_score = max(0.0, min(100.0, risk_score))
                except (ValueError, TypeError):
                    risk_score = 0.0
                
                anomalies = analysis.get("anomalies", {})
                if not isinstance(anomalies, dict):
                    anomalies = {}
                
                anomaly_count = anomalies.get("anomaly_count")
                if anomaly_count is None or not isinstance(anomaly_count, (int, float)):
                    anomaly_count = (
                        len(anomalies.get("critical_anomalies", [])) +
                        len(anomalies.get("high_anomalies", [])) +
                        len(anomalies.get("medium_anomalies", [])) +
                        len(anomalies.get("low_anomalies", []))
                    )
                
                anomaly_count = int(anomaly_count) if anomaly_count else 0
                if total_anomalies > 0:
                    weight = anomaly_count / total_anomalies
                    weighted_score += risk_score * weight
        
        # Simplified: Use maximum document score as the application risk score
        # Individual document scores already include all severity points (60 for critical, 30 for high, etc.)
        # The worst document determines the application risk level - one critical document = critical application
        # This avoids double-counting and keeps the calculation simple and transparent
        final_risk_score = max_risk_score
        final_risk_score = round(final_risk_score, 2)
        
        logger.info(
            f"Application risk score calculation (simplified): "
            f"avg={avg_risk_score:.2f}, max={max_risk_score:.2f}, "
            f"final={final_risk_score:.2f} (using max document score), "
            f"anomalies(critical={total_critical_anomalies}, high={total_high_anomalies}, "
            f"medium={total_medium_anomalies}, low={total_low_anomalies}, total={total_anomalies})"
        )

        most_recent_timestamp = None
        if analyses and len(analyses) > 0:
            most_recent_timestamp = analyses[0].get("analysis_timestamp")
        
        analyses_list = []
        for a in analyses:
            a_anomalies = a.get("anomalies", {})
            if not isinstance(a_anomalies, dict):
                a_anomalies = {}
            
            a_anomaly_count = a_anomalies.get("anomaly_count")
            if a_anomaly_count is None or not isinstance(a_anomaly_count, (int, float)):
                a_anomaly_count = (
                    len(a_anomalies.get("critical_anomalies", [])) +
                    len(a_anomalies.get("high_anomalies", [])) +
                    len(a_anomalies.get("medium_anomalies", [])) +
                    len(a_anomalies.get("low_anomalies", []))
                )
            
            analyses_list.append({
                "document_id": a.get("document_id"),
                "document_type": a.get("document_type"),
                "risk_score": a.get("risk_score"),
                "risk_level": a.get("risk_level"),
                "anomaly_count": int(a_anomaly_count) if a_anomaly_count else 0
            })
        
        return {
            "application_id": application_id,
            "total_documents": total,
            "average_risk_score": round(avg_risk_score, 2),
            "max_risk_score": round(max_risk_score, 2),
            "weighted_risk_score": round(weighted_score, 2) if total_anomalies > 0 else round(avg_risk_score, 2),
            "final_risk_score": final_risk_score,
            "risk_level_distribution": risk_levels,
            "total_anomalies": total_anomalies,
            "anomalies_by_severity": {
                "critical": total_critical_anomalies,
                "high": total_high_anomalies,
                "medium": total_medium_anomalies,
                "low": total_low_anomalies
            },
            "most_recent_analysis_timestamp": most_recent_timestamp.isoformat() if most_recent_timestamp else None,
            "analyses": analyses_list
        }
        
    except Exception as e:
        logger.error(f"Failed to get application risk summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}/summary")
async def get_user_risk_summary(user_id: str):
    """Get risk summary for all documents of a user"""
    try:
        db = await get_database()
        
        # Get all risk analyses for user
        cursor = db.risk_analyses.find({"user_id": user_id}).sort("analysis_timestamp", -1)
        analyses = await cursor.to_list(length=None)
        
        if not analyses:
            return {
                "user_id": user_id,
                "total_documents": 0,
                "average_risk_score": 0.0,
                "max_risk_score": 0.0,
                "weighted_risk_score": 0.0,
                "final_risk_score": 0.0,
                "risk_level_distribution": {},
                "total_anomalies": 0,
                "most_recent_analysis_timestamp": None,
                "risk_summary": {},
                "message": "No risk analyses found for this user"
            }
        
        # Calculate summary statistics
        total = len(analyses)
        risk_levels = {}
        avg_risk_score = 0.0
        max_risk_score = 0.0  # Track maximum risk score across all documents
        weighted_score = 0.0  # Weighted average based on anomaly count
        total_anomalies = 0
        
        # Track anomalies by severity across all documents
        total_critical_anomalies = 0
        total_high_anomalies = 0
        total_medium_anomalies = 0
        total_low_anomalies = 0

        for analysis in analyses:
            risk_level = analysis.get("risk_level", "UNKNOWN")
            # Normalize risk level to uppercase for consistency
            risk_level = risk_level.upper() if risk_level else "UNKNOWN"
            risk_levels[risk_level] = risk_levels.get(risk_level, 0) + 1
            
            # Get risk score, ensuring it's a valid number
            risk_score = analysis.get("risk_score", 0)
            try:
                risk_score = float(risk_score)
                # Clamp to valid range (0-100)
                risk_score = max(0.0, min(100.0, risk_score))
            except (ValueError, TypeError):
                logger.warning(f"Invalid risk_score in analysis: {risk_score}, using 0")
                risk_score = 0.0
            
            avg_risk_score += risk_score
            max_risk_score = max(max_risk_score, risk_score)  # Track maximum
            
            # Get anomalies object, ensure it's a dict
            anomalies = analysis.get("anomalies", {})
            if not isinstance(anomalies, dict):
                anomalies = {}
            
            # Count anomalies by severity
            critical_count = len(anomalies.get("critical_anomalies", []))
            high_count = len(anomalies.get("high_anomalies", []))
            medium_count = len(anomalies.get("medium_anomalies", []))
            low_count = len(anomalies.get("low_anomalies", []))
            
            total_critical_anomalies += critical_count
            total_high_anomalies += high_count
            total_medium_anomalies += medium_count
            total_low_anomalies += low_count
            
            # Calculate anomaly_count - prefer stored value, otherwise calculate from lists
            anomaly_count = anomalies.get("anomaly_count")
            if anomaly_count is None or not isinstance(anomaly_count, (int, float)):
                # Calculate from anomaly lists if count is missing or invalid
                anomaly_count = critical_count + high_count + medium_count + low_count
            
            anomaly_count = int(anomaly_count) if anomaly_count else 0
            total_anomalies += anomaly_count
        
        # Calculate average risk score
        if total > 0:
            avg_risk_score = avg_risk_score / total
            # Round to 2 decimal places and clamp to valid range
            avg_risk_score = round(max(0.0, min(100.0, avg_risk_score)), 2)
        else:
            avg_risk_score = 0.0
        
        # Calculate weighted risk score (documents with more anomalies contribute more)
        # Re-iterate to calculate weighted average
        if total_anomalies > 0:
            for analysis in analyses:
                risk_score = analysis.get("risk_score", 0)
                try:
                    risk_score = float(risk_score)
                    risk_score = max(0.0, min(100.0, risk_score))
                except (ValueError, TypeError):
                    risk_score = 0.0
                
                anomalies = analysis.get("anomalies", {})
                if not isinstance(anomalies, dict):
                    anomalies = {}
                
                anomaly_count = anomalies.get("anomaly_count")
                if anomaly_count is None or not isinstance(anomaly_count, (int, float)):
                    anomaly_count = (
                        len(anomalies.get("critical_anomalies", [])) +
                        len(anomalies.get("high_anomalies", [])) +
                        len(anomalies.get("medium_anomalies", [])) +
                        len(anomalies.get("low_anomalies", []))
                    )
                
                anomaly_count = int(anomaly_count) if anomaly_count else 0
                if total_anomalies > 0:
                    weight = anomaly_count / total_anomalies
                    weighted_score += risk_score * weight
        
        # Simplified: Use maximum document score as the application risk score
        # Individual document scores already include all severity points (60 for critical, 30 for high, etc.)
        # The worst document determines the application risk level
        # This avoids double-counting and keeps the calculation simple and transparent
        final_risk_score = max_risk_score
        final_risk_score = round(final_risk_score, 2)
        
        logger.info(
            f"User risk score calculation (simplified): "
            f"avg={avg_risk_score:.2f}, max={max_risk_score:.2f}, "
            f"final={final_risk_score:.2f} (using max document score), "
            f"anomalies(critical={total_critical_anomalies}, high={total_high_anomalies}, "
            f"medium={total_medium_anomalies}, low={total_low_anomalies}, total={total_anomalies})"
        )

        logger.info(
            f"Risk score calculation for user {user_id}: "
            f"avg={avg_risk_score:.2f}, max={max_risk_score:.2f}, "
            f"base_final={base_final_score:.2f}, severity_points={severity_points:.2f}, "
            f"final={final_risk_score:.2f}, "
            f"anomalies(critical={total_critical_anomalies}, high={total_high_anomalies}, "
            f"medium={total_medium_anomalies}, low={total_low_anomalies}, total={total_anomalies})"
        )
        
        # Get the most recent analysis timestamp (first one since sorted desc)
        most_recent_timestamp = None
        if analyses and len(analyses) > 0:
            most_recent_timestamp = analyses[0].get("analysis_timestamp")
        
        # Build analyses list with proper anomaly_count calculation
        analyses_list = []
        for a in analyses:
            a_anomalies = a.get("anomalies", {})
            if not isinstance(a_anomalies, dict):
                a_anomalies = {}
            
            a_anomaly_count = a_anomalies.get("anomaly_count")
            if a_anomaly_count is None or not isinstance(a_anomaly_count, (int, float)):
                # Calculate from lists if count is missing or invalid
                a_anomaly_count = (
                    len(a_anomalies.get("critical_anomalies", [])) +
                    len(a_anomalies.get("high_anomalies", [])) +
                    len(a_anomalies.get("medium_anomalies", [])) +
                    len(a_anomalies.get("low_anomalies", []))
                )
            
            analyses_list.append({
                "document_id": a.get("document_id"),
                "document_type": a.get("document_type"),
                "risk_score": a.get("risk_score"),
                "risk_level": a.get("risk_level"),
                "anomaly_count": int(a_anomaly_count) if a_anomaly_count else 0
            })
        
        return {
            "user_id": user_id,
            "total_documents": total,
            "average_risk_score": round(avg_risk_score, 2),
            "max_risk_score": round(max_risk_score, 2),
            "weighted_risk_score": round(weighted_score, 2) if total_anomalies > 0 else round(avg_risk_score, 2),
            "final_risk_score": final_risk_score,  # This is the improved score that accounts for anomaly count
            "risk_level_distribution": risk_levels,
            "total_anomalies": total_anomalies,
            "anomalies_by_severity": {
                "critical": total_critical_anomalies,
                "high": total_high_anomalies,
                "medium": total_medium_anomalies,
                "low": total_low_anomalies
            },
            "most_recent_analysis_timestamp": most_recent_timestamp.isoformat() if most_recent_timestamp else None,
            "analyses": analyses_list
        }
        
    except Exception as e:
        logger.error(f"Failed to get user risk summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

