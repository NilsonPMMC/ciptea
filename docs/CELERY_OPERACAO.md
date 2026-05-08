# Operacao Celery (CIPTEA)

## Topologia de workers

- **Worker principal**
  - Service: `celery-ciptea.service`
  - Queue: `ciptea`
  - Objetivo: tasks nao-IA e fluxo geral

- **Worker IA**
  - Service: `celery-ciptea-ia.service`
  - Queue: `ia_tasks`
  - Parametros de protecao:
    - `--concurrency=2`
    - `--max-tasks-per-child=10`
  - Objetivo: reduzir risco de exaustao de CPU e conter crescimento de memoria em tarefas OCR/ML.

## Arquivos de configuracao

- `core/celery.py`
- `deploy/celery/celery-ciptea.service`
- `deploy/celery/celery-ciptea-ia.service`

## Comandos de operacao (systemd)

```bash
sudo systemctl daemon-reload
sudo systemctl restart celery-ciptea.service celery-ciptea-ia.service
sudo systemctl status celery-ciptea.service --no-pager
sudo systemctl status celery-ciptea-ia.service --no-pager
```

## Verificacao de filas ativas

```bash
/var/www/ciptea/venv/bin/celery -A core inspect active_queues
```

Esperado:
- `worker_main@...` consumindo `ciptea`
- `worker_ia@...` consumindo `ia_tasks`

## Verificacao de tarefas em andamento

```bash
/var/www/ciptea/venv/bin/celery -A core inspect active -d worker_main@<hostname>
/var/www/ciptea/venv/bin/celery -A core inspect reserved -d worker_main@<hostname>
/var/www/ciptea/venv/bin/celery -A core inspect active -d worker_ia@<hostname>
```

## Verificacao de backlog no Redis

```bash
redis-cli -n 0 LLEN ciptea
redis-cli -n 0 LLEN ia_tasks
redis-cli -n 0 LLEN celery
```

## Runbook de incidentes

### 1) Triagem IA nao processa

Checklist:
- Redis ativo
- `celery-ciptea-ia.service` em `active (running)`
- queue `ia_tasks` vinculada no worker IA
- sem erro de import/modelo nos logs

Logs:

```bash
journalctl -u celery-ciptea-ia.service -n 200 --no-pager
sudo journalctl -u celery-ciptea.service -f
sudo journalctl -u celery-ciptea-ia.service -f
```

### 2) Task de IA indo para worker errado

Checklist:
- routes em `core/celery.py` para `ia_tasks`
- `worker_main` sem `-Q ia_tasks`
- `worker_ia` com `-Q ia_tasks`

### 3) Alto uso de memoria em IA

Acoes:
- confirmar `--max-tasks-per-child=10`
- reduzir `--concurrency` temporariamente
- verificar tamanho/resolucao de imagens de entrada

## Boas praticas operacionais

- Manter nomes de worker unicos (`worker_main@%h`, `worker_ia@%h`).
- Evitar compartilhar o mesmo Redis DB com muitos projetos sem isolamento.
- Em ambientes multi-projeto, considerar Redis DB dedicado para CIPTEA.
