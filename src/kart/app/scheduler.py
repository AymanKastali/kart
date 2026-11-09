"""The `scheduler` process. It idles until the sweepers are added."""

from kart.app.background_process import run_until_stopped

if __name__ == "__main__":
    run_until_stopped("scheduler")
