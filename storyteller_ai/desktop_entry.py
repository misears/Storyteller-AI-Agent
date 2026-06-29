import os

import uvicorn


def main() -> None:
    host = os.getenv("STORYTELLER_HOST", "127.0.0.1")
    port = int(os.getenv("STORYTELLER_PORT", "8000"))
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
