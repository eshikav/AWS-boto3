import boto3
import json
import sys

class checkPublicS3Buckets():

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

  def getBuckets(self):
    client = boto3.client('s3',
                           aws_access_key_id=self.credentials['access_key'],
                           aws_secret_access_key=self.credentials['secret_key'],
                           aws_session_token=self.credentials['session_token'])

    return list(bucket for bucket in client.list_buckets()['Buckets'])

  def getPublicBuckets(self):
    bucketlist = self.getBuckets()
    public_buckets = dict()
    client = boto3.client('s3',
                          aws_access_key_id=self.credentials['access_key'],
                          aws_secret_access_key=self.credentials['secret_key'],
                          aws_session_token=self.credentials['session_token'])
 
    for bucket in bucketlist:
      acl=client.get_bucket_acl(Bucket=bucket['Name'])
      permissions=(list(type['Permission'] for type in acl['Grants'] if type['Grantee']['Type']\
                     == 'Group' and "AllUsers" in type['Grantee']['URI'] ))
      if len(permissions) != 0:
        public_buckets[bucket['Name']] = permissions
    return public_buckets

  def checkPublicS3Buckets(self):
    publicbuckets = self.getPublicBuckets()
    result = True
    failReason = ""
    offenders = []
    control = "x.x"
    description = "Ensure there are no buckets exposed publicly"
    ignoredresources = 0
    scannedresources = 0
    ignored = []
    scored = True
    counter = 0
    for bucket in publicbuckets:
      if bucket not in self.rule_properties['IgnoreResourceList']: 
        counter += 1
        offenders.append({bucket: publicbuckets[bucket]})
        result = False
        failReason = "There are "+str(counter)+" buckets which are exposed publicly"
      else:
        if bucket in self.rule_properties['IgnoreResourceList']:
          ignored.append({bucket: publicbuckets[bucket]})
          ignoredresources += 1
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control, 'IgnoredResources': ignoredresources,"ScannedResources": scannedresources,"ignored": ignored }
