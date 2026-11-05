"""Data e hora no fuso da clínica (o servidor na nuvem costuma estar em UTC)."""
import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Brasília: UTC-3, sem horário de verão desde 2019. Usado se o computador não tiver a base de fusos
# (Windows sem o pacote tzdata).
_BRASILIA = datetime.timezone(datetime.timedelta(hours=-3), "America/Sao_Paulo")


def _fuso(nome):
    try:
        return ZoneInfo(nome or "America/Sao_Paulo")
    except (ZoneInfoNotFoundError, ValueError):
        return _BRASILIA


_FUSO = _fuso("America/Sao_Paulo")


def configurar(fuso):
    global _FUSO
    _FUSO = _fuso(fuso)


def agora():
    return datetime.datetime.now(_FUSO).replace(tzinfo=None)


def hoje():
    return agora().date().isoformat()


def agora_texto():
    return agora().strftime("%Y-%m-%d %H:%M:%S")


def soma_dias(iso, n):
    return (datetime.date.fromisoformat(iso[:10]) + datetime.timedelta(days=n)).isoformat()


def soma_meses(iso, n):
    d = datetime.date.fromisoformat(iso[:10])
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    import calendar
    dia = min(d.day, calendar.monthrange(a, m)[1])
    return datetime.date(a, m, dia).isoformat()


def data_br(iso):
    return "/".join(reversed(str(iso)[:10].split("-"))) if iso else ""


def agora_iso_utc():
    """Instante atual no formato do app em JavaScript (toISOString): 2026-11-05T13:15:00.123Z"""
    t = datetime.datetime.now(datetime.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def de_iso(iso):
    """Converte um instante ISO (com Z ou fuso) para datetime com fuso; None se inválido."""
    if not iso:
        return None
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=_FUSO)


def hora_local(iso):
    """'05/11/2026 10:15' no fuso da clínica."""
    t = de_iso(iso)
    return t.astimezone(_FUSO).strftime("%d/%m/%Y %H:%M") if t else ""


def horas_desde(iso):
    t = de_iso(iso)
    if not t:
        return 1e9
    return (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 3600


DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def data_extenso(iso):
    """'Quinta-feira, 05 de novembro de 2026'"""
    if not iso:
        return ""
    d = datetime.date.fromisoformat(str(iso)[:10])
    return f"{DIAS_SEMANA[d.weekday()].capitalize()}, {d.day:02d} de {MESES[d.month - 1]} de {d.year}"
