"""Data e hora no fuso da clínica (o servidor na nuvem costuma estar em UTC)."""
import datetime
from zoneinfo import ZoneInfo

_FUSO = ZoneInfo("America/Sao_Paulo")


def configurar(fuso):
    global _FUSO
    _FUSO = ZoneInfo(fuso or "America/Sao_Paulo")


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
