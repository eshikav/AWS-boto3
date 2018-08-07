import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
from dateutil.tz import tzutc
import json

class checkUnderUtilizedNetworkInstances():
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
    if len(rule_properties['RuleProperties'][0]['Filters'][0]['Region']) == 0:
      client = boto3.client('ec2',
                             aws_access_key_id=credentials['access_key'],
                             aws_secret_access_key=credentials['secret_key'],
                             aws_session_token=credentials['session_token'])
      self.regions = list(region['RegionName'] for region in client.describe_regions()['Regions'])
    else:
      self.regions = rule_properties['RuleProperties'][0]['Filters'][0]['Region']
    self.ignorefilters = rule_properties['RuleProperties'][0]['IgnoreFilters']

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
  getActiveInstances gets all the active instances which are part of a specified region as per the constructor

  Arguments:
  It doesnot takes any arguments

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the instances which are active in the particular region.
  '''
  def getActiveInstances(self):
    try:
      instances = collections.defaultdict(list)
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in self.regions:
        client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        if ( not self.ignorefilters ) and len(includeresources.keys()) != 0:
          instances[region] = []
          for tag in includeresources.keys():
            filter={"Name": "tag:"+tag,"Values": includeresources[tag]}
            for instance in client.describe_instances(Filters=[filter])['Reservations']:
              if (instance['Instances'][0]['State']['Name'] == 'running'\
                 and instance['Instances'][0] ['InstanceId'] not in list(instance['Instances'][0]['InstanceId'] for instance in instances[region])):
                 instances[region].append(instance)
        else:
          for instance in client.describe_instances()['Reservations']:
            if instance['Instances'][0]['State']['Name'] == 'running':
              instances[region].append(instance)
      return instances
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  filter method will filter the resources based on the exclude tag list which is specified in the rule_properties object

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the instances which are active in the particular region
  after the exclusion
  '''
  def filter(self):
    try:
      resources = self.getActiveInstances()
      object = self.getActiveInstances()
      excluderesources = self.rule_properties['Filters'][0]['ExcludeResourcesWithTagEquals']
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in object.keys():
        count = 0
        for index,resource in enumerate(object[region]):
          if "Tags" in resource['Instances'][0].keys():
            for resourcetag in resource['Instances'][0]['Tags']:
              for tag in excluderesources.keys():
                if tag == resourcetag['Key'] and resourcetag['Value'] in excluderesources[tag]:
                  if len(resources[region]) != 0 and resources[region][index-count]['Instances'][0]['InstanceId'] == resource['Instances'][0]['InstanceId']:
                    x=resources[region].pop(index-count)
                    count += 1
      return resources
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  getInstanceNetworkUtilization gets the cpu utilizations of the instances

  Arguments:
  It doesnot expects any arguments

  Return:
  It returns a defaultdict object which contains the region as keys and the list of instances which are active in a particular region along with their
  average cpuutilization
  '''
  def getInstanceNetworkUtilization(self):
    try:
      if ( not self.ignorefilters ):
        instances = self.filter()
      else:
        instances = self.getActiveInstances()
      for region in instances.keys():
        for index,instance in enumerate(instances[region]):
          dimensions=[
                    {
                      'Name': 'InstanceId',
                      'Value': instance['Instances'][0]['InstanceId']
                    }
                    ]
          StartTime=datetime.utcnow() - timedelta(hours=5)
          seconds_in_one_day =  86400# used for granularity
          cloudwatch = boto3.client('cloudwatch',
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
          response = cloudwatch.get_metric_statistics(
          Namespace='AWS/EC2',
          Dimensions=dimensions,
          MetricName='NetworkPacketsOut',
          StartTime=StartTime,
          EndTime=datetime.utcnow(),
          Period=seconds_in_one_day,
          Statistics=[
                     'Average'
                    ],
          )
          if len(response['Datapoints']) != 0:
            instances[region][index]['network_utilization'] = self.getAverageDatapoints(response['Datapoints'])
          else:
            instances[region][index]['network_utilization'] = 0
      return instances
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  getAverageDatapoints calculates the average of all the datapoints which are requested from the getInstanceNetworkUtilization

  Arguments:
  It doesnot expects any argument

  Return:
  It returns the average of the datapoints.
  '''
  def getAverageDatapoints(self,datapoints):
    try:
      datapointcount=len(datapoints)
      average = 0
      for datapoint in datapoints:
        average += datapoint['Average']
      return average / datapointcount
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  mark, marks all the instances with the timestamp. A mark is basically a tag to the resource with key as Mark and value as the timestamp.

  Arguments:
  It doesnot expets any arguments

  Return:
  It doesnot have any return objects
  '''
  def mark(self):
    try:
      instances = self.getInstanceNetworkUtilization()
      for region in instances.keys():
        mark_tag = [{
                   'Key': 'Mark',
                   'Value': datetime.now(tzutc()).isoformat(),
                   }]
        client = boto3.resource('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        for instance in instances[region]:
          if instance['Instances'][0]['InstanceId'] not in self.rule_properties['IgnoreResourceList']:
            if (instance['network_utilization'] < 10 and 'Tags' in instance['Instances'][0].keys() and 'Mark' in list(tag['Key'] for tag in instance['Instances'][0]['Tags'])):
              pass
            else:
              client.Instance(instance['Instances'][0]['InstanceId']).create_tags(Tags=mark_tag)
    except Exception as e:
      return self.returnFailjson(str(e)) 

  '''
  Description:
  It takes action on the instances which deviates from a specific condition and takes an action as specified in the rule_properties.

  Arguments:
  It doesnot expects any arguments

  Return:
  It doesnot returns anything
  '''
  def sweep(self):
    try:
      instances = self.getInstanceNetworkUtilization()
      for region in instances.keys():
        client = boto3.resource('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        for instance in instances[region] :
          if instance['Instances'][0]['InstanceId'] not in self.rule_properties['IgnoreResourceList']:
            if ('Tags' in instance['Instances'][0].keys() and 'Mark' in list(tag['Key'] for tag in instance['Instances'][0]['Tags'])):
              client.Instance(instance['Instances'][0]['InstanceId']).terminate()
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  checkUnderUtilizedNetworkInstances reports all the instances which deviates from a specific rule.

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contains the information of the failed instances.
  '''
  def checkUnderUtilizedNetworkInstances(self): 
    try:
      instances = self.getInstanceNetworkUtilization()
      result = True
      failReason = ""
      offenders = []
      control = "x.x"
      description = "Ensure there are no instances that are idle Network utilisation"
      scored = True
      counter = 0
      scannedresources = sum(list(len(instances[region]) for region in instances.keys()))
      ignoredresources = 0
      for region in instances.keys():
        for instance in instances[region]:
          if instance['Instances'][0]['InstanceId'] not in self.rule_properties['IgnoreResourceList']:
            if instance['network_utilization'] > 10:
              counter += 1
              offenders.append(dict({'region': region,'id': instance['Instances'][0]['InstanceId']}))
            else:
              pass
          else:
            ignoredresources += 1
      if counter != 0:
        failReason = "Account has "+str(counter)+" low Network utilization"
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources}
    except Exception as e:
      return self.returnFailjson(str(e))
