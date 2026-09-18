import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

app = Celery("project")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

from celery.schedules import crontab

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Ejecutar cada 15 minutos para buscar jobs sin embeddings
    sender.add_periodic_task(
        crontab(minute="*/15"),
        update_missing_job_embeddings_task.s(),
        name="update missing job embeddings every 15 minutes",
    )

    # Ejecutar cada 15 minutos para buscar feed posts sin embeddings
    sender.add_periodic_task(
        crontab(minute="*/15"),
        update_missing_post_embeddings_task.s(),
        name="update missing post embeddings every 15 minutes",
    )


@app.task
def update_missing_job_embeddings_task():
    from django.core.management import call_command

    call_command("update_job_embeddings", batch_size=50)


@app.task
def update_missing_post_embeddings_task():
    from django.core.management import call_command

    call_command("update_post_embeddings", batch_size=50)


@app.task
def update_missing_user_embeddings_task():
    return "retired: user embeddings are owned by profile_identity_backend"


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
