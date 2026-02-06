"""Observability policies component - MeshAccessLog, MeshMetric, MeshTrace."""

from typing import Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class ObservabilityPolicies(ComponentResource):
    """Creates MeshAccessLog, MeshMetric, and MeshTrace policies."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:ObservabilityPolicies", name, None, opts)

        # MeshAccessLog - structured JSON logging to stdout
        self.access_log = k8s.apiextensions.CustomResource(
            f"{name}-access-log",
            api_version="kuma.io/v1alpha1",
            kind="MeshAccessLog",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="mesh-access-log",
                namespace=config.kuma_namespace,
                labels={
                    "kuma.io/mesh": config.mesh_name,
                    "kuma.io/origin": "zone",
                },
            ),
            spec={
                "targetRef": {
                    "kind": "Mesh",
                },
                "to": [
                    {
                        "targetRef": {
                            "kind": "Mesh",
                        },
                        "default": {
                            "backends": [
                                {
                                    "type": "File",
                                    "file": {
                                        "path": "/dev/stdout",
                                        "format": {
                                            "type": "Json" if config.logging_format == "json" else "Plain",
                                            "json": [
                                                {"key": "start_time", "value": "%START_TIME%"},
                                                {"key": "method", "value": "%REQ(:METHOD)%"},
                                                {"key": "path", "value": "%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%"},
                                                {"key": "protocol", "value": "%PROTOCOL%"},
                                                {"key": "response_code", "value": "%RESPONSE_CODE%"},
                                                {"key": "response_flags", "value": "%RESPONSE_FLAGS%"},
                                                {"key": "bytes_received", "value": "%BYTES_RECEIVED%"},
                                                {"key": "bytes_sent", "value": "%BYTES_SENT%"},
                                                {"key": "duration", "value": "%DURATION%"},
                                                {"key": "upstream_service", "value": "%UPSTREAM_CLUSTER%"},
                                                {"key": "upstream_host", "value": "%UPSTREAM_HOST%"},
                                                {"key": "request_id", "value": "%REQ(X-REQUEST-ID)%"},
                                            ] if config.logging_format == "json" else None,
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
            opts=ResourceOptions(parent=self, provider=k8s_provider),
        )

        # MeshMetric - Prometheus endpoint exposure
        self.mesh_metric = k8s.apiextensions.CustomResource(
            f"{name}-mesh-metric",
            api_version="kuma.io/v1alpha1",
            kind="MeshMetric",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="mesh-prometheus-metrics",
                namespace=config.kuma_namespace,
                labels={
                    "kuma.io/mesh": config.mesh_name,
                    "kuma.io/origin": "zone",
                },
            ),
            spec={
                "targetRef": {
                    "kind": "Mesh",
                },
                "default": {
                    "backends": [
                        {
                            "type": "Prometheus",
                            "prometheus": {
                                "port": config.prometheus_port,
                                "path": "/metrics",
                                "tls": {
                                    "mode": "Disabled",
                                },
                            },
                        }
                    ],
                },
            },
            opts=ResourceOptions(parent=self, provider=k8s_provider),
        )

        # MeshTrace - tracing backend (Jaeger or Datadog)
        trace_backends = []
        if config.tracing_backend == "jaeger":
            trace_backends.append({
                "type": "Zipkin",
                "zipkin": {
                    "url": "http://jaeger-collector.observability.svc.cluster.local:9411/api/v2/spans",
                    "traceId128bit": True,
                    "apiVersion": "httpJsonV1",
                    "sharedSpanContext": True,
                },
            })
        elif config.tracing_backend == "datadog":
            trace_backends.append({
                "type": "Datadog",
                "datadog": {
                    "url": f"http://{config.datadog_agent_address or 'datadog-agent.datadog.svc.cluster.local:8126'}",
                    "splitService": True,
                },
            })

        self.mesh_trace = k8s.apiextensions.CustomResource(
            f"{name}-mesh-trace",
            api_version="kuma.io/v1alpha1",
            kind="MeshTrace",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="mesh-trace",
                namespace=config.kuma_namespace,
                labels={
                    "kuma.io/mesh": config.mesh_name,
                    "kuma.io/origin": "zone",
                },
            ),
            spec={
                "targetRef": {
                    "kind": "Mesh",
                },
                "default": {
                    "backends": trace_backends,
                    "sampling": {
                        "overall": int(config.trace_sample_rate * 100),
                    },
                },
            },
            opts=ResourceOptions(parent=self, provider=k8s_provider),
        )

        self.register_outputs(
            {
                "access_log_name": self.access_log.metadata.name,
                "mesh_metric_name": self.mesh_metric.metadata.name,
                "mesh_trace_name": self.mesh_trace.metadata.name,
                "tracing_backend": config.tracing_backend,
                "sample_rate": config.trace_sample_rate,
            }
        )
