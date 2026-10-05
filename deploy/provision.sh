#!/usr/bin/env bash
# Create (or find) every AWS resource of the Meal Tracker in eu-west-1.
# Run from the PC in Git Bash with the AWS CLI configured as mealtrack-deploy:
#   MY_IP=93.56.157.84 bash deploy/provision.sh
# Idempotent: existing resources are reused. Expected cost (2026-10, from
# memory): t3a.micro ~6.9 $/month, 12 GB gp3 ~1.2 $, public IPv4 ~3.7 $, S3 cents.
set -euo pipefail

REGION=${REGION:-eu-west-1}
NAME=mealtrack
DOMAIN=${DOMAIN:-meal.verenovotech.com}
ZONE_NAME=${ZONE_NAME:-verenovotech.com.}
INSTANCE_TYPE=${INSTANCE_TYPE:-t3a.micro}
DISK_GB=${DISK_GB:-12}
EMAIL=${EMAIL:-afguida@gmail.com}
BUDGET_USD=${BUDGET_USD:-15}
MY_IP=${MY_IP:?set MY_IP to your public IPv4 for the SSH rule}
KEY_FILE="$HOME/.ssh/$NAME.pem"
HERE="$(cd "$(dirname "$0")" && pwd)"

export AWS_DEFAULT_REGION=$REGION
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET=$NAME-$ACCOUNT
echo "account $ACCOUNT, region $REGION, bucket $BUCKET, domain $DOMAIN"

# --- key pair ---------------------------------------------------------------
if ! aws ec2 describe-key-pairs --key-names $NAME >/dev/null 2>&1; then
  mkdir -p "$HOME/.ssh"
  aws ec2 create-key-pair --key-name $NAME --key-type ed25519 --query KeyMaterial --output text > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  echo "key pair created: $KEY_FILE"
else
  echo "key pair exists ($KEY_FILE must be the matching private key)"
fi

# --- security group ---------------------------------------------------------
VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query "Vpcs[0].VpcId" --output text)
SG=$(aws ec2 describe-security-groups --filters Name=group-name,Values=$NAME Name=vpc-id,Values=$VPC --query "SecurityGroups[0].GroupId" --output text)
if [ "$SG" = "None" ]; then
  SG=$(aws ec2 create-security-group --group-name $NAME --description "Meal Tracker web" --vpc-id $VPC --query GroupId --output text)
  aws ec2 authorize-security-group-ingress --group-id $SG --ip-permissions \
    'IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0}]' \
    'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0}]' \
    "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$MY_IP/32,Description=ssh-from-home}]" >/dev/null
  echo "security group created: $SG"
else
  echo "security group exists: $SG"
fi

# --- S3 bucket: versioning, no public access, lifecycle ---------------------
if ! aws s3api head-bucket --bucket $BUCKET 2>/dev/null; then
  aws s3api create-bucket --bucket $BUCKET --create-bucket-configuration LocationConstraint=$REGION >/dev/null
  echo "bucket created: $BUCKET"
fi
aws s3api put-public-access-block --bucket $BUCKET --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket $BUCKET --versioning-configuration Status=Enabled
aws s3api put-bucket-lifecycle-configuration --bucket $BUCKET --lifecycle-configuration "file://$HERE/s3-lifecycle.json"

# --- IAM role for the instance (that bucket only) ---------------------------
ROLE=$NAME-instance
if ! aws iam get-role --role-name $ROLE >/dev/null 2>&1; then
  aws iam create-role --role-name $ROLE --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  echo "role created: $ROLE"
fi
sed "s/176146985576/$ACCOUNT/g" "$HERE/iam-instance-policy.json" > /tmp/$NAME-policy.json
aws iam put-role-policy --role-name $ROLE --policy-name $NAME-s3 --policy-document file:///tmp/$NAME-policy.json
if ! aws iam get-instance-profile --instance-profile-name $ROLE >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name $ROLE >/dev/null
  aws iam add-role-to-instance-profile --instance-profile-name $ROLE --role-name $ROLE
  echo "instance profile created; waiting for IAM to propagate"; sleep 12
