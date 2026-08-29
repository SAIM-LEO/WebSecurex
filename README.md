# WebSecureX - Full-Stack Security Auditor

WebSecureX is an advanced website security auditing platform designed to detect XSS, SQL Injection, and NoSQL Injection vulnerabilities using a multi-service architecture.

## Architecture

- **Node.js Frontend (Express):** Handles user authentication (JWT), scan history, and UI dashboard. (Port 3000)
- **Python Backend (FastAPI):** Orchestrates security tools (XSStrike, sqlmap, NoSQLMap) and performs database detection. (Port 8000)
- **Database:** MongoDB (User data and scan results).

## Prerequisites

- Node.js & npm
- Python 3.8+
- MongoDB (Running on `localhost:27017`)
- Vulnerability Tools: Ensure `XSStrike`, `sqlmap`, and `NoSQLMap` are in the root directory.

## Setup & Running

### 1. Database (MongoDB)
Start MongoDB on default port `27017`:
```powershell
# Option A: Using Docker (Recommended - No Admin needed)
docker run -d --name websecurex-mongo -p 27017:27017 mongo:latest

# Option B: Windows Service (Requires Administrator Terminal)
Start-Service MongoDB
# or: net start MongoDB

# Option C: Direct mongod CLI (No Admin required)
mongod --dbpath "C:\data\db"
```

### 2. Security Engines (Modular Deployment)
```bash
# Install XSS Engine
cd engines/xss_engine
pip install -r requirements.txt

# Install SQLi Engine
cd ../sqli_engine
pip install -r requirements.txt

# Install NoSQL Engine
cd ../nosql_engine
pip install -r requirements.txt
```

### 3. Python Backend
```bash
cd python-backend
pip install -r requirements.txt
python main.py
```

### 4. Node Frontend
```bash
cd node-frontend
npm install
node server.js
```

### 5. Usage
Open `http://localhost:3000` in your browser. Login/Signup and enter a target URL to begin auditing.

## Disclaimer
This tool is for educational and authorized security testing purposes only. Unauthorized scanning of websites is illegal.
