#!/usr/bin/env python3
"""
================================================================================
ouo.io & exe.io 24/7 Automation & Telegram Control Center (Standalone Pro Engine)
================================================================================
Features:
  1. ouo_login.py         - Headless / proxy login and session cookie generator
  2. ouo_shorten.py       - Authenticated link shortener using CSRF token
  3. exe_shorten          - Instant exe.io API shortening (0 MB proxy overhead)
  4. Human ad-view visitor - Cloudflare Turnstile & natural timer bypass
  5. Multi-platform view  - Dual earning (ouo.io + exe.io in single proxy session)
  6. Admin Link Pool      - Manual link injector + automated dynamic URL fallback
  7. Smart Campaign Mode  - Proxy GB estimator + uneven daily schedule distribution
  8. US Day/Night Curve   - Realistic traffic flow based on US Eastern timezone
  9. Stealth Antidetect   - Randomized User-Agents & WebGL/navigator spoofing
 10. Telegram Bot Control - Complete wizard for campaigns, links & live dashboard

Usage:
  python ouo_standalone.py daemon               # Run 24/7 multi-worker background engine
  python ouo_standalone.py bot                  # Run Telegram bot interface
  python ouo_standalone.py all                  # Run BOTH Daemon & Telegram Bot concurrently
  python ouo_standalone.py campaign [views]     # Run campaign for N views (e.g. 5)
  python ouo_standalone.py login                # Test login & generate session cookies
  python ouo_standalone.py shorten <target_url> # Shorten target URL
  python ouo_standalone.py visit <short_url>    # Visit and bypass a shortlink
  python ouo_standalone.py status               # Display current stats in terminal
================================================================================
"""

import os
import sys
import time
import json
import random
import string
import signal
import argparse
import threading
import subprocess
import urllib.parse
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False

# Optional Telegram bot support
try:
    import telebot
    from telebot import types
    from telebot.apihelper import ApiTelegramException
    TELEBOT_AVAILABLE = True
except ImportError:
    telebot = None
    types = None
    ApiTelegramException = Exception
    TELEBOT_AVAILABLE = False

# Force UTF-8 unbuffered output for live logging on all systems (Windows & Linux)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

# ------------------------------------------------------------------------------
# 1. PATH RESOLUTION & CONFIGURATION
# ------------------------------------------------------------------------------
BASE_DIR = os.environ.get("OUO_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))

def resolve_path(filename, legacy_path=None):
    local_p = os.path.join(BASE_DIR, filename)
    if not os.path.exists(local_p) and legacy_path and os.path.exists(legacy_path):
        return legacy_path
    return local_p

SESSION_FILE = resolve_path("ouo_session.json", "/home/ipx/ouo_session.json")
STATS_FILE = resolve_path("campaign_stats.json", "/home/ipx/campaign_stats.json")
AUTH_FILE = resolve_path("bot_auth.json", "/home/ipx/bot_auth.json")
LINK_POOL_FILE = resolve_path("link_pool.json", "/home/ipx/link_pool.json")
CAMPAIGN_FILE = resolve_path("active_campaign.json", "/home/ipx/active_campaign.json")

# Residential proxy for login & link shortener
PROXY_CONFIG = {
    'server': os.environ.get('OUO_PROXY_SERVER', 'http://gw.proxyrise.com:443'),
    'username': os.environ.get('OUO_PROXY_USER', 'res-ca'),
    'password': os.environ.get('OUO_PROXY_PASS', 'pgw-965647e9eeff6541c4ef48d4cd76bde00a51e5c609825dc3')
}

# Dedicated Rotating Residential Proxy for visitor traffic
VISITOR_PROXY_CONFIG = {
    'server': os.environ.get('OUO_VISITOR_PROXY_SERVER', 'http://gw.proxyrise.com:443'),
    'username': os.environ.get('OUO_VISITOR_PROXY_USER', 'res-ca'),
    'password': os.environ.get('OUO_VISITOR_PROXY_PASS', 'pgw-965647e9eeff6541c4ef48d4cd76bde00a51e5c609825dc3')
}

OUO_USERNAME = os.environ.get('OUO_USERNAME', "")
OUO_PASSWORD = os.environ.get('OUO_PASSWORD', "")
MASTER_PASSWORD = os.environ.get('MASTER_PASSWORD', "admin123")
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8980152386:AAE_Y9Z8NuKDrlV_8PouLBvGhuxT_xKfGgo")
EXE_API_TOKEN = os.environ.get('EXE_API_TOKEN', "997b4759bfd0db833ad83fdb5bcab92fbf8e422f")

HOURLY_CHECK_INTERVAL = 3600  # 1 hour
NUM_WORKERS = int(os.environ.get("OUO_WORKERS", 8))   # Recommended 8 workers for 4GB VPS
SESSION_LIFETIME = 86400      # 24 Hours

# ------------------------------------------------------------------------------
# 2. REALISTIC USER-AGENT POOL & HARDWARE STEALTH
# ------------------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
]

def get_random_ua():
    return random.choice(USER_AGENTS)

STEALTH_INJECT_JS = """
(() => {
    // 1. Hide webdriver flag
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // 2. Realistic languages
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

    // 3. Fake hardware concurrency & deviceMemory
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

    // 4. Fake Chrome plugins array
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });

    // 5. Spoof WebGL Vendor & Renderer
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Google Inc. (Intel)';
        if (parameter === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        return getParameter.apply(this, arguments);
    };
})();
"""

# ------------------------------------------------------------------------------
# 3. US DAY/NIGHT TRAFFIC CURVE (Natural Realistic Flow)
# ------------------------------------------------------------------------------
# US Eastern Time (UTC-5) hourly traffic weights
# 1.0 = baseline normal, >1.0 = peak hours, <1.0 = sleeping / slow hours
US_TRAFFIC_CURVE = {
    0: 0.30,   # 12 AM - night
    1: 0.18,   # 1 AM - quiet
    2: 0.12,   # 2 AM - dead
    3: 0.10,   # 3 AM - minimum traffic
    4: 0.12,   # 4 AM - dead
    5: 0.22,   # 5 AM - early risers
    6: 0.45,   # 6 AM - morning starts
    7: 0.65,   # 7 AM - breakfast/commute
    8: 0.85,   # 8 AM - work begins
    9: 0.95,   # 9 AM - morning rush
    10: 1.05,  # 10 AM - solid
    11: 1.10,  # 11 AM - active
    12: 1.15,  # 12 PM - lunch break
    13: 1.10,  # 1 PM - lunch
    14: 1.00,  # 2 PM - normal
    15: 1.05,  # 3 PM - afternoon
    16: 1.15,  # 4 PM - school/work end
    17: 1.30,  # 5 PM - evening commute
    18: 1.45,  # 6 PM - dinner
    19: 1.55,  # 7 PM - PEAK (Maximum US users online)
    20: 1.55,  # 8 PM - PEAK
    21: 1.40,  # 9 PM - evening relax
    22: 1.05,  # 10 PM - wind down
    23: 0.60   # 11 PM - late night
}

def get_us_hour_now():
    """Returns current hour (0-23) in US Eastern Time (UTC-5 approx)"""
    utc_now = datetime.now(timezone.utc)
    us_hour = (utc_now.hour - 5) % 24
    return us_hour

def get_traffic_weight():
    """Returns current traffic multiplier based on US Eastern time"""
    hour = get_us_hour_now()
    return US_TRAFFIC_CURVE.get(hour, 1.0)

def get_worker_sleep_for_current_traffic():
    """
    Returns natural sleep duration between views:
    - US Peak (weight >= 1.3): fast (2.0s - 4.5s)
    - US Normal (weight >= 0.8): standard (4.5s - 9.0s)
    - US Low (weight >= 0.3): slow (12.0s - 22.0s)
    - US Dead night (weight < 0.3): very slow (25.0s - 45.0s)
    """
    weight = get_traffic_weight()
    if weight >= 1.3:
        return random.uniform(2.0, 4.5)
    elif weight >= 0.8:
        return random.uniform(4.5, 9.0)
    elif weight >= 0.3:
        return random.uniform(12.0, 22.0)
    else:
        return random.uniform(25.0, 45.0)

# ------------------------------------------------------------------------------
# 4. HOURLY QUOTA SYSTEM & HUMAN BEHAVIOR MICRO-PACER (Poisson Bursts & Rest)
# ------------------------------------------------------------------------------
def _gen_uneven_hourly_target():
    """Generates random uneven hourly target (always odd/uneven, minimum 300)"""
    r = random.random()
    if r < 0.15:
        base = random.randint(300, 380)
    elif r < 0.40:
        base = random.randint(400, 599)
    elif r < 0.80:
        base = random.randint(600, 799)
    elif r < 0.95:
        base = random.randint(800, 999)
    else:
        base = random.randint(1000, 1100)

    jitter = random.choice([-7, -3, 3, 7, 11, 13, 17, 19, 23])
    result = base + jitter
    weight = get_traffic_weight()
    adjusted = int(result * (0.5 + (weight * 0.5)))
    return max(300, adjusted)

