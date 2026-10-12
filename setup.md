# Offline AI Platform — Setup and Deployment Guide

This guide covers setting up and running the Offline AI Platform (Backend, Frontend, PostgreSQL, and Redis) using either **Docker Compose** (recommended) or a **Bare-Metal Local Environment**.

---

## 1. Repository Layout

Ensure both directories are placed side-by-side under the same parent directory so Docker Compose can resolve both build contexts:

```text
<parent-directory>/
├── offline_ai_backend/      # FastAPI Backend, SQL init script, and docker-compose.yml
└── offline_frontend/        # React + Vite Frontend and Nginx Dockerfile
```

---

## 2. Environment Configuration (`.env`)

Both `.env.example` and `.env-example` are tracked in Git as reference templates. Your actual `.env` file is git-ignored so credentials are never committed.

### 2.1 Copy the Template to `.env`

From inside `offline_ai_backend/`:

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
# OR: Copy-Item .env-example .env
```

```bash
# Linux / macOS (Bash)
cp .env.example .env
# OR: cp .env-example .env
```

### 2.2 What to Replace in `offline_ai_backend/.env`

Open `offline_ai_backend/.env` and update the following fields:

1. **`POSTGRES_PASSWORD`:**
   - Replace `replace_with_your_postgres_password` with your PostgreSQL password (for Docker, whatever password you set here will be used to initialize the PostgreSQL container; for bare-metal, use your local `postgres` user password).
2. **`JWT_SECRET_KEY`:**
   - Generate a random 64-character hex key by running:
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
   - Paste the output into `JWT_SECRET_KEY`.
3. **Gmail SMTP Settings (`SMTP_*`):**
   - **To test immediately without Gmail credentials:** Keep `SMTP_DEV_MODE=true`. All 6-digit OTPs will be printed directly in the backend terminal or Docker logs (`docker compose logs -f backend`).
   - **To send real OTP emails via Gmail:**
     1. Enable 2-Step Verification on your Google Account.
     2. Generate a 16-character App Password at `https://myaccount.google.com/apppasswords` (regular Gmail passwords are rejected by `smtp.gmail.com`).
     3. Set `SMTP_USERNAME` and `SMTP_FROM_EMAIL` to your Gmail address.
     4. Set `SMTP_PASSWORD` to the 16-character App Password (without spaces).
     5. Set `SMTP_DEV_MODE=false`.

4. **Initial Super Admin Account (`SUPER_ADMIN_*`):**
   - Set `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD`, `SUPER_ADMIN_FIRST_NAME`, and `SUPER_ADMIN_LAST_NAME` in `.env` to whatever credentials you want for the initial Super Admin.
   - On startup, `ensure_db_schema()` checks if `SUPER_ADMIN_EMAIL` exists in `offlineai.users`. If it does not exist yet, it automatically hashes `SUPER_ADMIN_PASSWORD` with Bcrypt (12 rounds) and creates the active `super_admin` user.

### 2.3 Full `.env` Reference (`offline_ai_backend/.env`)

```ini
# PostgreSQL Connection
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=replace_with_your_postgres_password
POSTGRES_DB=auth_backend

# Redis Connection
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT Configuration
JWT_SECRET_KEY=replace_with_64_char_hex_secret_generated_via_secrets_token_hex_32
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
JWT_RESET_TOKEN_EXPIRE_MINUTES=15

# OTP Configuration
OTP_LENGTH=6
OTP_EXPIRE_SECONDS=300
OTP_RESEND_COOLDOWN_SECONDS=30
OTP_MAX_ATTEMPTS=5

# Gmail SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=replace_with_16_char_google_app_password
SMTP_FROM_EMAIL=your.email@gmail.com
SMTP_FROM_NAME=Offline AI Platform
SMTP_DEV_MODE=true

# Initial Super Admin Account (Auto-Seeded on Startup)
SUPER_ADMIN_EMAIL=admin@yourdomain.com
SUPER_ADMIN_PASSWORD=Admin@1234
SUPER_ADMIN_FIRST_NAME=Super
SUPER_ADMIN_LAST_NAME=Admin
```

---

## 3. Option A: Docker Setup (Full Stack)

Docker Compose builds and runs all four services (`postgres`, `redis`, `backend`, `frontend`) in isolated containers. You do not need PostgreSQL, Redis, Python, or Node.js installed on the host machine.

### 3.1 Port Mapping Summary
To prevent collisions with any local PostgreSQL or Redis services running on the host machine, the containers map to the following host ports:
- **Frontend (Nginx):** `http://localhost:3000` (Container port `80`)
- **Backend (FastAPI):** `http://localhost:8000` (Container port `8000`)
- **Swagger API Docs:** `http://localhost:8000/docs`
- **PostgreSQL 16:** `localhost:5433` (Container port `5432`)
- **Redis 7:** `localhost:6380` (Container port `6379`)

> Note: Inside `docker-compose.yml`, the `backend` service automatically overrides `POSTGRES_SERVER=postgres`, `POSTGRES_PORT=5432`, `REDIS_HOST=redis`, and `REDIS_PORT=6379` so inter-container networking works automatically without modifying your local `.env`.

### 3.2 Build and Start Containers

Run all commands from inside the `offline_ai_backend` directory:

```bash
cd offline_ai_backend

# Build images and start all 4 containers in detached mode
docker compose up --build -d
```

