import boto3
import collections
from time import gmtime, strftime
from datetime import datetime
import json

client = boto3.client('ec2')
client2 = boto3.resource('ec2')
regions = list( region['RegionName'] for region in client.describe_regions()['Regions'])
def get_inactive_volumes(regions):
  volumes = collections.defaultdict(list)
  for region in regions:
     client = boto3.client('ec2',region)
     for volume in client.describe_volumes()['Volumes']:
       if volume['State'] == 'available':
         volumes[region].append(volume)
  return volumes

def cal_inactive_time(fmt,previous_time):
  present_time = strftime(fmt,gmtime())
  return datetime.strptime(present_time,fmt) - datetime.strptime(previous_time,fmt)

def get_inactive_time(volumes):
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
            inactive_volumes[volume['VolumeId']]['idle_time'] = cal_inactive_time(fmt,tag['Value'])
  return inactive_volumes


def mark_inactive_volumes(volumes):
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
    
def sweep_inactive_volumes(ideal_volume_time):
  for volume in ideal_volume_time.keys():
    if ideal_volume_time[volume]['idle_time'].days == 0:
      client = boto3.resource('ec2',ideal_volume_time[volume]['region'])
      client.Volume(volume).delete()  
    else:
      pass

def control_x_x_inactive_volumes(regions):
   result = True
   failReason = ""
   offenders = []
   control = "x.x"
   description = "Ensure there are no inactive volumes"
   scored = True
   counter = 0
   try:
      volumes=get_inactive_volumes(regions)
      for region in volumes.keys():
         for volume in volumes[region]:
             counter += 1
             offenders.append(dict({'region': region,'id': volume['VolumeId']}))
      if counter != 0:
         failReason = "Account has "+str(counter)+" inactive volumes"
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter}
   except Exception as e:
      if "not able to validate the provided access credentials" in str(e):
         print 'check your credentials'
         sys.exit(300)
      else:
         print e


volumes=get_inactive_volumes(regions)
#ideal_volume_time = get_inactive_time(volumes)
#sweep_inactive_volumes(ideal_volume_time)
mark_inactive_volumes(volumes)
x=control_x_x_inactive_volumes(regions)
print json.dumps(x,indent=4)

