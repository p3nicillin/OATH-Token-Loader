# OATH Token Loader

A Python tool for bulk uploading and assigning Feitian hardware OATH tokens to users in Microsoft Entra ID (Azure AD) via the Microsoft Graph API.

## Features

- Upload HMAC-SHA256 hardware OATH tokens to Entra ID
- Assign tokens to users with automatic TOTP verification
- Supports both hex and Base32 seeds
- Bulk mode via CSV file
- Single token mode via interactive menu or command-line arguments
- Auto-installs Python dependencies on first run
- Handles duplicate tokens gracefully (looks up existing device on 409 conflict)

## Prerequisites

- Python 3.8+
- An Azure App Registration with the following Microsoft Graph **application** permission:
  - `Policy.ReadWrite.AuthenticationMethod`

## Setup

**1. Clone the repo**
```
git clone https://github.com/p3nicillin/OATH-Token-Loader.git
cd OATH-Token-Loader
```

**2. Configure credentials**

Copy `.env.example` to `.env` and fill in your Azure App Registration details:
```
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
```

> The `.env` file is git-ignored and will never be committed.

**3. Prepare your tokens**

Copy `tokens.example.csv` to `tokens.csv` and fill in your real data:
```
serial_number,seed,user
1234567890,JBSWY3DPEHPK3PXP,user@yourdomain.com
```

> `tokens.csv` is git-ignored and will never be committed.

- `serial_number` — the serial number printed on the token
- `seed` — the secret seed (Base32 or hex, both accepted)
- `user` — the user's UPN (email) or Azure Object ID

> **Excel warning:** If editing in Excel, format the `serial_number` column as **Text** before entering values, otherwise Excel will convert long numbers to scientific notation (e.g. `2.30753E+12`) and truncate them.

## Usage

### Double-click `run.bat` (Windows)

Launches an interactive menu:
```
========================================
  Feitian OTP Token Manager
========================================
  1. Single token
  2. Bulk from CSV
========================================
Select an option (1 or 2):
```

### Command line

**Single token:**
```
python manage_tokens.py <serial> <seed> <user>
```

**Bulk from CSV:**
```
python manage_tokens.py tokens.csv
```
Or just `python manage_tokens.py` to use `tokens.csv` by default.

## Configuration

Settings at the top of `manage_tokens.py`:

| Variable | Default | Description |
|---|---|---|
| `MANUFACTURER` | `Feitian` | Token manufacturer name |
| `MODEL` | `C200` | Token model name |
| `TIME_STEP` | `30` | TOTP interval in seconds (30 or 60 depending on batch) |
