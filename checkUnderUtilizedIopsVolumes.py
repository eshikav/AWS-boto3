import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
import json

class checkUnderUtilizedIopsVolumes:

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

  def getActiveProvisionedVolumes(self):
    volumes = collections.defaultdict(list)
    for region in self.regions:
      client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])

      for volume in client.describe_volumes()['Volumes']:
        if volume['State'] == 'in-use' and volume['VolumeType'] == 'io1':
          volumes[region].append(volume)
    return volumes

  def getAverageDatapoints(self,datapoints):
    datapointcount=len(datapoints)
    average = 0
    for datapoint in datapoints:
      average += datapoint['Average']
    return average / datapointcount

  def checkUnderUtilizedIopsVolumes(self): 
    volumes = self.getActiveProvisionedVolumes()
    result = True
    failReason = ""
    scannedresources = sum(list(len(volumes[region]) for region in volumes.keys()))
    ignoredresources = 0
    ignored = []
    offenders = []
    control = "x.x"
    description = "Ensure there are no underutilised provisioned disks"
    scored = True
    counter = 0
    for region in volumes.keys():
      for volume in volumes[region]:
        if volume['VolumeId'] not in self.rule_properties['IgnoreResourceList']:
          dimensions=[
                    {
                      'Name': 'VolumeId',
                      'Value': volume['VolumeId']
                    }
                    ]
          seconds_in_one_day = 86400# used for granularity
          StartTime=datetime.now() - timedelta(days=5)
          cloudwatch = boto3.client('cloudwatch',
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
          response = cloudwatch.get_metric_statistics(
          Namespace='AWS/EBS',
          Dimensions=dimensions,
          MetricName='VolumeReadBytes',
          StartTime=StartTime,
          EndTime=datetime.now(),
          Period=seconds_in_one_day,
          Statistics=[
                     event['MetricAggregationType']
                    ],
          Unit='Bytes'
          )
          if len(response['Datapoints']) != 0: 
            if getAverageDatapoints(response['Datapoints']) < volume['Iops']:
              counter += 1
              offenders.append(dict({'region': region,'id': cluster['Id']}))
          else:
            pass
        else:
          if  volume['VolumeId'] in self.rule_properties['IgnoreResourceList']:
            ignoredresources += 1
            ignored.append(dict({'region': region,'id': cluster['Id']}))
    if counter != 0:
      failReason = "Account has "+str(counter)+" iops provisioned disks whichare being underutilized"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources,'ignored': ignored}

