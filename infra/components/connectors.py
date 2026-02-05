"""Connector CRD factory and sample connector definitions."""

from typing import Any, Dict, List

import pulumi
import pulumi_kubernetes as k8s


def create_connector(
    name: str,
    connector_class: str,
    tasks_max: int,
    config: Dict[str, Any],
    connect_cluster_ref: str = "kafka-connect",
    namespace: str = "confluent",
    k8s_provider: k8s.Provider = None,
    depends_on: List[pulumi.Resource] = None,
    parent: pulumi.Resource = None,
) -> k8s.apiextensions.CustomResource:
    """Create a Confluent Connector CRD.

    Args:
        name: Unique name for the connector resource.
        connector_class: Fully-qualified connector Java class.
        tasks_max: Maximum number of tasks.
        config: Connector-specific configuration dict.
        connect_cluster_ref: Name of the Connect cluster CR.
        namespace: Kubernetes namespace.
        k8s_provider: Kubernetes provider.
        depends_on: Resources this connector depends on.
        parent: Parent resource.

    Returns:
        The created CustomResource.
    """
    connector_config = {
        "connector.class": connector_class,
        "tasks.max": str(tasks_max),
        **{k: str(v) for k, v in config.items()},
    }

    return k8s.apiextensions.CustomResource(
        name,
        api_version="platform.confluent.io/v1beta1",
        kind="Connector",
        metadata={
            "name": name,
            "namespace": namespace,
        },
        spec={
            "name": name,
            "class": connector_class,
            "taskMax": tasks_max,
            "connectClusterRef": {
                "name": connect_cluster_ref,
            },
            "configs": connector_config,
        },
        opts=pulumi.ResourceOptions(
            parent=parent,
            provider=k8s_provider,
            depends_on=depends_on or [],
        ),
    )


# --- Sample connector definitions ---

S3_SINK_CONNECTOR = {
    "name": "s3-sink",
    "connector_class": "io.confluent.connect.s3.S3SinkConnector",
    "tasks_max": 1,
    "config": {
        "topics": "my-topic",
        "s3.region": "us-east-1",
        "s3.bucket.name": "my-data-lake-bucket",
        "flush.size": "1000",
        "storage.class": "io.confluent.connect.s3.storage.S3Storage",
        "format.class": "io.confluent.connect.s3.format.parquet.ParquetFormat",
        "parquet.codec": "snappy",
        "schema.compatibility": "NONE",
        "behavior.on.null.values": "ignore",
    },
}

DEBEZIUM_SOURCE_CONNECTOR = {
    "name": "debezium-source",
    "connector_class": "io.debezium.connector.postgresql.PostgresConnector",
    "tasks_max": 1,
    "config": {
        "database.hostname": "placeholder-db-host",
        "database.port": "5432",
        "database.user": "placeholder-user",
        "database.password": "${file:/mnt/secrets/db-credentials:password}",
        "database.dbname": "mydb",
        "database.server.name": "mydb-server",
        "table.include.list": "public.orders,public.customers",
        "plugin.name": "pgoutput",
        "slot.name": "debezium_slot",
        "publication.name": "debezium_pub",
    },
}