class HumanTrafficPacer:
    """
    Simulates authentic human web browsing micro-dynamics:
    1. 60-Minute Slicing: Hour is partitioned into 6 x 10-Minute micro-windows.
    2. Uneven Sub-Allocations: e.g. 10m-1: 23 views, 10m-2: 47 views, etc. (Never equal, never round).
    3. Micro-Burst Dynamics: 2-4 views trigger in a quick flurry (2-5s apart) just like
       real social media link clicks.
    4. Adaptive Rest Modulation:
       - If time is surplus (ahead of quota): rest stretches naturally to 35s - 75s+.
       - If falling behind: rest tightens to 15s - 25s.
       - If 10-min block quota completes early: workers gently idle until the next 10-min block!
    5. Thread-safe coordination across all parallel workers.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.hour_start = 0.0
        self.hourly_target = 0
        self.sub_targets = [50] * 6
        self.sub_completed = [0] * 6
        self.current_burst_size = random.randint(2, 3)
        self.burst_count_done = 0
        self.burst_active = True
        self.last_view_time = 0.0

    def start_new_hour(self, hourly_target):
        with self.lock:
            self.hour_start = time.time()
            self.hourly_target = hourly_target
            self.sub_completed = [0] * 6

            # Distribute into 6 uneven 10-minute blocks
            weights = []
            for _ in range(6):
                w = random.uniform(0.72, 1.38) + random.choice([-0.06, 0.0, 0.06])
                weights.append(max(0.4, w))
            tot_w = sum(weights)
            rem = hourly_target
            sub = []
            for i, w in enumerate(weights):
                if i == 5:
                    v = rem
                else:
                    v = int((w / tot_w) * hourly_target)
                    v += random.choice([-5, -3, 3, 5, 7, -7])
                    v = max(15, v)
                rem -= v
                sub.append(v)
            self.sub_targets = sub
            self.current_burst_size = random.randint(2, 3)
            self.burst_count_done = 0
            self.burst_active = True

            print(f"\n[Human Pacer] 🎯 Hour target ({hourly_target} views) partitioned into 6x 10-minute micro-blocks:")
            for idx, cnt in enumerate(sub):
                print(f"  • Block #{idx+1} (Min {idx*10:02d}-{(idx+1)*10:02d}): {cnt} views")

    def get_current_block_index(self):
        if self.hour_start <= 0:
            return 0
        elapsed = time.time() - self.hour_start
        idx = int(elapsed // 600)
        return min(5, max(0, idx))

    def get_current_block_status(self):
        with self.lock:
            idx = self.get_current_block_index()
            elapsed_in_block = (time.time() - self.hour_start) % 600 if self.hour_start > 0 else 0
            rem_sec = max(0.0, 600.0 - elapsed_in_block)
            target = self.sub_targets[idx] if idx < len(self.sub_targets) else 0
            done = self.sub_completed[idx] if idx < len(self.sub_completed) else 0
            return {
                "block_num": idx + 1,
                "target": target,
                "completed": done,
                "rem_sec": rem_sec,
                "is_burst": self.burst_active
            }

    def before_view_wait(self, worker_id):
        """
        Called by worker before making a view attempt.
        Dynamically applies micro-burst flurry or calculates time-surplus rest window.
        """
        while daemon_running:
            delay = 0.0
            needs_block_idle = False
            idle_duration = 0.0

            with self.lock:
                idx = self.get_current_block_index()
                target = self.sub_targets[idx] if idx < len(self.sub_targets) else 50
                done = self.sub_completed[idx] if idx < len(self.sub_completed) else 0
                elapsed_in_block = (time.time() - self.hour_start) % 600 if self.hour_start > 0 else 0
                rem_sec = max(0.0, 600.0 - elapsed_in_block)

                # Check if this 10-minute block quota is already satisfied
                if done >= target and target > 0:
                    needs_block_idle = True
                    idle_duration = min(25.0, max(3.0, rem_sec))
                else:
                    if self.burst_active:
                        # In Flurry: Rapid 2-4 clicks with 2s - 5s natural human gap
                        delay = random.uniform(2.0, 5.0)
                    else:
                        # In Rest Mode: Calculate dynamic rest based on remaining time vs quota
                        rem_views = max(1, target - done)
                        bursts_left = max(1.0, rem_views / 2.5)
                        avg_rest = rem_sec / bursts_left
                        # Stretch if surplus time available
                        delay = random.uniform(max(18.0, avg_rest * 0.75), min(85.0, avg_rest * 1.35))
                        self.burst_active = True
                        self.current_burst_size = random.randint(2, 4)
                        self.burst_count_done = 0

            if needs_block_idle:
                time.sleep(idle_duration)
                continue
            else:
                time.sleep(delay)
                break

    def record_success(self, worker_id):
        with self.lock:
            idx = self.get_current_block_index()
            if idx < len(self.sub_completed):
                self.sub_completed[idx] += 1
            self.burst_count_done += 1
            self.last_view_time = time.time()

            target = self.sub_targets[idx] if idx < len(self.sub_targets) else 0
            done = self.sub_completed[idx] if idx < len(self.sub_completed) else 0
            elapsed_in_block = (time.time() - self.hour_start) % 600 if self.hour_start > 0 else 0
            rem_sec = max(0.0, 600.0 - elapsed_in_block)

            if self.burst_count_done >= self.current_burst_size:
                self.burst_active = False
                print(f"[Human Pacer] 🌊 Flurry of {self.burst_count_done} views finished. Entering adaptive rest window... (Block #{idx+1}: {done}/{target} views, {rem_sec/60:.1f}m left)")
            else:
                print(f"[Human Pacer] ⚡ Flurry ongoing ({self.burst_count_done}/{self.current_burst_size} views in current cluster).")

traffic_pacer = HumanTrafficPacer()

_hourly_lock = threading.Lock()
_hourly_quota = {
    "target": 0,
    "completed": 0,
    "hour_start": 0.0,
    "current_target_str": "Pending"
}

def _reset_hourly_quota():
    with _hourly_lock:
        target = _gen_uneven_hourly_target()
        _hourly_quota["target"] = target
        _hourly_quota["completed"] = 0
        _hourly_quota["hour_start"] = time.time()
        _hourly_quota["current_target_str"] = str(target)
        us_h = get_us_hour_now()
        weight = get_traffic_weight()
        print(f"\n{'='*65}")
        print(f"⏰ NEW 1-HOUR WINDOW | US Time: {us_h}:00 EST ({weight:.2f}x traffic multiplier)")
        print(f"🎯 Total Target: {target} views (Distributed into 10-min Human Flurry Blocks)")
        print(f"{'='*65}\n")
    traffic_pacer.start_new_hour(target)

def _increment_hourly_completed():
    with _hourly_lock:
        _hourly_quota["completed"] += 1

def _hourly_quota_met():
    with _hourly_lock:
        return _hourly_quota["completed"] >= _hourly_quota["target"]

def _time_remaining_in_hour():
    with _hourly_lock:
        elapsed = time.time() - _hourly_quota["hour_start"]
        return max(0.0, 3600.0 - elapsed)

def _hourly_quota_snapshot():
    with _hourly_lock:
        return dict(_hourly_quota)

# Concurrency Locks & Flags
stats_lock = threading.Lock()
shortener_lock = threading.Lock()
pool_lock = threading.Lock()
campaign_lock = threading.Lock()
daemon_running = False

# ------------------------------------------------------------------------------
# 5. ADMIN LINK POOL SYSTEM (Manual + Dynamic Hybrid)
# ------------------------------------------------------------------------------
def _load_link_pool_unlocked():
    if not os.path.exists(LINK_POOL_FILE):
        return {"links": []}
    try:
        with open(LINK_POOL_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"links": []}

def _save_link_pool_unlocked(data):
    try:
        os.makedirs(os.path.dirname(LINK_POOL_FILE), exist_ok=True)
        tmp = LINK_POOL_FILE + ".tmp"
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, LINK_POOL_FILE)
    except Exception as e:
        print(f"[!] Error saving link pool: {e}")

def add_link_to_pool(url, label=""):
    with pool_lock:
        data = _load_link_pool_unlocked()
        existing_ids = [l.get("id", 0) for l in data.get("links", [])]
        new_id = (max(existing_ids) + 1) if existing_ids else 1
        item = {
            "id": new_id,
            "url": url.strip(),
            "label": label.strip() or f"Link #{new_id}",
            "added_at": get_current_time_str(),
            "views_delivered": 0
        }
        data["links"].append(item)
        _save_link_pool_unlocked(data)
        return item

def remove_link_from_pool(link_id):
    with pool_lock:
        data = _load_link_pool_unlocked()
        initial_len = len(data.get("links", []))
        data["links"] = [l for l in data.get("links", []) if l.get("id") != link_id]
        if len(data["links"]) < initial_len:
            _save_link_pool_unlocked(data)
            return True
        return False

def clear_link_pool():
    with pool_lock:
        _save_link_pool_unlocked({"links": []})
        return True

def list_pool_links():
    with pool_lock:
        data = _load_link_pool_unlocked()
        return list(data.get("links", []))

def record_pool_link_view(link_id):
    with pool_lock:
        data = _load_link_pool_unlocked()
        for l in data.get("links", []):
            if l.get("id") == link_id:
                l["views_delivered"] = l.get("views_delivered", 0) + 1
                break
        _save_link_pool_unlocked(data)

def get_next_target_url():
    """
    Returns (target_url, pool_link_id_or_None)
    - If admin added links to pool: picks link (weighted by least views delivered)
    - If pool is empty: fallbacks to dynamic URL generator (Vercel portal)
    """
    with pool_lock:
        data = _load_link_pool_unlocked()
        links = data.get("links", [])
        if links:
            # Sort by least delivered views and pick among the lowest delivered
            sorted_links = sorted(links, key=lambda x: x.get("views_delivered", 0))
            candidate = random.choice(sorted_links[:3])
            return candidate["url"], candidate["id"]
    return get_dynamic_url(), None

# ------------------------------------------------------------------------------
# 6. SMART CAMPAIGN PLANNER (Proxy GB Estimation & Daily Uneven Schedule)
# ------------------------------------------------------------------------------
def generate_campaign_schedule(total_views, days):
    """
    Distributes total_views across N days with random, natural weights.
    Never equal splits; always uneven random numbers.
    """
    weights = []
    for _ in range(days):
        w = random.uniform(0.75, 1.45)
        jitter = random.choice([-0.08, -0.04, 0.04, 0.08, 0.12])
        weights.append(max(0.3, w + jitter))

    total_weight = sum(weights)
    schedule = []
    remaining = total_views
    base_date = datetime.now(timezone.utc)

    for i, w in enumerate(weights):
        day_date_str = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        if i == days - 1:
            day_views = remaining
        else:
            day_views = int((w / total_weight) * total_views)
            # Add uneven jitter
            day_views += random.choice([-17, -11, -7, 7, 11, 13, 19, 23])
            day_views = max(150, day_views)
        remaining -= day_views
        schedule.append({
            "day": i + 1,
            "date": day_date_str,
            "target": day_views,
            "completed": 0
        })
    return schedule

def save_campaign(campaign_data):
    with campaign_lock:
        try:
            os.makedirs(os.path.dirname(CAMPAIGN_FILE), exist_ok=True)
            tmp = CAMPAIGN_FILE + ".tmp"
            with open(tmp, 'w') as f:
                json.dump(campaign_data, f, indent=2)
            os.replace(tmp, CAMPAIGN_FILE)
        except Exception as e:
            print(f"[!] Error saving campaign: {e}")

def load_campaign():
    with campaign_lock:
        if not os.path.exists(CAMPAIGN_FILE):
            return None
        try:
            with open(CAMPAIGN_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return None

def cancel_campaign():
    with campaign_lock:
        if os.path.exists(CAMPAIGN_FILE):
            try:
                os.remove(CAMPAIGN_FILE)
                return True
            except Exception:
                pass
        return False

def is_campaign_active():
    camp = load_campaign()
    if not camp:
        return False
    return camp.get("status") == "active"

def get_todays_campaign_quota():
    """Returns today's target and completed for active campaign"""
    camp = load_campaign()
    if not camp:
        return {"target": 0, "completed": 0, "day": 0, "total_days": 0}
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for item in camp.get("schedule", []):
        if item.get("date") == today_str:
            return {
                "target": item.get("target", 0),
                "completed": item.get("completed", 0),
                "day": item.get("day", 1),
                "total_days": len(camp.get("schedule", []))
            }
    # Fallback to first incomplete day
    for item in camp.get("schedule", []):
        if item.get("completed", 0) < item.get("target", 0):
            return {
                "target": item.get("target", 0),
                "completed": item.get("completed", 0),
                "day": item.get("day", 1),
                "total_days": len(camp.get("schedule", []))
            }
    return {"target": 0, "completed": 0, "day": 0, "total_days": len(camp.get("schedule", []))}

