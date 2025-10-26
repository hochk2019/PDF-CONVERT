# Windows 11 Server Deployment Guide

This guide describes how to provision a Windows 11 host for the PDF Convert stack, configure automation and observability, and integrate with an on-premises NAS.

## 1. Prepare the Operating Environment

1. **Baseline updates**
   - Sign in with an administrative account and apply all pending Windows Updates (`Settings → Windows Update`).
   - Enable required Windows features (PowerShell, Hyper-V, Windows Subsystem for Linux if needed for tooling).
2. **Install package managers**
   - Install [Winget](https://learn.microsoft.com/windows/package-manager/winget/) (preinstalled on current Windows 11 builds). For older builds install manually.
   - Optional: Install [Chocolatey](https://chocolatey.org/install) for additional packages.
3. **Install Python**
   - Use Winget: `winget install --id Python.Python.3.11 --source winget`.
   - During setup enable "Add python.exe to PATH".
   - Verify with `python --version` and `pip --version` in PowerShell.
4. **Install Node.js (LTS)**
   - `winget install --id OpenJS.NodeJS.LTS --source winget`.
   - Confirm installation via `node --version` and `npm --version`.
5. **Install Git and build tools**
   - `winget install --id Git.Git --source winget`.
   - Add the repository SSH key (use `ssh-keygen`, register public key in Git server, add to `~/.ssh/config`).
6. **Install Docker Desktop**
   - `winget install --id Docker.DockerDesktop --source winget`.
   - Enable the "Start Docker Desktop when you log in" option and ensure the WSL 2 backend is enabled.
7. **Clone the project and create a Python virtual environment**
   ```powershell
   git clone git@github.com:example/PDF-CONVERT.git
   cd PDF-CONVERT
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install -r requirements.txt
   npm install --prefix ui
   ```

8. **Tạo file `.env` với cấu hình LLM**
   - Sao chép ví dụ dưới đây vào `C:\PDF-CONVERT\.env` (được backend đọc tự động):
     ```env
     # Ollama cục bộ
     PDFCONVERT_LLM_PROVIDER=ollama
     PDFCONVERT_LLM_MODEL=llama3
     PDFCONVERT_LLM_BASE_URL=http://localhost:11434/api/generate
     PDFCONVERT_LLM_FALLBACK_ENABLED=false

     # OpenRouter (bỏ comment khi sử dụng)
     # PDFCONVERT_LLM_PROVIDER=openrouter
     # PDFCONVERT_LLM_MODEL=meta-llama/llama-3-70b-instruct
     # PDFCONVERT_LLM_BASE_URL=https://openrouter.ai/api/v1/chat/completions
     # PDFCONVERT_LLM_API_KEY=sk-or-...

     # AgentRouter
     # PDFCONVERT_LLM_PROVIDER=agentrouter
     # PDFCONVERT_LLM_MODEL=gpt-4o-mini
     # PDFCONVERT_LLM_BASE_URL=https://api.agentrouter.ai/v1
     # PDFCONVERT_LLM_API_KEY=ar-...
     ```
   - Khi triển khai qua Windows Service hoặc Docker Compose, đảm bảo file `.env` được tham chiếu trong cấu hình.

## 2. Configure Services for Automatic Startup

### Option A: Windows Service
1. Create a wrapper PowerShell script (`C:\Services\pdf-convert.ps1`) that activates the virtual environment and runs the API (example using `uvicorn`):
   ```powershell
   param(
       [string]$WorkingDirectory = "C:\PDF-CONVERT",
       [string]$VenvPath = "C:\PDF-CONVERT\.venv"
   )

   Set-Location $WorkingDirectory
   & "$VenvPath\Scripts\Activate.ps1"
   $env:PYTHONUNBUFFERED = "1"
   Start-Process -FilePath "python" -ArgumentList "-m", "pdf_convert.api", "--host", "0.0.0.0", "--port", "8000" -NoNewWindow -Wait
   ```
2. Register the script as a service using `New-Service`:
   ```powershell
   New-Service -Name "PDFConvertAPI" -BinaryPathName "powershell.exe -ExecutionPolicy Bypass -File C:\Services\pdf-convert.ps1" -DisplayName "PDF Convert API" -Description "Runs the PDF Convert backend" -StartupType Automatic
   ```
3. Grant the service account "Log on as a service" rights, and set recovery actions (`sc failure PDFConvertAPI reset= 120 actions= restart/60000`).

### Option B: Docker Compose Stack
1. Create `docker-compose.yml` (stored under `C:\PDF-CONVERT\deploy\docker-compose.yml`):
   ```yaml
   version: "3.9"
   services:
     api:
       build: ..
       command: ["uvicorn", "pdf_convert.api:app", "--host", "0.0.0.0", "--port", "8000"]
       env_file:
         - ../.env.production
       volumes:
         - ../data:/app/data
       restart: unless-stopped
     worker:
       build: ..
       command: ["celery", "-A", "pdf_convert.celery_app", "worker", "--loglevel=INFO"]
       env_file:
         - ../.env.production
       volumes:
         - ../data:/app/data
       depends_on:
         - api
       restart: unless-stopped
   ```
2. Enable Docker Desktop to start on login and configure the stack to launch automatically:
   - Create `C:\PDF-CONVERT\deploy\start-stack.ps1` that runs `docker compose up -d`.
   - Add a Scheduled Task (Trigger: At startup) running the script with highest privileges.

## 3. Reverse Proxy and HTTPS

### Option A: IIS with URL Rewrite
1. Install IIS features:
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole
   Install-WindowsFeature Web-WebServer, Web-Asp-Net45, Web-Http-Redirect
   ```
2. Install URL Rewrite Module and Application Request Routing (ARR).
3. Create a site `PDFConvertProxy` bound to port 443 and configure an internal certificate (issued by corporate CA).
4. Add a `web.config` to proxy `/api` to the backend:
   ```xml
   <configuration>
     <system.webServer>
       <rewrite>
         <rules>
           <rule name="ReverseProxy" stopProcessing="true">
             <match url="(.*)" />
             <action type="Rewrite" url="http://127.0.0.1:8000/{R:1}" />
             <serverVariables>
               <set name="HTTP_X_FORWARDED_PROTO" value="https" />
             </serverVariables>
           </rule>
         </rules>
       </rewrite>
     </system.webServer>
   </configuration>
   ```
5. Bind the certificate and enforce TLS 1.2+, disable weak ciphers via Group Policy or IIS Crypto.

### Option B: NGINX on Windows
1. Download the Windows build from nginx.org and install under `C:\nginx`.
2. Configure `nginx.conf`:
   ```nginx
   events {}
   http {
     log_format main '$remote_addr - $remote_user [$time_local] "$request" ' '$status $body_bytes_sent "$http_referer" "$http_user_agent"';

     upstream pdf_convert_api {
       server 127.0.0.1:8000;
     }

     server {
       listen 443 ssl;
       server_name pdfconvert.internal;

       ssl_certificate     C:/certs/pdfconvert.pem;
       ssl_certificate_key C:/certs/pdfconvert.key;
       ssl_protocols       TLSv1.2 TLSv1.3;
       ssl_ciphers         HIGH:!aNULL:!MD5;

       location / {
         proxy_pass http://pdf_convert_api;
         proxy_set_header Host $host;
         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
         proxy_set_header X-Forwarded-Proto https;
       }
     }
   }
   ```
3. Install the SSL certificate issued by your internal CA into the Local Computer store and export to PEM for NGINX.
4. Create a Windows service via NSSM or `sc.exe` to keep NGINX running automatically at startup.

## 4. Data Backup and NAS Synchronisation

1. **Structure application data** under `C:\PDF-CONVERT\data` so code, configs, and generated assets remain consistent.
2. **NAS connectivity**
   - Join the server to the domain if applicable.
   - Map the NAS share (e.g., `\NAS01\pdf-backups`) with persistent credentials: `New-PSDrive -Name P -PSProvider FileSystem -Root "\\NAS01\pdf-backups" -Persist`.
3. **Local snapshots**
   - Enable File History targeting the NAS share for user profiles storing config.
4. **Scheduled backup script**
   ```powershell
   $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
   $source = "C:\PDF-CONVERT\data"
   $destination = "P:\pdf-convert\$timestamp"
   robocopy $source $destination /MIR /R:3 /W:5 /FFT /Z /XA:SH /XD "temp"
   ```
   - Save as `C:\Scripts\backup-pdf-convert.ps1`.
   - Register a scheduled task to run daily at 02:00 with email alerts on failure.
5. **Off-site replication**
   - If the NAS replicates off-site, ensure the backup directory is included.
   - Encrypt archives (BitLocker or 7-Zip) before replication if sensitive.

## 5. Monitoring and Observability

1. **Prometheus**
   - Deploy Prometheus via Docker (`prom/prometheus`) using a Windows bind mount for configs (`C:\Monitoring\prometheus.yml`).
   - Configure scrape targets for the API (exporter at `http://localhost:8000/metrics`) and system metrics (e.g., install `windows_exporter`).
2. **Grafana**
   - Run Grafana via Docker (`grafana/grafana`). Persist data in `C:\Monitoring\grafana`.
   - Import dashboards for Windows host metrics, application latency, queue depth.
   - Configure Azure AD/ADFS SSO if required.
3. **Sentry**
   - Use the SaaS version or self-host via Docker Compose (`getsentry/self-hosted`).
   - Set `SENTRY_DSN` in the application `.env` and enable release tracking.
4. **Alerting**
   - Integrate Prometheus Alertmanager (Docker) with email/Teams/Slack.
   - Configure Grafana alerts for SLA breaches (error rate > 1%, queue backlog).
   - Configure Sentry issue alerts for new errors.
5. **Log aggregation**
   - Centralize logs using the Windows Event Forwarding or install Fluent Bit to ship logs to ELK/CloudWatch.

## 6. Security and Maintenance Checklist

- Enforce Windows Defender with real-time scanning and periodic offline scans.
- Apply the principle of least privilege: run services with dedicated service accounts.
- Rotate API secrets and certificates at least every 90 days.
- Patch Windows, Docker images, Python/Node dependencies monthly via automated pipelines.
- Document change management and maintain runbooks in the internal wiki.

## 7. Validation

- Verify all services start automatically after reboot (`Get-Service PDFConvertAPI`, `docker compose ps`).
- Check HTTPS endpoints with `Invoke-WebRequest https://pdfconvert.internal/healthz`.
- Confirm Prometheus targets are `UP` and Grafana dashboards render data.
- Review backup logs to ensure NAS synchronization completes without errors.

