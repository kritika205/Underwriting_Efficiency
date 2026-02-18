"""
Customer Profile Models
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

class CustomerProfile(BaseModel):
    """Customer profile model matching the CSV structure"""
    customer_id: str = Field(..., description="Customer ID")
    full_name: str = Field(..., description="Full Name")
    father_name: Optional[str] = Field(None, description="Father's Name")
    gender: Optional[str] = Field(None, description="Gender")
    date_of_birth: Optional[str] = Field(None, description="Date of Birth")
    mobile_number: Optional[str] = Field(None, description="Mobile number")
    pan_number: Optional[str] = Field(None, description="PAN Number")
    aadhar_number: Optional[str] = Field(None, description="Aadhar Number")
    address: Optional[str] = Field(None, description="Address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State")
    pincode: Optional[str] = Field(None, description="Pincode")
    dl_number: Optional[str] = Field(None, description="DL Number")
    passport_number: Optional[str] = Field(None, description="Passport Number")
    cibil_score: Optional[float] = Field(None, description="CIBIL Score")
    existing_loan: Optional[str] = Field(None, description="Existing Loan")
    employment_type: Optional[str] = Field(None, description="Employment Type")
    employer_name: Optional[str] = Field(None, description="Employer Name")
    monthly_salary: Optional[float] = Field(None, description="Monthly Salary")
    gst_number: Optional[str] = Field(None, description="GST Number")
    annual_turnover: Optional[float] = Field(None, description="Annual Turnover")
    kyc_status: Optional[str] = Field(None, description="KYC Status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "234586500",
                "full_name": "Pinky Surajkumar Chourasiya",
                "father_name": "Surajkumar Chourasiya",
                "gender": "Female",
                "date_of_birth": "4/12/1993",
                "mobile_number": "8765767789",
                "pan_number": "EMMPS5338M",
                "aadhar_number": "8765 6765 9870",
                "address": "Andheri East",
                "city": "Mumbai",
                "state": "MH",
                "pincode": "400001",
                "dl_number": "MH1420119876543",
                "passport_number": "N1234567",
                "cibil_score": 742.0,
                "existing_loan": "No",
                "employment_type": "Salaried",
                "employer_name": "ABC Tech Pvt Ltd",
                "monthly_salary": 60000.0,
                "gst_number": "27ABCDE1234F1Z5",
                "annual_turnover": 1800000.0,
                "kyc_status": "Completed"
            }
        }


