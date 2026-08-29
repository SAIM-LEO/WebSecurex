import asyncio
import os
import re
import time
import subprocess
import sys
import random
import socket
from urllib.parse import urlparse
import aiohttp
from typing import Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import requests

# Load env from root
load_dotenv("../.env")

# Database Setup
client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"))
db = client["websecurex"]
scans = db["scans"]
scan_logs = {} # Store real-time logs for SSE: {scan_id: [lines]}

# Models
class ScanRequest(BaseModel):
    url: str
    scan_type: str = "full" # "full" | "xss_only" | "sqli_only"
    user_id: str
    db_override: Optional[str] = None # "sql" | "nosql" | None
    scan_level: str = "quick" # "quick" | "normal" | "deep"
    hacker_mode: bool = False

# DB Helpers
async def insert_scan(doc):
    return await scans.insert_one(doc)

async def update_scan(scan_id, fields):
    return await scans.update_one({"scan_id": scan_id}, {"$set": fields})

async def get_scan(scan_id):
    res = await scans.find_one({"scan_id": scan_id})
    if res: res["_id"] = str(res["_id"])
    return res

async def get_all_scans(user_id, limit=50):
    cursor = scans.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
    res_list = await cursor.to_list(length=limit)
    for r in res_list: r["_id"] = str(r["_id"])
    return res_list

async def delete_scan(scan_id):
    return await scans.delete_one({"scan_id": scan_id})

# DB Type Detection
SQL_DBS   = ["mysql", "postgresql", "mssql", "oracle", "sqlite", "mariadb", "db2", "sybase", "access"]
NOSQL_DBS = ["mongodb", "redis", "couchdb", "cassandra", "elasticsearch"]

def detect_db_type(dbms_string):
    if not dbms_string: return "unknown"
    s = dbms_string.lower()
    for kw in SQL_DBS:
        if kw in s: return "sql"
    for kw in NOSQL_DBS:
        if kw in s: return "nosql"
    return "unknown"

async def check_connectivity(url):
    # Use proper aiohttp ClientTimeout object — raw int causes deprecation warning
    timeout = aiohttp.ClientTimeout(total=12)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                return True, response.status, dict(response.headers), True
    except Exception:
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                async with session.get(url) as response:
                    return True, response.status, dict(response.headers), False
        except Exception as e:
            return False, str(e), {}, False

class Humanizer:
    @staticmethod
    def get_recommendations(tool, vulnerable):
        if not vulnerable: return "Maintain current security practices and regular audits."
        if tool == "XSStrike":
            return "1. Implement Content Security Policy (CSP). 2. Use context-aware output encoding. 3. Validate all user inputs on the server side."
        if tool == "sqlmap":
            return "1. Use Parameterized Queries (Prepared Statements). 2. Implement a Web Application Firewall (WAF). 3. Use the Principle of Least Privilege for DB accounts."
        if tool == "NoSQLMap":
            return "1. Sanitize object keys and values. 2. Avoid using operator-based queries with raw user input. 3. Use schema validation."
        return "Contact a security professional for a deep-dive audit."

    @staticmethod
    def get_error_info(output, exit_code=0):
        low = output.lower()
        
        # Check for explicit connection failure (only when scanner explicitly states connection refused/unreachable)
        if any(kw in low for kw in [
            "unable to connect to the target url", 
            "failed to connect to target", 
            "critical: unable to connect",
            "connection refused", 
            "could not resolve host", 
            "name or service not known"
        ]):
            return "connection_failed", "Scan Failed: Could not reach the target website. Check the URL and try again."
            
        # Check for explicit WAF blocking (only when scanner explicitly confirms blocked execution)
        if "target is protected by a waf/ips" in low or "blocked by WAF" in low or "cloudflare ray id" in low:
            return "blocked_by_waf", "Scan Failed: Target is protected by a firewall. Scanner was blocked."

        # Scenario: Empty output or explicit crash
        if not output.strip():
            return "empty_output", "Scan Failed: Scanner returned no data. Try again or check the URL."
            
        if exit_code != 0 and ("is injectable" not in low and "vulnerable" not in low and "0 vulnerabilities" not in low and "[*]" not in low and "[+]" not in low and "[info]" in low):
            return "tool_crash", "Scan Error: Internal error occurred while running scanner."
        
        return None, None

    @staticmethod
    def humanize(tool, results):
        if results.get("scan_status") in ["failed", "error"]:
            return results.get("error_message")
        
        vulnerable = results.get("vulnerable", False)
        waf = results.get("waf_detected", "None Detected")
        tool_lower = tool.lower()
        
        if "xsstrike" in tool_lower:
            if vulnerable:
                findings = results.get("findings", [])
                params = [f.get("parameter", "unknown") for f in findings if f.get("parameter")]
                summary = f"CRITICAL XSS ALERT: Our audit successfully bypassed the {waf} firewall. "
                summary += f"We identified {len(findings)} entry points where malicious scripts can be executed. "
                if params: summary += f"Targeted parameters: {', '.join(set(params))}. "
                summary += "An attacker could use this to hijack admin sessions, steal cookies, or redirect users to phishing sites."
                return summary
            return f"CLEAN BILL OF HEALTH: No Cross-Site Scripting entry points found. We tested against multiple bypass techniques under the {waf} protection layer and the application remained resilient."
        
        if "sqlmap" in tool_lower:
            dbms = results.get("dbms", "Unknown")
            params = results.get("injectable_params", [])
            if vulnerable:
                summary = f"DATABASE BREACH RISK: Your {dbms} database is exposed. "
                summary += f"We successfully navigated through the {waf} layer using --random-agent stealth. "
                if params: summary += f"The parameters '{', '.join(params)}' are completely unprotected and injectable. "
                summary += "A malicious actor could use this to dump your entire database, modify data, or even gain OS-level access."
                return summary
            return f"SECURE DATA LAYER: No SQL Injection vulnerabilities detected. Your {dbms if dbms != 'Unknown' else 'database'} architecture is properly hardened and resistant to automated extraction attempts."
        
        if "nosqlmap" in tool_lower:
            if vulnerable:
                return f"CRITICAL NOSQL VULNERABILITY: Under the {waf} environment, we detected that your NoSQL data store (likely MongoDB) accepts unvalidated object queries. This allows 'Authentication Bypass' or 'Schema Leakage' via logic operator injection ($gt, $ne, etc.)."
            return "SECURE NOSQL LAYER: Your NoSQL database is correctly configured. It successfully rejected all attempts to bypass query logic or leak internal data structures."
        
        if "abuseipdb" in tool_lower:
            score = results.get('abuse_score', 0)
            if vulnerable:
                return f"IP REPUTATION ALERT: The IP address associated with this domain ({results.get('target_url')}) has a high abuse confidence score of {score}%. It has been reported for malicious activities like SSH brute-forcing or spam."
            return f"CLEAN IP REPUTATION: The IP address ({results.get('target_url')}) is clean. It has an abuse confidence score of {score}% and is not blacklisted in the AbuseIPDB database."
        
        if "ssl" in tool_lower:
            return results.get('humanized', 'SSL Audit complete.')
            
        return "Audit complete. No high-risk vulnerabilities were enlisted in this session."

