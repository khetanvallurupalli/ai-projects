"""Kuma service mesh deployment via Helm with default Mesh CRD."""

import pulumi
import pulumi_kubernetes as k8s


class KumaMesh(pulumi.ComponentResource):
    """Deploys Kuma control plane via Helm and creates a default Mesh with mTLS."""

    namespace: pulumi.Output[str]

    def __init__(
        self,
        name: str,
        kuma_version: str,
        k8s_provider: k8s.Provider,
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__("custom:infrastructure:KumaMesh", name, {}, opts)

        child_opts = pulumi.ResourceOptions(parent=self, provider=k8s_provider)

        # Kuma namespace
        kuma_ns = k8s.core.v1.Namespace(
            f"{name}-namespace",
            metadata={
                "name": "kuma-system",
            },
            opts=child_opts,
        )
        self.namespace = kuma_ns.metadata.apply(lambda m: m.name)

        # Kuma Helm release
        kuma_release = k8s.helm.v3.Release(
            f"{name}-helm",
            chart="kuma",
            version=kuma_version,
            namespace="kuma-system",
            repository_opts={
                "repo": "https://kumahq.github.io/charts",
            },
            values={
                "controlPlane": {
                    "mode": "standalone",
                },
                "cni": {
                    "enabled": True,
                    "chained": True,
                },
            },
            opts=pulumi.ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[kuma_ns],
            ),
        )

        # Default Mesh CRD with mTLS enabled (builtin CA)
        k8s.apiextensions.CustomResource(
            f"{name}-default-mesh",
            api_version="kuma.io/v1alpha1",
            kind="Mesh",
            metadata={
                "name": "default",
            },
            spec={
                "mtls": {
                    "enabledBackend": "ca-1",
                    "backends": [
                        {
                            "name": "ca-1",
                            "type": "builtin",
                        }
                    ],
                },
            },
            opts=pulumi.ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[kuma_release],
            ),
        )

        # Create confluent namespace with Kuma sidecar injection
        k8s.core.v1.Namespace(
            f"{name}-confluent-namespace",
            metadata={
                "name": "confluent",
                "labels": {
                    "kuma.io/sidecar-injection": "enabled",
                },
            },
            opts=pulumi.ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[kuma_release],
            ),
        )

        self.register_outputs({"namespace": self.namespace})
