# WP Backup Vault

A complete, production-ready WordPress backup solution with a **pull-based architecture**. The WordPress plugin (WP Vault Bridge) creates encrypted, chunked backups on the server, and the Windows desktop client (SafeKeep) periodically connects and downloads them — no inbound connection to your Windows machine required.

## Architecture

```
┌─────────────────────────────────────┐        ┌──────────────────────────────────┐
│         WordPress Server            │        │      Windows Server (Local)       │
│                                     │        │                                   │
│  ┌──────────────────────────────┐   │  PULL  │  ┌────────────────────────────┐  │
│  │     WP Vault Bridge Plugin   │◄──┼────────┼──│       SafeKeep Client      │  │
│  │                              │   │        │  │                            │  │
│  │  • Creates chunked ZIPs      │   │        │  │  • Polls for new backups   │  │
│  │  • Exports database (SQL)    │   │        │  │  • Downloads chunks        │  │
│  │  • Generates manifest.json   │   │        │  │  • Verifies checksums      │  │
│  │  • REST API (API Key auth)   │   │        │  │  • Assembles final archive  │  │
│  │  • WP Cron scheduling        │   │        │  │  • Manages retention       │  │
│  └──────────────────────────────┘   │        │  └────────────────────────────┘  │
│                                     │        │                                   │
│  No public IP needed on Windows ──────────────────────────────────────────────► │
└─────────────────────────────────────┘        └──────────────────────────────────┘

  SafeKeep initiates ALL connections. WordPress server only needs to be
  reachable from the Windows machine (public URL or VPN).
```

---

## Features

### WP Vault Bridge (WordPress Plugin)
- **Full backup**: all `wp-content` files (uploads, themes, plugins) + complete database export
- **Chunked ZIPs**: configurable chunk size (default 50 MB) — survives shared hosting timeouts
- **Step-based processing**: background batch execution avoids `max_execution_time` limits
- **Database export**: uses `mysqldump` when available, falls back to pure-PHP query export
- **manifest.json** per backup: date, total size, chunk list with MD5 + SHA256 checksums, WP version
- **WP Cron scheduling**: run daily or multiple times per day at exact hours
- **Manual backup**: "Backup Now" button in admin panel
- **Retention management**: keep N most recent complete backups, auto-delete older ones
- **Secure REST API**: API Key authentication, rate limiting (60 req/min), Range-header support for resume
- **Admin UI**: Persian (RTL) dashboard with progress bar, log viewer, API key management
- **Security**: `.htaccess` blocks direct web access to backup folder; random component in backup filenames

### SafeKeep (Windows Client)
- **Multi-site**: manage any number of WordPress sites, each with its own URL, API Key, and save path
- **Resumable downloads**: uses HTTP Range headers — interrupted downloads continue from where they left off
- **Checksum verification**: verifies MD5 + SHA256 of every chunk against manifest before assembly
- **Retention management**: keep N most recent backups per site on Windows, auto-delete older
- **Persian RTL GUI**: built with PySide6 — site list, backup table, live download progress bars
- **System tray**: minimizes to tray, runs in background
- **Scheduler**: configurable poll interval per site (default 60 minutes)
- **Encrypted config**: API keys stored encrypted (Fernet + machine-derived key), never plain-text
- **Distributable**: build to standalone `.exe` with PyInstaller — no Python installation required

---

## Installation — WP Vault Bridge (WordPress Plugin)

### Requirements
- WordPress 5.8 or newer
- PHP 7.4 or newer
- Any shared hosting (no root access needed)

### Steps

1. **Download** the `wp-plugin/` folder from this repository.

2. **Rename** the folder to `wp-vault-bridge` (if not already).

3. **Upload** to your WordPress server:
   - Via FTP/SFTP: upload to `wp-content/plugins/wp-vault-bridge/`
   - Via cPanel File Manager: zip the folder, upload to `wp-content/plugins/`, then extract

4. **Activate** in WordPress Admin → Plugins → find "WP Vault Bridge" → Activate.

5. **Configure** in WordPress Admin → WP Vault Bridge:
   - Set your desired chunk size (default: 50 MB)
   - Set retention count (default: 2 backups)
   - Add schedule times (e.g., `02:00`, `14:00`)
   - Copy your **API Key** — you will need it in SafeKeep

6. **Verify** the backups folder is protected:
   - Visit `https://yoursite.com/wp-content/plugins/wp-vault-bridge/backups/` — you should get a 403 Forbidden

### WP Cron Note
WP Cron requires site traffic to trigger. On low-traffic sites, set up a real cron job:
```bash
# Add to server crontab (cPanel → Cron Jobs)
*/5 * * * * wget -q -O /dev/null "https://yoursite.com/wp-cron.php?doing_wp_cron" > /dev/null 2>&1
```

