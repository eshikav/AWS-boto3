import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

client = boto3.client('ec2')
client2 = boto3.resource('ec2')
regions = list( region['RegionName'] for region in client.describe_regions()['Regions'])


def get_autoscaling_instances(regions):
  instances = collections.defaultdict(list)
  for region in regions:
     client = boto3.client('autoscaling',region)
     for instance in client.describe_auto_scaling_instances()['AutoScalingInstances']:
         instances[region].append(instance)
  return instances

def get_public_instances(regions,event): 
  instances = get_autoscaling_instances(regions)
  result = True
  failReason = ""
  offenders = []
  control = "x.x"
  description = "Ensure there are no instances with public IP's"
  scored = True
  counter = 0
  scannedresources = sum(list(len(instances[region]) for region in instances.keys()))
  ignoredresources = 0
  for region in instances.keys():
    for instance in instances[region]:
      ec2_client = boto3.client('ec2',region)
      instance_details = ec2_client.describe_instances(Filters=[{'Name': 'instance-id','Values': [instance['InstanceId']]}])
      if instance['AutoScalingGroupName'] not in  event['IgnoreResourceList']:
        if "PublicIpAddress" in instance_details['Reservations'][0]['Instances'][0].keys():
             counter += 1
             offenders.append(dict({'region': region,'id': instance['InstanceId']}))
        else:
           pass
      else:
        ignoredresources += 1
  if counter != 0:
     failReason = "Account has "+str(counter)+" instances with public ips"
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
        "IgnoreResourceList": ["ASG_Insisiv_MP_DNT"],
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
print json.dumps(get_public_instances(regions,event),indent=4)
