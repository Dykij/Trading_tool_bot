from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Set, TextIO, Union, Protocol, Iterator, Type, overload
import os
import sys
from io import StringIO

class StreamWrapper(Protocol):
    def write(self, text: str) -> int: ...
    def flush(self) -> None: ...
    def isatty(self) -> bool: ...

class TerminalWriter:
    def __init__(
        self, file: Optional[Union[TextIO, StreamWrapper]] = None, stringio: bool = False
    ) -> None: ...

    @property
    def fullwidth(self) -> int: ...

    @property
    def chars_on_current_line(self) -> int: ...

    @property
    def file(self) -> Optional[Union[TextIO, StreamWrapper]]: ...

    @file.setter
    def file(self, file: Optional[Union[TextIO, StreamWrapper]]) -> None: ...

    def _write_source(self, lines: List[str], indents: List[str] = None) -> None: ...

    def write(
        self,
        msg: Union[str, bytes, Any],
        *args: Any,
        **kwargs: Any
    ) -> None: ...

    def line(self, s: str = "") -> None: ...

    def sep(
        self,
        sepchar: str,
        title: Optional[str] = None,
        fullwidth: Optional[int] = None,
        **kw: Any
    ) -> None: ...

    def flush(self) -> None: ...

    def width_of_current_line(self) -> int: ...

    def markup(
        self, 
        text: Union[str, bytes, Any], 
        **kw: Any
    ) -> str: ... 