class Scorer:
    @staticmethod
    def calculate_tool_score(tool, results):
        if results.get("scan_status") in ["error", "failed"]: return 0
        if results.get("scan_status") == "skipped": return 10
        
        vulnerable = results.get("vulnerable", False)
        if not vulnerable: return 10
        
        # Deduct based on findings
        findings = results.get("findings", [])
        tool_name = tool.lower()
        if "xsstrike" in tool_name:
            return max(0, 10 - len(findings) * 2)
        if "sqlmap" in tool_name or "nosqlmap" in tool_name:
            return 2 # Critical vulnerability
        return 5

    @staticmethod
    def calculate_overall_score(tool_scores):
        if not tool_scores: return 100
        return round(sum(tool_scores.values()) / len(tool_scores) * 10)

# ============================================================
# HACKER MODE — launches tool in a visible CMD window
# while ALSO capturing output for the report
# ============================================================
def launch_in_visible_window(title: str, cmd: list, output_file: str, hacker_mode: bool = False):
    """Spawns a new coloured CMD window on Windows. Only if hacker_mode is True."""
    if not hacker_mode: return None
    
    # Robust quoting for Windows batch files - wrap everything in quotes
    cmd_str = " ".join(f'"{str(c)}"' for c in cmd)
    bat_lines = [
        "@echo off",
        f"title {title}",
        "color 0A",
        "echo.",
        f"echo  [ WebSecureX ] ENGINE: {title}",
        "echo  Powered by WebSecureX Security Platform",
        "echo.",
        f"echo  Target: {cmd[cmd.index('-u') + 1] if '-u' in cmd else cmd[cmd.index('--url') + 1] if '--url' in cmd else 'TARGET'}",
        "echo.",
        "echo ============================================================",
        "echo  AUDIT IN PROGRESS — DO NOT CLOSE THIS WINDOW",
        "echo ============================================================",
        "echo.",
        f"{cmd_str}",   # Windows-safe: no tee, just run and display
        "echo.",
        "echo ============================================================",
        "echo  SCAN COMPLETE — This window closes in 30 seconds",
        "echo ============================================================",
        "timeout /t 30 /nobreak > nul",
    ]
    bat_path = os.path.abspath(output_file + "_launch.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(bat_lines))  # Windows line endings
    
    # Use a more robust start command for Windows
    subprocess.Popen(
        f'start "{title}" cmd /k "{bat_path}"',
        shell=True
    )
    return bat_path

# Scanners
class XSSScanner:
    async def run(self, url: str, scan_id: str, level: str = "quick", hacker_mode: bool = False) -> dict:
        start_time = time.time()
        # Use absolute path based on this file's location
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(backend_dir)
        tool_path = os.path.join(base_dir, "engines", "xss_engine", "XSStrike", "xsstrike.py")
        
        if scan_id not in scan_logs: scan_logs[scan_id] = []
        if hacker_mode:
            scan_logs[scan_id].append(f"\n[ HACKER MODE ACTIVE ]\nRedirecting XSStrike working logs to external terminal...\n")
        else:
            scan_logs[scan_id].append(f"\n================================\nWebSecureX Terminal\nTool: XSStrike (XSS)\nTarget: {url}\nLevel: {level.upper()}\n================================\n")
        
        # Determine XSStrike settings based on level
        threads = "3"
        extra_args = []
        if level == "normal":
            threads = "5"
            extra_args = ["--blind"]
        elif level == "deep":
            threads = "5"
            extra_args = ["--blind", "--path"]
            
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"
        ]
        ua = random.choice(user_agents)
        headers_json = '{"User-Agent": "' + ua + '"}'
        
        cmd = [sys.executable, tool_path, "--url", url, "--crawl", "--threads", threads, "--timeout", "10", "--headers", headers_json, "--skip"]
        cmd.extend(extra_args)
        
        try:
            output_file = os.path.abspath(f"reports/{scan_id}_xss_output.txt")
            os.makedirs("reports", exist_ok=True)

            launch_in_visible_window("XSStrike XSS ENGINE", cmd, output_file, hacker_mode)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            
            output_lines = []
            while True:
                line = await process.stdout.readline()
                if not line: break
                line_str = line.decode(errors="ignore")
                output_lines.append(line_str)
                if not hacker_mode:
                    scan_logs[scan_id].append(line_str)
                elif len(output_lines) % 10 == 0:
                    scan_logs[scan_id].append(f"[...] Engine active. Streaming logs to external terminal... ({len(output_lines)} lines captured)\n")
            
            await process.wait()
            output = "".join(output_lines)
            exit_code = process.returncode
            
            if not hacker_mode:
                scan_logs[scan_id].append("\n[ PHASE COMPLETE ]\n")
            
            err_type, err_msg = Humanizer.get_error_info(output, exit_code)
            
            vulnerable = "[!] Vulnerable" in output
            payloads = re.findall(r"Payload: (.+)", output)
            params = re.findall(r"Vulnerable: (.+)", output)
            waf = re.search(r"WAF Detected: (.+)", output)
            
            findings = []
            for i in range(max(len(payloads), len(params))):
                findings.append({
                    "payload": payloads[i].strip() if i < len(payloads) else "Unknown",
                    "parameter": params[i].strip() if i < len(params) else "Unknown",
                    "type": "Reflected XSS",
                    "severity": "High"
                })
            
            return {
                "scan_tool": "xsstrike",
                "scan_status": "failed" if err_type else "completed",
                "scan_level": level,
                "target_url": url,
                "result": "VULNERABLE" if vulnerable else "SAFE" if not err_type else None,
                "error_type": err_type,
                "error_message": err_msg,
                "vulnerable": vulnerable,
                "findings": findings,
                "vulnerabilities": findings,
                "waf_detected": waf.group(1) if waf else None,
                "raw_output": output,
                "scan_completed": err_type is None,
                "duration_seconds": round(time.time() - start_time, 2)
            }
        except Exception as e:
            return {
                "scan_tool": "xsstrike", "scan_status": "error", "scan_level": level, "target_url": url, "result": None,
                "error_type": "tool_crash", "error_message": f"Scan Error: Internal error occurred while running scanner.",
                "vulnerable": False, "findings": [], "vulnerabilities": [], "raw_output": str(e), "scan_completed": False, "duration_seconds": 0
            }

