from __future__ import absolute_import, unicode_literals

import os

from celery import Celery
from kombu import Exchange, Queue

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('ciptea')
app.config_from_object('django.conf:settings', namespace='CELERY')
ciptea_exchange = Exchange('ciptea', type='direct')
app.conf.update(
    task_default_queue='ciptea',
    task_default_exchange='ciptea',
    task_default_exchange_type='direct',
    task_default_routing_key='ciptea',
    task_queues=(
        Queue('ciptea', exchange=ciptea_exchange, routing_key='ciptea'),
        Queue('ia_tasks', exchange=ciptea_exchange, routing_key='ia_tasks'),
    ),
    task_routes={
        'cadastro.tasks.process_ciptea_documents': {'queue': 'ia_tasks', 'routing_key': 'ia_tasks'},
        'cadastro.tasks.process_ciptea_document_step': {'queue': 'ia_tasks', 'routing_key': 'ia_tasks'},
        'cadastro.tasks.finalize_ciptea_triagem': {'queue': 'ia_tasks', 'routing_key': 'ia_tasks'},
    },
)
app.autodiscover_tasks()
