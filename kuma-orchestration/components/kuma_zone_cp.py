"""Kuma Zone Control Plane component."""

from typing import Optional

import pulumi
import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class KumaZoneControlPlane(ComponentResource):
    """Deploys Kuma zone control plane that connects to global CP."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:KumaZoneControlPlane", name, None, opts)

        child_opts = ResourceOptions(parent=self, provider=k8s_provider)

        # Create namespace for Kuma if not exists
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

        # Build Helm values for zone mode
        helm_values = {
            "controlPlane": {
                "mode": "zone",
                "zone": config.kuma_zone_name,
                "environment": "kubernetes",
                "kdsGlobalAddress": config.kuma_global_address or "",
            },
            "ingress": {
                "enabled": True,
            },
            "egress": {
                "enabled": True,
            },
            "cni": {
                "enabled": True,
            },
        }

        # Deploy Kuma via Helm in zone mode
        self.helm_release = k8s.helm.v3.Release(
            f"{name}-helm",
            chart="kuma",
            version=config.kuma_version,
            namespace=config.kuma_namespace,
            repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                repo="https://kumahq.github.io/charts",
            ),
            values=helm_values,
            opts=ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[self.namespace],
            ),
        )

        # Create Mesh CRD with mTLS (for zone)
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
                "zone_name": config.kuma_zone_name,
                "mesh_name": config.mesh_name,
            }
        )
