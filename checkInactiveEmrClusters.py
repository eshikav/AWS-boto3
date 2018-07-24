import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

class checkInactiveEmrClusters:
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

  def getActiveEmrClusters(self):
    clusters = collections.defaultdict(list)
    for region in self.regions:
      client = boto3.client('emr',region,
                            aws_access_key_id=self.credentials['access_key'],
                            aws_secret_access_key=self.credentials['secret_key'],
                            aws_session_token=self.credentials['session_token'])
      for cluster in client.list_clusters()['Clusters']:
        if 'waiting' in cluster['Status']['State'].lower():
          clusters[region].append(cluster)
    return clusters

  def getAverageDatapoints(self,datapoints):
    datapointcount=len(datapoints)
    average = 0
    for datapoint in datapoints:
      average += datapoint['Average']
    return average / datapointcount
   
  def checkInactiveEmrClusters(self): 
    clusters = self.getActiveEmrClusters()
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
          seconds_in_one_day = 86400   # used for granularity
          StartTime=datetime.now() - timedelta(days=3)
          cloudwatch = boto3.client('cloudwatch',
                                    aws_access_key_id=self.credentials['access_key'],
                                    aws_secret_access_key=self.credentials['secret_key'],
                                    aws_session_token=self.credentials['session_token'])
          response = cloudwatch.get_metric_statistics(
          Namespace='AWS/ElasticMapReduce',
          Dimensions=dimensions,
          MetricName='IsIdle',
          StartTime=StartTime,
          EndTime=datetime.now(),
          Period=seconds_in_one_day,
          Statistics=[
               'Average'
              ],
          )
          if len(response['Datapoints']) != 0: 
            if self.getAverageDatapoints(response['Datapoints']) >= 1.0:
              counter += 1
              offenders.append(dict({'region': region,'id': cluster['Id']}))
          else:
            pass
        else:
          ignoredresources += 1 
    if counter != 0:
      failReason = "Account has "+str(counter)+" idle EMR clusters which are older than 3 days"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources}

