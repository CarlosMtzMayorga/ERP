from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.tenants.router import router as tenants_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: logging and warmup
    print(f"[STARTUP] Iniciando {settings.PROJECT_NAME} en entorno: {settings.ENVIRONMENT}")
    yield
    # Shutdown: connection cleanup
    print(f"[SHUTDOWN] Finalizando aplicación ERP.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="ERP Cloud-Native Multi-Empresa para México (CFDI 4.0, SAT, Microsip Modern Style)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware (Configurable for local React dev and AWS CloudFront/S3 origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base healthcheck route for AWS ALB / ECS / App Runner
@app.get("/health", tags=["Health & Monitoring"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }

# Register API Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(tenants_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
