import boto3
import collections
from time import gmtime, strftime
from datetime import datetime
from dateutil import parser
import json

client = boto3.client('ec2')
regions = list( region['RegionName'] for region in client.describe_regions()['Regions'])

def get_older_amis(regions):
   Filters=[
           {
             'Name': 'owner-id',
             'Values': [boto3.client('sts').get_caller_identity()["Account"]]
            }
            ]
   images = collections.defaultdict()
   for region in regions:
     client = boto3.client('ec2',region)
     if len(client.describe_images(Filters=Filters)['Images']) != 0: 
       images[region] = client.describe_images(Filters=Filters)['Images']
   return images

def get_amis_age(regions):
   images=get_older_amis(regions)
   for region in images.keys():
     for index,image in enumerate(images[region]):
       creationdate=parser.parse(image['CreationDate'])
       presenttime = datetime.now(creationdate.tzinfo)
       images[region][index]['age'] = (presenttime-creationdate).days
   return images

def mark_inactive_amis(images):
  fmt = "%a, %d %b %Y %H:%M:%S"
  for region in images.keys():
    mark_tag = [{
                 'Key': 'Mark',
                 'Value': strftime(fmt,gmtime()),
                 }]
    client = boto3.resource('ec2',region)
    for image in images[region]:
      if 'Tags' in image.keys() and 'Mark' in list(tag['Key'] for tag in image['Tags']):
        pass
      else:
        client.Image(image['ImageId']).create_tags(Tags=mark_tag)
   
def control_x_x_amis_(regions,event):
   images=get_amis_age(regions)
   result = True
   failReason = ""
   offenders = []
   control = "x.x"
   description = "Ensure there are no AMI's older than 30 days"
   scored = True
   counter = 0
   scannedresources = sum(list(len(images[region]) for region in images.keys()))
   ignoredresources = 0
   for region in images.keys():
     for image in images[region] :
       if image['age'] > 30 and image['Name'] not in event['IgnoreResourceList']:
         counter += 1
         offenders.append(dict({'region': region,'id': image['ImageId']}))
       else:
         if image['Name'] in  event['IgnoreResourceList']:
           ignoredresources =+ 1
   if counter != 0:
     failReason = "Account has "+str(counter)+" older AMI's which are older than 30 days"
   return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources}
event={
        "RuleID": 1,
        "RuleName": "UnencryptedEBSVolumes",
        "Severity": "High",
        "Description": "Find uncrypted EBD volumes",
        "Frequency": "cron(0 12 * * ? *)",
        "Service": "S3",
        "Default_tz": "et",
        "Ignore": "False",
        "IgnoreResourceList": ["WebServerV1.0"],
        "MetricAggregationType": "Average",
        "ComparisonOperator": "LessThanOrEqualToThreshold",
        "Filters" : [{
          "Period": 1,
          "PeriodUnits": "minutes",
          "Delta": 1,
          "DeltaUnits": "hours",
          "ConsecutiveInterval": 5
        }]
       }
#images=get_amis_age(regions,event)
#mark_inactive_amis(images)
x=control_x_x_amis_(regions,event)
print json.dumps(x,indent=4)
