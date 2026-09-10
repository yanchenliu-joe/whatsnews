"""
Admin-only route packages — every /admin/* endpoint except the handful
still registered directly by other feature packages (narrative/perspective/
watch_next/ai/intelligence, which already had their own admin routes before
this refactor and keep the same require_admin_key-parameter convention).

Public API:
  require_admin_key(x_admin_key) -> None   (raises 401 if ADMIN_API_KEY is set and mismatched)
  register_admin_pipeline_routes(app, require_admin_key)
  register_admin_diagnostics_routes(app, require_admin_key)
  register_admin_export_routes(app, require_admin_key)
  register_admin_feed_diagnostics_routes(app, require_admin_key)
  register_admin_feed_lifecycle_routes(app, require_admin_key)
  register_admin_feed_recommendation_routes(app, require_admin_key)
"""

from app.admin.deps import require_admin_key
from app.admin.pipeline_routes import register_admin_pipeline_routes
from app.admin.diagnostics_routes import register_admin_diagnostics_routes
from app.admin.export_routes import register_admin_export_routes
from app.admin.feed_diagnostics_routes import register_admin_feed_diagnostics_routes
from app.admin.feed_lifecycle_routes import register_admin_feed_lifecycle_routes
from app.admin.feed_recommendation_routes import register_admin_feed_recommendation_routes

__all__ = [
    "require_admin_key",
    "register_admin_pipeline_routes",
    "register_admin_diagnostics_routes",
    "register_admin_export_routes",
    "register_admin_feed_diagnostics_routes",
    "register_admin_feed_lifecycle_routes",
    "register_admin_feed_recommendation_routes",
]