---

## Installation — SafeKeep (Windows Client)

### Option A: Run from Python Source

**Requirements**: Python 3.11+

```bash
# Clone the repository
git clone https://github.com/farshadabolfathi/wp-backup-vault.git
cd wp-backup-vault/windows-client

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### Option B: Build Standalone .exe with PyInstaller

```bash
cd wp-backup-vault/windows-client

# Install dependencies
pip install -r requirements.txt

# Build (Windows only)
build.bat
# or manually:
pyinstaller --onefile --windowed --name SafeKeep main.py

# Output: dist/SafeKeep.exe
```

Run `dist/SafeKeep.exe` — no Python installation needed on the target machine.

### First Run Setup

1. Launch SafeKeep.
2. Click **افزودن سایت** (Add Site).
3. Fill in:
   - Site name (any label)
   - WordPress site URL (e.g., `https://yoursite.com`)
   - API Key (from WP Vault Bridge settings)
   - Save path (e.g., `D:\Backups\MySite`)
   - Retention count (how many backups to keep locally)
   - Check interval in minutes
4. Click **تست اتصال** (Test Connection) — you should see a success message.
5. Click OK. SafeKeep will start polling automatically.

---

## API Key

### Generating
The plugin auto-generates an API Key on first activation. Find it in:
**WordPress Admin → WP Vault Bridge → API Key** section.

### Regenerating
Click the **Regenerate** button in the API Key section. The old key is immediately invalidated. Update SafeKeep with the new key.

### Usage
SafeKeep sends the key in every request:
```
X-API-Key: your-32-character-key-here
```

---

## Settings Reference

| Setting | Location | Default | Description |
|---|---|---|---|
| Chunk Size (MB) | Plugin → Settings | 50 | Max size of each backup chunk ZIP |
| Retention Count (server) | Plugin → Settings | 2 | Complete backups kept on WordPress server |
| Schedule Times | Plugin → Settings | `02:00` | One or more HH:MM times for auto-backup |
| Retention Count (Windows) | SafeKeep → Site Settings | 5 | Complete backups kept per site on Windows |
| Check Interval (min) | SafeKeep → Site Settings | 60 | How often SafeKeep polls for new backups |
| Max Concurrent Downloads | SafeKeep → Global Settings | 2 | Simultaneous chunk downloads |

---

## Security

### API Key Model
- 32-character random key, generated server-side
- Sent in `X-API-Key` header (HTTPS strongly recommended)
- All REST API endpoints require valid key — no WordPress login needed
- Rate limited: 60 requests per minute per IP

### Backup Folder Protection
The plugin writes an `.htaccess` file in the backups folder:
```apache
Order deny,allow
Deny from all
```
Direct HTTP access to backup files returns 403. Files are only served through the authenticated REST API endpoint.

### Encrypted Config (SafeKeep)
API Keys are never stored in plain text. SafeKeep derives an encryption key from your machine's hostname and username using PBKDF2-HMAC-SHA256, then encrypts the config with Fernet symmetric encryption.

### Backup Filenames
Backup folder names include a random 8-character component (e.g., `backup_20240115_a3f8c2d1`) — not guessable by enumeration.

---

## Troubleshooting

### Backup never starts (WP Cron not firing)
WP Cron only runs when someone visits the site. On low-traffic sites:
- Set up a real server cron job (see WP Cron Note above)
- Or trigger manually with the "Backup Now" button

### Backup fails with timeout / memory errors
- Reduce the **Chunk Size** setting (try 25 MB or 10 MB)
- The step-based engine resumes across multiple WP Cron firings automatically

### Database export fails
- Check if `mysqldump` is available on your host
- The plugin falls back to PHP-based export automatically
- If PHP export also fails, check `wp-vault-bridge.log` in the plugin directory

### SafeKeep: download interrupted / stuck
- SafeKeep automatically resumes interrupted downloads using HTTP Range headers
- Check that your firewall allows outbound HTTPS from the Windows machine
- Try "Manual Check" button to re-trigger the download

### SafeKeep: "Connection failed"
- Verify the WordPress site URL includes `https://` (or `http://`)
- Verify the API Key is copied exactly (no extra spaces)
- Check that the WP Vault Bridge plugin is activated on the target site
- Test by visiting: `https://yoursite.com/wp-json/wp-vault-bridge/v1/backups` in a browser (should return 401)

### SafeKeep: checksums don't match
- Delete the partial download folder for that backup
- Click "Manual Check" to re-download

---

## Author

**Farshad Abolfathi**
[https://www.linkedin.com/in/farshad-abolfathi/](https://www.linkedin.com/in/farshad-abolfathi/)

---

## License

MIT License — see [LICENSE](LICENSE) file.

Copyright (c) 2024 Farshad Abolfathi
