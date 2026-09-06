"""Parser registry — add a new log format by implementing BaseParser.

Discovery is convention-based: every module in this package that exports a
``BaseParser`` subclass is registered on import. The registry is the single
dispatch point of the universal pre-processing framework: a new format means a
new parser module — nothing else in the pipeline changes.
"""

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING

from app.parsers.base import BaseParser, ParsedEvent

if TYPE_CHECKING:
    from app.parsers.case_record import CaseRecordParser
    from app.parsers.ipsec import IPsecParser
    from app.parsers.netflow import NetFlowParser
    from app.parsers.syslog import SyslogParser
    from app.parsers.windows import WindowsEventParser


class ParserRegistry:
    _parsers: dict[str, BaseParser] = {}

    @classmethod
    def register(cls, parser: BaseParser) -> None:
        cls._parsers[parser.format_name] = parser

    @classmethod
    def get(cls, format_name: str) -> BaseParser:
        parser = cls._parsers.get(format_name)
        if parser is None:
            raise ValueError(f"Unsupported log format: {format_name}")
        return parser

    @classmethod
    def all(cls) -> list[str]:
        return list(cls._parsers.keys())


def _discover() -> None:
    """Import every parser module and register its BaseParser subclasses."""
    package = "app.parsers"
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is BaseParser or not issubclass(obj, BaseParser):
                continue
            if getattr(obj, "format_name", "base") == "base":
                continue
            if obj.format_name not in ParserRegistry._parsers:
                ParserRegistry.register(obj())


_discover()