import boto3
import collections
from time import gmtime, strftime
from datetime import datetime
from dateutil import parser
import json

client = boto3.client('ec2')
regions = list( region['RegionName'] for region in client.describe_regions()['Regions'])

def get_older_snapshots(regions):
   Filters=[
           {
             'Name': 'owner-id',
             'Values': [boto3.client('sts').get_caller_identity()["Account"]]
            }
            ]
   snapshots = collections.defaultdict()
   for region in regions:
     client = boto3.client('ec2',region)
     if len(client.describe_snapshots(Filters=Filters)['Snapshots']) != 0: 
       snapshots[region] = client.describe_snapshots(Filters=Filters)['Snapshots']
   return snapshots

def get_snapshot_age(regions):
   snapshots=get_older_snapshots(regions)
   for region in snapshots.keys():
     for index,snapshot in enumerate(snapshots[region]):
       creationdate=snapshot['StartTime']
       presenttime = datetime.now(creationdate.tzinfo)
       snapshots[region][index]['age'] = (presenttime-creationdate).days
   return snapshots

def mark_inactive_snapshots(snapshots):
  fmt = "%a, %d %b %Y %H:%M:%S"
  for region in snapshots.keys():
    mark_tag = [{
                 'Key': 'Mark',
                 'Value': strftime(fmt,gmtime()),
                 }]
    client = boto3.resource('ec2',region)
    for snapshot in snapshots[region]:
      if 'Tags' in snapshot.keys() and 'Mark' in list(tag['Key'] for tag in snapshot['Tags']):
        pass
      else:
        client.Snapshot(snapshot['SnapshotId']).create_tags(Tags=mark_tag)
   
def control_x_x_snapshots(regions,event):
   snapshots=get_snapshot_age(regions)
   result = True
   failReason = ""
   offenders = []
   scannedresources = sum(list(len(snapshots[region]) for region in snapshots.keys()))
   ignoredresources = 0
   control = "x.x"
   description = "Ensure there are no Shapshots older than 10 days"
   scored = True
   counter = 0
   for region in snapshots.keys():
     for snapshot in snapshots[region]:
       if snapshot['age'] > 10 and snapshot['SnapshotId'] not in event['IgnoreResourceList']:
         counter += 1
         offenders.append(dict({'region': region,'id': snapshot['SnapshotId']}))
         mark_inactive_snapshots(snapshots)
       else:
         if snapshot['SnapshotId'] in event['IgnoreResourceList']:
           ignoredresources += 1
   if counter != 0:
     failReason = "Account has "+str(counter)+" older Snapshots which are older than 30 days"
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
        "IgnoreResourceList": ['snap-0e00527871e9ef9b6'],
        "MetricAggregationType": "Average",
        "ComparisonOperator": "LessThanOrEqualToThreshold",
        "Filters" : [{
          "Period": 60,
          "PeriodUnits": "minutes",
          "Delta": 1,
          "DeltaUnits": "days",
          "ConsecutiveInterval": 5
        }]
       }

x=control_x_x_snapshots(regions,event)
print json.dumps(x,indent=4)
