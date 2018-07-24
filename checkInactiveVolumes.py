import boto3
import collections
from time import gmtime, strftime
from datetime import datetime
import json

class checkInactiveVolumes:
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

  def getInactiveVolumes(self):
    volumes = collections.defaultdict(list)
    for region in self.regions:
      client = boto3.client('ec2',region)
      for volume in client.describe_volumes()['Volumes']:
        if volume['State'] == 'available':
          volumes[region].append(volume)
    return volumes

  def calInactiveTime(self,fmt,previous_time):
    present_time = strftime(fmt,gmtime())
    return datetime.strptime(present_time,fmt) - datetime.strptime(previous_time,fmt)

  def getInactiveTime(self):
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

  def mark(self):
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
   
  def sweep(self):
    ideal_volume_time = self.getInactiveTime()
    for volume in ideal_volume_time.keys():
      if ideal_volume_time[volume]['idle_time'].days > 3:
        client = boto3.resource('ec2',ideal_volume_time[volume]['region'])
        client.Volume(volume).delete()  
      else:
        pass

  def checkInactiveVolumes(self):
    result = True
    failReason = ""
    offenders = []
    control = "x.x"
    description = "Ensure there are no inactive volumes"
    scored = True
    counter = 0
    volumes=self.getInactiveVolumes()
    for region in volumes.keys():
      for volume in volumes[region]:
        counter += 1
        offenders.append(dict({'region': region,'id': volume['VolumeId']}))
    if counter != 0:
      failReason = "Account has "+str(counter)+" inactive volumes"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter}
