import boto3
import collections
from time import gmtime, strftime
from datetime import datetime
import json

class checkInactiveVolumes:
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
    print json.dumps(message,indent=3)


  '''
  Description:
  getInactiveVolumes gets all the active instances which are part of a specified region as per the constructor

  Arguments:
  It doesnot takes any arguments

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the volumes which are inactive in the particular region.
  '''
  def getInactiveVolumes(self):
    try:
      volumes = collections.defaultdict(list)
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
              if (volume['State'] == 'available'\
                and volume['VolumeId'] not in list(volume['VolumeId'] for volume in volumes[region])):
                volumes[region].append(volume)
        else:
          for volume in client.describe_volumes()['Volumes']:
            if volume['State'] == 'available':
              volumes[region].append(volume)
      return volumes
    except Exception as e:
      returnFailjson(str(e))

  '''
  Description:
  filter method will filter the resources based on the exclude tag list which is specified in the rule_properties object

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the volumes  which are in-active in the particular region
  after the exclusion
  '''
  def filter(self):
    try:
      resources = self.getInactiveVolumes()
      object = self.getInactiveVolumes()
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
      returnFailjson(str(e))

  '''
  Description:
  calInactiveTime, calculates the volume Inactive time

  Arguments:
  It doesnot expects any arguments

  Return:
  It returns the inactive time of the volume
  '''
  def calInactiveTime(self,fmt,previous_time):
    try:
      present_time = strftime(fmt,gmtime())
      return datetime.strptime(present_time,fmt) - datetime.strptime(previous_time,fmt)
    except:
      returnFailjson(str(e))

  '''
  Description:
  calInactiveTime, calculates the volume Inactive time

  Arguments:
  It doesnot expects any arguments

  Return:
  It returns the defaultdict object which contains the regions as the keys and the list of the volumes  which are in-active in the particular region
  along with the Inactivetime from the calInactiveTime method
  '''
  def getInactiveTime(self):
    try:
      if ( not self.ignorefilters ):
        volumes = self.filter()
      else:
        volumes = self.getInactiveVolumes()
      inactive_volumes = collections.defaultdict(dict)
      fmt = "%a, %d %b %Y %H:%M:%S"
      for region in volumes.keys():
        mark_tag = [{
                'Key': 'Mark',
                'Value': strftime(fmt,gmtime()),
                }]
        client = boto3.resource('ec2',region)
        for volume in volumes[region]:
          if 'Tags' in volume.keys() and 'Mark' in list(tag['Key'] for tag in volume['Tags']):
            tags = volume['Tags']
            for tag in volume['Tags']:
              if tag['Key'] == "Mark":
                inactive_volumes[volume['VolumeId']]['region'] = region
                inactive_volumes[volume['VolumeId']]['idle_time'] = self.calInactiveTime(fmt,tag['Value'])
      return inactive_volumes
    except Exception as e:
      returnFailjson(str(e))

  '''
  Description:
  mark, marks all the in-active volumes with a timestamp. A mark is basically a tag to the resource with key as Mark and value as the timestamp.

  Arguments:
  It doesnot expets any arguments

  Return:
  It doesnot have any return objects
  '''
  def mark(self):
    try:
      volumes=self.getInactiveVolumes()
      fmt = "%a, %d %b %Y %H:%M:%S"
      for region in volumes.keys():
        mark_tag = [{
                'Key': 'Mark',
                'Value': strftime(fmt,gmtime()),
                }]
        client = boto3.resource('ec2',region)
        for volume in volumes[region]:
          if 'Tags' in volume.keys() and 'Mark' in list(tag['Key'] for tag in volume['Tags']): 
            pass
          else:
            client.Volume(volume['VolumeId']).create_tags(Tags=mark_tag)
    except Exception as e:
      returnFailjson(str(e)) 

  '''
  Description:
  It takes action on the inactive volumes specified in the rule_properties.

  Arguments:
  It doesnot expects any arguments

  Return:
  It doesnot returns anything
  '''
  def sweep(self):
    try:
      ideal_volume_time = self.getInactiveTime()
      for volume in ideal_volume_time.keys():
        if ideal_volume_time[volume]['idle_time'].days > 3:
          client = boto3.resource('ec2',ideal_volume_time[volume]['region'])
          client.Volume(volume).delete()  
        else:
          pass
    except Exception as e:
      returnFailjson(str(e))

  '''
  Description:
  checkInactiveVolumes reports all the instances which deviates from a specific rule.

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contains the information of the failed volumes
  '''
  def checkInactiveVolumes(self):
    try:
      result = True
      failReason = ""
      offenders = []
      control = "x.x"
      description = "Ensure there are no inactive volumes"
      scored = True
      counter = 0
      ignored = []
      ignoredresources = 0
      if ( not self.ignorefilters ):
        volumes = self.filter()
      else:
        volumes = self.getInactiveVolumes()
      for region in volumes.keys():
        for volume in volumes[region]:
          if volume['VolumeId'] not in self.rule_properties['IgnoreResourceList']: 
            counter += 1
            offenders.append(dict({'region': region,'id': volume['VolumeId']}))
          else:
             ignoredresources += 1
             ignored.append(dict({'region': region,'id': volume['VolumeId']}))
      if counter != 0:
        failReason = "Account has "+str(counter)+" inactive volumes"
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter, "Ignoredresources": ignoredresources,"Ignored": ignored}
    except Exception as e:
      returnFailjson(str(e))