def update_campaign_view_completed():
    with campaign_lock:
        camp = load_campaign()
        if not camp:
            return
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        matched = False
        for item in camp.get("schedule", []):
            if item.get("date") == today_str:
                item["completed"] = item.get("completed", 0) + 1
                matched = True
                break
        if not matched:
            for item in camp.get("schedule", []):
                if item.get("completed", 0) < item.get("target", 0):
                    item["completed"] = item.get("completed", 0) + 1
                    break
        camp["total_completed"] = camp.get("total_completed", 0) + 1
        save_campaign(camp)

# ------------------------------------------------------------------------------
# 7. STATS PERSISTENCE & DASHBOARD CACHE (ouo_stats.py)
# ------------------------------------------------------------------------------
DEFAULT_STATS = {
    "total_links_created": 0,
    "total_views_completed": 0,
    "ouo_views": 0,
    "exe_views": 0,
    "failed_views": 0,
    "success_rate": "100%",
    "daemon_status": "⏸️ STOPPED",
    "daemon_started_at": 0,
    "daemon_started_str": "",
    "last_activity_time": 0,
    "last_activity_str": "None yet",
    "last_shortlink": "None yet",
    "last_target_url": "None yet",
    "last_visitor_country": "🇺🇸 US",
    "hourly_quota": {
        "target": 0,
        "completed": 0,
        "current_target_str": "Pending"
    },
    "dashboard": {
        "views": "0",
        "earnings": "$0.00",
        "ecpm": "$0.00",
        "available": "$0.00",
        "last_checked_at": 0,
        "last_checked_str": "Never",
        "next_check_at": 0,
        "next_check_str": "Pending"
    },
    "history": []
}

def get_current_time_str(ts=None):
    if ts is None:
        ts = time.time()
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

def _load_stats_unlocked():
    if not os.path.exists(STATS_FILE):
        return DEFAULT_STATS.copy()
    try:
        with open(STATS_FILE, 'r') as f:
            data = json.load(f)
            for k, v in DEFAULT_STATS.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        return DEFAULT_STATS.copy()

def _save_stats_unlocked(stats):
    try:
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        tmp_file = STATS_FILE + ".tmp"
        with open(tmp_file, 'w') as f:
            json.dump(stats, f, indent=2)
        os.replace(tmp_file, STATS_FILE)
    except Exception as e:
        print(f"[!] Error saving stats: {e}")

def load_stats():
    with stats_lock:
        if not os.path.exists(STATS_FILE):
            stats = DEFAULT_STATS.copy()
            stats["daemon_started_at"] = time.time()
            stats["daemon_started_str"] = get_current_time_str(stats["daemon_started_at"])
            _save_stats_unlocked(stats)
            return stats
        return _load_stats_unlocked()

def save_stats(stats):
    with stats_lock:
        _save_stats_unlocked(stats)

def record_link_created(short_url, target_url, platform="ouo"):
    with stats_lock:
        stats = _load_stats_unlocked()
        stats["total_links_created"] += 1
        stats["last_shortlink"] = f"[{platform.upper()}] {short_url}"
        stats["last_target_url"] = target_url
        stats["last_activity_time"] = time.time()
        stats["last_activity_str"] = get_current_time_str(stats["last_activity_time"])
        _save_stats_unlocked(stats)

def record_view_result(success, short_url, dest_url, country="🇺🇸 US", platform="ouo"):
    with stats_lock:
        stats = _load_stats_unlocked()
        if success:
            stats["total_views_completed"] += 1
            if platform == "ouo":
                stats["ouo_views"] = stats.get("ouo_views", 0) + 1
            elif platform == "exe":
                stats["exe_views"] = stats.get("exe_views", 0) + 1
        else:
            stats["failed_views"] += 1

        total_attempts = stats["total_views_completed"] + stats["failed_views"]
        if total_attempts > 0:
            pct = (stats["total_views_completed"] / total_attempts) * 100.0
            stats["success_rate"] = f"{pct:.1f}%"
        else:
            stats["success_rate"] = "100%"

        stats["last_activity_time"] = time.time()
        stats["last_activity_str"] = get_current_time_str(stats["last_activity_time"])
        stats["last_visitor_country"] = country

        snap = _hourly_quota_snapshot()
        stats["hourly_quota"] = {
            "target": snap["target"],
            "completed": snap["completed"],
            "current_target_str": snap["current_target_str"]
        }

        entry = {
            "time": get_current_time_str(),
            "platform": platform.upper(),
            "shortlink": short_url,
            "country": country,
            "status": "SUCCESS" if success else "FAILED",
            "dest": dest_url
        }
        history = stats.get("history", [])
        history.insert(0, entry)
        stats["history"] = history[:10]
        _save_stats_unlocked(stats)

def record_dashboard_stats(dashboard_data):
    with stats_lock:
        stats = _load_stats_unlocked()
        now = time.time()
        next_check = now + 3600
        stats["dashboard"] = {
            "views": dashboard_data.get("views", "0"),
            "earnings": dashboard_data.get("earnings", "$0.00"),
            "ecpm": dashboard_data.get("ecpm", "$0.00"),
            "available": dashboard_data.get("available", "$0.00"),
            "last_checked_at": now,
            "last_checked_str": get_current_time_str(now),
            "next_check_at": next_check,
            "next_check_str": get_current_time_str(next_check)
        }
        _save_stats_unlocked(stats)

# ------------------------------------------------------------------------------
# 8. AUTHENTICATION & SESSION MANAGEMENT (ouo_login.py)
# ------------------------------------------------------------------------------
def check_session_validity(headless=True):
    if not PLAYWRIGHT_AVAILABLE:
        print("[-] Error: 'playwright' is not installed.")
        return False
    if not os.path.exists(SESSION_FILE):
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                proxy=PROXY_CONFIG,
                user_agent=get_random_ua(),
                viewport={'width': 1280, 'height': 720}
            )
            with open(SESSION_FILE) as f:
                cookie_dict = json.load(f)
            context.add_cookies([{'name': k, 'value': v, 'domain': '.ouo.io', 'path': '/'} for k, v in cookie_dict.items()])
            page = context.new_page()
            page.goto('https://ouo.io/manage/home', wait_until='domcontentloaded', timeout=30000)

            for _ in range(15):
                time.sleep(1)
                if 'manage/home' in page.url or 'Dashboard' in page.title():
                    break

            is_valid = ('manage/home' in page.url or 'Dashboard' in page.title()) and 'auth/signin' not in page.url
            browser.close()
            return is_valid
    except Exception as e:
        print(f"[!] Session validity check error: {e}")
        return False

