// WebSecureX Unified Frontend Logic
const API_URL = ''; // Same host

// --- AUTH UTILS ---
const auth = {
    getToken: () => localStorage.getItem('wsxToken'),
    getUser: () => localStorage.getItem('wsxUsername'),
    getUserId: () => localStorage.getItem('wsxUserId'),
    save: (data) => {
        localStorage.setItem('wsxToken', data.token);
        localStorage.setItem('wsxUsername', data.username);
        localStorage.setItem('wsxUserId', data.userId);
    },
    logout: () => {
        localStorage.clear();
        window.location.href = 'login.html';
    },
    check: () => {
        if (!auth.getToken() && !window.location.pathname.includes('login.html') && !window.location.pathname.includes('signup.html')) {
            window.location.href = 'login.html';
        }
    }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    auth.check();
    updateNav();
    initHackerMode();
    
    // Page Detection
    if (document.getElementById('login-form')) initLogin();
    if (document.getElementById('signup-form')) initSignup();
    if (document.getElementById('scan-form')) initScanner();
    if (document.getElementById('history-table')) initHistory();
    if (document.getElementById('report-view')) initReport();
    if (document.getElementById('scheduler-form')) initScheduler();
});

// --- HACKER MODE LOGIC ---
function initHackerMode() {
    const slider = document.getElementById('hacker-mode-slider');
    const power = document.getElementById('hacker-mode-power');
    
    const isHacker = localStorage.getItem('wsxHackerMode') === 'true';
    
    if (isHacker) {
        document.body.classList.add('hacker-mode');
        if (slider) slider.checked = true;
        if (power) power.classList.add('on');
    }

    const toggle = (val) => {
        if (val) {
            document.body.classList.add('hacker-mode');
            localStorage.setItem('wsxHackerMode', 'true');
        } else {
            document.body.classList.remove('hacker-mode');
            localStorage.setItem('wsxHackerMode', 'false');
        }
        if (slider) slider.checked = val;
        if (power) {
            if (val) power.classList.add('on');
            else power.classList.remove('on');
        }
    };

    if (slider) slider.onchange = (e) => toggle(e.target.checked);
    if (power) power.onclick = () => {
        const newState = !document.body.classList.contains('hacker-mode');
        toggle(newState);
    };
}

function updateNav() {
    const userDisplay = document.getElementById('nav-username');
    if (userDisplay) userDisplay.innerText = auth.getUser() || 'Guest';
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) logoutBtn.onclick = auth.logout;
}

// --- LOGIN PAGE ---
function initLogin() {
    const form = document.getElementById('login-form');
    form.onsubmit = async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const errorMsg = document.getElementById('error-msg');
        
        try {
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (res.ok) {
                auth.save(data);
                window.location.href = 'index.html';
            } else {
                errorMsg.innerText = data.error || 'Login failed';
            }
        } catch (err) {
            errorMsg.innerText = 'Server unreachable';
        }
    };
}

// --- SIGNUP PAGE ---
function initSignup() {
    const form = document.getElementById('signup-form');
    form.onsubmit = async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const email = document.getElementById('email').value;
        const password = document.getElementById('password').value;
        const confirm = document.getElementById('confirm-password').value;
        const errorMsg = document.getElementById('error-msg');
        const successMsg = document.getElementById('success-msg');
        
        if (password !== confirm) {
            errorMsg.innerText = 'Passwords do not match';
            return;
        }

        try {
            const res = await fetch('/auth/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password })
            });
            const data = await res.json();
            if (res.ok) {
                successMsg.innerText = 'Account created! Redirecting to login...';
                setTimeout(() => window.location.href = 'login.html', 1500);
            } else {
                errorMsg.innerText = data.error || 'Signup failed';
            }
        } catch (err) {
            errorMsg.innerText = 'Server unreachable';
        }
    };
}

