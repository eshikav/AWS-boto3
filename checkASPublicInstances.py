import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

class checkASPublicInstances():
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

  def getASInstances(self):
    instances = collections.defaultdict(list)
    for region in self.regions:
      client = boto3.client('autoscaling',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
      for instance in client.describe_auto_scaling_instances()['AutoScalingInstances']:
        instances[region].append(instance)
    return instances

  def checkASPublicInstances(self): 
    instances = self.getASInstances()
    result = True
    failReason = ""
    offenders = []
    control = "x.x"
    description = "Ensure there are no instances with public IP's"
    scored = True
    counter = 0
    scannedresources = sum(list(len(instances[region]) for region in instances.keys()))
    ignoredresources = 0
    for region in instances.keys():
      for instance in instances[region]:
        ec2_client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        instance_details = ec2_client.describe_instances(Filters=[{'Name': 'instance-id','Values': [instance['InstanceId']]}])
        if instance['AutoScalingGroupName'] not in  self.rule_properties['IgnoreResourceList']:
          if "PublicIpAddress" in instance_details['Reservations'][0]['Instances'][0].keys():
            counter += 1
            offenders.append(dict({'region': region,'id': instance['InstanceId']}))
          else:
            pass
        else:
          ignoredresources += 1
    if counter != 0:
      failReason = "Account has "+str(counter)+" instances with public ips"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources}