def do_login(headless=True):
    if not PLAYWRIGHT_AVAILABLE:
        print("[-] Error: 'playwright' is not installed.")
        return False
    if not OUO_USERNAME or not OUO_PASSWORD:
        print("[*] OUO login skipped: No username/password configured in environment. Using existing session/visitor mode.")
        return False
    print("[*] Logging in to ouo.io with proxy...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled', '--disable-infobars', '--disable-dev-shm-usage']
            )
            context = browser.new_context(
                proxy=PROXY_CONFIG,
                user_agent=get_random_ua(),
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()
            print("[*] Opening signin page...")
            page.goto('https://ouo.io/auth/signin', wait_until='domcontentloaded', timeout=35000)

            for _ in range(15):
                time.sleep(1)
                if 'Sign in' in page.title():
                    break

            if 'Sign in' not in page.title():
                print(f"[-] Could not reach sign in page. Current title: {page.title()}")
                browser.close()
                return False

            print("[*] Submitting credentials...")
            page.fill('input[name="username"]', OUO_USERNAME)
            page.fill('input[name="password"]', OUO_PASSWORD)

            remember = page.query_selector('input[name="remember-me"]')
            if remember and not remember.is_checked():
                remember.check()

            page.click('button[type="submit"]')

            for _ in range(15):
                time.sleep(1)
                if '/manage/home' in page.url or 'Dashboard' in page.title():
                    break

            if '/manage/home' in page.url or 'Dashboard' in page.title():
                cookies = context.cookies()
                auth_cookies = {c['name']: c['value'] for c in cookies}
                os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
                with open(SESSION_FILE, 'w') as f:
                    json.dump(auth_cookies, f, indent=2)
                browser.close()
                print(f"[🎉 SUCCESS] Login successful! Session saved to: {SESSION_FILE}")
                return True
            else:
                print(f"[-] Login failed. Redirected to: {page.url}")
                browser.close()
                return False
    except Exception as e:
        print(f"[!] Login exception: {e}")
        return False

def ensure_valid_session():
    print("[*] Checking session health...")
    if check_session_validity():
        print("[+] Active session cookie found (skipping login).")
        return True
    else:
        print("[!] Session expired or not found. Performing fresh login...")
        return do_login()

# ------------------------------------------------------------------------------
# 9. HOURLY DASHBOARD CHECKER
# ------------------------------------------------------------------------------
def check_ouo_dashboard_hourly(force=False):
    if not PLAYWRIGHT_AVAILABLE:
        return
    stats = load_stats()
    last_check = stats.get("dashboard", {}).get("last_checked_at", 0)
    now = time.time()

    if not force and (now - last_check) < HOURLY_CHECK_INTERVAL and last_check > 0:
        return

    print("[*] Scraping hourly ouo.io dashboard snapshot...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(proxy=PROXY_CONFIG, user_agent=get_random_ua(), viewport={'width': 1280, 'height': 720})
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE) as f:
                    cookie_dict = json.load(f)
                context.add_cookies([{'name': k, 'value': v, 'domain': '.ouo.io', 'path': '/'} for k, v in cookie_dict.items()])

            page = context.new_page()
            page.goto('https://ouo.io/manage/home', wait_until='domcontentloaded', timeout=35000)

            for _ in range(15):
                time.sleep(1)
                if 'manage/home' in page.url or 'Dashboard' in page.title():
                    break

            dash_data = {'views': '0', 'earnings': '$0.00', 'ecpm': '$0.00', 'available': '$0.00'}
            cards = page.query_selector_all('.col-sm-3, .col-xs-6, .panel')
            for c in cards:
                lines = [l.strip() for l in c.inner_text().split('\n') if l.strip()]
                if len(lines) >= 2:
                    val, label = lines[0], lines[1]
                    if label.lower() == 'views':
                        dash_data['views'] = val
                    elif label.lower() == 'earnings':
                        dash_data['earnings'] = val
                    elif label.lower() == 'ecpm':
                        dash_data['ecpm'] = val
                    elif 'total available' in label.lower():
                        dash_data['available'] = val
            browser.close()
            record_dashboard_stats(dash_data)
            print(f"[+] Hourly Check Complete: Views={dash_data['views']}, Earnings={dash_data['earnings']}, Available={dash_data['available']}")
    except Exception as e:
        print(f"[!] Hourly dashboard check notice: {e}")

# ------------------------------------------------------------------------------
# 10. DYNAMIC URL GENERATOR & SHORTENERS (ouo.io + exe.io)
# ------------------------------------------------------------------------------
CLEAN_FALLBACK_URLS = [
    "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "https://en.wikipedia.org/wiki/Cloud_computing",
    "https://en.wikipedia.org/wiki/Computer_science",
    "https://en.wikipedia.org/wiki/Cybersecurity",
    "https://en.wikipedia.org/wiki/Data_science",
    "https://en.wikipedia.org/wiki/Internet_of_things",
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Quantum_computing"
]

def get_dynamic_url(fallback_url=None):
    """Returns safe destination URL (used only when admin link pool is empty)"""
    if fallback_url:
        return fallback_url
    return random.choice(CLEAN_FALLBACK_URLS)

def shorten_target(target_url, cookies_path=None):
    """Shortens target URL via ouo.io using CSRF token"""
    if not PLAYWRIGHT_AVAILABLE:
        return None
    c_path = cookies_path or SESSION_FILE
    with shortener_lock:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
                )
                context = browser.new_context(
                    proxy=PROXY_CONFIG,
                    user_agent=get_random_ua(),
                    viewport={'width': 1280, 'height': 720}
                )
                if os.path.exists(c_path):
                    with open(c_path) as f:
                        cookie_dict = json.load(f)
                    context.add_cookies([{'name': k, 'value': v, 'domain': '.ouo.io', 'path': '/'} for k, v in cookie_dict.items()])

                page = context.new_page()
                page.goto('https://ouo.io/manage/home', wait_until='domcontentloaded', timeout=30000)

                for _ in range(15):
                    time.sleep(1)
                    if 'Just a moment' not in page.title() and page.title() != '':
                        break

                token_el = page.query_selector('input[name="_token"]')
                csrf_token = token_el.get_attribute('value') if token_el else ""

                result = page.evaluate('''async ({url, token}) => {
                    const formData = new URLSearchParams();
                    formData.append('_token', token);
                    formData.append('url', url);

                    const res = await fetch('https://ouo.io/shorten', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                            'X-Requested-With': 'XMLHttpRequest',
                            'Accept': 'application/json, text/javascript, */*; q=0.01'
                        },
                        body: formData.toString()
                    });
                    const raw = await res.text();
                    let data = null;
                    try { data = JSON.parse(raw); } catch(e) { data = raw; }
                    return { status: res.status, data };
                }''', {'url': target_url, 'token': csrf_token})

                browser.close()
                status = result.get('status')
                data = result.get('data')
                if status == 200 and isinstance(data, dict) and not data.get('error'):
                    slug = data.get('slug')
                    return f"https://ouo.io/{slug}"
                return None
        except Exception as e:
            print(f"[!] ouo.io shorten error: {e}")
            return None

def shorten_exe(target_url):
    """Shortens target URL via exe.io API (Instant, HTTP only - Zero Proxy Data Used!)"""
    if not EXE_API_TOKEN or not REQUESTS_AVAILABLE:
        return None
    try:
        api_url = f"https://exe.io/api?api={EXE_API_TOKEN}&url={urllib.parse.quote(target_url)}"
        resp = requests.get(api_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success" and data.get("shortenedUrl"):
                return data["shortenedUrl"]
            elif data.get("shortenedUrl"):
                return data["shortenedUrl"]
    except Exception as e:
        print(f"[!] exe.io shorten error: {e}")
    return None

# ------------------------------------------------------------------------------
# 11. NATURAL AD-ENABLED VISITOR ENGINES (ouo.io + exe.io)
# ------------------------------------------------------------------------------
def wait_for_cloudflare_clearance(page, max_seconds=25):
    """Waits for Cloudflare challenge (Just a moment... or __cf_chl) to finish and clicks Turnstile if needed"""
    for _ in range(max_seconds):
        title = page.title() or ''
        url = page.url or ''
        if 'Just a moment' not in title and '__cf_chl' not in url and 'Attention Required' not in title:
            return True
        # Try finding Turnstile iframe or checkbox
        try:
            for frame in page.frames:
                for sel in ['input[type="checkbox"]', '.ctp-checkbox-label', '#challenge-stage', '#turnstile-wrapper']:
                    el = frame.query_selector(sel)
                    if el and el.is_visible():
                        el.click(force=True)
                        time.sleep(1.5)
                        break
        except Exception:
            pass
        time.sleep(1)
    return ('Just a moment' not in (page.title() or '') and '__cf_chl' not in (page.url or ''))

def visit_shortlink(short_url, worker_id=1, proxy=None):
    """Simulates realistic human visit on ouo.io with Cloudflare & timer bypass"""
    if not PLAYWRIGHT_AVAILABLE:
        return False, "Playwright not installed"
    use_proxy = proxy or VISITOR_PROXY_CONFIG
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-zygote'
                ]
            )
            context = browser.new_context(
                proxy=use_proxy,
                user_agent=get_random_ua(),
                viewport={'width': 1280, 'height': 720}
            )

            # Block heavy video streams (saves ~2-3 MB data per view) while keeping ad tracking safe
            def safe_resource_filter(route):
                req = route.request
                if req.resource_type in ["media"] or any(req.url.lower().endswith(ext) for ext in [".mp4", ".webm", ".m3u8", ".ts", ".mp3"]):
                    route.abort()
                else:
                    route.continue_()
            context.route("**/*", safe_resource_filter)

            popups = []
            page = context.new_page()
            page.add_init_script(STEALTH_INJECT_JS)
            page.on("popup", lambda p_tab: popups.append(p_tab))

            try:
                page.goto(short_url, wait_until='commit', timeout=25000)
            except Exception:
                page.goto(short_url, wait_until='domcontentloaded', timeout=30000)

            # Step 1: Wait for Cloudflare clearance on ouo.io
            wait_for_cloudflare_clearance(page, max_seconds=25)

            # Natural scrolling
            try:
                scroll_y = random.randint(200, 500)
                page.mouse.wheel(0, scroll_y)
                time.sleep(random.uniform(1.2, 2.5))
            except Exception:
                pass

            # Step 1 click
            try:
                btn1 = page.wait_for_selector('#btn-main', timeout=15000)
                time.sleep(random.uniform(1.0, 2.2))
                btn1.click(force=True, timeout=5000)
            except Exception:
                try:
                    page.evaluate('() => { const f = document.querySelector("#form-go"); if (f) f.submit(); }')
                except Exception:
                    pass

            time.sleep(random.uniform(2.5, 4.0))
            if popups:
                time.sleep(random.uniform(1.0, 2.0))
                for p_tab in popups:
                    try: p_tab.close()
                    except Exception: pass
                popups.clear()

            page.bring_to_front()

            # Step 2: Critical! ouo.io redirects to ouo.press. Wait for Cloudflare on ouo.press!
            wait_for_cloudflare_clearance(page, max_seconds=25)

            # Step 2: Wait for countdown to finish and GET LINK
            for _ in range(30):
                time.sleep(1)
                if 'ouo.io' not in page.url and 'ouo.press' not in page.url:
                    break
                # If Cloudflare challenge appears mid-flow on ouo.press
                if 'Just a moment' in (page.title() or '') or '__cf_chl' in (page.url or ''):
                    wait_for_cloudflare_clearance(page, max_seconds=10)
                    continue

                btn2 = page.query_selector('#btn-main')
                if btn2:
                    cls = btn2.get_attribute('class') or ''
                    txt = (btn2.inner_text() or '').strip()
                    if 'disabled' not in cls and ('GET LINK' in txt.upper() or 'GET' in txt.upper()):
                        time.sleep(random.uniform(0.8, 1.8))
                        try:
                            btn2.click(force=True, timeout=5000)
                        except Exception:
                            pass
                        try:
                            page.evaluate('() => { const f = document.querySelector("#form-go"); if (f) f.submit(); }')
                        except Exception:
                            pass
                        break

            final_url = page.url
            # Once redirected away from ouo, the view is ALREADY verified!
            for _ in range(12):
                time.sleep(1)
                if popups:
                    for p_tab in popups:
                        try: p_tab.close()
                        except Exception: pass
                    popups.clear()
                if 'ouo.io' not in page.url and 'ouo.press' not in page.url:
                    final_url = page.url
                    break

            browser.close()
            is_valid = 'ouo.io' not in final_url and 'ouo.press' not in final_url
            return is_valid, final_url
    except Exception as e:
        return False, str(e)

