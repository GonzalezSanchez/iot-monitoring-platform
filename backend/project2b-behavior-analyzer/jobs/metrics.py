import os

from opentelemetry import metrics

_provider = None


def init_meter(service_name: str) -> metrics.Meter:
    """Return an OTel Meter. No-op if OTEL_EXPORTER_OTLP_ENDPOINT is not set."""
    global _provider
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if endpoint:  # pragma: no cover
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        # The HTTP exporter uses an explicit endpoint as-is — unlike the env-var
        # path, the SDK does NOT append the signal path, so add it ourselves.
        exporter = OTLPMetricExporter(endpoint=f"{endpoint.rstrip('/')}/v1/metrics")
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5_000)
        _provider = MeterProvider(metric_readers=[reader])
        metrics.set_meter_provider(_provider)

    return metrics.get_meter(service_name)


def shutdown() -> None:  # pragma: no cover
    if _provider:
        _provider.force_flush()
        _provider.shutdown()
