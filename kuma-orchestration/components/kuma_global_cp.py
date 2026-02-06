"""Kuma Global Control Plane component."""

from typing import Optional

import pulumi
import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class KumaGlobalControlPlane(ComponentResource):
    """Deploys Kuma global control plane via Helm and creates default Mesh."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:KumaGlobalControlPlane", name, None, opts)

        child_opts = ResourceOptions(parent=self, provider=k8s_provider)

        # Create namespace for Kuma
        self.namespace = k8s.core.v1.Namespace(
            f"{name}-namespace",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=config.kuma_namespace,
                labels={
                    "kuma.io/system-namespace": "true",
                },
            ),
            opts=child_opts,
        )

        # Deploy Kuma via Helm in global mode
        self.helm_release = k8s.helm.v3.Release(
            f"{name}-helm",
            chart="kuma",
            version=config.kuma_version,
            namespace=config.kuma_namespace,
            repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                repo="https://kumahq.github.io/charts",
            ),
            values={
                "controlPlane": {
                    "mode": "global",
                    "environment": "kubernetes",
                    "tls": {
                        "general": {
                            "secretName": "",
                        },
                    },
                },
                "globalZoneSyncService": {
                    "enabled": True,
                    "type": "LoadBalancer",
                    "port": 5685,
                },
                "ingress": {
                    "enabled": True,
                },
                "egress": {
                    "enabled": True,
                },
            },
            opts=ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[self.namespace],
            ),
        )

        # Create default Mesh CRD with mTLS
        mtls_config = {}
        if config.mtls_enabled:
            mtls_config = {
                "mtls": {
                    "enabledBackend": config.mtls_backend,
                    "backends": [
                        {
                            "name": config.mtls_backend,
                            "type": "builtin" if config.mtls_backend == "builtin" else "provided",
                        }
                    ],
                }
            }

        self.mesh = k8s.apiextensions.CustomResource(
            f"{name}-mesh",
            api_version="kuma.io/v1alpha1",
            kind="Mesh",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=config.mesh_name,
            ),
            spec=mtls_config,
            opts=ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[self.helm_release],
            ),
        )

        self.register_outputs(
            {
                "namespace": self.namespace.metadata.name,
                "mesh_name": config.mesh_name,
            }
        )