fi

# --- instance ----------------------------------------------------------------
INSTANCE=$(aws ec2 describe-instances --filters Name=tag:Name,Values=$NAME Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query "Reservations[0].Instances[0].InstanceId" --output text)
if [ "$INSTANCE" = "None" ]; then
  AMI=$(aws ssm get-parameters --names /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query "Parameters[0].Value" --output text)
  INSTANCE=$(aws ec2 run-instances --image-id $AMI --instance-type $INSTANCE_TYPE --key-name $NAME \
    --security-group-ids $SG --iam-instance-profile Name=$ROLE --user-data "file://$HERE/user-data.sh" \
    --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":$DISK_GB,\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}]" \
    --metadata-options HttpTokens=required \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" "ResourceType=volume,Tags=[{Key=Name,Value=$NAME}]" \
    --query "Instances[0].InstanceId" --output text)
  echo "instance launched: $INSTANCE ($INSTANCE_TYPE, $AMI); waiting until running"
  aws ec2 wait instance-running --instance-ids $INSTANCE
else
  echo "instance exists: $INSTANCE"
fi

# --- fixed IP ----------------------------------------------------------------
ALLOC=$(aws ec2 describe-addresses --filters Name=tag:Name,Values=$NAME --query "Addresses[0].AllocationId" --output text)
if [ "$ALLOC" = "None" ]; then
  ALLOC=$(aws ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$NAME}]" --query AllocationId --output text)
  echo "elastic IP allocated: $ALLOC"
fi
IP=$(aws ec2 describe-addresses --allocation-ids $ALLOC --query "Addresses[0].PublicIp" --output text)
ASSOC=$(aws ec2 describe-addresses --allocation-ids $ALLOC --query "Addresses[0].InstanceId" --output text)
if [ "$ASSOC" != "$INSTANCE" ]; then
  aws ec2 associate-address --allocation-id $ALLOC --instance-id $INSTANCE >/dev/null
fi
echo "public IP: $IP"

# --- DNS ----------------------------------------------------------------------
ZONE=$(aws route53 list-hosted-zones-by-name --dns-name "$ZONE_NAME" --query "HostedZones[0].Id" --output text)
aws route53 change-resource-record-sets --hosted-zone-id "$ZONE" --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"$DOMAIN\",\"Type\":\"A\",\"TTL\":300,\"ResourceRecords\":[{\"Value\":\"$IP\"}]}}]}" >/dev/null
echo "DNS: $DOMAIN -> $IP"

# --- budget alert (free): email when spend passes 80 % actual or 100 % forecast
if ! aws budgets describe-budget --account-id $ACCOUNT --budget-name $NAME-monthly >/dev/null 2>&1; then
  aws budgets create-budget --account-id $ACCOUNT \
    --budget "{\"BudgetName\":\"$NAME-monthly\",\"BudgetLimit\":{\"Amount\":\"$BUDGET_USD\",\"Unit\":\"USD\"},\"TimeUnit\":\"MONTHLY\",\"BudgetType\":\"COST\"}" \
    --notifications-with-subscribers "[{\"Notification\":{\"NotificationType\":\"ACTUAL\",\"ComparisonOperator\":\"GREATER_THAN\",\"Threshold\":80,\"ThresholdType\":\"PERCENTAGE\"},\"Subscribers\":[{\"SubscriptionType\":\"EMAIL\",\"Address\":\"$EMAIL\"}]},{\"Notification\":{\"NotificationType\":\"FORECASTED\",\"ComparisonOperator\":\"GREATER_THAN\",\"Threshold\":100,\"ThresholdType\":\"PERCENTAGE\"},\"Subscribers\":[{\"SubscriptionType\":\"EMAIL\",\"Address\":\"$EMAIL\"}]}]"
  echo "budget alert created: $BUDGET_USD USD/month -> $EMAIL"
else
  echo "budget alert exists"
fi

echo
echo "next: ssh -i $KEY_FILE ubuntu@$IP   (after a minute or two of first boot)"
