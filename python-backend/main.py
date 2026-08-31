from fastapi import FastAPI, BackgroundTasks, HTTPException
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import uuid
import requests
from datetime import datetime
from scanner import (ScanRequest, insert_scan, update_scan, get_scan,
                     get_all_scans, delete_scan, run_all_scans, client)
from dotenv import load_dotenv
import re

# Load environment variables from the root folder
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("reports", exist_ok=True)
    # Start background scheduler
    import asyncio
    scheduler_task = asyncio.create_task(scheduler_loop())
    yield
    scheduler_task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"status": "online", "service": "WebSecureX Python Backend API", "version": "2.0.1"}

@app.get("/api/diag")
async def diagnostics():
    db_status = "unknown"
    mongo_uri = os.getenv("MONGO_URI", "not_set")
    masked_uri = re.sub(r':([^@]+)@', r':****@', mongo_uri) if mongo_uri else "none"
    try:
        await client.admin.command('ping')
        db_status = "connected"
    except Exception as e:
        db_status = f"connection_error: {str(e)}"
    
    return {
        "status": "online",
        "version": "2.0.1",
        "mongo_configured": bool(mongo_uri and mongo_uri != "not_set"),
        "mongo_uri_masked": masked_uri,
        "database_status": db_status
    }

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScheduleRequest(BaseModel):
    user_id: str
    url: str
    scan_type: str = "full"
    scan_level: str = "quick"
    interval_hours: int = 24
    scheduled_time: str = None # Format: "HH:MM" (24-hour)

# Mock DB for schedules for demo (Persistent in MongoDB in production)
schedules = []

async def scheduler_loop():
    from datetime import timedelta
    while True:
        try:
            now = datetime.now()
            for s in schedules:
                # If specific time is set, check if current HH:MM matches
                time_matches = True
                if s.get("scheduled_time"):
                    current_hm = now.strftime("%H:%M")
                    # If time matches and it hasn't run today (or within the last hour to prevent multiple triggers in the same minute)
                    if s["scheduled_time"] == current_hm:
                        if s.get("last_run") and (now - s["last_run"]).total_seconds() < 3600:
                            time_matches = False
                    else:
                        time_matches = False

                if s["next_run"] <= now or (s.get("scheduled_time") and time_matches):
                    scan_id = str(uuid.uuid4())
                    # Minimal scan doc for scheduler
                    doc = {
                        "scan_id": scan_id, "user_id": s["user_id"],
                        "target_url": s["url"], "scan_type": s["scan_type"],
                        "timestamp": now, "status": "pending", "progress": 0,
                        "current_phase": "Scheduled Auto-Scan", "overall_risk": "SAFE",
                        "summary": {"total_vulnerabilities": 0, "total_duration_seconds": 0},
                        "scans": {}, "scan_level": s["scan_level"], "hacker_mode": False
                    }
                    await insert_scan(doc)
                    # Trigger scan in background
                    asyncio.create_task(run_all_scans(s["url"], scan_id, s["scan_type"], s["user_id"], None, s["scan_level"], False))
                    
                    s["last_run"] = now
                    # If specific time, next_run is not primarily used, but we update it anyway
                    s["next_run"] = now + timedelta(hours=s["interval_hours"])
        except Exception as e:
            print(f"Scheduler Error: {e}")
        await asyncio.sleep(45) # Check often enough to catch HH:MM matches

@app.post("/api/schedule")
async def create_schedule(request: ScheduleRequest):
    from datetime import timedelta
    schedule_id = str(uuid.uuid4())
    doc = {
        "id": schedule_id, "user_id": request.user_id, "url": request.url,
        "scan_type": request.scan_type, "scan_level": request.scan_level,
        "interval_hours": request.interval_hours, "scheduled_time": request.scheduled_time, 
        "last_run": None,
        "next_run": datetime.now() + timedelta(hours=request.interval_hours)
    }
    schedules.append(doc)
    return {"status": "scheduled", "id": schedule_id}

@app.get("/api/schedules/{user_id}")
async def get_schedules(user_id: str):
    user_schedules = [s for s in schedules if s["user_id"] == user_id]
    return user_schedules

