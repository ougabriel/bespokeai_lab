#!/usr/bin/env python

import uvicorn

from app.config import load_settings


if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="warning",
    )
