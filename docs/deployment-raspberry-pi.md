# Raspberry Pi 3 Model B+ Light-Edge Deployment Guide

**Target Hardware:** Raspberry Pi 3 Model B+ (Broadcom BCM2837B0 Quad-Core Cortex-A53 @ 1.4 GHz, 1 GB LPDDR2 RAM)  
**Target Operating System:** Raspberry Pi OS Lite (64-bit / Debian Bookworm)  
**Profile:** Standalone Light-Edge Station Gateway & Bounded DSP Ingestion Node  
**Ecosystem:** SYSTEM CORRUPT / SYCO23 (`syco23.org`)

---

## 🔬 Hardware Evaluation & Feasibility Matrix

| Component | Can it run on Pi 3B+? | Technical Constraint & Optimization |
| :--- | :--- | :--- |
| **FastAPI REST & SSE Gateway** | **YES** | Uvicorn with 1 worker consumes ~45 MB RAM. |
| **SQLite (WAL Mode)** | **YES** | Replaces PostgreSQL to eliminate ~120 MB RAM container overhead. |
| **Redis 7 Broker** | **YES** | Configured with `maxmemory 48mb` and `volatile-lru` eviction policy. |
| **BPM & Camelot Key Analysis** | **YES** | Windowed FFT analysis with single-core worker processes a 60-min mix in ~90–120s. |
| **EBU R128 Loudness Normalizer** | **YES** | `ffmpeg -af ebur128` runs natively with ARM NEON SIMD acceleration. |
| **AzuraCast Station Sync** | **YES** | Webhook listener and cue injection consume negligible compute. |
| **DJ CUE & Playlist Exports** | **YES** | Text generation (.CUE, Rekordbox XML, Traktor NML) executes in milliseconds. |
| **Demucs 4-Stem Separation** | ❌ **DISABLED** | Requires 2.5–4.0 GB RAM. Triggers Linux OOM-killer immediately on 1 GB RAM. |
| **1080p FFmpeg Video Compositor** | ❌ **DISABLED** | Real-time 1080p H.264 software encoding drops to <3 fps on Cortex-A53. |

---

## 🛠️ Step 1: Operating System & Memory Hardening

### 1.1 Enable 64-Bit Mode and Allocate Minimal GPU Memory
Edit `/boot/firmware/config.txt` (or `/boot/config.txt` on older distributions):
```ini
# Allocate minimal RAM to GPU since this is a headless audio server
gpu_mem=16
arm_64bit=1
```

### 1.2 Install ZRAM Compressed In-Memory Swap
```bash
sudo apt update && sudo apt install -y zram-tools bc htop curl ffmpeg libsndfile1

# Configure 1 GB ZRAM compressed swap
sudo tee /etc/default/zramswap << 'EOF'
ALGO=lz4
PERCENT=100
PRIORITY=100
EOF

sudo systemctl restart zramswap
```

### 1.3 Tune Kernel Memory Swappiness
```bash
sudo tee /etc/sysctl.d/99-syco-rpi.conf << 'EOF'
vm.vfs_cache_pressure=50
vm.swappiness=80
vm.dirty_background_ratio=5
vm.dirty_ratio=10
EOF

sudo sysctl --system
```

---

## 📦 Step 2: Docker Compose Deployment

Run the memory-capped, single-concurrency compose stack:

```bash
# 1. Clone repository
git clone https://github.com/murphieslaw23/mix-analyst.git /opt/syco23/mix-analyst
cd /opt/syco23/mix-analyst

# 2. Create storage directory
mkdir -p storage/uploads storage/mastered
sudo chown -R 1000:1000 storage

# 3. Start lightweight stack
docker compose -f docker-compose.rpi.yml up -d --build

# 4. Verify memory and logs
docker stats
docker compose -f docker-compose.rpi.yml logs -f
```

---

## ⚡ Step 3: Native Systemd Deployment (Lowest RAM Overhead)

Running directly on the OS saves ~80 MB of container virtualization overhead:

### 3.1 Setup Python Virtual Environment
```bash
sudo mkdir -p /opt/syco23/mix-analyst /opt/syco23/storage
sudo chown -R $USER:$USER /opt/syco23

cd /opt/syco23/mix-analyst
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r api/requirements.txt
pip install -r worker/requirements.txt
```

### 3.2 FastAPI Systemd Service (`/etc/systemd/system/syco-api.service`)
```ini
[Unit]
Description=SYCO23 Mix Analyst FastAPI Gateway (Raspberry Pi)
After=network.target redis-server.service

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/syco23/mix-analyst/api
EnvironmentFile=/opt/syco23/mix-analyst/.env
ExecStart=/opt/syco23/mix-analyst/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
Restart=always
RestartSec=5
MemoryMax=200M

[Install]
WantedBy=multi-user.target
```

### 3.3 Celery Worker Systemd Service (`/etc/systemd/system/syco-worker.service`)
```ini
[Unit]
Description=SYCO23 Mix Analyst Bounded Celery Worker (Raspberry Pi)
After=network.target redis-server.service

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/syco23/mix-analyst/worker
EnvironmentFile=/opt/syco23/mix-analyst/.env
ExecStart=/opt/syco23/mix-analyst/.venv/bin/celery -A celery_app.celery worker --loglevel=INFO --concurrency=1 --max-memory-per-child=256000
Restart=always
RestartSec=10
MemoryMax=400M

[Install]
WantedBy=multi-user.target
```

### 3.4 Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now redis-server syco-api syco-worker
sudo systemctl status syco-api syco-worker
```

---

## 🛡️ MicroSD Wear-Leveling and Health Protections

1. **Mount `/tmp` and `/var/log` to RAM (`tmpfs`):**
   Add to `/etc/fstab`:
   ```fstab
   tmpfs    /tmp               tmpfs    defaults,noatime,nosuid,size=128m          0 0
   tmpfs    /var/log           tmpfs    defaults,noatime,nosuid,mode=0755,size=64m 0 0
   ```

2. **Mount External USB SSD for Audio Storage:**
   ```fstab
   UUID=YOUR-USB-UUID-HERE  /opt/syco23/storage  ext4  defaults,noatime  0 2
   ```

---

## 📊 Pi 3B+ Memory Budget Summary

```
Total Physical RAM: 1024 MB
├─ Kernel & OS Base:     ~110 MB
├─ Redis Server:          ~30 MB
├─ FastAPI Gateway:       ~60 MB
├─ Celery Audio Worker:  ~280 MB (Peak during FFT / BPM extraction)
├─ System Cache / Free:  ~544 MB
└─ ZRAM Swap Available: 1024 MB (Compressed in RAM with ~2.5:1 ratio)
```
