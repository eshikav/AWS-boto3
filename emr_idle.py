import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

client = boto3.client('ec2')
regions = list( region['RegionName'] for region in client.describe_regions()['Regions'])

def get_active_emr_clusters(regions):
  clusters = collections.defaultdict(list)
  for region in regions:
     client = boto3.client('emr',region)
     for cluster in client.list_clusters()['Clusters']:
       if 'waiting' in cluster['Status']['State'].lower():
         clusters[region].append(cluster)
  return clusters

def get_average_datapoints(datapoints):
  datapointcount=len(datapoints)
  average = 0
  for datapoint in datapoints:
    average += datapoint['Average']
  return average / datapointcount
   
def get_idle_emr_clusters(clusters,event): 
  clusters = get_active_emr_clusters(regions)
  result = True
  failReason = ""
  offenders = []
  control = "x.x"
  description = "Ensure there are no EMR clusters that are idle from 3 days"
  scored = True
  counter = 0
  scannedresources = sum(list(len(clusters[region]) for region in clusters.keys()))
  ignoredresources = 0
  for region in clusters.keys():
    for cluster in clusters[region] and  cluster['Id'] not in event['IgnoreResourceList']:
      if cluster['Id'] not in event['IgnoreResourceList']:
         dimensions=[
                    {
                      'Name': 'JobFlowId',
                      'Value': cluster['Id']
                    }
                    ]
         seconds_in_one_day = event['Filters'][0]['Period'] * event['Filters'][0]['ConsecutiveInterval']   # used for granularity
         if event['Filters'][0]['DeltaUnits'] == "hours":
           StartTime=datetime.now() - timedelta(hours=1)
         elif event['Filters'][0]['DeltaUnits'] == "days":
           StartTime=datetime.now() - timedelta(days=1)
         cloudwatch = boto3.client('cloudwatch')
         response = cloudwatch.get_metric_statistics(
         Namespace='AWS/ElasticMapReduce',
         Dimensions=dimensions,
         MetricName='IsIdle',
         StartTime=StartTime,
         EndTime=datetime.now(),
         Period=seconds_in_one_day,
         Statistics=[
               event['MetricAggregationType']
              ],
         )

         if len(response['Datapoints']) != 0: 
           if get_average_datapoints(response['Datapoints']) >= 1.0:
             counter += 1
             offenders.append(dict({'region': region,'id': cluster['Id']}))
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
        "IgnoreResourceList": ["j-2LNU7NW8SF37S"],
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

print json.dumps(get_idle_emr_clusters(regions,event),indent=4)
