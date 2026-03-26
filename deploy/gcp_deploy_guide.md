# GCP VPC Deployment Guide — Palladam Politics Scraper

A step-by-step guide to running the scraper on a **GCP Compute Engine VM** inside a **VPC** and pushing results to **Google Sheets** automatically.

---

> [!IMPORTANT]
> **Windows users (Cloud SDK on CMD/PowerShell):** The commands below use `$SA_EMAIL` (bash variable syntax).
> On Windows, run the `gcloud iam service-accounts list` command first, **copy the email printed**, then paste it literally into subsequent commands instead of `$SA_EMAIL`.

## Prerequisites

- A **Google Cloud** account with billing enabled
- `gcloud` CLI installed locally ([install](https://cloud.google.com/sdk/docs/install))
- A **Google Sheets** spreadsheet already created

---

## Step 1 — Enable Required APIs

```bash
gcloud services enable compute.googleapis.com sheets.googleapis.com drive.googleapis.com iam.googleapis.com
```

---

## Step 2 — Create a VPC Network

```bash
# Create a custom VPC
gcloud compute networks create palladam-vpc --subnet-mode=custom --bgp-routing-mode=regional

# Create a subnet (change region as needed)
gcloud compute networks subnets create palladam-subnet --network=palladam-vpc --region=asia-south1 --range=10.10.0.0/24

# Allow SSH only (no public HTTP ingress needed)
gcloud compute firewall-rules create allow-ssh-palladam --network=palladam-vpc --allow=tcp:22 --source-ranges=0.0.0.0/0 --description="Allow SSH to scraper VM"
```

---

## Step 3 — Create a GCP Service Account (no key file needed)

Because your GCP organisation has the `constraints/iam.disableServiceAccountKeyCreation` policy,
**do not create a JSON key**. Instead, you will attach the service account directly to the VM
and let the VM authenticate via **Application Default Credentials (ADC)** — no file download required.

```bash
# Create the service account
gcloud iam service-accounts create palladam-scraper-sa --display-name="Palladam Scraper Service Account"

# Get the service account email — copy the output of this command
gcloud iam service-accounts list --filter="displayName:Palladam Scraper Service Account" --format="value(email)"
# e.g. palladam-scraper-sa@project-eb04a8aa-7859-49d7-8a0.iam.gserviceaccount.com
```

> **Share your Google Sheet with the service account:**
> Open your sheet → **Share** → paste the email printed above → set role to **Editor** → click Send.

---

## Step 4 — Create the Compute Engine VM

```cmd
REM Replace the --service-account value with the email printed in Step 3
gcloud compute instances create palladam-scraper-vm --zone=asia-south1-a --machine-type=e2-medium --network=palladam-vpc --subnet=palladam-subnet --image-family=debian-12 --image-project=debian-cloud --boot-disk-size=20GB --boot-disk-type=pd-standard --service-account=palladam-scraper-sa@YOUR-PROJECT-ID.iam.gserviceaccount.com --scopes=https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive.file,https://www.googleapis.com/auth/cloud-platform --tags=scraper-vm --no-address
```

> **This is the key step for ADC:** by passing `--service-account` the VM gets automatic
> Google credentials — no JSON key file needed.

Enable IAP tunnel for SSH (no public IP needed):
```bash
gcloud compute firewall-rules create allow-iap-ssh \
    --network=palladam-vpc \
    --allow=tcp:22 \
    --source-ranges=35.235.240.0/20 \
    --description="Allow SSH from IAP"
```

---

## Step 5 — Upload Project Files to the VM

```bash
# SSH into the VM via IAP
gcloud compute ssh palladam-scraper-vm \
    --zone=asia-south1-a \
    --tunnel-through-iap

# ---------------------  ON THE VM  ---------------------
# Clone the repo
git clone https://github.com/mithunbarath/XDOSO-Palladam-scraper.git /opt/scraper
```

Or use `gcloud scp` to copy your local files:
```bash
gcloud compute scp --recurse \
    c:\Users\navee\Downloads\claude-brightdata-scraper\* \
    palladam-scraper-vm:/opt/scraper \
    --zone=asia-south1-a \
    --tunnel-through-iap
```

---

## Step 6 — (Skipped) No Key File to Upload

Since your organisation blocks service account key creation, **skip this step entirely**.
The VM authenticates via ADC automatically using the service account attached in Step 4.

---

## Step 7 — Run the VM Setup Script

```bash
# SSH in
gcloud compute ssh palladam-scraper-vm --zone=asia-south1-a --tunnel-through-iap

# On the VM:
sudo bash /opt/scraper/deploy/setup_vm.sh
```

This installs Python, Playwright/Chromium, Python dependencies, and sets up a systemd timer.

---

## Step 8 — Configure Secrets and Google Sheets

Edit `/opt/scraper/.env` on the VM:

```bash
sudo nano /opt/scraper/.env
```

Fill in (no JSON key path needed — ADC handles auth automatically):
```
BRIGHT_DATA_API_TOKEN=your_token_here
GOOGLE_SHEETS_SPREADSHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
```

Edit `/opt/scraper/config.yaml` and enable Sheets:
```yaml
google_sheets:
  enabled: true
  spreadsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"   # ← your Sheet ID
  sheet_name: "RawData"
  summary_tab_name: "Summary"
  credentials_path: ""    # leave empty — VM uses ADC automatically
  append_mode: false      # overwrite each run; set true for incremental
```

---

## Step 9 — Test a Manual Run

```bash
sudo -u scraper bash /opt/scraper/deploy/run_scraper.sh
```

Check your Google Sheet — you should see a `RawData` tab and a `Summary` tab populated.

---

## Step 10 — Enable Automatic Scheduling

The systemd timer runs the scraper every **6 hours**:

```bash
sudo systemctl status scraper.timer      # check timer status
sudo systemctl list-timers scraper.timer # see next fire time
sudo journalctl -u scraper.service -f    # watch live logs
```

To change the frequency, edit `/etc/systemd/system/scraper.timer`:
```ini
OnUnitActiveSec=6h   # change to e.g. 12h, 24h, 1h
```
Then: `sudo systemctl daemon-reload && sudo systemctl restart scraper.timer`

---

## Architecture Overview

```
                         ┌─────────────────────────────────────┐
                         │           GCP Project               │
  Your PC                │                                     │
  ─────────              │  ┌──── VPC: palladam-vpc ────────┐  │
  gcloud scp ──────────────►│                               │  │
  (IAP tunnel)           │  │  e2-medium VM                 │  │
                         │  │  ┌────────────────────────┐   │  │
                         │  │  │  systemd timer (6h)    │   │  │
                         │  │  │         ↓              │   │  │
                         │  │  │  main.py               │   │  │
                         │  │  │  ├─ Bright Data API    │   │  │
                         │  │  │  │  (Instagram, YT...) │   │  │
                         │  │  │  ├─ output/data.csv    │   │  │
                         │  │  │  └─ sheets_exporter.py │   │  │
                         │  │  └────────────┬───────────┘   │  │
                         │  └───────────────┼───────────────┘  │
                         └──────────────────┼──────────────────┘
                                            │ Google Sheets API
                                            ▼
                                   ┌─────────────────┐
                                   │  Google Sheet   │
                                   │  ┌─ RawData    │
                                   │  └─ Summary    │
                                   └─────────────────┘
```

---

## Cost Estimate

| Resource | Spec | Est. Monthly Cost |
|---|---|---|
| Compute Engine | e2-medium (2 vCPU, 4 GB) | ~$27/mo |
| Boot disk | 20 GB standard persistent | ~$0.80/mo |
| Network egress | minimal | ~$1-2/mo |
| **Total** | | **~$29/mo** |

> **Tip:** Stop the VM when not in use to save cost, or use a `e2-micro` (free tier) for lighter loads.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Key creation is not allowed` (iam.disableServiceAccountKeyCreation) | Your org blocks JSON keys. Use ADC: attach the service account to the VM (`--service-account` flag). No key file needed. |
| `Permission denied` on Sheet | Re-share Sheet with service account email as Editor |
| `No Google credentials found` locally | Run `gcloud auth application-default login --scopes=...spreadsheets,...drive.file` |
| `gspread` / `google-auth` not found | Run `pip install -r requirements.txt` in the venv |
| VM can't access internet | Add a Cloud NAT gateway to the VPC subnet |
| Playwright install fails | Run `playwright install-deps chromium` as root |

---

## Testing Locally (without a VM)

Since you cannot download a service account key, authenticate locally using your own Google account:

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive.file,https://www.googleapis.com/auth/cloud-platform
```

This saves credentials to your local machine. Then in `config.yaml` set `enabled: true` with your `spreadsheet_id` and leave `credentials_path` empty — the scraper picks up the local ADC automatically.