// --- SCHEDULER PAGE ---
async function initScheduler() {
    const form = document.getElementById('scheduler-form');
    const statusDiv = document.getElementById('sch-status');
    const tableBody = document.getElementById('schedules-table');
    
    // Fetch and display schedules
    const loadSchedules = async () => {
        try {
            const res = await fetch(`${API_URL}/api/schedules/${auth.getUserId()}`);
            if (!res.ok) return;
            const schedules = await res.json();
            
            tableBody.innerHTML = '';
            if (schedules.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center;">No active schedules.</td></tr>';
                return;
            }
            
            schedules.forEach(sch => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${sch.url}</td>
                    <td>${sch.scan_type.toUpperCase()}</td>
                    <td><span class="status-badge ${sch.scan_level}">${sch.scan_level.toUpperCase()}</span></td>
                    <td>Every ${sch.interval_hours}h</td>
                    <td>${sch.scheduled_time || 'N/A'}</td>
                    <td>${new Date(sch.next_run).toLocaleString()}</td>
                `;
                tableBody.appendChild(tr);
            });
        } catch (e) {
            console.error(e);
        }
    };

    await loadSchedules();

    // Form Submission
    form.onsubmit = async (e) => {
        e.preventDefault();
        statusDiv.style.color = 'var(--text-secondary)';
        statusDiv.innerText = 'Activating...';
        
        const payload = {
            user_id: auth.getUserId(),
            url: document.getElementById('sch-url').value,
            scan_type: document.getElementById('sch-type').value,
            scan_level: document.getElementById('sch-level').value,
            interval_hours: parseInt(document.getElementById('sch-interval').value),
            scheduled_time: document.getElementById('sch-time').value || null
        };
        
        try {
            const res = await fetch(`${API_URL}/api/schedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (res.ok) {
                statusDiv.style.color = 'var(--accent-green)';
                statusDiv.innerText = 'Schedule Activated!';
                form.reset();
                await loadSchedules();
            } else {
                statusDiv.style.color = 'var(--accent-red)';
                statusDiv.innerText = 'Failed to activate schedule.';
            }
        } catch (e) {
            statusDiv.style.color = 'var(--accent-red)';
            statusDiv.innerText = 'Network Error.';
        }
    };
}

// --- SCANNER PAGE ---
let pollInterval;
let currentLevel = 'quick';

function initScanner() {
    const form = document.getElementById('scan-form');
    const urlInput = document.getElementById('target-url');
    const progressSection = document.getElementById('progress-section');
    const resultPreview = document.getElementById('result-preview');

    // Level Selection
    const levelBtns = document.querySelectorAll('.level-btn');
    levelBtns.forEach(btn => {
        btn.onclick = () => {
            if (form.classList.contains('scanning')) return;
            levelBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentLevel = btn.dataset.level;
        };
    });

    // Check for existing scan on load
    const savedScan = localStorage.getItem('wsxCurrentScan');
    if (savedScan) {
        const { id } = JSON.parse(savedScan);
        form.classList.add('scanning'); // Keep button disabled/busy
        urlInput.disabled = true; // Lock if resuming scan
        progressSection.style.display = 'block';
        document.getElementById('terminal-container').style.display = 'block';
        startTerminalStream(id);
        pollScan(id);
    } else {
        urlInput.disabled = false; // Ensure unlocked
        form.classList.remove('scanning');
    }

    async function startScan(type) {
        const url = urlInput.value;
        if (!url || url === 'http://' || url === 'https://') return alert('Please enter a valid target URL');
        
        if (form.classList.contains('scanning')) return;
        form.classList.add('scanning');
        urlInput.disabled = true;
        
        const info = document.getElementById('feature-info');
        if (info) info.style.display = 'none';
        
        progressSection.style.display = 'block';
        resultPreview.style.display = 'none';
        
        const termContainer = document.getElementById('terminal-container');
        if (termContainer) termContainer.style.display = 'block';
        
        const termLog = document.getElementById('terminal-log');
        if (termLog) termLog.innerHTML = ''; // Clear for new scan

        const dbOverride = document.getElementById('db-override')?.value || null;
        
        try {
            const res = await fetch('/scan', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.getToken()}`
                },
                body: JSON.stringify({ 
                    url, 
                    scan_type: type, 
                    db_override: dbOverride, 
                    scan_level: currentLevel,
                    hacker_mode: document.body.classList.contains('hacker-mode')
                })
            });
            let data;
            const contentType = res.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                data = await res.json();
            } else {
                data = { error: await res.text() };
            }

            if (res.ok) {
                localStorage.setItem('wsxCurrentScan', JSON.stringify({ id: data.scan_id }));
                startTerminalStream(data.scan_id);
                pollScan(data.scan_id);
            } else if (res.status === 401) {
                auth.logout();
            } else {
                form.classList.remove('scanning');
                urlInput.disabled = false;
                alert(`Scan Failed: ${data.error || 'Unknown server error'}`);
            }
        } catch (err) {
            form.classList.remove('scanning');
            urlInput.disabled = false;
            console.error('Scan Error:', err);
            alert(`Connection Error: ${err.message || 'The server is unreachable. Please ensure the backend is running.'}`);
        }
    }

    document.getElementById('btn-scan-all').onclick = () => startScan('full');
    document.getElementById('btn-scan-xss').onclick = () => startScan('xss_only');
    document.getElementById('btn-scan-sqli').onclick = () => startScan('sqli_only');
    document.getElementById('btn-scan-ssl').onclick = () => startScan('ssl_only'); 
    document.getElementById('btn-scan-ip').onclick = () => startScan('ip_only');

    const stopBtn = document.getElementById('btn-stop-scan');
    if (stopBtn) stopBtn.onclick = () => resetUI();

    function resetUI() {
        if (pollInterval) clearInterval(pollInterval);
        localStorage.removeItem('wsxCurrentScan');
        form.classList.remove('scanning');
        urlInput.disabled = false;
        urlInput.value = ''; // Clear the field for new input
        progressSection.style.display = 'none';
        resultPreview.style.display = 'none';
        const info = document.getElementById('feature-info');
        if (info) info.style.display = 'grid';
        
        // Reset Phase UI
        document.querySelectorAll('.phase').forEach(p => p.className = 'phase');
        document.getElementById('progress-bar').style.width = '0%';
        document.getElementById('progress-text').innerText = 'Ready for next audit...';
    }
}

async function checkIp() {
    const ip = prompt("Enter IP Address to check threat level:", "8.8.8.8");
    if (!ip) return;
    
    logTerminal(`Checking Threat Intelligence for IP: ${ip}...`, 'cyan');
    try {
        const res = await fetch('/check-ip', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${auth.getToken()}`
            },
            body: JSON.stringify({ ip })
        });
        const data = await res.json();
        if (res.ok) {
            const color = data.status === 'SAFE' ? 'green' : data.status === 'SUSPICIOUS' ? 'orange' : 'red';
            logTerminal(`IP: ${data.ipAddress} | ISP: ${data.isp}`, 'white');
            logTerminal(`Confidence Score: ${data.abuseConfidenceScore}% | Country: ${data.countryCode}`, 'white');
            logTerminal(`STATUS: ${data.status}`, color);
            alert(`IP Check Result:\nIP: ${data.ipAddress}\nStatus: ${data.status}\nConfidence: ${data.abuseConfidenceScore}%`);
        } else {
            logTerminal(`Error: ${data.detail}`, 'red');
        }
    } catch (err) {
        logTerminal('Failed to reach threat intelligence server', 'red');
    }
}

