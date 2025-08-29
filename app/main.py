from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import catalog, meta, stream, configure
from app.manifest import get_manifest
import os

app = FastAPI(
    title="Catch-up TV & More for Stremio",
    description="A Python-based Stremio add-on for French live TV and replays",
    version="1.0.0"
)

# Add CORS middleware to allow requests from Stremio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for logos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(catalog.router, prefix="", tags=["catalog"])
app.include_router(meta.router, prefix="", tags=["meta"])
app.include_router(stream.router, prefix="", tags=["stream"])
app.include_router(configure.router, prefix="", tags=["configure"])

@app.get("/manifest.json")
async def manifest():
    return get_manifest()

@app.get("/")
async def root():
    return {"message": "Catch-up TV & More for Stremio API"}