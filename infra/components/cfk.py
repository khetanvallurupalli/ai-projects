"""Confluent for Kubernetes (CFK) operator, credentials, and Connect cluster."""

import pulumi
import pulumi_kubernetes as k8s


class CfkPlatform(pulumi.ComponentResource):
    """Deploys CFK operator via Helm, creates Confluent Cloud credentials secret,
    and a Kafka Connect cluster CR pointing to external Confluent Cloud."""

    connect_name: pulumi.Output[str]

    def __init__(
        self,
        name: str,
        cfk_version: str,
        environment: str,
        confluent_cloud_bootstrap: str,
        confluent_cloud_api_key: pulumi.Input[str],
        confluent_cloud_api_secret: pulumi.Input[str],
        k8s_provider: k8s.Provider,
        opts: pulumi.ResourceOptions = None,
    ):
        super().__init__("custom:infrastructure:CfkPlatform", name, {}, opts)

        child_opts = pulumi.ResourceOptions(parent=self, provider=k8s_provider)

        # CFK Operator Helm release
        cfk_release = k8s.helm.v3.Release(
            f"{name}-operator",
            chart="confluent-for-kubernetes",
            version=cfk_version,
            namespace="confluent",
            repository_opts={
                "repo": "https://packages.confluent.io/helm",
            },
            values={
                "namespaced": False,
            },
            opts=child_opts,
        )

        # Confluent Cloud SASL/PLAIN credentials secret
        cc_credentials = k8s.core.v1.Secret(
            f"{name}-cc-credentials",
            metadata={
                "name": "confluent-cloud-credentials",
                "namespace": "confluent",
            },
            type="Opaque",
            string_data={
                "plain.txt": pulumi.Output.all(
                    confluent_cloud_api_key, confluent_cloud_api_secret
                ).apply(
                    lambda args: f"username={args[0]}\npassword={args[1]}"
                ),
            },
            opts=pulumi.ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[cfk_release],
            ),
        )

        # Connect replicas: 1 for dev, 2 for prod
        connect_replicas = 1 if environment == "dev" else 2

        # Kafka Connect cluster CR
        connect_cr = k8s.apiextensions.CustomResource(
            f"{name}-connect",
            api_version="platform.confluent.io/v1beta1",
            kind="Connect",
            metadata={
                "name": "kafka-connect",
                "namespace": "confluent",
                "annotations": {
                    "kuma.io/sidecar-injection": "enabled",
                },
            },
            spec={
                "replicas": connect_replicas,
                "image": {
                    "application": "confluentinc/cp-server-connect:7.7.1",
                    "init": "confluentinc/confluent-init-container:2.9.3",
                },
                "dependencies": {
                    "kafka": {
                        "bootstrapEndpoint": confluent_cloud_bootstrap,
                        "authentication": {
                            "type": "plain",
                            "jaasConfig": {
                                "secretRef": "confluent-cloud-credentials",
                            },
                        },
                        "tls": {
                            "enabled": True,
                        },
                    },
                },
            },
            opts=pulumi.ResourceOptions(
                parent=self,
                provider=k8s_provider,
                depends_on=[cfk_release, cc_credentials],
            ),
        )

        self.connect_name = connect_cr.metadata.apply(lambda m: m["name"])

        self.register_outputs({"connect_name": self.connect_name})
