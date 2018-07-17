import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
import json

client = boto3.client('ec2')
regions = list( region['RegionName'] for region in client.describe_regions()['Regions'])


def get_active_provisioned_volumes(regions):
  volumes = collections.defaultdict(list)
  for region in regions:
     client = boto3.client('ec2',region)
     for volume in client.describe_volumes()['Volumes']:
       if volume['State'] == 'in-use' and volume['VolumeType'] == 'io1':
         volumes[region].append(volume)
  return volumes

def get_average_datapoints(datapoints):
  datapointcount=len(datapoints)
  average = 0
  for datapoint in datapoints:
    average += datapoint['Average']
  return average / datapointcount


def get_average_iops_provisioned_volumes(regions,event): 
  volumes = get_active_provisioned_volumes(regions)
  result = True
  failReason = ""
  scannedresources = sum(list(len(volumes[region]) for region in volumes.keys()))
  ignoredresources = 0
  offenders = []
  control = "x.x"
  description = "Ensure there are no underutilised provisioned disks"
  scored = True
  counter = 0
  for region in volumes.keys():
    for volume in volumes[region]:
      if volume['VolumeId'] not in event['IgnoreResourceList']:
         dimensions=[
                    {
                      'Name': 'VolumeId',
                      'Value': volume['VolumeId']
                    }
                    ]
         seconds_in_one_day = event['Filters'][0]['Period'] * event['Filters'][0]['ConsecutiveInterval'] # used for granularity
         if event['Filters'][0]['DeltaUnits'] == "hours":
           StartTime=datetime.now() - timedelta(hours=1)
         elif event['Filters'][0]['DeltaUnits'] == "days":
           StartTime=datetime.now() - timedelta(days=1)
         cloudwatch = boto3.client('cloudwatch')
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
           if get_average_datapoints(response['Datapoints']) < volume['Iops']:
             counter += 1
             offenders.append(dict({'region': region,'id': cluster['Id']}))
         else:
           pass
      else:
        ignoredresources += 1
    if counter != 0:
      failReason = "Account has "+str(counter)+" iops provisioned disks whichare being underutilized"
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
        "IgnoreResourceList": [],
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
print json.dumps(get_average_iops_provisioned_volumes(regions,event),indent=4)
