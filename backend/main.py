import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

app = FastAPI(title="Greenwashing Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/runs")
def list_runs():
    response = supabase.table("runs").select("*").order("created_at", desc=True).execute()
    return response.data


@app.get("/api/runs/{run_id}/pages")
def list_pages(run_id: str):
    response = (
        supabase.table("pages")
        .select("*")
        .eq("run_id", run_id)
        .order("created_at", desc=True)
        .execute()
    )
    if not response.data and not isinstance(response.data, list):
        raise HTTPException(status_code=404, detail="Run not found")
    return response.data
