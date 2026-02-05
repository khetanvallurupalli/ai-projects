# EKS + Kuma + CFK Infrastructure

Pulumi (Python) project that provisions EKS clusters across multi-account AWS (dev + prod), deploys Kuma service mesh, installs CFK operator with Kafka Connect pointing to external Confluent Cloud, and manages connector CRDs.

## Project Structure

```
bootstrap/          One-time S3 state bucket setup (use local backend)
infra/              Main infrastructure project
  __main__.py       Entrypoint - wires all components in dependency order
  config.py         Typed dataclass config loader from Pulumi config
  components/
    vpc.py          Lookup existing VPC + subnets by ID
    eks_cluster.py  EKS cluster + node groups + OIDC + K8s provider
    irsa.py         IAM Roles for Service Accounts helper
    eks_addons.py   CoreDNS, kube-proxy, VPC CNI, EBS CSI
    kuma.py         Kuma control plane (Helm) + default Mesh CRD
    cfk.py          CFK operator (Helm) + Connect cluster CR
    connectors.py   Connector CRD factory + sample definitions
.github/workflows/
  infra-preview.yml   Pulumi preview on PRs
  infra-deploy.yml    Pulumi up on merge (dev then prod)
```

## Commands

```bash
# Bootstrap (one-time)
cd bootstrap
pulumi login --local
pulumi stack init dev
pulumi up --stack dev

# Infrastructure preview
cd infra
pulumi login s3://<bucket-name>
pulumi preview --stack dev

# Infrastructure deploy
pulumi up --stack dev
pulumi up --stack prod
```

## Setting Secrets

```bash
cd infra
pulumi config set --secret confluentCloudApiKey <value> --stack dev
pulumi config set --secret confluentCloudApiSecret <value> --stack dev
```

## Adding a New Connector

1. Define a new connector config dict in `infra/components/connectors.py`:
   ```python
   MY_NEW_CONNECTOR = {
       "name": "my-connector",
       "connector_class": "com.example.MyConnector",
       "tasks_max": 1,
       "config": {
           "key": "value",
       },
   }
   ```

2. Instantiate it in `infra/__main__.py`:
   ```python
   from components.connectors import MY_NEW_CONNECTOR

   my_connector = create_connector(
       **MY_NEW_CONNECTOR,
       k8s_provider=eks_cluster.k8s_provider,
       depends_on=[cfk],
       parent=cfk,
   )
   ```

## Environments

| Setting | Dev | Prod |
|---------|-----|------|
| Instance type | t3.large | m5.xlarge |
| Node desired/min/max | 2/1/5 | 3/3/10 |
| Public endpoint | Enabled | Disabled |
| Connect replicas | 1 | 2 |

## CI/CD

- **PRs**: `infra-preview.yml` runs `pulumi preview` and comments on the PR
- **Merge to main**: `infra-deploy.yml` deploys dev first, then prod (with GitHub Environment approval gate)
- AWS auth via OIDC (no long-lived credentials)
- Pulumi state stored in S3 with `PULUMI_CONFIG_PASSPHRASE` for secret encryption

## Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `PULUMI_CONFIG_PASSPHRASE` | Passphrase for Pulumi secret encryption |
| `PULUMI_STATE_BUCKET` | S3 bucket name for state backend |
| `AWS_DEV_ROLE_ARN` | IAM role ARN for dev account (OIDC) |
| `AWS_PROD_ROLE_ARN` | IAM role ARN for prod account (OIDC) |

## Key Patterns

- Every module is a `ComponentResource` with `parent=self` on children
- K8s provider created from EKS kubeconfig and passed explicitly
- VPC is not created — existing VPC and subnet IDs are provided via config
- `depends_on` chains: VpcLookup → EKS → Add-ons → Kuma → CFK → Connectors
- Auto-tagging transformation applies Environment/ManagedBy/Project to all AWS resources
