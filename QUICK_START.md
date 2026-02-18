# Quick Start Guide

## Prerequisites

- Python 3.11+ installed
- Node.js 18+ installed
- MongoDB 6.0+ installed and running
- Azure OpenAI account with Vision API access
- 15 minutes setup time

## Step 1: Install MongoDB

**Windows:**
- Download MongoDB Community Server from https://www.mongodb.com/try/download/community
- Install and start MongoDB service:
  ```bash
  net start MongoDB
  ```

**Linux:**
```bash
sudo apt-get install mongodb
sudo systemctl start mongod
```

**macOS:**
```bash
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community
```

**Or use MongoDB Atlas (Cloud - Recommended):**
- Sign up at https://www.mongodb.com/cloud/atlas
- Create a free cluster
- Get connection string (e.g., `mongodb+srv://user:pass@cluster.mongodb.net/`)

## Step 2: Configure Azure OpenAI

1. Create an Azure OpenAI resource in Azure Portal
2. Deploy GPT-4 Vision model (deployment name: `gpt-4-vision`)
3. Get your endpoint and API key

## Step 3: Set Up Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env`:
```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision

MONGODB_URL=mongodb://localhost:27017
# Or for MongoDB Atlas:
# MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DB_NAME=underwriting_ocr

SECRET_KEY=change-this-in-production
```

Start the backend:
```bash
python -m uvicorn app.main:app --reload
```

Backend will run on http://localhost:8000

## Step 4: Set Up Frontend

Open a new terminal:

```bash
cd frontend
npm install
cp .env.example .env
```

Edit `frontend/.env`:
```env
REACT_APP_API_URL=http://localhost:8000/api/v1
```

Start the frontend:
```bash
npm start
```

Frontend will run on http://localhost:3000

## Step 4: Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Step 5: Test Upload

1. Go to http://localhost:3000/upload
2. Upload a test document (PDF, JPG, or PNG)
3. Wait for processing
4. View results in Documents page

## Step 5: Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Step 6: Test Upload

1. Go to http://localhost:3000/upload
2. Upload a test document (PDF, JPG, or PNG)
3. Wait for processing
4. View results in Documents page

## Troubleshooting

### MongoDB Connection Error

**Check if MongoDB is running:**
```bash
# Windows
net start MongoDB

# Linux
sudo systemctl status mongod

# macOS
brew services list
```

**Test MongoDB connection:**
```bash
mongosh
# or
mongo
```

**Common issues:**
- MongoDB service not started
- Wrong connection string in `.env`
- Firewall blocking port 27017

### Backend Not Starting

**Check Python version:**
```bash
python --version  # Should be 3.11+
```

**Install dependencies:**
```bash
cd backend
pip install -r requirements.txt
```

**Check if port 8000 is available:**
```bash
# Windows
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :8000
```

### Azure OpenAI API Error
- Verify API key and endpoint in `backend/.env`
- Check deployment name matches your Azure deployment
- Ensure you have quota available
- Verify API version is correct

### Frontend Not Loading
- Check if backend is running: http://localhost:8000/health
- Verify `REACT_APP_API_URL` in frontend `.env`
- Check browser console for errors
- Ensure backend CORS is configured correctly

### Port Already in Use

If port 8000 or 3000 is already in use:

**Backend (change port):**
```bash
python -m uvicorn app.main:app --reload --port 8001
```

**Frontend (change port):**
```bash
PORT=3001 npm start
```

## Running Services

You need to run these services in separate terminals:

**Terminal 1 - MongoDB:**
```bash
# If using local MongoDB
mongod --dbpath ./data/db
```

**Terminal 2 - Backend:**
```bash
cd backend
python -m uvicorn app.main:app --reload
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm start
```

## Next Steps

1. Review `ARCHITECTURE.md` for system design
2. Check `docs/API_DESIGN.md` for API usage
3. Read `docs/BUSINESS_WORKFLOW.md` for business rules
4. See `docs/DEPLOYMENT.md` for production deployment

