import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
import json

class checkUnderUtilizedIopsVolumes:
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
    self.ignorefilters = rule_properties['RuleProperties'][0]['IgnoreFilters']

  '''
  Description:
  returnFailjson returns a json object if there

  Arguments:
  it takes the failmessage as the argument

  Return:
  json object which contains the failed message
  '''
  def returnFailjson(self,failmessage):
    message={
          "failed": True,
          "reason": failmessage
          }
    return message

  '''
  Description:
  getActiveProvisionedVolumes gets the active volumes( which are in use and type io) and returns 

  Arguments: 
  it doesnot takes any arguments
 
  Return:
  defaultdict object which contains all the active volumes in a specified region or all the regions
  if none of the regions are mentioned
  '''
  def getActiveProvisionedVolumes(self):
    try:
      volumes = collections.defaultdict(list) # for storing the volumes per region
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in self.regions:
        client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        if ( not self.ignorefilters ) and len(includeresources.keys()) != 0:
          volumes[region] = []
          for tag in includeresources.keys():
            filter={"Name": "tag:"+tag,"Values": includeresources[tag]}
            for volume in client.describe_volumes(Filters=[filter])['Volumes']:
              if (volume['State'] == 'in-use' and volume['VolumeType'] == 'io1'\
               and volume['VolumeId'] not in list(volume['VolumeId'] for volume in volumes[region])):
               volumes[region].append(volume)
        else: 
          for volume in client.describe_volumes()['Volumes']:
            if volume['State'] == 'in-use' and volume['VolumeType'] == 'io1':
              volumes[region].append(volume)
      return volumes
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  Filters the resourses based on the exclude list specified in the rule_properties, inclusion of the 
  resources are part of the getActiveProvisionedVolumes function.

  Arguments:
  It doesnot expects any arguments
  
  Return:
  default dict object which contains the resource list after the removal of the resources based on the
  exclude tags
  '''
  def filter(self):
    try:
      resources = self.getActiveProvisionedVolumes()
      object = self.getActiveProvisionedVolumes()
      excluderesources = self.rule_properties['Filters'][0]['ExcludeResourcesWithTagEquals']
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in object.keys():
        count = 0
        for index,resource in enumerate(object[region]):
          if "Tags" in resource.keys():
            for resourcetag in resource['Tags']:
              for tag in excluderesources.keys():
                if tag == resourcetag['Key'] and resourcetag['Value'] in excluderesources[tag]:
                  if len(resources[region]) != 0 and resources[region][index-count]['VolumeId'] == resource['VolumeId']:
                    x=resources[region].pop(index-count)
                    count += 1
      return resources
    except Exception as e:
      return self.returnFailjson(str(e)) 

  '''
  Description:
  Calculate the average of all the datapoints that are gathered from the metrics using the checkUnderUtilizedIopsVolumes

  Arguments:
  It doesnot expects any arguments

  Return:
  returns the average of the metrics of a specified resource.
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
  Checks and reports all the objects which are underutilized than a threshold IOPS value.

  Arguments:
  It doesnot expects any arguments

  Return:
  returns the json with the failure and success also contains the details like which resources have failed and what regions
  they belong to
  '''
  def checkUnderUtilizedIopsVolumes(self): 
    try:
      if ( not self.ignorefilters ):
        volumes = self.filter()
      else:
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
        failReason = "Account has "+str(counter)+" iops provisioned disks which are being underutilized"
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources,'ignored': ignored}
    except Exception as e:
      return self.returnFailjson(str(e))