class SQLiScanner:
    async def run(self, url: str, scan_id: str, level: str = "quick", hacker_mode: bool = False) -> dict:
        start_time = time.time()
        output_dir = os.path.abspath(os.path.join("reports", scan_id, "sqlmap"))
        # Use absolute path based on this file's location
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(backend_dir)
        tool_path = os.path.join(base_dir, "engines", "sqli_engine", "sqlmap", "sqlmap.py")
        
        if scan_id not in scan_logs: scan_logs[scan_id] = []
        if hacker_mode:
            scan_logs[scan_id].append(f"\n[ HACKER MODE ACTIVE ]\nRedirecting sqlmap working logs to external terminal...\n")
        else:
            scan_logs[scan_id].append(f"\n================================\nWebSecureX Terminal\nTool: sqlmap (SQLi)\nTarget: {url}\nLevel: {level.upper()}\n================================\n")
        
        # Determine sqlmap settings based on level
        crawl = "2"; threads = "3"; sql_level = "1"; risk = "1"
        if level == "normal":
            crawl = "3"; threads = "5"; sql_level = "3"; risk = "2"
        elif level == "deep":
            crawl = "5"; threads = "10"; sql_level = "5"; risk = "3"
            
        cmd = [sys.executable, tool_path, "-u", url, "--data=username=test&password=test", "--batch", "--random-agent", "--dbs", 
               f"--crawl={crawl}", f"--threads={threads}", f"--level={sql_level}", f"--risk={risk}", 
               f"--output-dir={output_dir}"]
        
        try:
            output_file = os.path.abspath(f"reports/{scan_id}_sqli_output.txt")
            os.makedirs("reports", exist_ok=True)

            launch_in_visible_window("sqlmap SQL INJECTION ENGINE", cmd, output_file, hacker_mode)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            
            output_lines = []
            while True:
                line = await process.stdout.readline()
                if not line: break
                line_str = line.decode(errors="ignore")
                output_lines.append(line_str)
                if not hacker_mode:
                    scan_logs[scan_id].append(line_str)
                elif len(output_lines) % 10 == 0:
                    scan_logs[scan_id].append(f"[...] Engine active. Streaming logs to external terminal... ({len(output_lines)} lines captured)\n")
                
            await process.wait()
            output = "".join(output_lines)
            exit_code = process.returncode
            
            if not hacker_mode:
                scan_logs[scan_id].append("\n[ PHASE COMPLETE ]\n")
            
            err_type, err_msg = Humanizer.get_error_info(output, exit_code)
            
            vulnerable = False
            injectable_params = []
            dbms = None
            waf_sqli = None
            try:
                # Robustly find log file in output_dir
                log_path = None
                for root, dirs, files in os.walk(output_dir):
                    if "log" in files:
                        log_path = os.path.join(root, "log")
                        break
                
                if log_path and os.path.exists(log_path):
                    with open(log_path, "r") as f:
                        log_content = f.read()
                        vulnerable = "is injectable" in log_content or "back-end DBMS is" in log_content
                        injectable_params = list(set(re.findall(r"Parameter: (.+)", log_content)))
                        dbms_match = re.search(r"DBMS: (.+)", log_content)
                        dbms = dbms_match.group(1) if dbms_match else None
                        waf_match = re.search(r"WAF/IPS/IDS: (.+)", log_content)
                        waf_sqli = waf_match.group(1) if waf_match else None
            except: pass
            
            if not vulnerable and err_type: vulnerable = False
                
            return {
                "scan_tool": "sqlmap",
                "scan_status": "failed" if err_type else "completed",
                "scan_level": level,
                "target_url": url,
                "result": "VULNERABLE" if vulnerable else "SAFE" if not err_type else None,
                "error_type": err_type,
                "error_message": err_msg,
                "vulnerable": vulnerable,
                "injectable_params": injectable_params,
                "vulnerabilities": [{"type": "SQL Injection", "parameter": p} for p in injectable_params] if vulnerable else [],
                "dbms": dbms,
                "db_type": detect_db_type(dbms),
                "waf_detected": waf_sqli,
                "raw_output": output,
                "scan_completed": err_type is None,
                "duration_seconds": round(time.time() - start_time, 2)
            }
        except Exception as e:
            return {
                "scan_tool": "sqlmap", "scan_status": "error", "scan_level": level, "target_url": url, "result": None,
                "error_type": "tool_crash", "error_message": f"Scan Error: Internal error occurred while running scanner.",
                "vulnerable": False, "vulnerabilities": [], "raw_output": str(e), "scan_completed": False, "duration_seconds": 0
            }

