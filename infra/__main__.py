"""Main entrypoint: wires VPC → EKS → Add-ons → Kuma → CFK → Connectors."""

import pulumi

from config import load_config
from components import VpcLookup, EksCluster, EksAddons, KumaMesh, CfkPlatform, create_connector
from components.connectors import S3_SINK_CONNECTOR, DEBEZIUM_SOURCE_CONNECTOR

# --- Auto-tagging transformation ---
cfg = load_config()


def auto_tag(args: pulumi.ResourceTransformationArgs):
    """Apply standard tags to all AWS resources that support tags."""
    if args.type_.startswith("aws:"):
        props = args.props
        tags = props.get("tags", {})
        if tags is None:
            tags = {}
        tags["Environment"] = cfg.environment
        tags["ManagedBy"] = "pulumi"
        tags["Project"] = "eks-kuma-cfk"
        props["tags"] = tags
        return pulumi.ResourceTransformationResult(props, args.opts)
    return None


pulumi.runtime.register_stack_transformation(auto_tag)

# --- 1. VPC (existing) ---
vpc = VpcLookup(
    "main",
    vpc_id=cfg.vpc_id,
    public_subnet_ids=cfg.public_subnet_ids,
    private_subnet_ids=cfg.private_subnet_ids,
)

# --- 2. EKS Cluster ---
eks_cluster = EksCluster(
    "main",
    vpc_id=vpc.vpc_id,
    private_subnet_ids=vpc.private_subnet_ids,
    public_subnet_ids=vpc.public_subnet_ids,
    cluster_name=cfg.eks_cluster_name,
    eks_version=cfg.eks_version,
    node_instance_types=cfg.node_instance_types,
    node_desired_size=cfg.node_desired_size,
    node_min_size=cfg.node_min_size,
    node_max_size=cfg.node_max_size,
    public_access=cfg.eks_public_access,
    opts=pulumi.ResourceOptions(depends_on=[vpc]),
)

# --- 3. EKS Add-ons ---
addons = EksAddons(
    "main",
    cluster_name=eks_cluster.cluster_name,
    oidc_provider_arn=eks_cluster.oidc_provider_arn,
    oidc_issuer=eks_cluster.oidc_issuer,
    eks_version=cfg.eks_version,
    opts=pulumi.ResourceOptions(depends_on=[eks_cluster]),
)

# --- 4. Kuma Service Mesh ---
kuma = KumaMesh(
    "main",
    kuma_version=cfg.kuma_version,
    k8s_provider=eks_cluster.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[addons]),
)

# --- 5. CFK Platform (Operator + Connect) ---
cfk = CfkPlatform(
    "main",
    cfk_version=cfg.cfk_version,
    environment=cfg.environment,
    confluent_cloud_bootstrap=cfg.confluent_cloud_bootstrap,
    confluent_cloud_api_key=cfg.confluent_cloud_api_key,
    confluent_cloud_api_secret=cfg.confluent_cloud_api_secret,
    k8s_provider=eks_cluster.k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[kuma]),
)

# --- 6. Connectors ---
s3_sink = create_connector(
    **S3_SINK_CONNECTOR,
    k8s_provider=eks_cluster.k8s_provider,
    depends_on=[cfk],
    parent=cfk,
)

debezium_source = create_connector(
    **DEBEZIUM_SOURCE_CONNECTOR,
    k8s_provider=eks_cluster.k8s_provider,
    depends_on=[cfk],
    parent=cfk,
)

# --- Exports ---
pulumi.export("vpc_id", vpc.vpc_id)
pulumi.export("cluster_name", eks_cluster.cluster_name)
pulumi.export("cluster_endpoint", eks_cluster.cluster_endpoint)
pulumi.export("kubeconfig", pulumi.Output.secret(eks_cluster.kubeconfig))
