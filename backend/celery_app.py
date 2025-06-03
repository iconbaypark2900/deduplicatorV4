from celery import Celery
from utils.config import settings

# Construct Broker and Backend URLs if not explicitly set
# Defaulting to Redis using REDIS_HOST and REDIS_PORT if specific Celery URLs aren't provided
broker_url = settings.CELERY_BROKER_URL
if not broker_url:
    broker_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

result_backend_url = settings.CELERY_RESULT_BACKEND
if not result_backend_url:
    result_backend_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1" 
    # Using a different DB number for results is a common practice

app = Celery(
    'deduplicator_tasks',
    broker=broker_url,
    backend=result_backend_url,
    include=[
        'backend.tasks.pipeline_tasks', # We will create this file for orchestrator tasks
        'backend.tasks.clustering_tasks'  # We will create this for clustering tasks
    ]
)

# Optional Celery configuration
app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    # Add other configurations as needed
    # Example: task_acks_late = True, worker_prefetch_multiplier = 1
)

# If you want Celery to automatically discover tasks in files named tasks.py in your INSTALLED_APPS (Django style)
# or in the include paths, you can use autodiscover_tasks. Explicit include is often clearer.
# app.autodiscover_tasks()

if __name__ == '__main__':
    # This allows running celery worker directly using: python -m backend.celery_app worker -l info
    app.start() 