def visit_exe_shortlink(short_url, worker_id=1, proxy=None):
    """Simulates realistic human visit on exe.io shortlinks"""
    if not PLAYWRIGHT_AVAILABLE:
        return False, "Playwright not installed"
    use_proxy = proxy or VISITOR_PROXY_CONFIG
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--no-zygote'
                ]
            )
            context = browser.new_context(
                proxy=use_proxy,
                user_agent=get_random_ua(),
                viewport={'width': 1280, 'height': 720}
            )

            def safe_filter(route):
                req = route.request
                if req.resource_type in ["media"] or any(req.url.lower().endswith(ext) for ext in [".mp4", ".webm", ".m3u8"]):
                    route.abort()
                else:
                    route.continue_()
            context.route("**/*", safe_filter)

            popups = []
            page = context.new_page()
            page.add_init_script(STEALTH_INJECT_JS)
            page.on("popup", lambda p_tab: popups.append(p_tab))

            try:
                page.goto(short_url, wait_until='commit', timeout=25000)
            except Exception:
                page.goto(short_url, wait_until='domcontentloaded', timeout=30000)

            time.sleep(random.uniform(2.0, 3.5))

            # Natural scroll
            try:
                page.mouse.wheel(0, random.randint(250, 600))
                time.sleep(random.uniform(1.2, 2.0))
            except Exception:
                pass

            # Exe.io Step 1: Click Continue / Go
            try:
                btn = page.query_selector('#btn-main, .btn-primary, button[type="submit"]')
                if btn:
                    time.sleep(random.uniform(1.0, 2.0))
                    btn.click(force=True, timeout=5000)
            except Exception:
                pass

            time.sleep(random.uniform(2.0, 3.5))
            if popups:
                for p_tab in popups:
                    try: p_tab.close()
                    except Exception: pass
                popups.clear()

            page.bring_to_front()

            # Wait for countdown timer and GET LINK
            for _ in range(15):
                time.sleep(1)
                if 'exe.io' not in page.url and 'exee.io' not in page.url:
                    break
                get_btn = page.query_selector('#btn-main, a.get-link, .get-link')
                if get_btn:
                    cls = get_btn.get_attribute('class') or ''
                    if 'disabled' not in cls:
                        time.sleep(random.uniform(0.8, 1.5))
                        try: get_btn.click(force=True, timeout=5000)
                        except Exception: pass
                        break

            final_url = page.url
            for _ in range(6):
                time.sleep(1)
                if 'exe.io' not in page.url and 'exee.io' not in page.url:
                    final_url = page.url
                    break

            browser.close()
            is_valid = 'exe.io' not in final_url and 'exee.io' not in final_url
            return is_valid, final_url
    except Exception as e:
        return False, str(e)

# ------------------------------------------------------------------------------
# 12. CAMPAIGN LOOP (ouo_campaign.py)
# ------------------------------------------------------------------------------
def run_campaign_loop(total_views=1, vercel_url=None):
    print("\n=======================================================")
    print("🚀 STARTING COMPLETE CAMPAIGN AUTOMATION")
    print(f"🎯 Total Views Goal: {total_views}")
    print(f"🌐 Dynamic Portal: {vercel_url or DEFAULT_VERCEL_APP}")
    print("=======================================================\n")

    if not ensure_valid_session():
        print("[-] Failed to establish valid session. Aborting.")
        return False

    successful = 0
    for cycle in range(1, total_views + 1):
        target_url, pool_id = get_next_target_url()
        print(f"\n>>> [CYCLE {cycle}/{total_views}] Target: {target_url} (Pool ID: {pool_id})")

        short_link = shorten_target(target_url)
        if not short_link:
            if not check_session_validity():
                do_login()
                short_link = shorten_target(target_url)

        if not short_link:
            print("[-] Skipping cycle due to shorten failure.")
            continue

        print(f"[+] Generated Shortlink: {short_link}")
        record_link_created(short_link, target_url, platform="ouo")

        ok, dest = visit_shortlink(short_link)
        record_view_result(ok, short_link, dest, platform="ouo")
        if ok:
            successful += 1
            if pool_id:
                record_pool_link_view(pool_id)
            print(f"[🎉 CYCLE {cycle} SUCCESS] Landed on: {dest}")
        else:
            print(f"[!] Cycle {cycle} failed: {dest}")

        if cycle < total_views:
            w = random.randint(4, 9)
            print(f"[*] Sleeping {w}s before next cycle...")
            time.sleep(w)

    print("\n=======================================================")
    print(f"🏁 CAMPAIGN COMPLETED: {successful}/{total_views} Views Delivered!")
    print("=======================================================\n")
    return successful

# ------------------------------------------------------------------------------
# 13. 24/7 PARALLEL MULTI-WORKER ENGINE (Traffic Curve + Campaign Aware)
# ------------------------------------------------------------------------------
def _single_view_cycle(worker_id):
    """Executes one complete view cycle (ouo.io + optional exe.io dual earning)"""
    try:
        target_url, pool_id = get_next_target_url()

        # 1. ouo.io Link Generation & Visit
        short_ouo = shorten_target(target_url)
        ouo_ok = False
        if short_ouo:
            record_link_created(short_ouo, target_url, platform="ouo")
            print(f"[Worker #{worker_id}] 🔗 [OUO] Shortened: {short_ouo}")
            ouo_ok, dest_ouo = visit_shortlink(short_ouo, worker_id=worker_id)
            record_view_result(ouo_ok, short_ouo, dest_ouo, country="🇺🇸 US (Rotating IP)", platform="ouo")
            if ouo_ok:
                _increment_hourly_completed()
                traffic_pacer.record_success(worker_id)
                if is_campaign_active():
                    update_campaign_view_completed()
                if pool_id:
                    record_pool_link_view(pool_id)
                print(f"[Worker #{worker_id}] ✅ [OUO View Verified] ({dest_ouo[:45]}...)")
            else:
                print(f"[Worker #{worker_id}] ⚠️ [OUO View Ended] ({dest_ouo[:45]}...)")

        # 2. exe.io Dual Earning (If token provided, monetizes same session with daily payout!)
        if EXE_API_TOKEN:
            short_exe = shorten_exe(target_url)
            if short_exe:
                record_link_created(short_exe, target_url, platform="exe")
                print(f"[Worker #{worker_id}] ⚡ [EXE] Shortened via API: {short_exe}")
                exe_ok, dest_exe = visit_exe_shortlink(short_exe, worker_id=worker_id)
                record_view_result(exe_ok, short_exe, dest_exe, country="🇺🇸 US (Rotating IP)", platform="exe")
                if exe_ok:
                    print(f"[Worker #{worker_id}] 💰 [EXE View Verified] (Daily Cashflow!)")

        return ouo_ok
    except Exception as e:
        print(f"[Worker #{worker_id}] Cycle error: {e}")
        return False

