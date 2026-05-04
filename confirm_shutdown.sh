#!/usr/bin/env bash
# confirm_shutdown.sh — checks that all demo AWS infrastructure has been torn down

set -euo pipefail

echo ""
echo "Assuming AWS credentials (eu-west-3)..."
eval "$(GRANTED_ALIAS_INSTALLED=true assume --region eu-west-3)" || {
  echo "ERROR: 'assume --region eu-west-3' failed."
  exit 1
}

REGION="eu-west-3"
TAG_KEY="Name"
TAG_VALUE="RedhatSummitEDADemo*"
FOUND=0

echo ""
echo "  Checking eu-west-3 for RedhatSummitEDADemo resources..."
echo ""

# EC2 instances (any state except terminated)
INSTANCES=$(aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:$TAG_KEY,Values=$TAG_VALUE" \
            "Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down" \
  --query 'Reservations[].Instances[].[Tags[?Key==`Name`]|[0].Value,InstanceId,State.Name]' \
  --output text)

COUNT=$(echo "$INSTANCES" | grep -c '\S' || true)
if [ "$COUNT" -gt 0 ]; then
  echo "  [!] EC2 instances — $COUNT still exist:"
  echo "$INSTANCES" | while IFS=$'\t' read -r name id state; do
    echo "        $name  ($id, $state)"
  done
  FOUND=$((FOUND + COUNT))
else
  echo "  [✓] EC2 instances — none found"
fi

# Elastic IPs
EIPS=$(aws ec2 describe-addresses --region "$REGION" \
  --filters "Name=tag:$TAG_KEY,Values=$TAG_VALUE" \
  --query 'Addresses[].[Tags[?Key==`Name`]|[0].Value,PublicIp,AllocationId]' \
  --output text)

COUNT=$(echo "$EIPS" | grep -c '\S' || true)
if [ "$COUNT" -gt 0 ]; then
  echo "  [!] Elastic IPs — $COUNT still exist:"
  echo "$EIPS" | while IFS=$'\t' read -r name ip alloc; do
    echo "        $name  ($ip)"
  done
  FOUND=$((FOUND + COUNT))
else
  echo "  [✓] Elastic IPs — none found"
fi

# Security groups
SGS=$(aws ec2 describe-security-groups --region "$REGION" \
  --filters "Name=tag:$TAG_KEY,Values=$TAG_VALUE" \
  --query 'SecurityGroups[].[Tags[?Key==`Name`]|[0].Value,GroupId]' \
  --output text)

COUNT=$(echo "$SGS" | grep -c '\S' || true)
if [ "$COUNT" -gt 0 ]; then
  echo "  [!] Security groups — $COUNT still exist:"
  echo "$SGS" | while IFS=$'\t' read -r name id; do
    echo "        $name  ($id)"
  done
  FOUND=$((FOUND + COUNT))
else
  echo "  [✓] Security groups — none found"
fi

# Key pairs
KEYS=$(aws ec2 describe-key-pairs --region "$REGION" \
  --filters "Name=tag:$TAG_KEY,Values=$TAG_VALUE" \
  --query 'KeyPairs[].[Tags[?Key==`Name`]|[0].Value,KeyName,KeyPairId]' \
  --output text)

COUNT=$(echo "$KEYS" | grep -c '\S' || true)
if [ "$COUNT" -gt 0 ]; then
  echo "  [!] Key pairs — $COUNT still exist:"
  echo "$KEYS" | while IFS=$'\t' read -r name keyname id; do
    echo "        $keyname  ($id)"
  done
  FOUND=$((FOUND + COUNT))
else
  echo "  [✓] Key pairs — none found"
fi

echo ""
if [ "$FOUND" -eq 0 ]; then
  echo "  All demo infrastructure is torn down. Nothing running in eu-west-3."
else
  echo "  $FOUND resource(s) still present. Run ./teardown_infra.sh to remove them."
fi
echo ""
