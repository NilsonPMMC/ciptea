try:
    from .celery import app as celery_app
except Exception:  # pragma: no cover - ambiente sem celery instalado ainda
    celery_app = None

__all__ = ('celery_app',)
