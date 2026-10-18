<div align="center">

<!-- ANIMATED FUTURISTIC WAVE HEADER -->
<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=0:0f0c29,50:302b63,100:24243e&height=220&section=header&text=TJP%20MULTIPLEX%20OS&fontSize=55&fontColor=00F7FF&animation=fadeIn&fontAlignY=35&desc=%E2%9A%A1%20NEXT-GEN%20AUTONOMOUS%20CINEMA%20RESERVATION%20ENGINE%20%E2%9A%A1&descAlignY=58&descSize=16&descColor=A5B4FC" />

<!-- SELF-TYPING TERMINAL SUBTITLE -->
<a href="https://tjp-multiplex-utsw.onrender.com">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=700&size=20&duration=2800&pause=800&color=00F7FF&center=true&vCenter=true&multiline=false&width=750&lines=%3E+SYSTEM_ONLINE+%3A%3A+REAL-TIME+ATOMIC+SEAT+LOCKING;%3E+LUMI%C3%88RE_AI_CONCIERGE+%3A%3A+POWERED+BY+GOOGLE+GEMINI;%3E+STRESS_TESTED+%3A%3A+99%25+LATENCY+REDUCTION+UNDER+SWARM+LOAD;%3E+ZERO_COLLISION_GUARANTEE+%3A%3A+SUPABASE+CLOUD+LEDGER" alt="Typing SVG" />
</a>

<br/>

