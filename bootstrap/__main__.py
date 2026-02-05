"""Bootstrap: S3 bucket for Pulumi state backend."""

import pulumi
import pulumi_aws as aws

config = pulumi.Config()
environment = config.require("environment")
dev_account_id = config.require("devAccountId")
prod_account_id = config.require("prodAccountId")

bucket_name = f"pulumi-state-{environment}-{pulumi.get_stack()}"

# S3 bucket for Pulumi state
state_bucket = aws.s3.BucketV2(
    "state-bucket",
    bucket=bucket_name,
    tags={
        "Environment": environment,
        "ManagedBy": "pulumi",
        "Project": "pulumi-state-backend",
    },
)

# Enable versioning
aws.s3.BucketVersioningV2(
    "state-bucket-versioning",
    bucket=state_bucket.id,
    versioning_configuration={
        "status": "Enabled",
    },
)

# SSE-S3 encryption
aws.s3.BucketServerSideEncryptionConfigurationV2(
    "state-bucket-encryption",
    bucket=state_bucket.id,
    rules=[
        {
            "apply_server_side_encryption_by_default": {
                "sse_algorithm": "aws:kms",
            },
            "bucket_key_enabled": True,
        }
    ],
)

# Block all public access
aws.s3.BucketPublicAccessBlock(
    "state-bucket-public-access-block",
    bucket=state_bucket.id,
    block_public_acls=True,
    block_public_policy=True,
    ignore_public_acls=True,
    restrict_public_buckets=True,
)

# Bucket policy restricting access to dev and prod account roles
bucket_policy_doc = aws.iam.get_policy_document_output(
    statements=[
        {
            "sid": "AllowStateBucketAccess",
            "effect": "Allow",
            "principals": [
                {
                    "type": "AWS",
                    "identifiers": [
                        f"arn:aws:iam::{dev_account_id}:root",
                        f"arn:aws:iam::{prod_account_id}:root",
                    ],
                }
            ],
            "actions": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
            ],
            "resources": [
                state_bucket.arn,
                pulumi.Output.concat(state_bucket.arn, "/*"),
            ],
        },
    ]
)

aws.s3.BucketPolicy(
    "state-bucket-policy",
    bucket=state_bucket.id,
    policy=bucket_policy_doc.json,
)

pulumi.export("bucket_name", state_bucket.bucket)
pulumi.export("bucket_arn", state_bucket.arn)
