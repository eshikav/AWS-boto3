import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

class checkASPublicInstances():
  '''
  Description:
  Constructor for the class, it takes the rule_properties and the credentials objects as the arguments.
  rule_properties should be aligned to a specific format. Please see the guidelines.

  Arguments:
  It takes the rule_properties and the credentials objects as the arguments.rule_properties should be aligned to a specific format. Please see the guidelines.
  If there are no regions which are defined in the rule_properties then the region would be constructed with all the regions that pertains for the specific
  user.

  Return:
  It doesnot have any return objects.
  '''
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

  '''
  Description:
  returnFailjson returns a json object if there

  Arguments:
  it takes the failmessage as the argument

  Return:
  json object which contains the failed message
  '''
  def returnFailjson(failmessage):
    message={
          "failed": True,
          "reason": failmessage
          }
    return message

  '''
  Description:
  getASInstances gets the list of the AutoScaling groups for a specified region

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the Autoscaling Groups in the particular region
  '''
  def getASInstances(self):
    try:
      instances = collections.defaultdict(list)
      for region in self.regions:
        client = boto3.client('autoscaling',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        for instance in client.describe_auto_scaling_instances()['AutoScalingInstances']:
          instances[region].append(instance)
      return instances
   except Exception as e:
     return self.returnFailjson(str(e))

  '''
  Description:
  filter excludes the resourses as specified in the rule_properties

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the Autoscaling Groups in the particular region
  after the exclusions
  '''
  def filter(self):
    try:
      resources = self.getASInstances()
      object = self.getASInstances()
      count = 0
      excluderesources = self.rule_properties['Filters'][0]['ExcludeResourcesWithTagEquals']
      for region in object.keys():
        for index,resource in enumerate( object[region]):
          if "Tags" in resource.keys():
            for resourcetag in resource['Tags']:
              for tag in excluderesources.keys():
                print resourcetag['Key'], resourcetag['Value']
                if tag == resourcetag['Key'] and resourcetag['Value'] == excluderesources[tag]:
                  x=resources[region].pop(index-count)
                  count += 1
      return resources
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  checkASPublicInstances reports all the instances with public ip addresses.

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contins information of the Instances with public ip addresses
  '''
  def checkASPublicInstances(self): 
    try:
      instances = self.filter()
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
    except Exception as e:
      return self.returnFailjson(str(e))
