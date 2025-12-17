"""Route registration.

PUBLIC API:
  - include_routes: Register all API route modules with FastAPI app

Route Modules:
  - browser.py: DOM inspection and element selection endpoints
  - cdp.py: Direct CDP command relay
  - connection.py: Chrome connection management
  - data.py: Event data queries
  - fetch.py: Request interception control
  - filters.py: Filter management
"""

from fastapi import FastAPI


def include_routes(app: FastAPI):
    """Include all route modules.

    Args:
        app: FastAPI application instance
    """
    from webtap.api.routes import browser, cdp, connection, data, fetch, filters
    from webtap.api.sse import router as sse_router

    app.include_router(data.router)
    app.include_router(fetch.router)
    app.include_router(connection.router)
    app.include_router(filters.router)
    app.include_router(browser.router)
    app.include_router(cdp.router)
    app.include_router(sse_router)
