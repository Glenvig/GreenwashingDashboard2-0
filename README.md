# Greenwashing Dashboard

A minimal dashboard to monitor greenwashing crawl runs and their scraped pages.

## Stack

- **Backend**: FastAPI (Python) + Supabase (service role key for server-side queries)
- **Frontend**: Next.js 15 (App Router, TypeScript, Tailwind CSS) + Supabase (anon key + realtime)

---

## Supabase Setup

### 1. Create a Supabase project

Go to [supabase.com](https://supabase.com) and create a new project.

### 2. Create the database tables

Run the following SQL in the **Supabase SQL Editor**:

```sql
-- Crawl runs
create table crawl_runs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  url text not null,
  status text not null default 'pending', -- pending | running | completed | failed
  created_at timestamptz not null default now()
);

-- Pages discovered during a run
create table pages (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references crawl_runs(id) on delete cascade,
  url text not null,
  title text,
  greenwashing_score float,  -- 0.0 (clean) to 1.0 (high greenwashing)
  created_at timestamptz not null default now()
);

-- Enable Row Level Security (RLS)
alter table crawl_runs enable row level security;
alter table pages enable row level security;

-- Allow authenticated users to read all rows
create policy "Authenticated read crawl_runs"
  on crawl_runs for select to authenticated using (true);

create policy "Authenticated read pages"
  on pages for select to authenticated using (true);
```

### 3. Enable Realtime

In Supabase: **Database → Replication** → enable the `crawl_runs` and `pages` tables for realtime.

### 4. Get your credentials

From **Settings → API**:
- `SUPABASE_URL` (e.g. `https://xxxx.supabase.co`)
- `anon` public key → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `service_role` secret key → `SUPABASE_SERVICE_ROLE_KEY` (backend only, never expose)

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- A Supabase project (see above)

---

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY

# Start the server
uvicorn main:app --reload --port 8000
```

API is available at <http://localhost:8000>

Health check: `curl http://localhost:8000/health`

---

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local and fill in NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
# NEXT_PUBLIC_API_URL defaults to http://localhost:8000

# Start the dev server
npm run dev
```

App is available at <http://localhost:3000>

---

## App Routes

| Route | Description |
|---|---|
| `/login` | Email + password sign-in via Supabase Auth |
| `/runs` | List all crawl runs, live-updated via Supabase Realtime |
| `/runs/[id]/pages` | List pages for a run, live-updated via Supabase Realtime |

Unauthenticated users are redirected to `/login` by Next.js middleware.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/runs` | List all runs |
| `GET` | `/api/runs/{run_id}/pages` | List pages for a run |