def worker_routine(worker_id):
    time.sleep(random.uniform(0.5, 3.5) * worker_id * 0.25)
    print(f"[Worker #{worker_id}] 🟢 Active. Running Natural Human Pacing Engine.")

    while daemon_running:
        try:
            # Check 1: Active Campaign Quota Gate
            if is_campaign_active():
                c_quota = get_todays_campaign_quota()
                if c_quota["target"] > 0 and c_quota["completed"] >= c_quota["target"]:
                    print(f"[Worker #{worker_id}] 🏁 Today's Campaign Quota Met ({c_quota['completed']}/{c_quota['target']}). Idling...")
                    time.sleep(60)
                    continue

            # Check 2: Hourly Quota Gate (When no campaign is active)
            else:
                if _hourly_quota_met():
                    remaining = _time_remaining_in_hour()
                    if remaining > 5:
                        sleep_chunk = 20
                        slept = 0
                        while daemon_running and slept < remaining:
                            time.sleep(min(sleep_chunk, remaining - slept))
                            slept += sleep_chunk
                    continue

            # Check 3: Human Behavior Micro-Pacing Gate (10-minute block bursts & adaptive rest)
            traffic_pacer.before_view_wait(worker_id)

            # Run View Cycle
            _single_view_cycle(worker_id)

            # Micro-jitter between sequential attempts (1.5s - 3.5s)
            time.sleep(random.uniform(1.5, 3.5))

        except Exception as e:
            print(f"[Worker #{worker_id}] Main loop error: {e}")
            time.sleep(6)

def _hourly_quota_manager():
    _reset_hourly_quota()
    last_reset = time.time()
    last_banner = time.time()

    while daemon_running:
        time.sleep(15)
        now = time.time()

        if now - last_reset >= 3600:
            _reset_hourly_quota()
            last_reset = now
            last_banner = now
            continue

        if now - last_banner >= 300:
            us_h = get_us_hour_now()
            weight = get_traffic_weight()
            p_stat = traffic_pacer.get_current_block_status()
            if is_campaign_active():
                cq = get_todays_campaign_quota()
                print(f"\n📊 Campaign Day {cq['day']}/{cq['total_days']} → {cq['completed']}/{cq['target']} views | US Hour: {us_h}:00 EST ({weight:.2f}x)")
            else:
                snap = _hourly_quota_snapshot()
                remaining_min = _time_remaining_in_hour() / 60
                print(f"\n📊 Hourly Total: {snap['completed']}/{snap['target']} views ({remaining_min:.0f}m left) | US Hour: {us_h}:00 EST ({weight:.2f}x)")
            print(f"⏱️ 10m Micro-Block #{p_stat['block_num']}/6: {p_stat['completed']}/{p_stat['target']} views ({p_stat['rem_sec']/60:.1f}m left in block)\n")
            last_banner = now

