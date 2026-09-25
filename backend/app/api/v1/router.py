from fastapi import APIRouter

from app.api.v1.endpoints import auth, batches, companies, graph, internal, watchlist

api_router = APIRouter()
api_router.include_router(companies.router, tags=["companies"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(watchlist.router, tags=["watchlist"])
api_router.include_router(batches.router, tags=["batches"])
api_router.include_router(internal.router, tags=["internal"])
