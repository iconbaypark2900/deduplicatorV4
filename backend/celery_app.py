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
        'backend.tasks.clustering_tasks',  # We will create this for clustering tasks
        'backend.tasks.lsh_tasks', # Added LSH tasks module
        'backend.tasks.vectorizer_tasks' # Added TF-IDF vectorizer tasks module
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

# Celery Beat Schedule
app.conf.beat_schedule = {
    'rebuild-lsh-every-5-minutes': {
        'task': 'tasks.rebuild_global_lsh_index',
        'schedule': 300.0,  # 300 seconds = 5 minutes
    },
    'manage-tfidf-vectorizer-daily': { # Added schedule for TF-IDF vectorizer management
        'task': 'tasks.manage_tfidf_vectorizer',
        'schedule': 86400.0,  # 86400 seconds = 24 hours
        'args': (False,) # Corresponds to force_refit=False. Change to True to force refit on schedule.
    },
    'run-dbscan-clustering-periodically': { # Added schedule for periodic DBSCAN clustering
        'task': 'clustering.run_dbscan', # Name defined in @app.task decorator
        'schedule': 21600.0,  # 21600 seconds = 6 hours
    },
}

# If you want Celery to automatically discover tasks in files named tasks.py in your INSTALLED_APPS (Django style)
# or in the include paths, you can use autodiscover_tasks. Explicit include is often clearer.
# app.autodiscover_tasks()

if __name__ == '__main__':
    # This allows running celery worker directly using: python -m backend.celery_app worker -l info
    app.start() 