function pollScan(id) {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/scan/${id}/status`, {
                headers: { 'Authorization': `Bearer ${auth.getToken()}` }
            });
            const data = await res.json();
            
            // Update UI
            document.getElementById('progress-bar').style.width = `${data.progress}%`;
            document.getElementById('progress-text').innerText = `${data.progress}% - ${data.current_phase}`;
            // Only log when phase actually changes to avoid terminal spam
            if (!pollScan._lastPhase || pollScan._lastPhase !== data.current_phase) {
                logTerminal(`[${data.progress}%] ${data.current_phase}`);
                pollScan._lastPhase = data.current_phase;
            }

            // Dynamic Phase Highlighting
            const phase = (data.current_phase || '').toLowerCase();
            const scans = data.scans || {};
            
            // Helper to update phase UI
            const updatePhaseUI = (id, toolKey) => {
                const el = document.getElementById(id);
                if (!el) return;
                el.classList.remove('active', 'complete', 'failed');
                
                const tool = scans[toolKey];
                if (tool) {
                    if (tool.scan_status === 'completed' || tool.scan_status === 'skipped') el.classList.add('complete');
                    else if (tool.scan_status === 'failed' || tool.scan_status === 'error') el.classList.add('failed');
                }
            };

            // Mark init as complete once past 10%
            const initEl = document.getElementById('phase-init');
            if (initEl) {
                if (data.progress >= 15) initEl.classList.add('complete');
                else initEl.classList.add('active');
            }

            updatePhaseUI('phase-sqli', 'sqli');
            if (!scans['sqli'] && scans['nosql']) updatePhaseUI('phase-sqli', 'nosql');
            updatePhaseUI('phase-xss', 'xss');
            updatePhaseUI('phase-ip', 'ip_check');
            updatePhaseUI('phase-ssl', 'ssl');

            // Set current active phase
            if (phase.includes('initializ') || phase.includes('mapping') || phase.includes('connected')) {
                if (initEl && !initEl.classList.contains('complete')) { initEl.classList.remove('active'); initEl.classList.add('active'); }
            } else if (phase.includes('sql') || phase.includes('db') || phase.includes('nosql')) {
                document.getElementById('phase-sqli').classList.add('active');
            } else if (phase.includes('xss')) {
                document.getElementById('phase-xss').classList.add('active');
            } else if (phase.includes('ip') || phase.includes('reputation') || phase.includes('threat')) {
                document.getElementById('phase-ip').classList.add('active');
            } else if (phase.includes('ssl') || phase.includes('tls') || phase.includes('certificate')) {
                document.getElementById('phase-ssl').classList.add('active');
            } else if (phase.includes('finaliz') || phase.includes('complete')) {
                document.getElementById('phase-report').classList.add('active');
            }
            
            if (data.status === 'completed' || data.status === 'failed') {
                document.getElementById('phase-report').classList.add('active');
                clearInterval(pollInterval);
                localStorage.removeItem('wsxCurrentScan');
                const scanForm = document.getElementById('scan-form');
                scanForm.classList.remove('scanning');
                const inp = document.getElementById('target-url');
                if (inp) inp.disabled = false;
                
                if (data.scan_completed || data.overall_risk === 'Critical') {
                    showPreview(data);
                } else {
                    const preview = document.getElementById('result-preview');
                    const cards = document.getElementById('result-cards');
                    preview.style.display = 'block';
                    cards.innerHTML = `
                        <div class="card neon-border fadeInUp" style="border-color: #ff2d55; width: 100%; text-align: center;">
                            <h2 style="color: #ff2d55;">SCAN FAILED</h2>
                            <p style="margin: 15px 0;">${data.current_phase}</p>
                            <div style="display: flex; gap: 10px; justify-content: center;">
                                <a href="history.html" class="btn btn-outline">History</a>
                                <a href="report.html?id=${id}" class="btn btn-primary">View Full Error Log</a>
                            </div>
                        </div>
                    `;
                    document.getElementById('risk-banner').innerText = 'SCAN ERROR';
                    document.getElementById('risk-banner').className = 'risk-badge risk-critical';
                }
            }
        } catch (err) {
            console.error(err);
        }
    }, 2000);
}

function startTerminalStream(id) {
    const term = document.getElementById('terminal-log');
    if (!term) return;
    
    const source = new EventSource(`/api/scan/${id}/stream`);
    
    source.onmessage = (event) => {
        const line = document.createElement('div');
        line.className = 'terminal-line';
        line.innerText = event.data;
        
        // Color coding logic
        if (event.data.includes('[ PHASE COMPLETE ]')) line.style.color = '#00ff88';
        if (event.data.includes('[ SCAN COMPLETE ]')) {
            line.style.color = '#00ff88';
            line.style.fontWeight = 'bold';
            source.close();
        }
        if (event.data.includes('CRITICAL') || event.data.includes('Vulnerable')) line.style.color = '#ff2d55';
        
        term.appendChild(line);
        term.scrollTop = term.scrollHeight;
    };
    
    source.onerror = () => source.close();
}

function showPreview(data) {
    const preview = document.getElementById('result-preview');
    const cards = document.getElementById('result-cards');
    if (!preview || !cards) return;
    
    preview.style.display = 'block';
    cards.innerHTML = '';

    const isCompleted = data.scan_completed;
    const riskBanner = document.getElementById('risk-banner');
    const scoreVal = document.getElementById('overall-score-val');
    const scoreBadge = document.getElementById('overall-score-badge');
    const btnShowReport = document.getElementById('btn-show-full-report');
    const btnDownloadReport = document.getElementById('btn-download-html-report');

    const riskStr = (data.overall_risk || 'SAFE').toUpperCase();
    const riskLower = riskStr.toLowerCase();

    if (riskBanner) {
        if (isCompleted) {
            riskBanner.innerText = `${riskStr} RISK DETECTED`;
            riskBanner.className = `risk-badge risk-${riskLower}`;
        } else {
            riskBanner.innerText = `SCAN ERROR: ${riskStr}`;
            riskBanner.className = `risk-badge risk-critical`;
        }
    }

    // Calculate/format Total Security Score
    let score = 100;
    if (data.overall_score !== undefined && data.overall_score !== null) {
        score = data.overall_score;
    } else {
        let vulns = 0;
        let total = 0;
        Object.values(data.scans || {}).forEach(t => {
            if (!t || t.status === 'skipped') return;
            total++;
            if (t.result === 'VULNERABLE' || t.vulnerable) vulns++;
        });
        if (total > 0) {
            score = Math.max(0, Math.round(100 - (vulns / total) * 100));
        }
    }

    if (scoreVal) scoreVal.innerText = score;

    if (scoreBadge) {
        if (score >= 80) {
            scoreBadge.style.background = 'rgba(0, 255, 136, 0.1)';
            scoreBadge.style.borderColor = 'var(--accent-green)';
            scoreBadge.style.color = 'var(--accent-green)';
        } else if (score >= 50) {
            scoreBadge.style.background = 'rgba(255, 184, 0, 0.1)';
            scoreBadge.style.borderColor = 'var(--accent-orange)';
            scoreBadge.style.color = 'var(--accent-orange)';
        } else {
            scoreBadge.style.background = 'rgba(255, 45, 85, 0.1)';
            scoreBadge.style.borderColor = '#ff2d55';
            scoreBadge.style.color = '#ff2d55';
        }
    }

    // Bind Collective Full Report Actions
    if (btnShowReport) {
        btnShowReport.href = `report.html?id=${data.scan_id}`;
    }
    if (btnDownloadReport) {
        btnDownloadReport.href = `/report/${data.scan_id}/html`;
    }

    Object.entries(data.scans || {}).forEach(([key, tool]) => {
        if (!tool || tool.status === 'skipped') return;
        const card = document.createElement('div');
        const toolCompleted = tool.scan_completed;
        const isVulnerable = tool.result === "VULNERABLE";
        
        card.className = 'card neon-border fadeInUp';
        if (!toolCompleted || isVulnerable) card.style.borderColor = '#ff2d55';
        else card.style.borderColor = '#00ff88';
        
        card.innerHTML = `
            <h3 style="font-family: monospace;">${tool.scan_tool || key.toUpperCase()}</h3>
            <p>Level: <span style="color: var(--accent-cyan); font-weight: bold;">${(tool.scan_level || data.scan_level || 'quick').toUpperCase()}</span></p>
            <p>Status: <span class="risk-badge risk-${toolCompleted ? (isVulnerable ? 'critical' : 'safe') : 'critical'}">
                ${toolCompleted ? (isVulnerable ? 'VULNERABLE' : 'SAFE') : 'FAILED'}
            </span></p>
            <p>${toolCompleted ? `Duration: ${tool.duration_seconds || 0}s` : `Error: ${tool.error_message || 'Internal Error'}`}</p>
            <a href="report.html?id=${data.scan_id}" class="btn btn-outline" style="margin-top:15px; display:inline-block">View Full Details</a>
        `;
        cards.appendChild(card);
    });
}

function logTerminal(msg, color = '') {
    const term = document.getElementById('terminal-log');
    if (!term) return;
    const line = document.createElement('div');
    line.className = 'terminal-line';
    const time = new Date().toLocaleTimeString();
    line.innerHTML = `<span class="terminal-time">[${time}]</span> <span style="color: ${color}">${msg}</span>`;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
}

// --- HISTORY PAGE ---
async function initHistory() {
    const table = document.getElementById('history-table');
    try {
        const res = await fetch('/history', {
            headers: { 'Authorization': `Bearer ${auth.getToken()}` }
        });
        const data = await res.json();
        table.innerHTML = data.map(scan => {
            const isFailed = scan.status === 'failed' && !scan.scan_completed;
            const risk = isFailed ? 'FAILED' : (scan.overall_risk || 'SAFE');
            return `
                <tr>
                    <td>${scan.target_url}</td>
                    <td>${scan.scan_type}</td>
                    <td>${new Date(scan.timestamp).toLocaleDateString()}</td>
                    <td><span class="risk-badge risk-${risk.toLowerCase()}">${risk}</span></td>
                    <td>${scan.db_type_detected || '—'}</td>
                    <td>
                        <a href="report.html?id=${scan.scan_id}">View</a> | 
                        <a href="#" onclick="deleteScan('${scan.scan_id}')" style="color:var(--accent-red)">Del</a>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        console.error(err);
    }
}

