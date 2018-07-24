import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
from dateutil.tz import tzutc
import json

class checkUnderUtilizedNetworkInstances():

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

  def getActiveInstances(self):
    instances = collections.defaultdict(list)
    for region in self.regions:
      client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
      for instance in client.describe_instances()['Reservations']:
        if instance['Instances'][0]['State']['Name'] == 'running':
          instances[region].append(instance)
    return instances

  def getInstanceNetworkUtilization(self):
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

  def getAverageDatapoints(self,datapoints):
    datapointcount=len(datapoints)
    average = 0
    for datapoint in datapoints:
      average += datapoint['Average']
    return average / datapointcount

  def mark(self):
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

  def sweep(self):
    instances = self.getInstanceNetworkUtilization()
    for region in instances.keys():
      client = boto3.resource('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
      for instance in instances[region] :
        if instance['Instances'][0]['InstanceId'] not in self.rule_properties['IgnoreResourceList']:
          if ('Tags' in instance['Instances'][0].keys() and 'Mark' in list(tag['Key'] for tag in instance['Instances'][0]['Tags'])):
            print instance['Instances'][0]['InstanceId']
            client.Instance(instance['Instances'][0]['InstanceId']).terminate()

  def checkUnderUtilizedNetworkInstances(self): 
    instances = self.getInstanceNetworkUtilization()
    result = True
    failReason = ""
    offenders = []
    control = "x.x"
    description = "Ensure there are no EMR clusters that are idle from 3 days"
    scored = True
    counter = 0
    scannedresources = sum(list(len(instances[region]) for region in instances.keys()))
    ignoredresources = 0
    for region in instances.keys():
      for instance in instances[region]:
        if instance['Instances'][0]['InstanceId'] not in self.rule_properties['IgnoreResourceList']:
          if instance['network_utilization'] < 10:
              counter += 1
              offenders.append(dict({'region': region,'id': instance['Instances'][0]['InstanceId']}))
          else:
            pass
        else:
          ignoredresources += 1
    if counter != 0:
      failReason = "Account has "+str(counter)+" low CPU utilization"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources}

