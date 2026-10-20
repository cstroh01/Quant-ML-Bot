"""056 T011 / 049 T014: safe PAPER diagnostics without changing frozen research source."""
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from data_sources import AlpacaDailyBars, SourceFetchError


class DiagnosticFetchError(SourceFetchError):
    """Fixed category and bounded numeric status only; never a backend payload."""

    def __init__(self, message, *, category, http_status):
        super().__init__(message)
        self.category, self.http_status = category, http_status


def _transport_failure(source, error):
    category = next((name for kind, name in ((HTTPError, "HTTPError"), (TimeoutError, "TimeoutError"),
                                            (URLError, "URLError"), (OSError, "OSError"))
                     if isinstance(error, kind)), "TransportError")
    status = error.code if isinstance(error, HTTPError) else None
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    label = str(status) if status is not None else "unknown"
    return DiagnosticFetchError(f"{source} request failed ({category}; http_status={label})",
                                category=category, http_status=status)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _paper_transport(method, url, headers, body=None):
    with build_opener(_NoRedirect()).open(Request(url, data=body, headers=headers, method=method), timeout=30) as response:
        return response.read()


@dataclass
class DiagnosticAlpacaDailyBars(AlpacaDailyBars):
    """Keep the original request contract and digest semantics; expose safe failures."""

    transport: object = _paper_transport

    def _request(self, digest, url, headers, method="GET", body=None):
        try:
            payload = self.transport(method, url, headers, body)
        except Exception as error:
            raise _transport_failure(self.source, error) from None
        digest.update(payload)
        return payload
