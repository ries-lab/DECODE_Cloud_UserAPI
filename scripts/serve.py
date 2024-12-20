import multiprocessing
import os

import gunicorn.app.base  # type: ignore
import uvicorn


class StandaloneApplication(gunicorn.app.base.BaseApplication):  # type: ignore
    def __init__(self, app: str, options: dict[str, str | int] | None = None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self) -> None:
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self) -> str:
        return self.application


def main() -> None:
    app = "api.main:app"
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    prod = bool(int(os.environ.get("IS_PROD", "0")))

    if not prod:
        uvicorn.run(app, host=host, port=port, reload=True)
    else:
        StandaloneApplication(
            app="app:app",
            options={
                "bind": f"{host}:{port}",
                "workers": (multiprocessing.cpu_count() * 2) + 1,
                "worker_class": "uvicorn.workers.UvicornWorker",
            },
        ).run()
