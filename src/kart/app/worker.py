"""The `worker` process. It idles until RabbitMQ consumers are added (#7)."""

from kart.app.background_process import run_until_stopped

if __name__ == "__main__":
    run_until_stopped("worker")
