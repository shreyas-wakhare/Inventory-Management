<#
.SYNOPSIS
    Bootstraps the local PostgreSQL database, role, extensions, and backend/.env
    for the SER Inventory Management System using a locally installed PostgreSQL instance.
#>
param(
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432,
    [string]$AdminUser = "postgres",
    [string]$AppUser = "ser_admin",
    [string]$DbName = "ser_inventory"
)

$ErrorActionPreference = "Stop"

$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    throw "psql was not found on PATH. Ensure PostgreSQL bin directory is added to PATH."
}

function Read-PlainSecret([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

Write-Host "=== SER Inventory Management System - Local PostgreSQL Setup ===" -ForegroundColor Cyan
Write-Host "Host: ${PgHost}:${PgPort} | Superuser: $AdminUser | App User: $AppUser | DB: $DbName"

$adminPassword = Read-PlainSecret "Enter existing PostgreSQL superuser password for '$AdminUser'"
$appPassword = Read-PlainSecret "Enter a local password to set for PostgreSQL app user '$AppUser'"

if ([string]::IsNullOrWhiteSpace($appPassword)) {
    throw "App user password cannot be empty."
}

$escapedSqlPassword = $appPassword.Replace("'", "''")

try {
    if (-not [string]::IsNullOrEmpty($adminPassword)) {
        $env:PGPASSWORD = $adminPassword
    }

    Write-Host "`nStep 1/4: Creating/updating role '$AppUser'..." -ForegroundColor Yellow
    $roleSql = @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$AppUser') THEN
        CREATE ROLE $AppUser WITH LOGIN PASSWORD '$escapedSqlPassword';
    ELSE
        ALTER ROLE $AppUser WITH LOGIN PASSWORD '$escapedSqlPassword';
    END IF;
END
`$`$;
"@
    & psql -h $PgHost -p $PgPort -U $AdminUser -d postgres -v ON_ERROR_STOP=1 -c $roleSql
    if ($LASTEXITCODE -ne 0) { throw "Failed to create or update role '$AppUser'." }

    Write-Host "`nStep 2/4: Creating database '$DbName' if it does not exist..." -ForegroundColor Yellow
    $rawDbExists = & psql -h $PgHost -p $PgPort -U $AdminUser -d postgres -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM pg_database WHERE datname = '$DbName'"
    if ($LASTEXITCODE -ne 0) { throw "Failed to check existing databases." }
    $dbExists = ($rawDbExists | Out-String).Trim()

    if ($dbExists -ne "1") {
        & psql -h $PgHost -p $PgPort -U $AdminUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DbName OWNER $AppUser;"
        if ($LASTEXITCODE -ne 0) { throw "Failed to create database '$DbName'." }
    } else {
        Write-Host "Database '$DbName' already exists. Ensuring ownership..."
        & psql -h $PgHost -p $PgPort -U $AdminUser -d postgres -v ON_ERROR_STOP=1 -c "ALTER DATABASE $DbName OWNER TO $AppUser;"
        if ($LASTEXITCODE -ne 0) { throw "Failed to update database ownership." }
    }

    Write-Host "`nStep 3/4: Applying PostgreSQL extensions from database/init/01_init.sql..." -ForegroundColor Yellow
    $initSqlPath = Join-Path $PSScriptRoot "..\init\01_init.sql"
    & psql -h $PgHost -p $PgPort -U $AdminUser -d $DbName -v ON_ERROR_STOP=1 -f $initSqlPath
    if ($LASTEXITCODE -ne 0) { throw "Failed to apply 01_init.sql." }
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host "`nStep 4/4: Writing backend/.env (gitignored)..." -ForegroundColor Yellow
$encodedPassword = [System.Uri]::EscapeDataString($appPassword)
$databaseUrl = "postgresql+psycopg://${AppUser}:${encodedPassword}@${PgHost}:${PgPort}/${DbName}"
$backendEnvPath = Join-Path $PSScriptRoot "..\..\.env"

$envContent = @"
APP_NAME="SER Inventory Management System API"
APP_ENV=development
APP_DEBUG=true
API_V1_PREFIX=/api/v1
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]

# PostgreSQL (Local)
DATABASE_URL=$databaseUrl
DB_ECHO=false

# Security (local dev only)
JWT_SECRET_KEY=local-dev-secret-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# AI Module (isolated)
AI_ENABLED=false
AI_PROVIDER=none
AI_API_KEY=
"@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($backendEnvPath, $envContent, $utf8NoBom)

Write-Host "`nLocal PostgreSQL setup complete!" -ForegroundColor Green
Write-Host " - Database '$DbName' ready with uuid-ossp & pgcrypto extensions"
Write-Host " - Created gitignored backend/.env"
Write-Host "`nNext: Verify connection from backend/ via:" -ForegroundColor Cyan
Write-Host '  cd backend; .\.venv\Scripts\python.exe -c "from database.session import check_db_connection; print(''DB connected:'', check_db_connection())"'