<!-- FUTURISTIC GLOWING STATUS BADGES -->
[![SYSTEM STATUS](https://img.shields.io/badge/SYSTEM_STATUS-ONLINE-00F7FF?style=for-the-badge&logo=statuspage&logoColor=black&labelColor=0D1117)](https://tjp-multiplex-utsw.onrender.com)
[![ENGINE](https://img.shields.io/badge/CORE-FLASK_%7C_PYTHON_3.14-FF007F?style=for-the-badge&logo=python&logoColor=white&labelColor=0D1117)]()
[![DATABASE](https://img.shields.io/badge/LEDGER-SUPABASE_POSTGRES-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white&labelColor=0D1117)]()
[![NEURAL AI](https://img.shields.io/badge/LUMIÈRE_AI-GEMINI_FLASH-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white&labelColor=0D1117)]()
[![SWARM VERIFIED](https://img.shields.io/badge/LOCUST_SWARM-PASSED_100%25-A3E635?style=for-the-badge&logo=opsgenie&logoColor=white&labelColor=0D1117)]()

<br/>

<!-- ANIMATED NEON DIVIDER -->
<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">

### 🛸 `[ ACCESS LIVE COMMAND PORTAL ]`
### 👉 **[`https://tjp-multiplex-utsw.onrender.com`](https://tjp-multiplex-utsw.onrender.com)** 👈

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">

</div>

---

## 🧠 `01 // SYSTEM ARCHITECTURE BLUEPRINT`

> *GitHub natively renders this interactive neural flow diagram:*

```mermaid
flowchart LR
    subgraph CLIENT ["🌐 CLIENT INTERFACE"]
        U["👤 Guest Browser"]
        B["🤖 Locust Swarm Bots"]
    end

    subgraph EDGE ["⚡ RENDER CLOUD ENGINE (Gunicorn 2W x 4T)"]
        F["🐍 Flask Core Router"]
        L["🔒 Atomic Seat-Lock Guard"]
    end

    subgraph CLOUD ["☁️ EXTERNAL NEURAL & DATA NODES"]
        S[("🟢 Supabase Cloud\n(bookings & seat_locks)")]
        G["✨ Lumière AI\n(Google Gemini API)"]
        E["📧 Brevo SMTP Engine\n(QR Passes & Daily Ledger)"]
    end

    U & B -->|HTTPS POST/GET| F
    F -->|/api/lock-seats| L
    L -->|409 Conflict Guard| S
    F -->|/api/ai-concierge| G
    F -->|/confirm-booking| S
    F -->|Async Dispatch| E

    style CLIENT fill:#0d1117,stroke:#00f7ff,stroke-width:2px,color:#fff
    style EDGE fill:#161b22,stroke:#ff007f,stroke-width:2px,color:#fff
    style CLOUD fill:#0d1117,stroke:#3ecf8e,stroke-width:2px,color:#fff
```

---

## ⚡ `02 // CORE CAPABILITY MATRIX`

<table>
  <tr>
    <td width="50%">
      <h3 align="center">🔒 Atomic Race-Condition Shield</h3>
      <p align="center">
        Time-bound seat holds (<code>seat_locks</code>) backed by Supabase prevent double-bookings across simultaneous sessions. Concurrent collisions are intercepted in real time via <code>HTTP 409 Conflict</code> guards before checkout.
      </p>
    </td>
    <td width="50%">
      <h3 align="center">🤖 Lumière Neural Concierge</h3>
      <p align="center">
        Embedded conversational AI powered by <b>Google Gemini</b>. Advises guests in real time on IMAX/Dolby Atmos screenings, showtimes, seat availability, and gourmet concessions.
      </p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3 align="center">🎟️ Automated Pass & Ledger Dispatch</h3>
      <p align="center">
        Generates unique <code>TJP-XXXXXXXX</code> cryptographic ticket IDs upon checkout, dispatching instant HTML passes to guests and automated daily revenue briefings to the cinema owner via <b>Brevo API</b>.
      </p>
    </td>
    <td width="50%">
      <h3 align="center">🛡️ Encrypted Admin & Gate Scanner</h3>
      <p align="center">
        Dual-passcode protected executive portal (<code>/bookings</code>) featuring live cloud ledger inspection, one-click executive email reporting, and emergency database purge protocols.
      </p>
    </td>
  </tr>
</table>

---

## 🔥 `03 // LOCUST SWARM TELEMETRY & BENCHMARKS`

The platform underwent high-concurrency stress testing using **Locust** (`HttpUser` swarm automation), simulating simultaneous seat-lock wars, AI queries, and end-to-end ticket checkouts.

### 🚀 WSGI Multi-Threaded Optimization Impact
By re-architecting the production container from a single synchronous worker to a multi-threaded worker pool (`gunicorn -w 2 --threads 4 --timeout 90 app:app`), system latency dropped by **up to 99%**:

```diff
+ [STATUS: VERIFIED] 317 Concurrent Requests Processed | 48/48 Live Tickets Minted | 0 Duplicate Seat Bookings
- [LEGACY BOTTLENECK] Single Worker Queueing (29,000ms) -> ELIMINATED
```

| Target Endpoint | Operation | Legacy (`1 Sync Worker`) | Tuned (`2W × 4T Pool`) | Delta / Velocity |
| :--- | :--- | :---: | :---: | :---: |
| `GET /` | Matrix Initialization | `29,000 ms` | **`280 ms`** | 🟢 **99.0% Faster** |
| `GET /select-seats` | Live Seat Map Sync | `18,000 ms` | **`1,100 ms`** | 🟢 **93.8% Faster** |
| `POST /api/lock-seats` | Atomic Seat Hold | `18,000 ms` | **`1,900 ms`** | 🟢 **89.4% Faster** |
| `POST /confirm-booking` | Ledger Commit + Brevo | `Timeout` | **`2,000 ms`** | 🟢 **100% Checkout Success** |
| `POST /api/ai-concierge` | Lumière Neural Query | `31,000 ms` | **`1,800 ms`** | 🟢 **94.2% Faster** |

<details>
<summary><b>📂 [ CLICK TO EXPAND RAW LOCUST SWARM TELEMETRY LOGS ]</b></summary>
<br/>

```text
====================================================================================================
LOCUST SWARM REPORT // TARGET: tjp-multiplex-utsw.onrender.com
====================================================================================================
Type     Name                  # Reqs   # Fails   Median (ms)   95%ile (ms)   Avg (ms)   RPS
----------------------------------------------------------------------------------------------------
GET      /                         89         0           280           890     327.86   1.0
POST     /api/ai-concierge         29         0          1800          2700    1938.20   0.1
POST     /api/lock-seats           64        15*         1900          4300    2129.23   0.8
POST     /confirm-booking          48         0          2000          3300    2088.40   0.7
GET      /select-seats             87         0          1100          2100    1304.50   0.7
----------------------------------------------------------------------------------------------------
         Aggregated               317        15          1400          2900    1373.48   3.3
====================================================================================================
* NOTE: 409 Conflict responses on /api/lock-seats confirm active race-condition interception when
  multiple bots targeted identical seat coordinates simultaneously.
```
</details>

---

## 🛠️ `04 // TECH ARSENAL`

<div align="center">

  <img src="https://skillicons.dev/icons?i=python,flask,postgres,supabase,gcp,html,css,js,git,github&perline=5" />

</div>

---

## 💻 `05 // LOCAL DEPLOYMENT & SWARM SIMULATION`

### 1️⃣ Clone & Initialize Environment
```bash
git clone [https://github.com/MEETH007/TJP--MULTIPLEX.git](https://github.com/MEETH007/TJP--MULTIPLEX.git)
cd TJP--MULTIPLEX
pip install -r requirements.txt
```

### 2️⃣ Inject Environment Keys (`.env`)
```ini
SECRET_KEY="TJP_ULTRA_SECRET_HASH"
SUPABASE_URL="[https://your-project.supabase.co](https://your-project.supabase.co)"
SUPABASE_KEY="your-supabase-service-role-key"
GEMINI_API_KEY="your-google-gemini-key"
BREVO_API_KEY="your-brevo-smtp-api-key"
BOOKINGS_PASSWORD="admin-ledger-view-pass"
ADMIN_RESET_PASSWORD="admin-emergency-wipe-pass"
```

### 3️⃣ Launch Production Engine or Locust Swarm
```bash
# Start Multi-Threaded Production Server
gunicorn -w 2 --threads 4 --timeout 90 app:app

# Launch Locust Stress-Test Swarm (localhost:8089)
python -m locust -f locustfile.py --host [https://tjp-multiplex-utsw.onrender.com](https://tjp-multiplex-utsw.onrender.com)
```

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:24243e,50:302b63,100:0f0c29&height=120&section=footer" width="100%" />

**⚡ Engineered by [MEETH007](https://github.com/MEETH007) — TJP Cinema Systems ⚡**

</div>