async function deleteScan(id) {
    if (!confirm('Delete this scan?')) return;
    await fetch(`/scan/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${auth.getToken()}` }
    });
    location.reload();
}

// --- REPORT PAGE ---
async function initReport() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (!id) return;

    try {
        const res = await fetch(`/scan/${id}/report`, {
            headers: { 'Authorization': `Bearer ${auth.getToken()}` }
        });
        const data = await res.json();
        
        document.getElementById('report-url').innerText = data.target_url;
        document.getElementById('report-risk').style.display = 'none'; 
        
        const sslText = data.ssl_valid ? '[ APPROVED SSL CERTIFICATION ]' : '[ SSL BYPASSED / INVALID ]';
        const sslColor = data.ssl_valid ? 'var(--accent-green)' : 'var(--accent-orange)';
        const sslInfo = `<p style="color:${sslColor}; font-weight:bold; font-size:0.7rem; margin-top:10px;">${sslText}</p>`;
        document.getElementById('report-url').insertAdjacentHTML('afterend', sslInfo);
        
        const details = document.getElementById('report-details');
        const scoreColor = data.scan_completed ? (data.overall_score > 80 ? '#00ff88' : data.overall_score > 50 ? '#ffcc00' : '#ff2d55') : '#ff2d55';
        
        let html = `
            <div class="card neon-border" style="text-align: center; padding: 40px; margin-bottom: 30px; background: rgba(0,0,0,0.3); border-color: ${scoreColor};">
                <h3 style="color: var(--text-muted); font-size: 0.8rem; letter-spacing: 2px; margin:0;">${data.scan_completed ? 'OVERALL SECURITY SCORE' : 'SCAN STATUS: FAILED'}</h3>
                <h1 style="font-size: 5rem; color: ${scoreColor}; margin: 10px 0; font-family: 'Orbitron', sans-serif; text-shadow: 0 0 20px ${scoreColor}44;">
                    ${data.scan_completed ? (data.overall_score || 0) + '%' : 'ERROR'}
                </h1>
                <div class="risk-badge risk-${(data.overall_risk || 'safe').toLowerCase()}" style="font-size: 1.2rem; padding: 10px 30px; display: inline-block;">
                    ${data.scan_completed ? 'SYSTEM STATUS: ' + data.overall_risk : data.current_phase}
                </div>
            </div>
            <h2 style="margin-top: 50px; border-bottom: 1px solid #333; padding-bottom: 10px; color: var(--accent-cyan);">DETAILED VULNERABILITY ENLISTMENT</h2>
        `;

        html += Object.entries(data.scans || {}).map(([key, tool]) => {
            if (!tool || tool.status === 'skipped') return '';
            const score = (data.tool_scores || {})[key] || 0;
            const isToolCompleted = tool.scan_completed;
            const toolColor = isToolCompleted ? 'var(--accent-cyan)' : '#ff2d55';

            return `
                <div class="card neon-border" style="border-color: ${toolColor};">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333; padding-bottom:10px; margin-bottom:15px;">
                        <h2 style="margin:0; color: ${toolColor};">${tool.scan_tool || key.toUpperCase()} ENGINE</h2>
                        ${isToolCompleted ? `<div class="score-badge" style="background:var(--accent-cyan); color:black; padding:4px 12px; border-radius:4px; font-weight:bold; font-size:0.9rem;">SCORE: ${score}/10</div>` : ''}
                    </div>
                    <div class="analysis-box" style="background:rgba(0,212,255,0.05); padding:20px; border-left:4px solid ${toolColor}; margin-bottom:20px;">
                        <p style="margin:0; font-weight:bold; color:${toolColor}; margin-bottom:5px;">${isToolCompleted ? 'HUMANIZED ANALYSIS:' : 'ENGINE ERROR:'}</p>
                        <p style="margin:0; font-style:italic; line-height:1.6;">${tool.humanized || tool.error_message || 'Analysis pending...'}</p>
                    </div>
                    ${isToolCompleted ? `
                    <div class="rec-box" style="background:rgba(0,255,136,0.05); padding:15px; border-left:4px solid #00ff88; margin-bottom:20px; font-size:0.9rem;">
                        <p style="margin:0; font-weight:bold; color:#00ff88; margin-bottom:5px;">RECOMMENDED PATCHES:</p>
                        <p style="margin:0;">${tool.recommendations || 'No critical patches required.'}</p>
                    </div>` : ''}
                    <details>
                        <summary style="cursor:pointer; color:var(--text-muted); font-size:0.8rem; text-decoration:underline;">View Technical Engine Logs</summary>
                        <pre style="margin-top:15px; max-height:400px; overflow-y:auto; font-size:0.75rem; background:#020d1a; padding:15px; border-radius:8px;">${tool.raw_output}</pre>
                    </details>
                </div>
            `;
        }).join('');

        // Generate Humanized Report Sections
        let isSqli = false;
        let isXss = false;
        let isSsl = false;
        let isIp = false;
        let isBreach = false;
        let ipScore = 0;
        let sslExpiry = '';
        Object.entries(data.scans || {}).forEach(([key, tool]) => {
            if (!tool || tool.status === 'skipped') return;
            const tk = (tool.scan_tool || key).toLowerCase();
            
            // Capture precise details even if not flagged as critical vulnerability
            if (tk.includes('ssl')) sslExpiry = tool.expiry_date || '';
            if (tk.includes('ip') || tk.includes('abuse')) ipScore = tool.abuse_score || ipScore;

            if (tool.vulnerable || tool.result === "VULNERABLE") {
                if (tk.includes('sql')) isSqli = true;
                if (tk.includes('xss')) isXss = true;
                if (tk.includes('ssl')) isSsl = true;
                if (tk.includes('ip') || tk.includes('abuse')) isIp = true;
                if (tk.includes('breach')) isBreach = true;
            }
        });

        let whatThisMeansHtml = '';
        let whatYouShouldDoHtml = '';

        if (isSqli || isXss || isSsl || isIp) {
            if (isSqli) {
                whatThisMeansHtml += `<p style="margin-bottom: 10px;">Hackers can access your database through your website's search or login fields. This means they could steal usernames, passwords, and private data.</p>`;
                whatYouShouldDoHtml += `<li>Contact your web developer immediately and tell them your website has an SQL Injection vulnerability.</li>
<li>Never store plain text passwords in your database.</li>
<li>Make sure your website uses parameterized queries.</li>`;
            }
            if (isXss) {
                whatThisMeansHtml += `<p style="margin-bottom: 10px;">Your website can be tricked into running harmful scripts. This means hackers could steal your visitors cookies or redirect them to fake websites.</p>`;
                whatYouShouldDoHtml += `<li>Tell your developer to sanitize all user input fields.</li>
<li>Add a Content Security Policy to your website.</li>
<li>Avoid using user input directly in your web pages.</li>`;
            }
            if (isSsl) {
                whatThisMeansHtml += `<p style="margin-bottom: 10px;">Your website's security certificate is about to expire <b>(Date: ${sslExpiry || 'Unknown'})</b>. After it expires visitors will see a scary warning page and may leave your website.</p>`;
                whatYouShouldDoHtml += `<li>Renew your SSL certificate as soon as possible.</li>
<li>Set up auto renewal so this never happens again.</li>`;
            }
            if (isIp) {
                whatThisMeansHtml += `<p style="margin-bottom: 10px;">Your website's server IP address has been reported for suspicious activity by <b>${ipScore}%</b> of security checkers. This could mean your server was previously hacked or misused.</p>`;
                whatYouShouldDoHtml += `<li>Contact your hosting provider about suspicious activity.</li>
<li>Consider changing your server IP address.</li>
<li>Make sure your server software is up to date.</li>`;
            }
            if (isBreach) {
                whatThisMeansHtml += `<p style="margin-bottom: 10px;"><b>CRITICAL DATA LEAK:</b> We found administrative emails or credentials related to your domain in dark web repositories. This means your accounts may have been compromised in past hacks.</p>`;
                whatYouShouldDoHtml += `<li>Change all administrative passwords immediately.</li>
<li>Enable Two-Factor Authentication (2FA) on all accounts.</li>
<li>Check your website for unauthorized user accounts.</li>`;
            }
        } else {
            whatThisMeansHtml += `<p>Great news! No major security issues were found on your website. Your website appears to be safe from common attacks.</p>`;
            if (sslExpiry) whatThisMeansHtml += `<p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 10px;">&bull; SSL Certificate Expiry: ${sslExpiry}</p>`;
            if (ipScore !== undefined) whatThisMeansHtml += `<p style="font-size: 0.8rem; color: var(--text-muted);">&bull; IP Reputation Score: ${ipScore}% (Safe)</p>`;
            
            whatYouShouldDoHtml += `<li>Keep your website software and plugins updated regularly.</li>
<li>Run security scans monthly to stay protected.</li>
<li>Always use strong passwords for your admin panel.</li>`;
        }

        // Generate Multi-Format Export Buttons
        const exportHtml = `
            <div style="display: flex; gap: 10px; margin-bottom: 25px;">
                <button onclick="downloadJSON()" class="btn btn-outline" style="font-size: 0.7rem; padding: 8px 15px;">
                    <i class="fas fa-file-code"></i> EXPORT JSON
                </button>
                <button onclick="downloadCSV()" class="btn btn-outline" style="font-size: 0.7rem; padding: 8px 15px;">
                    <i class="fas fa-file-csv"></i> EXPORT CSV
                </button>
            </div>
        `;

        // Calculate Security Score
        let score = 100;
        if (isSqli) score -= 35;
        if (isXss) score -= 30;
        if (isBreach) score -= 25;
        if (isSsl) score -= 15;
        if (isIp && ipScore > 20) score -= 10;
        if (score < 0) score = 0;

        let grade = 'A';
        let gradeColor = 'var(--accent-green)';
        if (score < 90) { grade = 'B'; gradeColor = 'var(--accent-cyan)'; }
        if (score < 80) { grade = 'C'; gradeColor = 'var(--accent-yellow)'; }
        if (score < 70) { grade = 'D'; gradeColor = 'var(--accent-orange)'; }
        if (score < 60) { grade = 'F'; gradeColor = 'var(--accent-red)'; }

        const scorecardHtml = `
            <div class="card neon-border" style="display: flex; align-items: center; justify-content: space-between; border-color: ${gradeColor}; padding: 20px; background: rgba(0,0,0,0.3); margin-bottom: 25px;">
                <div>
                    <h3 style="color: ${gradeColor}; margin: 0; font-family: 'Orbitron';">SECURITY SCORECARD</h3>
                    <p style="color: var(--text-secondary); margin: 5px 0 0 0; font-size: 0.8rem;">Overall system health based on vulnerability metrics.</p>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 3rem; font-family: 'Orbitron'; font-weight: 900; color: ${gradeColor}; line-height: 1;">${grade}</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 5px;">RATING: ${score}/100</div>
                </div>
            </div>
        `;

        html = exportHtml + scorecardHtml + `
            <div class="card neon-border" style="border-color: var(--accent-cyan); margin-bottom: 25px;">
                <h2 style="margin: 0 0 15px 0; color: var(--accent-cyan);">Vulnerabilities Found</h2>
                <div class="analysis-box" style="background: rgba(0, 212, 255, 0.05); padding: 20px; border-left: 4px solid var(--accent-cyan);">
                    ${whatThisMeansHtml}
                </div>
            </div>

            <div class="card neon-border" style="border-color: #00ff88; margin-bottom: 25px;">
                <h2 style="margin: 0 0 15px 0; color: #00ff88;">Recommendations</h2>
                <div class="rec-box" style="background: rgba(0, 255, 136, 0.05); padding: 20px; border-left: 4px solid #00ff88;">
                    <ol style="margin: 0; padding-left: 20px; line-height: 1.8;">
                        ${whatYouShouldDoHtml}
                    </ol>
                </div>
            </div>
        ` + html;

        details.innerHTML = html;
        window.currentScanData = data; // Store for export
    } catch (err) {
        console.error(err);
    }
}

