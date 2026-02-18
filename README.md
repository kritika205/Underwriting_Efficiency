# Underwriting OCR Platform

Enterprise-grade document processing system using Azure OpenAI Vision for financial and identity document extraction.

## Features

- 📄 Multi-document upload support
- 🔍 Azure OpenAI Vision OCR
- 🏷️ Automatic document classification
- 📊 Structured JSON data extraction
- ✅ Business rule validation
- 📈 Quality scoring
- 🔐 Enterprise security

## Supported Document Types

- **Identity Documents**: Aadhaar, PAN, Passport, Driving License, Voter ID
- **Financial Documents**: GST Returns, ITR Forms, Payslips, Bank Statements
- **Business Documents**: Balance Sheet, Shop Registration, Business License
- **Credit Reports**: CIBIL, CRIF, Experian, Equifax
- **Loan Documents**: Loan Sanction Letter, EMI Schedule, Loan Agreement

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB 6.0+
- Azure OpenAI account with Vision API access
- Azure Blob Storage account (optional, can use local storage)

### Installation

#### Database Setup (MongoDB)

**Option 1: Install MongoDB locally**
- Download and install MongoDB from https://www.mongodb.com/try/download/community
- Start MongoDB service:
  ```bash
  # Windows
  net start MongoDB
  
  # Linux/Mac
  sudo systemctl start mongod
  # or
  mongod --dbpath ./data/db
  ```

**Option 2: Use MongoDB Atlas (Cloud)**
- Sign up at https://www.mongodb.com/cloud/atlas
- Create a free cluster
- Get connection string and update `MONGODB_URL` in backend `.env`

#### Backend Setup

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Azure OpenAI credentials and MongoDB URL
python -m uvicorn app.main:app --reload
```

**Or use the startup script:**
- Windows: `start-backend.bat`
- Linux/Mac: `./start-backend.sh`

The backend will run on http://localhost:8000

#### Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env
# Edit .env with API endpoint (default: http://localhost:8000/api/v1)
npm start
```

**Or use the startup script:**
- Windows: `start-frontend.bat`
- Linux/Mac: `./start-frontend.sh`

The frontend will run on http://localhost:3000

**Note:** You need to run backend and frontend in separate terminals.

## Project Structure

```
.
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Core configuration
│   │   ├── models/         # Database models
│   │   ├── services/       # Business logic
│   │   ├── utils/          # Utilities
│   │   └── prompts/        # OCR prompts
│   ├── tests/              # Unit tests
│   └── requirements.txt
├── frontend/                # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API services
│   │   ├── store/          # Redux store
│   │   └── utils/          # Utilities
│   └── package.json
├── docs/                    # Documentation
└── ARCHITECTURE.md          # Architecture details
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Environment Variables

### Backend (.env)

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision

MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=underwriting_ocr

AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_STORAGE_CONTAINER=documents

SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

REDIS_URL=redis://localhost:6379
```

### Frontend (.env)

```env
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_WS_URL=ws://localhost:8000/ws
```

## Usage Examples

### Upload Document

```bash
curl -X POST "http://localhost:8000/api/v1/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf" \
  -F "user_id=user123"
```

### Get Extraction Results

```bash
curl -X GET "http://localhost:8000/api/v1/extracted/{document_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## Deployment

See `docs/DEPLOYMENT.md` for detailed deployment instructions.

## License

Proprietary - All rights reserved

## Support

For issues and questions, contact the development team.