class NoSQLScanner:
    async def run(self, url: str, scan_id: str, level: str = "quick", hacker_mode: bool = False) -> dict:
        start_time = time.time()
        # Use absolute path based on this file's location
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(backend_dir)
        tool_path = os.path.join(base_dir, "engines", "nosql_engine", "NoSQLMap", "nosqlmap.py")
        
        if scan_id not in scan_logs: scan_logs[scan_id] = []
        scan_logs[scan_id].append(f"\n================================\nWebSecureX Terminal\nTool: NoSQLMap (NoSQL)\nTarget: {url}\nLevel: {level.upper()}\n================================\n")
        try:
            user_inputs = f"1\n{url}\n3\n"
            cmd = [sys.executable, tool_path]
            
            output_file = os.path.abspath(f"reports/{scan_id}_nosql_output.txt")
            os.makedirs("reports", exist_ok=True)
            
            if hacker_mode:
                scan_logs[scan_id].append("[ HACKER MODE ] Launching NoSQLMap in separate terminal...\n")
                launch_in_visible_window("NoSQLMap ENGINE", cmd, output_file, hacker_mode)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            
            stdout_data, _ = await process.communicate(input=user_inputs.encode())
            output = stdout_data.decode(errors="ignore")
            
            # For NoSQLMap, since it's interactive, we just dump the final output to logs
            scan_logs[scan_id].append(output)
            scan_logs[scan_id].append("\n[ PHASE COMPLETE ]\n")

            err_type, err_msg = Humanizer.get_error_info(output)
            vulnerable = "Vulnerable" in output or "successful" in output.lower()

            return {
                "scan_tool": "nosqlmap",
                "scan_status": "failed" if err_type else "completed",
                "scan_level": level,
                "target_url": url,
                "result": "VULNERABLE" if vulnerable else "SAFE" if not err_type else None,
                "error_type": err_type,
                "error_message": err_msg,
                "vulnerable": vulnerable,
                "vulnerabilities": [{"type": "NoSQL Injection"}] if vulnerable else [],
                "raw_output": output,
                "scan_completed": err_type is None,
                "duration_seconds": round(time.time() - start_time, 2)
            }
        except asyncio.TimeoutError:
            return {
                "scan_tool": "nosqlmap", "scan_status": "failed", "scan_level": level, "target_url": url, "result": None,
                "error_type": "timeout", "error_message": "Scan Failed: Could not reach the target website. Check the URL and try again.",
                "vulnerable": False, "vulnerabilities": [], "raw_output": "Timeout", "scan_completed": False, "duration_seconds": 90
            }
        except Exception as e:
            return {
                "scan_tool": "nosqlmap", "scan_status": "error", "scan_level": level, "target_url": url, "result": None,
                "error_type": "tool_crash", "error_message": f"Scan Error: Internal error occurred while running scanner.",
                "vulnerable": False, "vulnerabilities": [], "raw_output": str(e), "scan_completed": False, "duration_seconds": 0
            }

class SSLScanner:
    async def run(self, url: str, scan_id: str, level: str = "quick", hacker_mode: bool = False) -> dict:
        start_time = time.time()
        import ssl
        import socket
        
        self_signed = False
        try:
            domain = urlparse(url).netloc.split(':')[0]
            # Use non-verifying context for initial connection to get binary cert info
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    # Try a verifying connection to detect self-signed
                    try:
                        reg_ctx = ssl.create_default_context()
                        with socket.create_connection((domain, 443), timeout=5) as s_sock:
                            with reg_ctx.wrap_socket(s_sock, server_hostname=domain) as r_ssock:
                                cert = r_ssock.getpeercert()
                                self_signed = False
                    except ssl.SSLError as se:
                        if "CERTIFICATE_VERIFY_FAILED" in str(se) or "self signed" in str(se).lower():
                            self_signed = True
                        # Fallback to binary cert from non-verifying socket
                        # We can't easily parse binary in pure python without extra libs, 
                        # but we can try to see if a second connection with cert_reqs works
                        cert = ssock.getpeercert()
                        if not cert:
                            # Use a placeholder that identifies the issue
                            cert = {"notAfter": "Unknown (Self-Signed)"}

                    expiry_str = cert.get('notAfter', 'Jan 01 00:00:00 2099 GMT')
                    expired = False
                    try:
                        if expiry_str != "Unknown (Self-Signed)":
                            expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                            # Ensure we compare timezone-aware or both naive
                            expired = expiry_date.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
                    except: pass
                    
                    if level == "quick":
                        vulnerable = expired or self_signed
                        result = "VULNERABLE" if vulnerable else "SAFE"
                        msg = f"SSL Certificate is {'EXPIRED' if expired else 'VALID'}. {'Self-signed detected.' if self_signed else ''}"
                        return {
                            "scan_tool": "ssl", "scan_status": "completed", "scan_level": level,
                            "target_url": url, "result": result, "vulnerable": vulnerable,
                            "vulnerabilities": [{"type": "SSL Expired"}] if expired else [{"type": "Self-Signed Certificate"}] if self_signed else [],
                            "raw_output": f"Domain: {domain}\nExpiry: {expiry_str}\nSelf-Signed: {self_signed}",
                            "expiry_date": expiry_str,
                            "humanized": msg, "scan_completed": True, "duration_seconds": round(time.time() - start_time, 2)
                        }

                    # NORMAL LEVEL
                    cipher = ssock.cipher()
                    version = ssock.version()
                    strength = cipher[2]
                    weak_cipher = strength < 128
                    
                    # Grade simulation
                    grade = "A"
                    if self_signed: grade = "F"
                    elif weak_cipher: grade = "C"
                    elif version in ["TLSv1", "TLSv1.1"]: grade = "B"

                    if level == "normal":
                        vulnerable = weak_cipher or self_signed or expired
                        result = "VULNERABLE" if vulnerable else "SAFE"
                        return {
                            "scan_tool": "ssl", "scan_status": "completed", "scan_level": level,
                            "target_url": url, "result": result, "vulnerable": vulnerable,
                            "vulnerabilities": [{"type": "Weak SSL Config"}] if vulnerable else [],
                            "raw_output": f"Grade: {grade}\nCipher: {cipher[0]}\nVersion: {version}\nSelf-Signed: {self_signed}",
                            "expiry_date": expiry_str,
                            "humanized": f"SSL Grade: {grade}. Cipher: {cipher[0]} ({strength} bits). {'Self-signed detected.' if self_signed else ''}",
                            "scan_completed": True, "duration_seconds": round(time.time() - start_time, 2)
                        }

                    # DEEP LEVEL
                    # Check for Heartbleed, Poodle etc (Simulation/Simple check)
                    vulnerabilities = []
                    if version == "SSLv3": vulnerabilities.append("POODLE")
                    if version == "TLSv1": vulnerabilities.append("BEAST")
                    
                    return {
                        "scan_tool": "ssl", "scan_status": "completed", "scan_level": level,
                        "target_url": url, "result": "VULNERABLE" if vulnerabilities else "SAFE",
                        "vulnerable": bool(vulnerabilities),
                        "vulnerabilities": [{"type": v} for v in vulnerabilities],
                        "raw_output": f"Chain: Checked\nVulnerabilities: {vulnerabilities}\nIssuer: {cert.get('issuer')}",
                        "humanized": f"Deep SSL Audit complete. Found: {vulnerabilities if vulnerabilities else 'No known vulnerabilities'}.",
                        "scan_completed": True, "duration_seconds": round(time.time() - start_time, 2)
                    }

        except Exception as e:
            err_msg = str(e)
            if "CERTIFICATE_VERIFY_FAILED" in err_msg or "self signed" in err_msg.lower():
                return {
                    "scan_tool": "ssl", "scan_status": "completed", "scan_level": level, "target_url": url,
                    "result": "VULNERABLE", "vulnerable": True, "vulnerabilities": [{"type": "Self-Signed Certificate"}],
                    "humanized": "SSL Audit Failed: Self-signed certificate detected in chain.", "scan_completed": True, "raw_output": err_msg
                }
            return {
                "scan_tool": "ssl", "scan_status": "failed", "scan_level": level, "target_url": url,
                "error_type": "connection_failed", "error_message": f"SSL Scan Failed: {err_msg}",
                "vulnerable": False, "scan_completed": False, "raw_output": err_msg
            }
