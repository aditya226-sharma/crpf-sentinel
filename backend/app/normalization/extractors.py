"""Format → field-extraction registry for the normalization engine.

Each parser exposes a static ``extract_fields(event) -> dict`` returning the
common-schema field set. The engine dispatches through this registry, so all
formats normalize through the same code path.
"""

from typing import Callable

from app.parsers.base import ParsedEvent

# Registered lazily on first use so parser modules can import engine modules.
_EXTRACTORS: dict[str, Callable[[ParsedEvent], dict]] = {}


def _load() -> dict[str, Callable[[ParsedEvent], dict]]:
    from app.parsers import ParserRegistry
    from app.parsers.case_record import CaseRecordParser
    from app.parsers.ipsec import IPsecParser
    from app.parsers.netflow import NetFlowParser
    from app.parsers.osint_record import OSINTRecordParser
    from app.parsers.syslog import SyslogParser
    from app.parsers.windows import WindowsEventParser

    _EXTRACTORS.clear()
    for parser in (
        WindowsEventParser, SyslogParser, NetFlowParser, IPsecParser,
        CaseRecordParser, OSINTRecordParser,
    ):
        _EXTRACTORS[parser.format_name] = parser.extract_fields
    for name in ParserRegistry.all():
        parser_cls = type(ParserRegistry.get(name))
        _EXTRACTORS.setdefault(name, parser_cls.extract_fields)
    return _EXTRACTORS


EXTRACTORS = _load()