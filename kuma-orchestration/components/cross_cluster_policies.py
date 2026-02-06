"""Cross-cluster traffic policies for multi-zone Kuma deployments."""

from typing import List, Optional

import pulumi_kubernetes as k8s
from pulumi import ComponentResource, ResourceOptions

from config import KumaConfig


class CrossClusterPolicies(ComponentResource):
    """Creates policies for cross-cluster service communication with mTLS."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:CrossClusterPolicies", name, None, opts)

        if not config.is_multi_cluster() or not config.cross_cluster.enabled:
            self.register_outputs({"enabled": False})
            return

        child_opts = ResourceOptions(parent=self, provider=k8s_provider)

        # Create cross-zone traffic permission
        self.cross_zone_permission = k8s.apiextensions.CustomResource(
            f"{name}-cross-zone-traffic-permission",
            api_version="kuma.io/v1alpha1",
            kind="MeshTrafficPermission",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="cross-zone-traffic-permission",
                namespace=config.kuma_namespace,
                labels={
                    "kuma.io/mesh": config.mesh_name,
                    "kuma.io/origin": "zone",
                    "kuma.io/policy-type": "cross-cluster",
                },
            ),
            spec={
                "targetRef": {
                    "kind": "Mesh",
                },
                "from": [
                    {
                        "targetRef": {
                            "kind": "Mesh",
                        },
                        "default": {
                            "action": config.cross_cluster.cross_zone_traffic_default_action,
                        },
                    }
                ],
            },
            opts=child_opts,
        )

        # Create cross-cluster service policies for each cross-cluster service
        self.cross_cluster_permissions: List[k8s.apiextensions.CustomResource] = []
        for service in config.cross_cluster_services:
            permission = k8s.apiextensions.CustomResource(
                f"{name}-cross-cluster-permission-{service}",
                api_version="kuma.io/v1alpha1",
                kind="MeshTrafficPermission",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-cross-cluster-permission",
                    namespace=config.kuma_namespace,
                    labels={
                        "kuma.io/mesh": config.mesh_name,
                        "kuma.io/origin": "zone",
                        "kuma.io/policy-type": "cross-cluster",
                        "app": service,
                    },
                ),
                spec={
                    "targetRef": {
                        "kind": "MeshService",
                        "name": service,
                    },
                    "from": [
                        {
                            "targetRef": {
                                "kind": "Mesh",
                            },
                            "default": {
                                "action": "Allow",
                            },
                        }
                    ],
                },
                opts=child_opts,
            )
            self.cross_cluster_permissions.append(permission)

        # Create locality-aware load balancing policy if enabled
        self.locality_lb_policy = None
        if config.cross_cluster.locality_aware_lb_enabled:
            self.locality_lb_policy = k8s.apiextensions.CustomResource(
                f"{name}-locality-lb",
                api_version="kuma.io/v1alpha1",
                kind="MeshLoadBalancingStrategy",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name="locality-aware-lb",
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
                                "localityAwareness": {
                                    "disabled": False,
                                    "localZone": {
                                        "affinityTags": [
                                            {
                                                "key": "kuma.io/zone",
                                                "weight": config.cross_cluster.locality_priority_weight,
                                            }
                                        ],
                                    },
                                    "crossZone": {
                                        "failover": [
                                            {
                                                "from": {
                                                    "zones": ["*"],
                                                },
                                                "to": {
                                                    "type": "AnyZone",
                                                },
                                            }
                                        ],
                                    },
                                },
                            },
                        }
                    ],
                },
                opts=child_opts,
            )

        # Create MeshPassthrough policy for external services if configured
        self.passthrough_policy = None
        if config.cross_cluster.passthrough_mode != "none":
            passthrough_mode_map = {
                "matched": "MATCHED",
                "all": "ALL",
            }
            self.passthrough_policy = k8s.apiextensions.CustomResource(
                f"{name}-passthrough",
                api_version="kuma.io/v1alpha1",
                kind="MeshPassthrough",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name="external-passthrough",
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
                        "passthroughMode": passthrough_mode_map.get(
                            config.cross_cluster.passthrough_mode, "NONE"
                        ),
                    },
                },
                opts=child_opts,
            )

        # Create MeshHealthCheck for cross-cluster services
        self.cross_cluster_health_checks: List[k8s.apiextensions.CustomResource] = []
        for service in config.cross_cluster_services:
            health_check = k8s.apiextensions.CustomResource(
                f"{name}-health-check-{service}",
                api_version="kuma.io/v1alpha1",
                kind="MeshHealthCheck",
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name=f"{service}-cross-cluster-health-check",
                    namespace=config.kuma_namespace,
                    labels={
                        "kuma.io/mesh": config.mesh_name,
                        "kuma.io/origin": "zone",
                        "app": service,
                    },
                ),
                spec={
                    "targetRef": {
                        "kind": "MeshService",
                        "name": service,
                    },
                    "to": [
                        {
                            "targetRef": {
                                "kind": "MeshService",
                                "name": service,
                            },
                            "default": {
                                "interval": "10s",
                                "timeout": "5s",
                                "unhealthyThreshold": 3,
                                "healthyThreshold": 2,
                                "http": {
                                    "path": "/health",
                                    "expectedStatuses": [200, 204],
                                },
                            },
                        }
                    ],
                },
                opts=child_opts,
            )
            self.cross_cluster_health_checks.append(health_check)

        self.register_outputs({
            "enabled": True,
            "cross_cluster_service_count": len(config.cross_cluster_services),
            "locality_lb_enabled": config.cross_cluster.locality_aware_lb_enabled,
            "passthrough_mode": config.cross_cluster.passthrough_mode,
        })


class CrossClusterMTLS(ComponentResource):
    """Configures mTLS for cross-cluster communication."""

    def __init__(
        self,
        name: str,
        config: KumaConfig,
        k8s_provider: k8s.Provider,
        opts: Optional[ResourceOptions] = None,
    ):
        super().__init__("kuma:orchestration:CrossClusterMTLS", name, None, opts)

        if not config.is_multi_cluster():
            self.register_outputs({"enabled": False})
            return

        child_opts = ResourceOptions(parent=self, provider=k8s_provider)

        # Configure Mesh with cross-cluster mTLS settings
        mtls_backends = []
        if config.cross_cluster.ca_backend == "builtin":
            mtls_backends.append({
                "name": "builtin-ca",
                "type": "builtin",
                "dpCert": {
                    "rotation": {
                        "expiration": f"{config.cross_cluster.cert_validity_days * 24}h",
                    },
                },
            })
        elif config.cross_cluster.ca_backend == "vault":
            mtls_backends.append({
                "name": "vault-ca",
                "type": "provided",
                "conf": {
                    "cert": {
                        "secret": "vault-ca-cert",
                    },
                    "key": {
                        "secret": "vault-ca-key",
                    },
                },
            })

        self.mesh_mtls = k8s.apiextensions.CustomResource(
            f"{name}-mesh-mtls",
            api_version="kuma.io/v1alpha1",
            kind="Mesh",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=config.mesh_name,
            ),
            spec={
                "mtls": {
                    "enabledBackend": mtls_backends[0]["name"] if mtls_backends else "builtin-ca",
                    "backends": mtls_backends or [
                        {
                            "name": "builtin-ca",
                            "type": "builtin",
                        }
                    ],
                },
                "networking": {
                    "outbound": {
                        "passthrough": config.cross_cluster.passthrough_mode == "all",
                    },
                },
                "routing": {
                    "zoneEgress": True,
                    "localityAwareLoadBalancing": config.cross_cluster.locality_aware_lb_enabled,
                },
            },
            opts=child_opts,
        )

        # Create MeshTLS policy for strict mTLS mode
        mtls_mode_map = {
            "strict": "Strict",
            "permissive": "Permissive",
        }

        self.mesh_tls_policy = k8s.apiextensions.CustomResource(
            f"{name}-mesh-tls-policy",
            api_version="kuma.io/v1alpha1",
            kind="MeshTLS",
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name="cross-cluster-mtls",
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
                "from": [
                    {
                        "targetRef": {
                            "kind": "Mesh",
                        },
                        "default": {
                            "mode": mtls_mode_map.get(config.cross_cluster.mtls_mode, "Strict"),
                        },
                    }
                ],
            },
            opts=child_opts,
        )

        self.register_outputs({
            "enabled": True,
            "mtls_mode": config.cross_cluster.mtls_mode,
            "ca_backend": config.cross_cluster.ca_backend,
        })
