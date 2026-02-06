"""Observability stack component - Prometheus and Jaeger Helm releases."""

from typing import Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class ObservabilityStack(ComponentResource):
    """Deploys Prometheus and Jaeger for observability."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:ObservabilityStack", name, None, opts)

        # Create observability namespace
        self.namespace = k8s.core.v1.Namespace(
            f"{name}-namespace",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="observability",
                labels={
                    "kuma.io/sidecar-injection": "disabled",
                },
            ),
            opts=ResourceOptions(parent=self, provider=k8s_provider),
        )

        # Deploy Prometheus with Kuma scrape config
        self.prometheus = k8s.helm.v3.Release(
            f"{name}-prometheus",
            chart="prometheus",
            version="25.8.0",
            namespace="observability",
            repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                repo="https://prometheus-community.github.io/helm-charts",
            ),
            values={
                "alertmanager": {
                    "enabled": False,
                },
                "prometheus-pushgateway": {
                    "enabled": False,
                },
                "server": {
                    "global": {
                        "scrape_interval": "15s",
                        "evaluation_interval": "15s",
                    },
                    "persistentVolume": {
                        "enabled": True,
                        "size": "10Gi",
                    },
                },
                "serverFiles": {
                    "prometheus.yml": {
                        "scrape_configs": [
                            {
                                "job_name": "kuma-dataplanes",
                                "scrape_interval": "15s",
                                "relabel_configs": [
                                    {
                                        "source_labels": ["__meta_kuma_mesh"],
                                        "regex": "(.*)",
                                        "target_label": "mesh",
                                    },
                                    {
                                        "source_labels": ["__meta_kuma_dataplane"],
                                        "regex": "(.*)",
                                        "target_label": "dataplane",
                                    },
                                    {
                                        "source_labels": ["__meta_kuma_service"],
                                        "regex": "(.*)",
                                        "target_label": "service",
                                    },
                                ],
                                "kuma_sd_configs": [
                                    {
                                        "server": f"http://kuma-control-plane.{config.kuma_namespace}.svc.cluster.local:5676",
                                    }
                                ],
                            },
                            {
                                "job_name": "kuma-control-plane",
                                "scrape_interval": "15s",
                                "static_configs": [
                                    {
                                        "targets": [
                                            f"kuma-control-plane.{config.kuma_namespace}.svc.cluster.local:5680"
                                        ],
                                    }
                                ],
                            },
                        ],
                    },
                },
            },
            opts=ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[self.namespace],
            ),
        )

        # Deploy Jaeger (only if tracing backend is jaeger)
        self.jaeger = None
        if config.tracing_backend == "jaeger":
            # Use all-in-one for dev, production config for prod
            is_dev = config.environment == "dev"

            jaeger_values = {
                "provisionDataStore": {
                    "cassandra": False,
                    "elasticsearch": not is_dev,
                },
                "allInOne": {
                    "enabled": is_dev,
                    "image": {
                        "tag": "1.53.0",
                    },
                    "resources": {
                        "limits": {
                            "cpu": "500m",
                            "memory": "512Mi",
                        },
                        "requests": {
                            "cpu": "256m",
                            "memory": "256Mi",
                        },
                    },
                },
                "collector": {
                    "enabled": not is_dev,
                    "replicaCount": 2 if not is_dev else 1,
                },
                "query": {
                    "enabled": not is_dev,
                    "replicaCount": 2 if not is_dev else 1,
                },
                "agent": {
                    "enabled": True,
                },
                "storage": {
                    "type": "memory" if is_dev else "elasticsearch",
                },
            }

            if not is_dev:
                jaeger_values["elasticsearch"] = {
                    "client": {
                        "replicas": 1,
                    },
                    "master": {
                        "replicas": 3,
                    },
                    "data": {
                        "replicas": 2,
                    },
                }

            self.jaeger = k8s.helm.v3.Release(
                f"{name}-jaeger",
                chart="jaeger",
                version="2.0.0",
                namespace="observability",
                repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                    repo="https://jaegertracing.github.io/helm-charts",
                ),
                values=jaeger_values,
                opts=ResourceOptions(
                    parent=self,
                    provider=k8s_provider,
                    depends_on=[self.namespace],
                ),
            )

        self.register_outputs(
            {
                "namespace": self.namespace.metadata.name,
                "prometheus_installed": True,
                "jaeger_installed": config.tracing_backend == "jaeger",
            }
        )
