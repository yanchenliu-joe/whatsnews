import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.admin import (
    register_admin_diagnostics_routes,
    register_admin_export_routes,
    register_admin_feed_diagnostics_routes,
    register_admin_feed_lifecycle_routes,
    register_admin_feed_recommendation_routes,
    register_admin_pipeline_routes,
    require_admin_key as _require_admin_key,
)
from app.history import register_history_routes
from app.narrative.routes import register_narrative_routes
from app.perspective.routes import register_perspective_routes
from app.watch_next.routes import register_watch_next_routes
from app.ai.routes import register_ai_admin_routes
from app.ai.chat_routes import register_ai_chat_routes
from app.auth.routes import register_auth_routes
from app.auth.preferences_routes import register_preferences_routes
from app.auth.saved_articles_routes import register_saved_articles_routes
from app.auth.avatar_routes import register_avatar_routes
from app.entitlements.routes import register_entitlement_routes
from app.related.routes import register_related_routes
from app.intelligence.routes import register_intelligence_routes
from app.briefing.routes import register_briefing_routes
from app.cognitive.routes import register_cognitive_routes
from app.feed.routes import register_feed_routes
from app.narrative.audio_config import get_local_audio_dir
from app.notifications.device_scheduler import _device_notification_scheduler_loop
from app.pipeline.scheduler import scheduler_loop
from app.public_routes import register_public_routes
from app.startup_tasks import _archive_cleanup_loop, _feed_cache_warmup, _global_graph_decay_loop

_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=_sentry_dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        # Error monitoring only — no tracing/profiling (matches the Sentry
        # project's onboarding selection); keeps this well within the free tier.
        traces_sample_rate=0.0,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI startup/shutdown hook. Starts the scheduler if ENABLE_SCHEDULER=true."""
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        daily_time = os.getenv("SCHEDULER_DAILY_TIME")
        if daily_time:
            tz = os.getenv("SCHEDULER_TIMEZONE", "UTC")
            print(f"[scheduler] Daily mode — runs at {daily_time} {tz}.")
        else:
            interval = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))
            print(f"[scheduler] Interval mode (dev fallback) — runs every {interval}s.")
        asyncio.create_task(scheduler_loop())
    # Phase 23D: always start global graph decay loop regardless of scheduler flag
    asyncio.create_task(_global_graph_decay_loop())
    asyncio.create_task(_feed_cache_warmup())
    # Phase 34: per-device scheduled push delivery — a delivery mechanism, not
    # content generation, so (like the decay loop) it runs regardless of
    # ENABLE_SCHEDULER.
    asyncio.create_task(_device_notification_scheduler_loop())
    # Archive retention — a maintenance job, not content generation, so (like
    # the decay loop) it runs regardless of ENABLE_SCHEDULER.
    asyncio.create_task(_archive_cleanup_loop())
    yield
    # Background tasks are automatically cleaned up when the event loop closes.


app = FastAPI(title="WhatsNews API", version="0.1.0", lifespan=lifespan)

app.mount(
    "/media/audio",
    StaticFiles(directory=str(get_local_audio_dir())),
    name="narrative_audio",
)

register_history_routes(app)

# CORS_ALLOWED_ORIGINS: comma-separated list of allowed browser origins.
# Defaults to "*" (unrestricted) to preserve prior behavior when unset —
# set explicitly in production (e.g. via render.yaml) to narrow this.
# Note: CORS only restricts browser-based requests; the mobile app (React
# Native) and direct API calls (curl/Postman) are unaffected either way —
# there is currently no browser-based web client for this product.
_cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS")
_cors_origins = (
    [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    if _cors_origins_raw is not None
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_narrative_routes(app, _require_admin_key)
register_perspective_routes(app, _require_admin_key)
register_watch_next_routes(app, _require_admin_key)
register_ai_admin_routes(app, _require_admin_key)
register_ai_chat_routes(app)
register_auth_routes(app)
register_saved_articles_routes(app)
register_preferences_routes(app)
register_avatar_routes(app)
register_entitlement_routes(app)
register_related_routes(app)
register_intelligence_routes(app, _require_admin_key)
register_briefing_routes(app)
register_cognitive_routes(app)
register_feed_routes(app, _require_admin_key)

register_public_routes(app)
register_admin_pipeline_routes(app, _require_admin_key)
register_admin_diagnostics_routes(app, _require_admin_key)
register_admin_export_routes(app, _require_admin_key)
register_admin_feed_diagnostics_routes(app, _require_admin_key)
register_admin_feed_lifecycle_routes(app, _require_admin_key)
register_admin_feed_recommendation_routes(app, _require_admin_key)