def run_multi_worker_daemon(num_workers=NUM_WORKERS, blocking=True):
    global daemon_running
    daemon_running = True

    print("=======================================================")
    print("🚀 OUO.IO & EXE.IO 24/7 DUAL MONETIZATION ENGINE")
    print(f"👥 Concurrent Workers : {num_workers} Parallel Playwright Instances")
    print(f"🌐 Target Source      : Hybrid (Admin Link Pool + Auto Portal)")
    print(f"⏰ US Traffic Curve   : Active (Peak 7-9 PM EST, Night Slowdown)")
    print(f"📡 Visitor Network    : US Residential Rotating IP")
    print(f"💰 Secondary Platform : {'EXE.IO (Daily Payout Enabled)' if EXE_API_TOKEN else 'Disabled (Set EXE_API_TOKEN)'}")
    print("=======================================================\n")

    stats = load_stats()
    stats["daemon_status"] = f"🟢 RUNNING 24/7 ({num_workers} US Workers)"
    if not stats.get("daemon_started_at"):
        stats["daemon_started_at"] = time.time()
        stats["daemon_started_str"] = get_current_time_str(stats["daemon_started_at"])
    save_stats(stats)

    if not check_session_validity():
        do_login()
    check_ouo_dashboard_hourly()

    threading.Thread(target=_hourly_quota_manager, daemon=True).start()

    def hourly_timer_thread():
        while daemon_running:
            time.sleep(60)
            try: check_ouo_dashboard_hourly()
            except Exception: pass
    threading.Thread(target=hourly_timer_thread, daemon=True).start()

    threads = []
    for w_id in range(1, num_workers + 1):
        t = threading.Thread(target=worker_routine, args=(w_id,), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(random.uniform(0.6, 1.6))

    print(f"[+] All {num_workers} Workers dispatched! Running 24/7 with Natural Traffic Curve.")

    if blocking:
        def handle_exit(sig, frame):
            global daemon_running
            print("\n[!] Stopping daemon workers...")
            daemon_running = False
            s = load_stats()
            s["daemon_status"] = "⏸️ STOPPED"
            save_stats(s)
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

        while daemon_running:
            time.sleep(1)

# ------------------------------------------------------------------------------
# 14. TELEGRAM BOT ENGINE & CAMPAIGN WIZARD (ouo_bot.py)
# ------------------------------------------------------------------------------
def run_telegram_bot():
    if not TELEBOT_AVAILABLE:
        print("[-] Error: 'pyTelegramBotAPI' package not installed. Run: pip install pyTelegramBotAPI")
        sys.exit(1)

    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
    active_status_messages = {}
    wizard_temp = {}

    def is_user_authenticated(chat_id):
        if not os.path.exists(AUTH_FILE):
            return False
        try:
            with open(AUTH_FILE, 'r') as f:
                data = json.load(f)
            auth_time = data.get(str(chat_id), 0)
            return (time.time() - auth_time) < SESSION_LIFETIME
        except Exception:
            return False

    def set_user_authenticated(chat_id):
        data = {}
        if os.path.exists(AUTH_FILE):
            try:
                with open(AUTH_FILE, 'r') as f:
                    data = json.load(f)
            except Exception:
                pass
        data[str(chat_id)] = time.time()
        os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
        with open(AUTH_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def safe_delete(chat_id, message_id):
        try: bot.delete_message(chat_id, message_id)
        except Exception: pass

    def safe_edit(chat_id, message_id, text, reply_markup=None):
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup, disable_web_page_preview=True)
            return True
        except ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                return True
            return False
        except Exception:
            return False

    def get_main_reply_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        b1 = types.KeyboardButton("📊 Dashboard")
        b2 = types.KeyboardButton("🚀 New Campaign")
        b3 = types.KeyboardButton("🔗 Link Pool")
        b4 = types.KeyboardButton("🇺🇸 US Traffic")
        b5 = types.KeyboardButton("📋 View Campaign")
        b6 = types.KeyboardButton("🛑 Stop Campaign")
        markup.row(b1, b2)
        markup.row(b3, b4)
        markup.row(b5, b6)
        return markup

    def build_status_card_text():
        stats = load_stats()
        daemon_badge = stats.get("daemon_status", "⏸️ STOPPED")

        views_completed = stats.get("total_views_completed", 0)
        ouo_v = stats.get("ouo_views", 0)
        exe_v = stats.get("exe_views", 0)
        failed_views = stats.get("failed_views", 0)
        success_rate = stats.get("success_rate", "100%")

        # Pool info
        p_links = list_pool_links()
        pool_str = f"{len(p_links)} Active Links" if p_links else "Default Safe Articles"

        # US traffic info
        us_h = get_us_hour_now()
        weight = get_traffic_weight()
        traffic_badge = "🟢 PEAK" if weight >= 1.3 else ("🟡 NORMAL" if weight >= 0.8 else "🔴 NIGHT/SLOW")

        # Campaign status & 10m Micro Block
        p_stat = traffic_pacer.get_current_block_status()
        p_mode = "⚡ Flurry" if p_stat["is_burst"] else "🌊 Rest"
        micro_line = f"⏱️ <b>10m Block #{p_stat['block_num']}/6:</b> <code>{p_stat['completed']}/{p_stat['target']} views</code> ({p_mode} | {p_stat['rem_sec']/60:.1f}m left)\n"

        if is_campaign_active():
            cq = get_todays_campaign_quota()
            camp_line = f"🎯 <b>Active Campaign:</b> Day {cq['day']}/{cq['total_days']} ({cq['completed']}/{cq['target']} today)\n"
        else:
            hq = stats.get("hourly_quota", {})
            hq_done = hq.get("completed", 0)
            hq_target = hq.get("target", 0)
            hq_pct = f"{(hq_done/hq_target*100):.0f}%" if hq_target else "—"
            camp_line = f"⏰ <b>Hourly Quota:</b> <code>{hq_done}/{hq_target}</code> ({hq_pct})\n"

        return (
            "⚡ <b>ROX AI — Automation Engine</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 <b>Status:</b> <b>{daemon_badge}</b>\n"
            f"✅ <b>Total Paid Views:</b> <code>{views_completed}</code> views\n"
            f"  • 🔗 ouo.io: <code>{ouo_v}</code> | ⚡ exe.io: <code>{exe_v}</code>\n"
            f"🎯 <b>Success Rate:</b> <b>{success_rate}</b> (Failed: {failed_views})\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{camp_line}"
            f"{micro_line}"
            f"🇺🇸 <b>US Traffic Clock:</b> <code>{us_h}:00 EST</code> ({traffic_badge} {weight:.2f}x)\n"
            f"🔗 <b>Target Links:</b> <code>{pool_str}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Use the menu buttons below to control everything.</i>"
        )

    def send_or_update_status_card(chat_id, edit_msg_id=None):
        text = build_status_card_text()
        markup = get_main_reply_keyboard()
        bot.send_message(chat_id, text, reply_markup=markup, disable_web_page_preview=True)

    def prompt_for_password(chat_id, original_msg_id=None):
        if original_msg_id:
            safe_delete(chat_id, original_msg_id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cb_cancel_auth"))
        lock_msg = bot.send_message(
            chat_id,
            "🔒 <b>Security Verification Required (24-Hour Access)</b>\n\n"
            "Enter Master Security Password:\n\n"
            "🔑 <b>Password:</b>",
            reply_markup=markup
        )
        bot.register_next_step_handler(lock_msg, process_password_step)

    def process_password_step(message):
        chat_id = message.chat.id
        user_pass = (message.text or "").strip()
        safe_delete(chat_id, message.message_id)
        if user_pass == MASTER_PASSWORD:
            set_user_authenticated(chat_id)
            send_or_update_status_card(chat_id)
        else:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text="🔄 Try Again", callback_data="cb_reauth"))
            bot.send_message(chat_id, "❌ <b>Access Denied: Incorrect Password!</b>", reply_markup=markup)

    # --- CAMPAIGN WIZARD HANDLERS ---
    def start_campaign_wizard(chat_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="❌ Cancel Wizard", callback_data="cb_cancel_wizard"))
        msg = bot.send_message(
            chat_id,
            "📦 <b>Step 1/2: Proxy Data Estimation</b>\n\n"
            "Aapke paas kitne GB Proxy Bandwidth available hai?\n"
            "<i>(Example: Send <code>40</code> for 40 GB, ya <code>20</code> for 20 GB)</i>",
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_wizard_gb_step)

    def process_wizard_gb_step(message):
        chat_id = message.chat.id
        text = (message.text or "").strip()
        safe_delete(chat_id, message.message_id)

        try:
            gb = float(text)
            if gb <= 0: raise ValueError
        except ValueError:
            bot.send_message(chat_id, "❌ Invalid input. Please enter numbers only (e.g., 40).")
            return

        # Estimate views based on 2.5 MB/view
        total_mb = gb * 1024
        est_views_avg = int(total_mb / 2.5)
        min_views = int(est_views_avg * 0.82)
        max_views = int(est_views_avg * 1.15)

        wizard_temp[chat_id] = {
            "gb": gb,
            "est_views": est_views_avg,
            "min_views": min_views,
            "max_views": max_views
        }

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="❌ Cancel", callback_data="cb_cancel_wizard"))
        msg = bot.send_message(
            chat_id,
            f"📊 <b>Proxy Estimation for {gb:.0f} GB:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• 📉 <b>Minimum Guaranteed Views:</b> ~{min_views:,}\n"
            f"• 🎯 <b>Realistic Expected Views:</b> ~{est_views_avg:,}\n"
            f"• 🚀 <b>Maximum Potential Views:</b> ~{max_views:,}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⏰ <b>Step 2/2: Delivery Timeframe</b>\n"
            "Ye views aapko kitne din me deliver karwane hain?\n"
            "<i>(Example: Send <code>2</code> for 2 days, <code>3</code> for 3 days)</i>",
            reply_markup=markup
        )
        bot.register_next_step_handler(msg, process_wizard_days_step)

    def process_wizard_days_step(message):
        chat_id = message.chat.id
        text = (message.text or "").strip()
        safe_delete(chat_id, message.message_id)

        try:
            days = int(text)
            if days <= 0 or days > 30: raise ValueError
        except ValueError:
            bot.send_message(chat_id, "❌ Please enter a valid number of days between 1 and 30.")
            return

        data = wizard_temp.get(chat_id)
        if not data:
            bot.send_message(chat_id, "❌ Session expired. Please start with /newcampaign again.")
            return

        total_views = data["est_views"]
        schedule = generate_campaign_schedule(total_views, days)
        data["days"] = days
        data["schedule"] = schedule

        # Build schedule preview
        lines = []
        for s in schedule:
            lines.append(f"• <b>Day {s['day']} ({s['date']}):</b> <code>{s['target']:,}</code> views")

        schedule_str = "\n".join(lines)

        markup = types.InlineKeyboardMarkup(row_width=2)
        b_confirm = types.InlineKeyboardButton(text="🚀 Activate Campaign", callback_data="cb_confirm_campaign")
        b_cancel = types.InlineKeyboardButton(text="❌ Cancel", callback_data="cb_cancel_wizard")
        markup.row(b_confirm, b_cancel)

        bot.send_message(
            chat_id,
            "🗓️ <b>Automated Natural Flow Schedule:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Proxy Bandwidth:</b> {data['gb']:.0f} GB\n"
            f"🎯 <b>Total Views Target:</b> {total_views:,}\n"
            f"⏳ <b>Campaign Duration:</b> {days} Days\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Day-by-Day Natural Uneven Distribution:</b>\n"
            f"{schedule_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>✨ Traffic will automatically peak during US 7 PM–9 PM and slow down naturally at night.</i>\n\n"
            "Kya aap ye campaign start karna chahte hain?",
            reply_markup=markup
        )

    # --- COMMAND & MENU HANDLERS ---
    @bot.message_handler(commands=['start', 'status', 'help'])
    def cmd_start(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        send_or_update_status_card(chat_id)

    @bot.message_handler(commands=['newcampaign'])
    def cmd_newcampaign(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        start_campaign_wizard(chat_id)

    @bot.message_handler(commands=['campaign'])
    def cmd_view_campaign(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        camp = load_campaign()
        if not camp:
            bot.send_message(chat_id, "ℹ️ No active campaign currently running. Use '🚀 New Campaign' button to schedule one.", reply_markup=get_main_reply_keyboard())
            return

        lines = []
        for s in camp.get("schedule", []):
            pct = f"{(s['completed']/s['target']*100):.0f}%" if s['target'] else "0%"
            lines.append(f"• <b>Day {s['day']} ({s['date']}):</b> {s['completed']:,} / {s['target']:,} ({pct})")

        sched_str = "\n".join(lines)
        bot.send_message(
            chat_id,
            "📊 <b>Active Campaign Schedule:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Total Target:</b> {camp.get('total_views', 0):,} views ({camp.get('gb_used', 0)} GB)\n"
            f"✅ <b>Delivered:</b> {camp.get('total_completed', 0):,} views\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sched_str}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            reply_markup=get_main_reply_keyboard()
        )

    @bot.message_handler(commands=['stopcampaign'])
    def cmd_stop_campaign(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        cancel_campaign()
        bot.send_message(chat_id, "🛑 Active campaign has been stopped. Workers reverted to standard human hourly mode.", reply_markup=get_main_reply_keyboard())

    @bot.message_handler(commands=['addlink'])
    def cmd_add_link(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        parts = message.text.split(maxsplit=2)
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        if len(parts) < 2:
            bot.send_message(chat_id, "ℹ️ Usage: <code>/addlink &lt;url&gt; [optional label]</code>\nExample: <code>/addlink https://example.com/page My Site</code>", reply_markup=get_main_reply_keyboard())
            return
        url = parts[1].strip()
        label = parts[2].strip() if len(parts) > 2 else ""
        item = add_link_to_pool(url, label)
        bot.send_message(chat_id, f"✅ <b>Link Added to Pool!</b>\n🆔 ID: <code>{item['id']}</code>\n🏷️ Label: {item['label']}\n🔗 URL: <code>{item['url']}</code>\n\nViews will now route to this destination.", reply_markup=get_main_reply_keyboard())

    @bot.message_handler(commands=['listlinks'])
    def cmd_list_links(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        links = list_pool_links()
        if not links:
            bot.send_message(chat_id, "ℹ️ <b>Link Pool is empty.</b>\nWorkers are using safe default articles.\nUse <code>/addlink &lt;url&gt;</code> to add custom target links.", reply_markup=get_main_reply_keyboard())
            return
        lines = []
        for l in links:
            lines.append(f"• [ID: <code>{l['id']}</code>] <b>{l['label']}</b>\n  🔗 <code>{l['url']}</code>\n  👁️ Delivered: <b>{l['views_delivered']}</b>\n")
        bot.send_message(chat_id, f"📋 <b>Active Link Pool ({len(links)} links):</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines) + "━━━━━━━━━━━━━━━━━━━━━━━━━━\nTo remove a link: <code>/removelink &lt;id&gt;</code>", reply_markup=get_main_reply_keyboard())

    @bot.message_handler(commands=['removelink'])
    def cmd_remove_link(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        parts = message.text.split()
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        if len(parts) < 2:
            bot.send_message(chat_id, "ℹ️ Usage: <code>/removelink &lt;id&gt;</code>", reply_markup=get_main_reply_keyboard())
            return
        try:
            lid = int(parts[1])
            if remove_link_from_pool(lid):
                bot.send_message(chat_id, f"✅ Link #{lid} removed from pool.", reply_markup=get_main_reply_keyboard())
            else:
                bot.send_message(chat_id, f"❌ Link #{lid} not found.", reply_markup=get_main_reply_keyboard())
        except ValueError:
            bot.send_message(chat_id, "❌ Invalid ID number.", reply_markup=get_main_reply_keyboard())

    @bot.message_handler(commands=['clearlinks'])
    def cmd_clear_links(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        clear_link_pool()
        bot.send_message(chat_id, "🧹 Link pool cleared. Default safe educational links active.", reply_markup=get_main_reply_keyboard())

    @bot.message_handler(commands=['traffic'])
    def cmd_traffic(message):
        if message.chat.type != 'private':
            return
        chat_id = message.chat.id
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return
        us_h = get_us_hour_now()
        weight = get_traffic_weight()
        bot.send_message(
            chat_id,
            "🇺🇸 <b>US Eastern Day/Night Traffic Curve:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <b>Current US Time:</b> <code>{us_h}:00 EST</code>\n"
            f"⚡ <b>Current Traffic Rate:</b> <code>{weight:.2f}x</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Traffic Breakdown Schedule:</b>\n"
            "• 🔴 <b>2 AM – 5 AM EST:</b> <code>0.10x – 0.15x</code> (Dead Night / Minimal)\n"
            "• 🟡 <b>6 AM – 9 AM EST:</b> <code>0.45x – 0.85x</code> (Morning / Waking up)\n"
            "• 🟢 <b>10 AM – 4 PM EST:</b> <code>1.00x – 1.15x</code> (Standard Workday Traffic)\n"
            "• 🚀 <b>5 PM – 9 PM EST:</b> <code>1.30x – 1.55x</code> (⭐ PRIME PEAK HOURS)\n"
            "• 🟡 <b>10 PM – 1 AM EST:</b> <code>0.30x – 1.05x</code> (Evening Wind Down)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Engine automatically increases delivery during US peak hours and slows down at night to guarantee 100% human-like flow.</i>",
            reply_markup=get_main_reply_keyboard()
        )

    @bot.message_handler(func=lambda m: True)
    def handle_all_messages(message):
        # STRICT GROUP/CHANNEL SILENCE: completely silent outside private chat
        if message.chat.type != 'private':
            return

        chat_id = message.chat.id
        text = (message.text or "").strip()
        safe_delete(chat_id, message.message_id)
        if not is_user_authenticated(chat_id):
            prompt_for_password(chat_id)
            return

        # Route Reply Keyboard button taps
        if text in ["📊 Dashboard", "/status", "/start"]:
            send_or_update_status_card(chat_id)
        elif text in ["🚀 New Campaign", "/newcampaign"]:
            start_campaign_wizard(chat_id)
        elif text in ["🔗 Link Pool", "/listlinks"]:
            cmd_list_links(message)
        elif text in ["🇺🇸 US Traffic", "/traffic"]:
            cmd_traffic(message)
        elif text in ["📋 View Campaign", "/campaign"]:
            cmd_view_campaign(message)
        elif text in ["🛑 Stop Campaign", "/stopcampaign"]:
            cmd_stop_campaign(message)
        else:
            send_or_update_status_card(chat_id)

    # --- CALLBACK QUERIES ---
    @bot.callback_query_handler(func=lambda call: True)
    def handle_callbacks(call):
        if call.message and call.message.chat.type != 'private':
            return

        chat_id = call.message.chat.id
        data = call.data

        if data == "cb_cancel_auth":
            bot.clear_step_handler_by_chat_id(chat_id)
            safe_edit(chat_id, call.message.message_id, "❌ <b>Verification Cancelled.</b>")
            bot.answer_callback_query(call.id, "Cancelled")
            return

        if data == "cb_reauth":
            bot.answer_callback_query(call.id)
            prompt_for_password(chat_id, original_msg_id=call.message.message_id)
            return

        if not is_user_authenticated(chat_id):
            bot.answer_callback_query(call.id, "Master Password required!")
            prompt_for_password(chat_id)
            return

        if data == "cb_refresh_status":
            bot.answer_callback_query(call.id, "Refreshed! ⚡")
            send_or_update_status_card(chat_id, edit_msg_id=call.message.message_id)

        elif data == "cb_wizard_start":
            bot.answer_callback_query(call.id)
            start_campaign_wizard(chat_id)

        elif data == "cb_cancel_wizard":
            bot.clear_step_handler_by_chat_id(chat_id)
            safe_edit(chat_id, call.message.message_id, "❌ <b>Campaign setup cancelled.</b>")
            bot.answer_callback_query(call.id, "Cancelled")

        elif data == "cb_confirm_campaign":
            d = wizard_temp.get(chat_id)
            if not d:
                bot.answer_callback_query(call.id, "Session expired!")
                return
            campaign_data = {
                "total_views": d["est_views"],
                "gb_used": d["gb"],
                "days": d["days"],
                "total_completed": 0,
                "schedule": d["schedule"],
                "status": "active",
                "started_at": get_current_time_str()
            }
            save_campaign(campaign_data)
            wizard_temp.pop(chat_id, None)
            safe_edit(chat_id, call.message.message_id, "🚀 <b>Campaign Activated Successfully!</b>\n\nWorkers are now locked onto this natural daily schedule. View progress anytime with /campaign.")
            bot.answer_callback_query(call.id, "Activated!")

        elif data == "cb_stop_campaign":
            cancel_campaign()
            safe_edit(chat_id, call.message.message_id, "🛑 <b>Campaign Stopped.</b> Reverted to standard hourly mode.")
            bot.answer_callback_query(call.id, "Stopped")

        elif data == "cb_show_pool":
            bot.answer_callback_query(call.id)
            cmd_list_links(call.message)

        elif data == "cb_show_traffic":
            bot.answer_callback_query(call.id)
            cmd_traffic(call.message)

        elif data == "cb_force_check":
            bot.answer_callback_query(call.id, "Checking ouo.io...")
            def bg_check():
                check_ouo_dashboard_hourly(force=True)
                send_or_update_status_card(chat_id, edit_msg_id=call.message.message_id)
            threading.Thread(target=bg_check, daemon=True).start()

    print(f"[*] Starting Telegram Bot with token: {BOT_TOKEN[:10]}...")
    try:
        me = bot.get_me()
        print(f"[+] Bot Online: @{me.username} ({me.first_name})")
    except Exception as e:
        print(f"[!] Warning connecting to Telegram: {e}")
    bot.infinity_polling(timeout=20, long_polling_timeout=15)

# ------------------------------------------------------------------------------
# 15. CLI ARGUMENT PARSER & MAIN ENTRYPOINT
# ------------------------------------------------------------------------------
def print_status_terminal():
    stats = load_stats()
    hq = stats.get("hourly_quota", {})
    us_h = get_us_hour_now()
    weight = get_traffic_weight()

    print("\n" + "="*60)
    print("📊 CURRENT OUO.IO & EXE.IO DUAL AUTOMATION STATS")
    print("="*60)
    print(f"Status:             {stats.get('daemon_status')}")
    print(f"Total Completed:    {stats.get('total_views_completed')}")
    print(f"  • ouo.io Views:   {stats.get('ouo_views', 0)}")
    print(f"  • exe.io Views:   {stats.get('exe_views', 0)}")
    print(f"Failed Views:       {stats.get('failed_views')}")
    print(f"Success Rate:       {stats.get('success_rate')}")
    print(f"Last Activity:      {stats.get('last_activity_str')}")
    print("-"*60)
    print(f"US Clock (EST):     {us_h}:00 EST (Traffic Multiplier: {weight:.2f}x)")
    if is_campaign_active():
        cq = get_todays_campaign_quota()
        print(f"Active Campaign:    Day {cq['day']}/{cq['total_days']} ({cq['completed']}/{cq['target']} today)")
    else:
        print(f"Hourly Target:      {hq.get('target', '—')}")
        print(f"Hourly Completed:   {hq.get('completed', '—')}")
    print("-"*60)
    dash = stats.get("dashboard", {})
    print(f"ouo.io Views:       {dash.get('views')}")
    print(f"ouo.io Earnings:    {dash.get('earnings')}")
    print(f"ouo.io eCPM:        {dash.get('ecpm')}")
    print(f"Available Balance:  {dash.get('available')}")
    print("="*60 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description="ouo.io & exe.io 24/7 Automation & Telegram Control Center (Pro Engine)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    sub_daemon = subparsers.add_parser("daemon", help="Run 24/7 multi-worker earning daemon")
    sub_daemon.add_argument("-w", "--workers", type=int, default=NUM_WORKERS, help=f"Number of concurrent workers (default: {NUM_WORKERS})")

    subparsers.add_parser("bot", help="Run Telegram control bot")

    sub_all = subparsers.add_parser("all", help="Run BOTH multi-worker daemon and Telegram bot concurrently")
    sub_all.add_argument("-w", "--workers", type=int, default=NUM_WORKERS, help=f"Number of concurrent workers (default: {NUM_WORKERS})")

    sub_campaign = subparsers.add_parser("campaign", help="Run end-to-end campaign loop for N views")
    sub_campaign.add_argument("views", type=int, nargs="?", default=1, help="Total views to deliver (default: 1)")
    sub_campaign.add_argument("--url", type=str, default=None, help="Vercel portal URL")

    subparsers.add_parser("login", help="Run login and save session cookies")

    sub_shorten = subparsers.add_parser("shorten", help="Shorten a specific URL")
    sub_shorten.add_argument("url", type=str, nargs="?", default="https://ouo-portal.vercel.app", help="URL to shorten")

    sub_visit = subparsers.add_parser("visit", help="Visit and bypass a shortlink")
    sub_visit.add_argument("url", type=str, help="Shortlink URL to visit")

    subparsers.add_parser("status", help="Display current stats in terminal")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "daemon":
        run_multi_worker_daemon(num_workers=args.workers, blocking=True)
    elif args.command == "bot":
        run_telegram_bot()
    elif args.command == "all":
        run_multi_worker_daemon(num_workers=args.workers, blocking=False)
        run_telegram_bot()
    elif args.command == "campaign":
        run_campaign_loop(total_views=args.views, vercel_url=args.url)
    elif args.command == "login":
        success = do_login(headless=True)
        print("[+] Login result:", "Success" if success else "Failed")
    elif args.command == "shorten":
        short = shorten_target(args.url)
        print(f"[+] Result: {short}")
    elif args.command == "visit":
        ok, dest = visit_shortlink(args.url)
        print(f"[+] Visit result: {'Success' if ok else 'Failed'} -> {dest}")
    elif args.command == "status":
        print_status_terminal()

if __name__ == '__main__':
    main()
