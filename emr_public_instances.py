import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

client = boto3.client('ec2')
client2 = boto3.resource('ec2')
regions = list( region['RegionName'] for region in client.describe_regions()['Regions'])


def get_emr_clusters(regions):
  clusters = collections.defaultdict(list)
  for region in regions:
     client = boto3.client('emr',region)
     for cluster in client.list_clusters()['Clusters']:
       if "terminated" not in cluster['Status']['State'].lower():
          clusters[region].append(cluster)
  return clusters

def get_public_instances(regions,event): 
  clusters = get_emr_clusters(regions)
  result = True
  failReason = ""
  offenders = []
  control = "x.x"
  description = "Ensure there are no instances with public IP's in the EMR clusters"
  scored = True
  counter = 0
  scannedresources = sum(list(len(clusters[region]) for region in clusters.keys()))
  ignoredresources = 0
  for region in clusters.keys():
    for cluster in clusters[region]:
      if cluster['Id'] not in  event['IgnoreResourceList']:
        emr_client = boto3.client('emr',region)
        instance_details = emr_client.list_instances(ClusterId=cluster['Id'])['Instances']
        for instance in instance_details:
           if "PublicIpAddress" in instance.keys():
             counter += 1
             offenders.append(dict({'region': region,'id': instance['Ec2InstanceId']}))
           else:
             pass
      else:
        ignoredresources += 1
  if counter != 0:
     failReason = "Account has "+str(counter)+" instances with public ips in the EMR Clusters"
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
