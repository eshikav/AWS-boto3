import boto3
import json
import sys

class checkNoUnEncryptedBucket:
  def __init__(self,rule_properties,credentials):
    self.rule_properties = rule_properties["RuleProperties"][0]
    self.credentials = credentials
    if len(rule_properties['RuleProperties'][0]['regions']) == 0:
      client = boto3.client('ec2',
                             aws_access_key_id=credentials['access_key'],
                             aws_secret_access_key=credentials['secret_key'],
                             aws_session_token=credentials['session_token'])
      self.regions = list(region['RegionName'] for region in client.describe_regions()['Regions'])
    else:
      self.regions = rule_properties['RuleProperties'][0]['regions']

  def checkNoUnEncryptedBucket(self):
    client = boto3.client('s3',
                           aws_access_key_id=self.credentials['access_key'],
                           aws_secret_access_key=self.credentials['secret_key'],
                           aws_session_token=self.credentials['session_token'])
    buckets =  list(bucket['Name'] for bucket in client.list_buckets()['Buckets'])
    scannedresources = len(buckets)
    ignoredresources = 0
    result = True
    failReason = ""
    offenders = []
    control = "x.x"
    description = "Ensure there are no buckets without  SSE/KMS encryption"
    scored = True
    ignored= []
    counter = 0
    for bucket in buckets:
      if bucket not in self.rule_properties['IgnoreResourceList']: 
        try:
          resource=client.get_bucket_encryption(Bucket=bucket)
        except Exception as e:
          if "encryption configuration was not found" in str(e):
            counter += 1
            offenders.append(bucket)
      else:
        if bucket in self.rule_properties['IgnoreResourceList'] :
          ignoredresources += 1 
          ignored.append(bucket)
    if counter != 0:   
      failReason = "There are "+str(counter)+" buckets without  SSE/KMS encryption"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources,'ignored': ignored}

