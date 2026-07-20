# Add docs mount to serve simulation guide
if os.path.exists(os.path.join(BASE_DIR, "docs")):
    app.mount("/docs", StaticFiles(directory=os.path.join(BASE_DIR, "docs")), name="docs")