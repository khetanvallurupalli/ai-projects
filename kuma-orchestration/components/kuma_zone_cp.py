"""Kuma Zone Control Plane component for multi-cluster deployments."""

from typing import Optional

import pulumi
import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions, Output

from config import KumaConfig, ClusterConfig, KumaMode


class KumaZoneControlPlane(ComponentResource):
    """Deploys Kuma zone control plane that connects to global CP."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        cluster_config: ClusterConfig,
        k8s_provider: k8s.Provider,
        global_address: Optional[Output[str]] = None,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:KumaZoneControlPlane", name, None, opts)

        self.cluster_config = cluster_config
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

        # Determine the global address to connect to
        kds_global_address = ""
        if config.mode == KumaMode.ZONE and global_address:
            kds_global_address = global_address
        elif config.global_cp.external_address:
            kds_global_address = f"grpcs://{config.global_cp.external_address}:{config.global_cp.external_port}"

        # Build Helm values for zone mode
        helm_values = {
            "controlPlane": {
                "mode": "zone",
                "zone": cluster_config.zone_name,
                "environment": "kubernetes",
                "kdsGlobalAddress": kds_global_address,
                "tls": {
                    "general": {
                        "secretName": "",
                    },
                    "kdsZoneClient": {
                        "secretName": "",
                        "create": config.global_cp.kds_tls_enabled,
                    },
                },
                "resources": {
                    "requests": {
                        "cpu": "250m",
                        "memory": "256Mi",
                    },
                    "limits": {
                        "cpu": "500m",
                        "memory": "512Mi",
                    },
                },
            },
            "ingress": {
                "enabled": cluster_config.zone_ingress_enabled,
            },
            "egress": {
                "enabled": cluster_config.zone_egress_enabled,
            },
            "cni": {
                "enabled": True,
            },
        }

        # Add cloud-specific settings
        if cluster_config.type.value == "aks" or cluster_config.type.value == "aks-local":
            # Azure-specific CNI settings
            helm_values["cni"]["containerSecurityContext"] = {
                "privileged": True,
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

        # Only create Mesh if this is standalone mode (zone mode gets Mesh from global)
        self.mesh = None
        if config.mode == KumaMode.STANDALONE:
            mesh_spec = {}
            if config.mtls_enabled:
                mesh_spec["mtls"] = {
                    "enabledBackend": config.mtls_backend,
                    "backends": [
                        {
                            "name": config.mtls_backend,
                            "type": "builtin" if config.mtls_backend == "builtin" else "provided",
                        }
                    ],
                }

            self.mesh = k8s.apiextensions.CustomResource(
                f"{name}-mesh",
                api_version="kuma.io/v1alpha1",
                kind="Mesh",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=config.mesh_name,
                ),
                spec=mesh_spec,
                opts=ResourceOptions(
                    parent=self,
                    provider=k8s_provider,
                    depends_on=[self.helm_release],
                ),
            )

        self.register_outputs({
            "namespace": self.namespace.metadata.name,
            "zone_name": cluster_config.zone_name,
            "mesh_name": config.mesh_name,
            "cluster_type": cluster_config.type.value,
        })


class MultiZoneDeployment(ComponentResource):
    """Deploys Kuma across multiple zones/clusters."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        cluster_providers: dict,  # Dict[str, ClusterProvider]
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:MultiZoneDeployment", name, None, opts)

        self.zone_control_planes = {}
        self.global_control_plane = None

        # First, deploy global control plane on the designated cluster
        global_cluster = config.get_global_cp_cluster()
        if global_cluster and global_cluster.name in cluster_providers:
            from .kuma_global_cp import KumaGlobalControlPlane

            global_provider = cluster_providers[global_cluster.name]
            self.global_control_plane = KumaGlobalControlPlane(
                f"{name}-global-cp",
                config,
                global_provider.k8s_provider,
                opts=ResourceOptions(parent=self),
            )

        # Then deploy zone control planes on each zone cluster
        for cluster in config.get_zone_clusters():
            if cluster.name not in cluster_providers:
                pulumi.log.warn(f"No provider found for cluster {cluster.name}, skipping")
                continue

            provider = cluster_providers[cluster.name]

            # Get global address for zone to connect to
            global_address = None
            if self.global_control_plane:
                global_address = self.global_control_plane.global_address

            zone_cp = KumaZoneControlPlane(
                f"{name}-zone-{cluster.zone_name}",
                config,
                cluster,
                provider.k8s_provider,
                global_address=global_address,
                opts=ResourceOptions(
                    parent=self,
                    depends_on=[self.global_control_plane] if self.global_control_plane else [],
                ),
            )
            self.zone_control_planes[cluster.name] = zone_cp

        self.register_outputs({
            "global_cp_cluster": global_cluster.name if global_cluster else None,
            "zone_count": len(self.zone_control_planes),
            "zone_names": list(self.zone_control_planes.keys()),
        })