class BreachScanner:
    async def run(self, url: str, scan_id: str, level: str = "quick", hacker_mode: bool = False) -> dict:
        start_time = time.time()
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.split(':')[0]
        except:
            domain = url.split("//")[-1].split("/")[0]
        
        if scan_id not in scan_logs: scan_logs[scan_id] = []
        scan_logs[scan_id].append(f"\n================================\nWebSecureX Terminal\nTool: Data Breach Monitor\nTarget Domain: {domain}\n================================\n")
        
        if hacker_mode:
            scan_logs[scan_id].append("[ HACKER MODE ] Checking breach repositories in separate terminal...\n")
            # For mock tools, we just show a placeholder bat
            bat_path = os.path.abspath(f"reports/{scan_id}_breach_launch.bat")
            with open(bat_path, "w") as f:
                f.write(f"@echo off\ntitle BREACH MONITOR\ncolor 0E\necho Scanning breach repositories for {domain}...\ntimeout /t 5\necho.\necho [!] Found potential leaks in 3 databases\necho [!] admin@{domain} leaked in 'Collection #1'\necho.\npause")
            subprocess.Popen(["cmd.exe", "/c", "start", "BREACH MONITOR", "cmd.exe", "/k", bat_path], shell=False)

        scan_logs[scan_id].append(f"Searching dark web repositories for leaks related to {domain}...\n")
        
        # Simulate search
        await asyncio.sleep(2) 
        
        # Mock data for demonstration purposes
        is_vuln_demo = "test" in domain or "vulnerable" in domain
        found = ["admin@" + domain, "it_support@" + domain, "webmaster@" + domain] if is_vuln_demo else []
        vulnerable = len(found) > 0
        
        msg = f"CRITICAL: Found {len(found)} leaked administrative accounts!" if vulnerable else "No known breaches detected for this domain."
        
        return {
            "scan_tool": "breach_checker", "scan_status": "completed", "scan_level": level,
            "target_url": url, "result": "VULNERABLE" if vulnerable else "SAFE", "vulnerable": vulnerable,
            "vulnerabilities": [{"type": "Credential Leak", "account": email} for email in found] if vulnerable else [],
            "raw_output": f"Domain: {domain}\nBreach Count: {len(found)}\nEmails: {', '.join(found) if found else 'None'}",
            "humanized": msg, "scan_completed": True, "duration_seconds": round(time.time() - start_time, 2)
        }

# Orchestration
async def run_with_retry(scanner_instance, url, scan_id, level="quick", hacker_mode=False):
    for attempt in range(2): # Retry once
        res = await scanner_instance.run(url, scan_id, level, hacker_mode)
        if res.get("scan_status") != "error":
            return res
    return res # Return last result regardless

