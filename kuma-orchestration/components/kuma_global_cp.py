"""Kuma Global Control Plane component for multi-cluster deployments."""

from typing import Optional

import pulumi
import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions, Output

from config import KumaConfig, KumaMode


class KumaGlobalControlPlane(ComponentResource):
    """Deploys Kuma global control plane via Helm for multi-zone federation."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:KumaGlobalControlPlane", name, None, opts)

        # Validate this is appropriate for global mode
        if config.mode not in [KumaMode.GLOBAL, KumaMode.STANDALONE]:
            pulumi.log.warn(f"KumaGlobalControlPlane created but mode is {config.mode.value}")

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

        # Build Helm values for global mode
        helm_values = {
            "controlPlane": {
                "mode": "global",
                "replicas": config.global_cp.replicas,
                "environment": "kubernetes",
                "tls": {
                    "general": {
                        "secretName": "",
                    },
                    "kdsGlobalServer": {
                        "secretName": "",
                        "create": config.global_cp.kds_tls_enabled,
                    },
                },
                "resources": {
                    "requests": {
                        "cpu": "500m",
                        "memory": "512Mi",
                    },
                    "limits": {
                        "cpu": "1000m",
                        "memory": "1024Mi",
                    },
                },
            },
            "globalZoneSyncService": {
                "enabled": True,
                "type": config.global_cp.zone_sync_service_type,
                "port": config.global_cp.kds_port,
                "annotations": {},
            },
            "ingress": {
                "enabled": True,
            },
            "egress": {
                "enabled": True,
            },
        }

        # Add external address if configured
        if config.global_cp.external_address:
            helm_values["globalZoneSyncService"]["annotations"]["external-dns.alpha.kubernetes.io/hostname"] = config.global_cp.external_address

        # Deploy Kuma via Helm in global mode
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

        # Create default Mesh CRD with mTLS and cross-cluster settings
        mesh_spec = {}

        if config.mtls_enabled:
            mesh_spec["mtls"] = {
                "enabledBackend": config.mtls_backend,
                "backends": [
                    {
                        "name": config.mtls_backend,
                        "type": "builtin" if config.mtls_backend == "builtin" else "provided",
                        "dpCert": {
                            "rotation": {
                                "expiration": f"{config.cross_cluster.cert_validity_days * 24}h",
                            },
                        },
                    }
                ],
            }

        # Configure networking for multi-zone
        mesh_spec["networking"] = {
            "outbound": {
                "passthrough": config.cross_cluster.passthrough_mode == "all",
            },
        }

        # Configure routing for multi-zone
        mesh_spec["routing"] = {
            "zoneEgress": True,
            "localityAwareLoadBalancing": config.cross_cluster.locality_aware_lb_enabled,
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

        # Get the global zone sync service address
        self.global_zone_sync_service = k8s.core.v1.Service.get(
            f"{name}-zone-sync-service",
            pulumi.Output.concat(config.kuma_namespace, "/kuma-global-zone-sync"),
            opts=ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[self.helm_release],
            ),
        )

        # Export the global address for zone control planes
        if config.global_cp.external_address:
            self.global_address = Output.from_input(
                f"grpcs://{config.global_cp.external_address}:{config.global_cp.external_port}"
            )
        else:
            self.global_address = self.global_zone_sync_service.status.apply(
                lambda status: f"grpcs://{status.load_balancer.ingress[0].hostname or status.load_balancer.ingress[0].ip}:{config.global_cp.kds_port}"
                if status and status.load_balancer and status.load_balancer.ingress
                else f"grpcs://kuma-global-zone-sync.{config.kuma_namespace}.svc.cluster.local:{config.global_cp.kds_port}"
            )

        self.register_outputs({
            "namespace": self.namespace.metadata.name,
            "mesh_name": config.mesh_name,
            "global_address": self.global_address,
            "replicas": config.global_cp.replicas,
        })
