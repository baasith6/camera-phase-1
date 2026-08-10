"""
"""

WIZARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Setup - ONETIX Local Connector 1.1.20</ title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #f5f6f7;
      --panel: #ffffff;
      --text: #172033;
      --muted: #64748b;
      --accent: #0066ff;
      --accent-hover: #0052cc;
      --border: #d1d5db;
      --success: #16a34a;
      --success-bg: #ecfdf5;
      --error: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      overflow: hidden;
    }

    /* Main Container */
    .wizard-window {
      width: 950px;
      height: 680px;
      background: var(--panel);
      display: flex;
      flex-direction: column;
      box-shadow: 0 15px 30px rgba(0,0,0,0.1);
      border-radius: 4px;
      position: relative;
    }

    /* Header Section */
    .header {
      padding: 30px 45px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 1px solid transparent;
    }
    .header h1 { font-size: 1.4rem; font-weight: 700; color: #000; margin-bottom: 5px; }
    .header p { color: var(--muted); font-size: 0.95rem; }
    .box-icon { width: 75px; height: 75px; object-fit: contain; }

    /* Content Area */
    .content {
      flex: 1;
      padding: 0 45px;
      overflow-y: auto;
    }
    .hidden { display: none !important; }

    /* Icons & Info Boxes */
    .info-row { display: flex; align-items: center; gap: 15px; margin: 25px 0; font-size: 0.95rem; line-height: 1.5; color: #334155; }
    .key-icon { font-size: 28px; color: #334155; transform: rotate(-45deg); }
    .security-note { display: flex; align-items: center; gap: 12px; margin-top: 45px; font-size: 0.95rem; color: #334155; }
    .shield-icon { color: #3b82f6; font-size: 28px; }

    /* Inputs & Forms */
    label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 8px; color: #334155; }
    .input-group { position: relative; }
    input, textarea, select {
      width: 100%; padding: 12px 14px; border: 1px solid #3b82f6; 
      border-radius: 4px; font-size: 1rem; margin-bottom: 4px;
    }
    .copy-icon { position: absolute; right: 12px; top: 12px; color: #3b82f6; cursor: pointer; }
    .hint { font-size: 0.85rem; color: var(--muted); margin-bottom: 20px; }

    /* Source Grid Cards */
    .source-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 25px; }
    .source-card {
      border: 1px solid var(--border); padding: 15px; border-radius: 8px;
      cursor: pointer; text-align: center; transition: 0.2s;
    }
    .source-card.active { border: 2px solid var(--accent); background: #f0f7ff; }
    .source-card .icon { font-size: 24px; margin-bottom: 8px; color: var(--accent); }
    .source-card h3 { font-size: 0.9rem; font-weight: 600; }
    .source-card p { font-size: 0.75rem; color: var(--muted); }

    /* Table Design */
    table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 0.85rem; border: 1px solid #f1f5f9; }
    th { text-align: left; padding: 12px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; color: var(--muted); }
    td { padding: 12px; border-bottom: 1px solid #f1f5f9; }
    .badge-valid { background: #dcfce7; color: #166534; padding: 3px 10px; border-radius: 4px; font-weight: 600; }

    /* Zone Page Layout */
    .zone-layout { display: grid; grid-template-columns: 1.6fr 1fr; gap: 20px; margin-top: 5px; }
    canvas { background: #000; width: 100%; border-radius: 6px; border: 1px solid var(--border); }
    .zone-side { border: 1px solid var(--border); border-radius: 8px; padding: 20px; background: #fff; }
    .zone-item { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid #f1f5f9; font-size: 0.9rem; }
    .zone-item:last-child { border: none; }

    /* Success Screen */
    .success-ui { text-align: center; padding-top: 10px; }
    .check-mark { 
      width: 80px; height: 80px; background: #dcfce7; color: #22c55e; 
      border-radius: 50%; display: flex; align-items: center; justify-content: center;
      font-size: 40px; margin: 0 auto 15px;
    }
    .summary-box { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 25px; margin-top: 20px; text-align: left; }
    .summary-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
    .success-pill { background: #ecfdf5; color: #16a34a; font-weight: 700; padding: 4px 12px; border-radius: 6px; font-size: 0.75rem; }

    /* Dashboard UI (Single Stop/Start Toggle) */
    .dash-ui { padding: 20px; }
    .status-card { background: #f8fafc; border: 1px solid #e2e8f0; padding: 25px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; }
    .btn-toggle { padding: 14px 30px; border-radius: 8px; font-weight: 700; cursor: pointer; border: none; min-width: 160px; font-size: 1rem; color: #fff; transition: 0.3s; }
    .btn-stop { background: var(--error); }
    .btn-start { background: var(--success); }

    /* Footer Section */
    .footer {
      padding: 20px 45px;
      border-top: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .btn { padding: 10px 30px; border-radius: 6px; font-weight: 600; cursor: pointer; border: 1px solid var(--border); font-size: 0.95rem; }
    .btn-next { background: var(--accent); color: #fff; border: none; }
    .btn-next:hover { background: var(--accent-hover); }
    .btn-skip { background: #fff; color: var(--text); }
    .btn-hidden { visibility: hidden; }

  </style>
</head>
<body>

  <div class="wizard-window" id="mainWizard">
    <!-- Header -->
    <div class="header" id="wizardHeader">
      <div>
        <h1 id="titleText">Enter Setup Code</h1>
        <p id="subText">Please enter the setup code provided for this store.</p>
      </div>
      <img src="https://cdn-icons-png.flaticon.com/512/3014/3014165.png" class="box-icon" alt="package">
    </div>

    <!-- Step 0: Setup Code -->
    <div class="content" id="panel0">
      <div class="info-row">
        <span class="key-icon">🔑</span>
        <span>The setup code links this installation to your store.<br>You can find your setup code in the ONETIX dashboard.</span>
      </div>
      <label>Setup Code</label>
      <div class="input-group">
        <input type="text" id="setupCodeInput" placeholder="Enter your setup code here">
        <span class="copy-icon">📋</span>
      </div>
      <p class="hint">Example: ABCD-EFGH-IJKL-MNOP</p>
      <div class="security-note">
        <span class="shield-icon">🛡️</span>
        <span>Your setup code is encrypted and secure.</span>
      </div>
    </div>

    <!-- Step 1: Add Source -->
    <div class="content hidden" id="panel1">
      <div class="source-grid">
        <div class="source-card active" onclick="setSource('rtsp')">
          <div class="icon">🎥</div>
          <h3>RTSP Camera</h3>
          <p>Add one or more RTSP links</p>
        </div>
        <div class="source-card" onclick="setSource('onvif')">
          <div class="icon">📡</div>
          <h3>ONVIF Camera</h3>
          <p>Connect using IP, port and login</p>
        </div>
        <div class="source-card" onclick="setSource('mp4')">
          <div class="icon">📁</div>
          <h3>Local MP4</h3>
          <p>Upload a test video file</p>
        </div>
      </div>

      <div id="src-rtsp">
        <label>RTSP URLs (one per line)</label>
        <textarea style="height: 100px;" placeholder="rtsp://admin:pass@192.168.1.64:554/stream1"></textarea>
      </div>

      <div id="src-onvif" class="hidden">
        <label>IP Address or Hostname</label>
        <input type="text" value="192.168.1.100">
        <div style="display:flex; gap:10px; margin-top:10px;">
          <div style="flex:1"><label>Port</label><input type="number" value="80"></div>
          <div style="flex:1"><label>Username</label><input type="text" value="admin"></div>
        </div>
        <label style="margin-top:10px;">Password</label>
        <input type="password" value="********">
      </div>

      <div id="src-mp4" class="hidden" style="border: 2px dashed #cbd5e1; padding: 40px; text-align: center; border-radius: 8px;">
        <span style="font-size: 32px;">☁️</span>
        <p style="margin-top:10px;">Drag and drop your MP4 file here or <span style="color:var(--accent); cursor:pointer;">Select File</span></p>
      </div>

      <h3 style="font-size: 0.95rem; margin: 25px 0 10px;">Added Sources (2)</h3>
      <table>
        <thead>
          <tr><th>#</th><th>Source URL</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr><td>1</td><td>rtsp://admin:pass@192.168.1.64:554/stream1</td><td><span class="badge-valid">Valid</span></td><td>✏️ 🗑️</td></tr>
          <tr><td>2</td><td>rtsp://admin:pass@192.168.1.65:554/stream1</td><td><span class="badge-valid">Valid</span></td><td>✏️ 🗑️</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Step 2: Zone -->
    <div class="content hidden" id="panel2">
      <div style="display:flex; justify-content: flex-end; margin-bottom: 10px;">
        <button class="btn btn-skip" style="padding: 5px 15px; font-size: 0.8rem;">🔄 Refresh Frame</button>
      </div>
      <div class="zone-layout">
        <canvas id="zoneCanvas" width="500" height="320"></canvas>
        <div class="zone-side">
          <label>Zones</label>
          <div class="zone-item"><input type="checkbox" checked> <span style="color:green">●</span> High Value Shelf <span style="margin-left:auto">✏️ 🗑️</span></div>
          <div class="zone-item"><input type="checkbox" checked> <span style="color:red">●</span> Checkout Area <span style="margin-left:auto">✏️ 🗑️</span></div>
          <div class="zone-item"><input type="checkbox" checked> <span style="color:blue">●</span> Entrance Area <span style="margin-left:auto">✏️ 🗑️</span></div>
          <button class="btn" style="width:100%; margin-top:20px; border-style: dashed; color: var(--accent);">+ Add Zone</button>
        </div>
      </div>
      <p style="font-size: 0.85rem; color: var(--muted); margin-top: 15px;">ⓘ <b>Tip:</b> Drag points to create or edit a zone.</p>
    </div>

    <!-- Step 3: Success -->
    <div class="content hidden" id="panel3">
      <div class="success-ui">
        <div class="check-mark">✓</div>
        <h2 style="font-size: 1.6rem; margin-bottom: 8px;">Installation Successful!</h2>
        <p style="color:var(--muted)">ONETIX Local Connector has been installed and configured successfully.</p>
        
        <div class="summary-box">
          <h3 style="font-size: 1rem; margin-bottom: 15px;">Summary</h3>
          <div class="summary-row">
            <span>🔑 Setup Code <br><small id="finalCode" style="color:var(--muted)">ABCD-EFGH-IJKL-MNOP</small></span>
            <span class="success-pill">Success</span>
          </div>
          <div class="summary-row">
            <span>🎥 Sources Added <br><small style="color:var(--muted)">2 source(s)</small></span>
            <span class="success-pill">Success</span>
          </div>
          <div class="summary-row">
            <span>▧ Detection Zones <br><small style="color:var(--muted)">3 zone(s)</small></span>
            <span class="success-pill">Success</span>
          </div>
          <div class="summary-row">
            <span>🛡️ Service Status <br><small style="color:var(--muted)">Connector service is running</small></span>
            <span class="success-pill">Success</span>
          </div>
        </div>
        
        <div style="background: #eff6ff; padding: 15px; border-radius: 8px; margin-top: 20px; display: flex; align-items: center; gap: 12px; text-align: left; font-size: 0.85rem; border: 1px solid #bfdbfe;">
            <span style="font-size: 20px; color: var(--accent);">ⓘ</span>
            <span>You can manage and monitor your connector from the dashboard.<br>Health Page: <a href="#" style="color:var(--accent)">http://localhost:8099/</a></span>
        </div>
      </div>
    </div>

    <!-- Dashboard (Hidden until Finish) -->
    <div class="content hidden" id="panelDashboard">
      <div class="dash-ui">
        <h1 style="margin-bottom: 25px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px;">Connector Dashboard</h1>
        <div class="status-card">
          <div>
            <h2 style="font-size: 1.2rem;">Connector Name: <span style="color:var(--accent)">ONETIX Store 01</span></h2>
            <p style="color:var(--muted); margin-top: 5px;">Primary Camera: <b>Main Entrance</b></p>
          </div>
          <button id="toggleBtn" class="btn-toggle btn-stop" onclick="toggleService()">Stop Service</button>
        </div>
        
        <div style="margin-top: 30px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
           <div class="summary-box" style="margin:0;"><h3>Active Sources</h3><p style="margin-top:10px; color:var(--muted);">2 RTSP Streams Connected</p></div>
           <div class="summary-box" style="margin:0;"><h3>Detection Events</h3><p style="margin-top:10px; color:var(--muted);">Monitoring Active...</p></div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="footer" id="wizardFooter">
      <button class="btn btn-skip btn-hidden" id="btnBack" onclick="changeStep(-1)">Back</button>
      <div>
        <button class="btn btn-skip btn-hidden" id="btnSkip" onclick="changeStep(1)">Skip</button>
        <button class="btn btn-next" id="btnNext" onclick="changeStep(1)">Next</button>
      </div>
    </div>
  </div>

  <script>
    let step = 0;
    const titles = [
      "Enter Setup Code", 
      "Add Camera Source (Optional)", 
      "Set Detection Zone (Optional)", 
      "Installation Successful!"
    ];
    const subs = [
      "Please enter the setup code provided for this store.",
      "Connect a camera or upload a video. You can also skip this step and add sources later.",
      "Draw and define detection zones on the video frame.",
      "ONETIX Local Connector has been installed and configured successfully."
    ];

    function changeStep(dir) {
      if (step + dir >= 0 && step + dir <= 3) {
        document.getElementById('panel' + step).classList.add('hidden');
        step += dir;
        document.getElementById('panel' + step).classList.remove('hidden');
        updateUI();
      } else if (step === 3 && dir === 1) {
        // Go to Dashboard
        showDashboard();
      }
    }

    function updateUI() {
      // Title & Header Update
      document.getElementById('titleText').textContent = titles[step];
      document.getElementById('subText').textContent = subs[step];

      // Button Visibility
      document.getElementById('btnBack').classList.toggle('btn-hidden', step === 0 || step === 3);
      document.getElementById('btnSkip').classList.toggle('btn-hidden', step === 0 || step === 3);
      document.getElementById('btnNext').textContent = (step === 3) ? "Finish" : "Next";

      // Final Code Display
      if(step === 3) {
        const code = document.getElementById('setupCodeInput').value || "ABCD-EFGH-IJKL-MNOP";
        document.getElementById('finalCode').textContent = code;
        document.getElementById('wizardHeader').style.display = "none"; // Hide header on success like image
      } else {
        document.getElementById('wizardHeader').style.display = "flex";
      }
    }

    function setSource(type) {
      document.querySelectorAll('.source-card').forEach(c => c.classList.remove('active'));
      event.currentTarget.classList.add('active');
      document.getElementById('src-rtsp').classList.toggle('hidden', type !== 'rtsp');
      document.getElementById('src-onvif').classList.toggle('hidden', type !== 'onvif');
      document.getElementById('src-mp4').classList.toggle('hidden', type !== 'mp4');
    }

    function showDashboard() {
      document.getElementById('panel3').classList.add('hidden');
      document.getElementById('wizardFooter').classList.add('hidden');
      document.getElementById('panelDashboard').classList.remove('hidden');
      document.getElementById('mainWizard').style.height = "auto";
      document.getElementById('mainWizard').style.minHeight = "400px";
    }

    // Toggle Service Logic
    let isRunning = true;
    function toggleService() {
      const btn = document.getElementById('toggleBtn');
      if (isRunning) {
        btn.textContent = "Start Service";
        btn.className = "btn-toggle btn-start";
        isRunning = false;
        console.log("ONETIX Service: Stopped");
      } else {
        btn.textContent = "Stop Service";
        btn.className = "btn-toggle btn-stop";
        isRunning = true;
        console.log("ONETIX Service: Running");
      }
    }

    // Canvas Background Simulation
    const canvas = document.getElementById('zoneCanvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    img.onload = () => ctx.drawImage(img, 0, 0, 500, 320);
    img.src = "https://images.unsplash.com/photo-1534452203293-494d7ddbf7e0?auto=format&fit=crop&w=500&q=80";

  </script>
</body>
</html>
"""