@app.post("/api/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    try:
        scan_id = str(uuid.uuid4())
        doc = {
            "scan_id": scan_id, "user_id": request.user_id,
            "target_url": request.url, "scan_type": request.scan_type,
            "timestamp": datetime.now(), "status": "pending", "progress": 0,
            "current_phase": "Queued", "overall_risk": "SAFE", 
            "summary": {"total_vulnerabilities": 0, "total_duration_seconds": 0}, 
            "scans": {"xss": {"status": "pending"}, "sqli": {"status": "pending"}, "nosql": {"status": "pending"}},
            "scan_level": request.scan_level,
            "hacker_mode": request.hacker_mode
        }
        await insert_scan(doc)
        background_tasks.add_task(run_all_scans, request.url, scan_id, request.scan_type, request.user_id, request.db_override, request.scan_level, request.hacker_mode)
        return {"scan_id": scan_id, "status": "started"}
    except Exception as e:
        print(f"Error starting scan: {e}")
        raise HTTPException(status_code=500, detail=f"Database/Scan startup error: {str(e)}")

@app.get("/api/scan/{scan_id}/stream")
async def stream_scan(scan_id: str):
    from fastapi.responses import StreamingResponse
    import asyncio
    from scanner import scan_logs

    async def event_generator():
        last_index = 0
        retry_count = 0
        while True:
            if scan_id in scan_logs:
                current_logs = scan_logs[scan_id]
                if last_index < len(current_logs):
                    for i in range(last_index, len(current_logs)):
                        line = current_logs[i]
                        yield f"data: {line}\n\n"
                        last_index = i + 1
                
                # Check if scan is finished
                if last_index > 0 and "[ SCAN COMPLETE ]" in current_logs[-1]:
                    break
            else:
                # Check DB if logs are gone or not started yet
                from scanner import get_scan
                res = await get_scan(scan_id)
                if res and res.get("status") in ["completed", "failed"]:
                    yield "data: [ SCAN LOGS ARCHIVED / COMPLETE ]\n\n"
                    yield "data: [ SCAN COMPLETE ]\n\n"
                    break
                
                retry_count += 1
                if retry_count > 60: # 30 seconds timeout
                    yield "data: [ STREAM TIMEOUT ]\n\n"
                    break
            
            await asyncio.sleep(0.5)
        
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/scan/{scan_id}/status")
async def get_status(scan_id: str):
    res = await get_scan(scan_id)
    if not res: raise HTTPException(status_code=404)
    return res

@app.get("/api/scan/{scan_id}/report")
async def get_report_json(scan_id: str):
    res = await get_scan(scan_id)
    if not res: raise HTTPException(status_code=404)
    return res

@app.get("/api/scans/{user_id}")
async def get_user_scans(user_id: str):
    return await get_all_scans(user_id)

@app.delete("/api/scan/{scan_id}")
async def remove_scan(scan_id: str):
    await delete_scan(scan_id)
    # Cleanup reports folder could be added here
    return {"status": "deleted"}

@app.get("/api/report/{scan_id}/html")
async def get_report_html(scan_id: str):
    path = f"reports/{scan_id}/report.html"
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Report not generated yet")


class IPCheckRequest(BaseModel):
    ip: str

@app.post("/api/check-ip")
async def check_ip(request: IPCheckRequest):
    api_key = os.getenv("ABUSEIPDB_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ABUSEIPDB_API_KEY not set in .env file")
    url = "https://api.abuseipdb.com/api/v2/check"
    
    headers = {
        'Accept': 'application/json',
        'Key': api_key
    }
    
    params = {
        'ipAddress': request.ip,
        'maxAgeInDays': '90'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()['data']
        
        score = data.get('abuseConfidenceScore', 0)
        status = "SAFE"
        if score > 50:
            status = "DANGEROUS"
        elif score >= 20:
            status = "SUSPICIOUS"
            
        return {
            "ipAddress": data.get('ipAddress'),
            "abuseConfidenceScore": score,
            "countryCode": data.get('countryCode'),
            "isp": data.get('isp'),
            "isWhitelisted": data.get('isWhitelisted'),
            "status": status
        }
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"IP Check Failed: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "ok"}

def test_ip_check():
    # Simple local test for IP 118.25.6.39
    print("Testing IP Check for 118.25.6.39...")
    # Note: This requires a real API key to work correctly
    pass

if __name__ == "__main__":
    import uvicorn
    # test_ip_check() # Uncomment to run test on startup
    uvicorn.run(app, host="127.0.0.1", port=8000)
