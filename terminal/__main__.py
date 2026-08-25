from terminal.app import app
from terminal.config import load_settings

import uvicorn


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "terminal.app:app",
        host=settings.app.host,
        port=settings.app.python_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