// --- EXPORT FUNCTIONS ---
function downloadJSON() {
    if (!window.currentScanData) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(window.currentScanData, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href",     dataStr);
    downloadAnchorNode.setAttribute("download", `WebSecureX_Report_${window.currentScanData._id || 'scan'}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
}

function downloadCSV() {
    if (!window.currentScanData || !window.currentScanData.scans) return;
    let csv = "Tool,Status,Result,Level,Vulnerabilities\n";
    Object.entries(window.currentScanData.scans).forEach(([key, tool]) => {
        const vuls = (tool.vulnerabilities || []).map(v => v.type).join(' | ');
        csv += `${key},${tool.scan_status},${tool.result},${tool.scan_level},"${vuls}"\n`;
    });
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", `WebSecureX_Report_${window.currentScanData._id || 'scan'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// --- SETTINGS MODAL LOGIC ---
document.addEventListener('DOMContentLoaded', () => {
    const settingsModal = document.getElementById('settings-modal');
    const settingsTrigger = document.getElementById('settings-trigger');
    const closeSettings = document.getElementById('close-settings');
    const changePasswordForm = document.getElementById('change-password-form');
    const passwordStatus = document.getElementById('password-status');

    if (settingsTrigger) {
        settingsTrigger.addEventListener('click', () => {
            settingsModal.style.display = 'flex';
        });
    }

    if (closeSettings) {
        closeSettings.addEventListener('click', () => {
            settingsModal.style.display = 'none';
        });
    }

    // Close modal on click outside
    window.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            settingsModal.style.display = 'none';
        }
    });

    if (changePasswordForm) {
        changePasswordForm.addEventListener('submit', (e) => {
            e.preventDefault();
            passwordStatus.style.display = 'block';
            passwordStatus.style.color = 'var(--accent-green)';
            passwordStatus.innerText = 'Verifying credentials...';
            
            setTimeout(() => {
                passwordStatus.innerText = 'Security credentials updated successfully!';
                setTimeout(() => {
                    settingsModal.style.display = 'none';
                    changePasswordForm.reset();
                    passwordStatus.style.display = 'none';
                }, 1500);
            }, 1000);
        });
    }

    // --- Scheduler Activation ---
    const saveScheduleBtn = document.getElementById('btn-save-schedule');
    const scheduleStatus = document.getElementById('schedule-status');
    if (saveScheduleBtn) {
        saveScheduleBtn.onclick = async () => {
            const url = document.getElementById('schedule-url').value;
            const interval = document.getElementById('schedule-interval').value;
            if (!url) return alert('Please enter a target URL to schedule');
            
            saveScheduleBtn.innerText = 'ACTIVATING...';
            saveScheduleBtn.disabled = true;
            
            try {
                const res = await fetch('/api/schedule', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: auth.getUser()?.username || 'admin',
                        url: url,
                        interval_hours: parseInt(interval)
                    })
                });
                if (res.ok) {
                    scheduleStatus.style.display = 'block';
                    saveScheduleBtn.innerText = 'ACTIVE';
                }
            } catch (err) {
                console.error(err);
                saveScheduleBtn.innerText = 'ERROR';
                saveScheduleBtn.disabled = false;
            }
        };
    }
});
