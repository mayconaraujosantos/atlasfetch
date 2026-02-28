"""
Agendamento programado para executar o scraper e salvar no banco.
Baseado nas referências (MM/YYYY) dos débitos retornados.
"""

import logging
import os
import sys
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

# Garante que src/ esteja no path
_src = Path(__file__).parent / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_sync_job() -> dict:
    """Executa job de sincronização via use case."""
    from atlasfetch.api.container import get_config, _create_sincronizar_debitos

    config = get_config()
    if not config["cpf"] or not config["senha"]:
        raise ValueError("AGUAS_CPF e AGUAS_SENHA não configurados")
    if not config["matricula"] or not config["sequencial"]:
        raise ValueError("AGUAS_MATRICULA e AGUAS_SEQUENCIAL não configurados")

    use_case = _create_sincronizar_debitos()
    return use_case.execute(
        cpf=config["cpf"],
        senha=config["senha"],
        matricula=config["matricula"],
        sequencial=config["sequencial"],
        zona=config["zona"],
    )


def _scheduled_task():
    """Tarefa executada pelo scheduler."""
    try:
        result = _run_sync_job()
        logger.info("Scheduler: job executado com sucesso - %s", result)
    except Exception as e:
        logger.exception("Scheduler: erro ao executar job - %s", e)


def _parse_cron(expr: str) -> dict:
    """
    Converte expressão cron (ex: '0 6 * * *') em kwargs para CronTrigger.
    Formato: minuto hora dia_do_mes mes dia_da_semana
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(
            "SCHEDULER_CRON deve ter 5 campos: minuto hora dia mes dia_semana "
            "(ex: 0 6 * * * = todo dia às 6h)"
        )
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def start_scheduler() -> bool:
    """
    Inicia o scheduler se SCHEDULER_ENABLED=1.
    Configuração:
      - SCHEDULER_ENABLED=1
      - SCHEDULER_CRON=0 6 * * *  (todo dia às 6h) - padrão
      - ou SCHEDULER_HOUR=6, SCHEDULER_MINUTE=0 (alternativa)
    """
    global _scheduler

    if os.environ.get("SCHEDULER_ENABLED", "").strip() != "1":
        logger.info("Scheduler desabilitado (SCHEDULER_ENABLED != 1)")
        return False

    if _scheduler is not None:
        logger.warning("Scheduler já está rodando")
        return True

    cron_expr = os.environ.get("SCHEDULER_CRON", "0 6 * * *").strip()
    hour = os.environ.get("SCHEDULER_HOUR", "").strip()
    minute = os.environ.get("SCHEDULER_MINUTE", "").strip()

    if cron_expr:
        try:
            trigger = CronTrigger(**_parse_cron(cron_expr))
            desc = f"cron={cron_expr}"
        except ValueError as e:
            logger.warning("SCHEDULER_CRON inválido (%s), usando 6h diária", e)
            trigger = CronTrigger(hour=6, minute=0)
            desc = "6:00 diário (fallback)"
    elif hour and minute:
        trigger = CronTrigger(hour=int(hour), minute=int(minute))
        desc = f"{hour}:{minute} diário"
    else:
        trigger = CronTrigger(hour=6, minute=0)
        desc = "6:00 diário (padrão)"

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_scheduled_task, trigger, id="sync_debitos")
    _scheduler.start()

    logger.info("Scheduler iniciado - execução: %s", desc)
    return True


def stop_scheduler():
    """Para o scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler parado")


def run_now() -> dict:
    """Executa o job imediatamente (útil para testes)."""
    return _run_sync_job()


if __name__ == "__main__":
    # Execução standalone: roda o job uma vez
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "--schedule":
        # Modo daemon: inicia scheduler e fica rodando
        from database import init_db

        init_db()
        start_scheduler()
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            stop_scheduler()
    else:
        # Modo one-shot: executa uma vez
        from database import init_db

        init_db()
        result = run_now()
        print("Resultado:", result)