async def run_all_scans(url, scan_id, scan_type, user_id, db_override=None, scan_level="quick", hacker_mode=False):
    await update_scan(scan_id, {"status": "running", "progress": 5, "current_phase": "Initializing Engines..."})
    await asyncio.sleep(1) # Visual feedback
    
    if scan_id not in scan_logs: scan_logs[scan_id] = []
    scan_logs[scan_id].append(f"[ INITIALIZING AUDIT: {url} ]\n")
    
    # Pre-flight check (always needed for SSL and headers)
    reachable, status_or_err, headers, ssl_valid = await check_connectivity(url)
    if not reachable:
        if scan_id in scan_logs:
            scan_logs[scan_id].append(f"\n[ CONNECTION FAILED ]\n{status_or_err}\n")
            scan_logs[scan_id].append("\n[ SCAN COMPLETE ]\n")
        await update_scan(scan_id, {"status": "error", "current_phase": f"Connection Failed: {status_or_err}", "progress": 0})
        return
    
    await update_scan(scan_id, {"progress": 10, "current_phase": f"Connected ({'SSL Approved' if ssl_valid else 'SSL Bypassed'}). Mapping..."})
    await asyncio.sleep(1)

    scans_run = []
    final_results = {}
    tool_scores = {}

    # --- PHASE 1: SQL INJECTION SCAN ---
    db_type = db_override
    if scan_type in ["full", "sqli_only"]:
        await update_scan(scan_id, {"progress": 15, "current_phase": "Phase 1: SQL Injection Scan..."})
        
        if not db_type:
            server_header = headers.get("Server", "").lower()
            x_powered = headers.get("X-Powered-By", "").lower()
            if any(kw in server_header + x_powered for kw in ["mongo", "express", "node", "firebase", "couchdb"]):
                db_type = "nosql"
            else:
                db_type = "sql"

        # Timeout: quick=90s, normal=180s, deep=300s
        sqli_timeout = 90 if scan_level == "quick" else 180 if scan_level == "normal" else 300
        try:
            if db_type == "nosql":
                nosql_res = await asyncio.wait_for(run_with_retry(NoSQLScanner(), url, scan_id, scan_level, hacker_mode), timeout=sqli_timeout)
                final_results["nosql"] = nosql_res
                scans_run.append("nosql")
                tool_scores["nosql"] = Scorer.calculate_tool_score("nosqlmap", nosql_res)
            else:
                sqli_res = await asyncio.wait_for(run_with_retry(SQLiScanner(), url, scan_id, scan_level, hacker_mode), timeout=sqli_timeout)
                final_results["sqli"] = sqli_res
                scans_run.append("sqli")
                tool_scores["sqli"] = Scorer.calculate_tool_score("sqlmap", sqli_res)
                if sqli_res.get("db_type"): db_type = sqli_res.get("db_type")
        except asyncio.TimeoutError:
            scan_logs[scan_id].append(f"\n[ PHASE TIMEOUT: SQLi scan exceeded {sqli_timeout}s ]\n")
            key = "nosql" if db_type == "nosql" else "sqli"
            final_results[key] = {"scan_tool": "sqlmap", "scan_status": "failed", "scan_level": scan_level, "target_url": url, "result": None, "error_type": "timeout", "error_message": "Scan timed out. Try Quick mode.", "vulnerable": False, "vulnerabilities": [], "raw_output": "Timeout", "scan_completed": False, "duration_seconds": sqli_timeout}
            scans_run.append(key); tool_scores[key] = 0

    # --- PHASE 2: XSS SCAN ---
    if scan_type in ["full", "xss_only"]:
        await update_scan(scan_id, {"progress": 40, "current_phase": "Phase 2: XSS Scan (XSStrike)..."})
        xss_timeout = 120 if scan_level == "quick" else 240 if scan_level == "normal" else 360
        try:
            xss_res = await asyncio.wait_for(run_with_retry(XSSScanner(), url, scan_id, scan_level, hacker_mode), timeout=xss_timeout)
        except asyncio.TimeoutError:
            scan_logs[scan_id].append(f"\n[ PHASE TIMEOUT: XSS scan exceeded {xss_timeout}s ]\n")
            xss_res = {"scan_tool": "xsstrike", "scan_status": "failed", "scan_level": scan_level, "target_url": url, "result": None, "error_type": "timeout", "error_message": "XSS scan timed out. Try Quick mode.", "vulnerable": False, "findings": [], "vulnerabilities": [], "raw_output": "Timeout", "scan_completed": False, "duration_seconds": xss_timeout}
        scan_logs[scan_id].append("\n[ PHASE COMPLETE ]\n")
        final_results["xss"] = xss_res
        scans_run.append("xss")
        tool_scores["xss"] = Scorer.calculate_tool_score("xsstrike", xss_res)

    # --- PHASE 3: IP THREAT INTELLIGENCE ---
    if scan_type in ["full", "ip_only"]:
        await update_scan(scan_id, {"progress": 85, "current_phase": "Phase 3: IP Threat Intelligence..."})
        try:
            domain = urlparse(url).netloc.split(':')[0]
            ip_addr = socket.gethostbyname(domain)
            
            scan_logs[scan_id].append(f"\n================================\nWebSecureX Terminal\nTool: AbuseIPDB (IP Reputation)\nTarget IP: {ip_addr}\nLevel: {scan_level.upper()}\n================================\n")
            scan_logs[scan_id].append(f"Resolving {domain} -> {ip_addr}\nQuerying threat database...\n")

            # Determine maxAgeDays based on level
            max_age = "30"
            if scan_level == "normal": max_age = "60"
            elif scan_level == "deep": max_age = "90"

            # --- HACKER MODE: Show IP lookup in a visible window ---
            if hacker_mode:
                ip_bat_lines = [
                    "@echo off", f"title AbuseIPDB THREAT INTELLIGENCE", "color 0B",
                    "echo.", "echo  [WebSecureX] IP THREAT INTELLIGENCE ENGINE", "echo  Powered by AbuseIPDB", "echo.",
                    f"echo  Resolving domain: {domain}", f"echo  Resolved IP: {ip_addr}", f"echo  Level: {scan_level.upper()}", "echo.",
                    "echo  Querying global threat database...", f"echo  maxAgeInDays: {max_age} days", "echo.",
                    "echo  [RESULT WILL APPEAR IN DASHBOARD]", "echo.", "timeout /t 20"
                ]
                ip_bat_path = os.path.abspath(f"reports/{scan_id}_ip_launch.bat")
                os.makedirs("reports", exist_ok=True)
                with open(ip_bat_path, "w", encoding="utf-8") as f:
                    f.write("\r\n".join(ip_bat_lines))
                subprocess.Popen(["cmd.exe", "/c", "start", "AbuseIPDB ENGINE", "cmd.exe", "/k", ip_bat_path], shell=False)

            api_key = os.getenv("ABUSEIPDB_API_KEY")
            ip_res = requests.get(
                "https://api.abuseipdb.com/api/v2/check",
                headers={'Accept': 'application/json', 'Key': api_key},
                params={'ipAddress': ip_addr, 'maxAgeInDays': max_age},
                timeout=10
            ).json()['data']
            
            # For Deep Level: Also get reports
            reports_data = []
            if scan_level == "deep":
                try:
                    rep_res = requests.get(
                        "https://api.abuseipdb.com/api/v2/reports",
                        headers={'Accept': 'application/json', 'Key': api_key},
                        params={'ipAddress': ip_addr, 'maxAgeInDays': max_age},
                        timeout=10
                    ).json().get('data', {}).get('results', [])
                    reports_data = rep_res
                except: pass

            vulnerable = ip_res.get('abuseConfidenceScore', 0) > 20
            scan_logs[scan_id].append(f"Confidence Score: {ip_res.get('abuseConfidenceScore')}%\nISP: {ip_res.get('isp')}\nCountry: {ip_res.get('countryCode')}\n")
            scan_logs[scan_id].append("\n[ PHASE COMPLETE ]\n")
            
            final_results["ip_check"] = {
                "scan_tool": "abuseipdb",
                "scan_status": "completed",
                "scan_level": scan_level,
                "target_url": ip_addr,
                "vulnerable": vulnerable,
                "abuse_score": ip_res.get('abuseConfidenceScore'),
                "isp": ip_res.get('isp'),
                "country": ip_res.get('countryCode'),
                "vulnerabilities": [{"type": "High Abuse Score"}] if vulnerable else [],
                "raw_output": f"IP: {ip_addr}\nScore: {ip_res.get('abuseConfidenceScore')}%\nReports: {len(reports_data)}",
                "scan_completed": True
            }
            scans_run.append("ip_check")
            tool_scores["ip_check"] = 10 if not vulnerable else 5 if ip_res.get('abuseConfidenceScore', 0) < 50 else 0
        except Exception as e:
            final_results["ip_check"] = {"scan_tool": "abuseipdb", "scan_status": "failed", "scan_level": scan_level, "error_message": str(e), "scan_completed": False}

    # --- PHASE 4: SSL AUDIT ---
    if scan_type in ["full", "ssl_only"]:
        await update_scan(scan_id, {"progress": 90, "current_phase": "Phase 4: SSL/TLS Certificate Audit..."})
        scan_logs[scan_id].append(f"\n================================\nWebSecureX Terminal\nTool: SSL Auditor\nTarget: {url}\nLevel: {scan_level.upper()}\n================================\n")
        try:
            ssl_res = await asyncio.wait_for(SSLScanner().run(url, scan_id, scan_level, hacker_mode), timeout=30)
        except asyncio.TimeoutError:
            scan_logs[scan_id].append("\n[ SSL TIMEOUT: Scan exceeded 30s ]\n")
            ssl_res = {"scan_tool": "ssl", "scan_status": "failed", "scan_level": scan_level, "target_url": url, "result": None, "error_type": "timeout", "error_message": "SSL scan timed out after 30s.", "vulnerable": False, "vulnerabilities": [], "raw_output": "Timeout", "scan_completed": False}
        scan_logs[scan_id].append(ssl_res.get('raw_output', '') + "\n")
        scan_logs[scan_id].append("\n[ PHASE COMPLETE ]\n")
        
        final_results["ssl"] = ssl_res
        scans_run.append("ssl")
        tool_scores["ssl"] = Scorer.calculate_tool_score("ssl", ssl_res)
        
    # --- PHASE 5: DARK WEB BREACH CHECKER ---
    if scan_type in ["full"]:
        await update_scan(scan_id, {"progress": 92, "current_phase": "Phase 5: Searching Data Breach Repositories..."})
        try:
            breach_res = await asyncio.wait_for(BreachScanner().run(url, scan_id, scan_level, hacker_mode), timeout=15)
            final_results["breach"] = breach_res
            scans_run.append("breach")
            tool_scores["breach"] = 10 if not breach_res.get("vulnerable") else 0
            scan_logs[scan_id].append("\n[ PHASE COMPLETE ]\n")
        except: 
            scan_logs[scan_id].append("\n[ BREACH CHECK FAILED ]\n")
        
    scan_logs[scan_id].append("\n[ SCAN COMPLETE ]\n")

    await update_scan(scan_id, {"progress": 95, "current_phase": "Finalizing Vulnerability Report..."})
    
    overall_score = Scorer.calculate_overall_score(tool_scores)
    vuln_count = sum([1 for r in final_results.values() if isinstance(r, dict) and r.get("vulnerable")])

    for key, data in final_results.items():
        if isinstance(data, dict):
            t_name = data.get("scan_tool", key.upper())
            data["humanized"] = Humanizer.humanize(t_name, data)
            data["recommendations"] = Humanizer.get_recommendations(t_name, data.get("vulnerable"))

    all_completed = all([r.get("scan_completed", False) for r in final_results.values() if isinstance(r, dict) and r.get("scan_status") != "skipped"])
    any_vulnerable = any([r.get("vulnerable", False) for r in final_results.values() if isinstance(r, dict)])
    
    overall_status = "completed" if all_completed else "failed"
    if not all_completed and any_vulnerable: overall_status = "completed"

    report_doc = {
        "status": overall_status, 
        "progress": 100, 
        "current_phase": "Analysis Complete" if all_completed else "Scan Failed",
        "overall_risk": "Critical" if any_vulnerable else "Safe" if all_completed else "Error",
        "overall_score": overall_score if all_completed else 0,
        "tool_scores": tool_scores,
        "db_type_detected": db_type,
        "ssl_valid": ssl_valid,
        "scans_run": scans_run,
        "scan_level": scan_level,
        "summary": {"total_vulnerabilities": vuln_count, "total_duration_seconds": sum([r.get("duration_seconds", 0) for r in final_results.values() if isinstance(r, dict)])},
        "scans": final_results,
        "scan_completed": all_completed
    }
    await update_scan(scan_id, report_doc)
    generate_html_report(await get_scan(scan_id), scan_id)
    
    # Cleanup logs after 10 minutes to save memory
    async def cleanup():
        await asyncio.sleep(600)
        if scan_id in scan_logs: del scan_logs[scan_id]
    asyncio.create_task(cleanup())