On first startup:
1. `offline_ai_postgres` initializes database `auth_backend` and executes `sql/init.sql`.
2. `offline_ai_backend` runs `ensure_db_schema()` on startup to verify all 21 tables and idempotent seed records exist inside the `offlineai` schema.

### 3.3 Verify Container Status and Logs

```bash
# Check container states and health status
docker compose ps

# Follow live backend logs (shows startup status and dev-mode OTPs)
docker compose logs -f backend

# Verify backend health endpoint
curl http://localhost:8000/health
```

### 3.4 Stop, Restart, or Reset Docker Environment

```bash
# Restart only the backend container
docker compose restart backend

# Stop all containers (preserves database and Redis data volumes)
docker compose down

# Stop all containers AND wipe database/Redis volumes for a clean slate
docker compose down -v
```

### 3.5 Migrating an Existing Local PostgreSQL Database into Docker (Optional)

If you have existing data in a local PostgreSQL instance on port `5432` and want to import it into the Docker PostgreSQL container on port `5433`:

```powershell
# 1. Dump the offlineai schema from local PostgreSQL (port 5432)
pg_dump -h localhost -p 5432 -U postgres -d auth_backend -n offlineai --no-owner --no-privileges -f local_offlineai_dump.sql

# 2. If dumping from PostgreSQL 17/18 into PostgreSQL 16, strip transaction_timeout
(Get-Content local_offlineai_dump.sql) | Where-Object { $_ -notmatch "transaction_timeout" } | Set-Content local_offlineai_clean.sql

# 3. Drop the fresh schema in Docker and import your dump
docker exec -i offline_ai_postgres psql -U postgres -d auth_backend -c "DROP SCHEMA IF EXISTS offlineai CASCADE;"
Get-Content local_offlineai_clean.sql | docker exec -i offline_ai_postgres psql -U postgres -d auth_backend

# 4. Re-apply sql/init.sql to ensure all latest columns/seeds exist
Get-Content sql/init.sql | docker exec -i offline_ai_postgres psql -U postgres -d auth_backend
```

---

## 4. Option B: Bare-Metal Local Setup (Without Docker)

### 4.1 Prerequisites
- **Python:** 3.10 or 3.11+
- **Node.js:** 18+ or 20+ (with `npm`)
- **PostgreSQL:** 15+ running locally on port `5432`
- **Redis:** 7+ running locally on port `6379`

### 4.2 Database Setup (PostgreSQL)

Create the `auth_backend` database if it does not exist:

```bash
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE auth_backend;"
```

Initialize the `offlineai` schema, all 21 tables, and seed data manually (note: the backend also runs `sql/init.sql` automatically at startup via `ensure_db_schema()`):

```bash
psql -h localhost -p 5432 -U postgres -d auth_backend -f sql/init.sql
```

### 4.3 Redis Setup

Ensure the local Redis server is running and reachable on `localhost:6379`:

```bash
# Start Redis server (if not running as a system service)
redis-server

# Verify connectivity (should return PONG)
redis-cli ping
```

### 4.4 Backend Setup and Startup

From inside `offline_ai_backend/`:

#### Windows (PowerShell)
```powershell
# 1. Create a virtual environment
python -m venv venv

# 2. Activate the virtual environment
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Start the FastAPI server with hot-reload on port 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Linux / macOS (Bash)
```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Start the FastAPI server with hot-reload on port 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4.5 Frontend Setup and Startup

From inside `offline_frontend/`:

```bash
# 1. Configure frontend environment variable
echo "VITE_API_BASE_URL=http://localhost:8000" > .env

# 2. Install Node packages
npm install

# 3. Start the Vite development server
npm run dev
```

For a production static build without Docker:

```bash
npm run build
npm run preview -- --port 3000
```

---

## 5. Default Seeded Credentials and Verification

Once `sql/init.sql` has been applied, the following Super Admin account is seeded by default:

- **Email:** `humza.ahmad050504@gmail.com`
- **Password:** `Test@1234`
- **Role:** `super_admin`

### Quick API Verification Commands

```bash
# 1. Health Check
curl -X GET http://localhost:8000/health

# 2. Step 1 Login (triggers 6-digit OTP to email or console log)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier": "humza.ahmad050504@gmail.com", "password": "Test@1234"}'

# 3. Step 2 Verify OTP (replace 123456 with the 6-digit OTP received)
curl -X POST http://localhost:8000/api/v1/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"identifier": "humza.ahmad050504@gmail.com", "otp": "123456"}'
```

---

## 6. Troubleshooting

1. **`socket.gaierror: [Errno -3] Temporary failure in name resolution` in Docker:**
   - Ensure `POSTGRES_SERVER=postgres` and `REDIS_HOST=redis` are set in the `backend` service's `environment:` block in `docker-compose.yml` and that `.env` is not volume-mounted over `/app/.env`.
2. **`503 Service Unavailable: Failed to send verification email` on `/api/v1/auth/login`:**
   - Either set a valid 16-character Google App Password in `SMTP_PASSWORD` with `SMTP_DEV_MODE=false`, or set `SMTP_DEV_MODE=true` in `.env` to read OTP codes from the terminal/Docker logs.
3. **Port `8000` or `3000` already in use:**
   - Stop any bare-metal `uvicorn` or `npm run dev` processes before running `docker compose up -d`, or adjust the host port mappings in `docker-compose.yml`.
