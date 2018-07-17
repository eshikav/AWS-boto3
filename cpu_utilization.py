import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

client = boto3.client('ec2')
client2 = boto3.resource('ec2')
regions = list( region['RegionName'] for region in client.describe_regions()['Regions'])


def get_active_instances(regions):
  instances = collections.defaultdict(list)
  for region in regions:
     client = boto3.client('ec2',region)
     for instance in client.describe_instances()['Reservations']:
       if instance['Instances'][0]['State']['Name'] == 'running':
         instances[region].append(instance)
  return instances

def get_average_datapoints(datapoints):
  datapointcount=len(datapoints)
  average = 0
  for datapoint in datapoints:
    average += datapoint['Average']
  return average / datapointcount


def get_average_iops_provisioned_volumes(regions,event): 
  instances = get_active_instances(regions)
  result = True
  failReason = ""
  offenders = []
  control = "x.x"
  description = "Ensure there are no EMR clusters that are idle from 3 days"
  scored = True
  counter = 0
  scannedresources = sum(list(len(instances[region]) for region in instances.keys()))
  ignoredresources = 0
  if event['Filters'][0]['DeltaUnits'] == "hours":
    StartTime=datetime.utcnow() - timedelta(hours=event['Filters'][0]["Delta"])
  elif event['Filters'][0]['DeltaUnits'] == "days":
    StartTime=datetime.utcnow() - timedelta(days=event['Filters'][0]["Delta"])
  for region in instances.keys():
    for instance in instances[region]:
      if instance['Instances'][0]['InstanceId'] not in  event['IgnoreResourceList']:
         dimensions=[
                    {
                      'Name': 'InstanceId',
                      'Value': instance['Instances'][0]['InstanceId']
                    }
                    ]
         seconds_in_one_day =  event['Filters'][0]['Period'] * event['Filters'][0]['ConsecutiveInterval']  # used for granularity
         cloudwatch = boto3.client('cloudwatch')
         response = cloudwatch.get_metric_statistics(
         Namespace='AWS/EC2',
         Dimensions=dimensions,
         MetricName='CPUUtilization',
         StartTime=StartTime,
         EndTime=datetime.utcnow(),
         Period=seconds_in_one_day,
         Statistics=[
                     event['MetricAggregationType']
                    ],
         )
         if len(response['Datapoints']) != 0: 
           if get_average_datapoints(response['Datapoints']) < 10:
             counter += 1
             offenders.append(dict({'region': region,'id': instance['Instances'][0]['InstanceId']}))
         else:
           pass
      else:
        ignoredresources += 1
  if counter != 0:
     failReason = "Account has "+str(counter)+" idle EMR clusters which are older than 3 days"
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
        "IgnoreResourceList": ["i-0e1919abdeb4bb495"],
        "MetricAggregationType": "Average",
        "ComparisonOperator": "LessThanOrEqualToThreshold",
        "Filters" : [{
          "Period": 60,
          "PeriodUnits": "minutes",
          "Delta": 3,
          "DeltaUnits": "hours",
          "ConsecutiveInterval": 5
        }]
       }
print json.dumps(get_average_iops_provisioned_volumes(regions,event),indent=4)