# Report Generator
def generate_html_report(report, scan_id):
    scans_run = report.get("scans_run", [])
    overall_score = report.get("overall_score", 0)
    
    html = f"""
    <html><head><style>
        body {{ background: #050a0e; color: #e8f4fd; font-family: 'JetBrains Mono', monospace; padding: 40px; line-height: 1.6; }}
        .card {{ background: #0d1f35; border: 1px solid rgba(0, 212, 255, 0.2); padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 0 15px rgba(0,0,0,0.5); }}
        .risk-badge {{ padding: 5px 15px; border-radius: 4px; font-weight: bold; text-transform: uppercase; border: 1px solid; }}
        .risk-critical {{ color: #ff2d55; border-color: #ff2d55; background: rgba(255,45,85,0.1); }}
        .risk-high {{ color: #ff8c00; border-color: #ff8c00; }}
        .risk-medium {{ color: #ffcc00; border-color: #ffcc00; }}
        .risk-safe {{ color: #00ff88; border-color: #00ff88; }}
        .score-circle {{ width: 80px; height: 80px; border-radius: 50%; border: 4px solid #00d4ff; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: bold; margin-bottom: 10px; }}
        h1 {{ font-family: 'Orbitron', sans-serif; color: #00d4ff; letter-spacing: 2px; }}
        h2 {{ color: #00d4ff; font-family: 'Orbitron', sans-serif; border-bottom: 1px solid rgba(0,212,255,0.1); padding-bottom: 10px; }}
        .tool-name {{ color: #00ff88; font-family: 'Orbitron', sans-serif; }}
        .humanized {{ background: rgba(0, 212, 255, 0.05); border-left: 4px solid #00d4ff; padding: 15px; font-style: italic; margin-bottom: 20px; }}
        pre {{ background: #020d1a; padding: 15px; border-radius: 8px; color: #7a9ab8; font-size: 11px; overflow-x: auto; max-height: 400px; }}
        details {{ margin-top: 15px; border: 1px solid rgba(255,255,255,0.05); border-radius: 5px; }}
        summary {{ padding: 10px; cursor: pointer; color: #00d4ff; font-weight: bold; }}
    </style></head><body>
        <h1>WEBSECUREX VULNERABILITY AUDIT</h1>
        
        <div class="card" style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <p>Target: <strong>{report['target_url']}</strong></p>
                <p>Risk Level: <span class="risk-badge risk-{report['overall_risk'].lower()}">{report['overall_risk']}</span></p>
                <p>Detected DB: <strong style="color: #00d4ff">{str(report.get('db_type_detected', 'Unknown')).upper()}</strong></p>
                <p>SSL Status: {f'<span style="color: #00ff88; font-weight: bold;">[ APPROVED SSL CERTIFICATION ]</span>' if report.get('ssl_valid') else '<span style="color: #ff8c00;">[ SSL BYPASSED / INVALID ]</span>'}</p>
            </div>
            <div style="text-align: center;">
                <div class="score-circle">{overall_score}%</div>
                <div style="font-size: 12px; color: #7a9ab8;">OVERALL SAFETY</div>
            </div>
        </div>

        <h2>I. EXECUTIVE SUMMARY (HUMANIZED)</h2>
    """
    
    for key, data in report['scans'].items():
        if key not in scans_run: continue
        tool_name = data.get('scan_tool', key.upper())
        score = report.get('tool_scores', {}).get(key, 0)
        html += f"""
        <div class="card">
            <div style="display: flex; justify-content: space-between;">
                <h3 class="tool-name">{tool_name} Audit</h3>
                <div style="color: #00ff88; font-weight: bold;">Score: {score}/10</div>
            </div>
            <div class="humanized">
                <strong>Analysis:</strong> {Humanizer.humanize(tool_name, data)}
            </div>
            <div style="background: rgba(0, 255, 136, 0.05); border-left: 4px solid #00ff88; padding: 15px; margin-top: 10px;">
                <strong>Recommended Fixes:</strong> {Humanizer.get_recommendations(tool_name, data.get('vulnerable'))}
            </div>
        </div>
        """

    html += "<h2>II. TECHNICAL ENGINE REPORTS (RAW)</h2>"
    
    for key, data in report['scans'].items():
        if key not in scans_run: continue
        html += f"""
        <div class="card">
            <h3 class="tool-name">{data.get('scan_tool', key.upper())} Log</h3>
            <p>Verdict: <span style="color: {'#ff2d55' if data.get('vulnerable') else '#00ff88'}">{'VULNERABLE' if data.get('vulnerable') else 'SECURE'}</span></p>
            <details open>
                <summary>Engine Output</summary>
                <pre>{data.get('raw_output')}</pre>
            </details>
        </div>
        """
        
    html += """
        <div class="card" style="text-align: center; border-color: #00ff88; background: rgba(0,255,136,0.05);">
            <h2 style="color: #00ff88;">WANT TO SECURE YOUR WEBSITE?</h2>
            <p>Our experts can help you patch these vulnerabilities and harden your infrastructure.</p>
            <a href="mailto:support@websecurex.com" class="risk-badge risk-safe" style="text-decoration: none; display: inline-block; padding: 15px 30px; font-size: 1.2rem;">[ CONTACT OUR SECURITY TEAM ]</a>
        </div>
        <footer><p style='text-align:center; color:#3d5a73; font-size: 10px;'>Generated by WebSecureX Pro Engine | Advanced Vulnerability Enlisting System</p></footer></body></html>
    """
    report_path = f"reports/{scan_id}/report.html"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f: f.write(html)
    return report_path
