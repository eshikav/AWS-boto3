import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

class checkInactiveEmrClusters:
  '''
  Description:
  Constructor for the class, it takes the rule_properties and the credentials objects as the arguments.
  rule_properties should be aligned to a specific format. Please see the guidelines.

  Arguments:
  It takes the rule_properties and the credentials objects as the arguments.rule_properties should be aligned to a specific format. Please see the guidelines.
  If there are no regions which are defined in the rule_properties then the region would be constructed with all the regions that pertains for the specific
  user.

  Return:
  It doesnot have any return objects.
  '''
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
    self.ignorefilters = rule_properties['RuleProperties'][0]['IgnoreFilters']

  '''
  Description:
  returnFailjson returns a json object if there

  Arguments:
  it takes the failmessage as the argument

  Return:
  json object which contains the failed message
  '''
  def returnFailjson(self,failmessage):
    message={
          "failed": True,
          "reason": failmessage
          }
    return message

  '''
  Description:
  getActiveEmrClusters gathers  list of EMR Clusters, also includes the objects which are specified in the include filters

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns the default dict object which contains the information about the EMR Clusters in the regions.
  '''
  def getActiveEmrClusters(self):
    try:
      clusters = collections.defaultdict(list)
      for region in self.regions:
        client = boto3.client('emr',region,
                            aws_access_key_id=self.credentials['access_key'],
                            aws_secret_access_key=self.credentials['secret_key'],
                            aws_session_token=self.credentials['session_token'])
        for cluster in client.list_clusters(ClusterStates=['RUNNING','WAITING'])['Clusters']:
          clusters[region].append(cluster)
      return clusters
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  filter method will filter the resources based on the exclude tag list which is specified in the rule_properties object

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the EMR Clusters in the particular region
  after the exclusion
  '''
  def filter(self):
    try:
      resources = self.getActiveEmrClusters()
      object = self.getActiveEmrClusters()
      excluderesources = self.rule_properties['Filters'][0]['ExcludeResourcesWithTagEquals']
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in object.keys():
        count = 0
        for index,resource in enumerate(object[region]):
          client = boto3.client('emr',region,
                            aws_access_key_id=self.credentials['access_key'],
                            aws_secret_access_key=self.credentials['secret_key'],
                            aws_session_token=self.credentials['session_token'])
          resource_description = client.describe_cluster(ClusterId=resource['Id'])['Cluster']
          if "Tags" in resource_description.keys():
            for resourcetag in resource_description['Tags']:
              for tag in excluderesources.keys():
                if tag == resourcetag['Key'] and resourcetag['Value'] in excluderesources[tag]:
                  if len(resources[region]) != 0 and resources[region][index-count]['Id'] == resource['Id']:
                    x=resources[region].pop(index-count)
                    count += 1
      return resources
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  getAverageDatapoints method will calculate the average of the datapoints for inactivity calculation

  Arguments:
  takes in the datapoints for which average is calculated

  Return:
  average of the datapoints which are passed to the finction
  '''
  def getAverageDatapoints(self,datapoints):
    try:
      datapointcount=len(datapoints)
      average = 0
      for datapoint in datapoints:
        average += datapoint['Average']
      return average / datapointcount
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  checkInactiveEmrClusters reports all the EMR cluster which are inactive from a specified time.

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contains the information of the inactive EMR clusters
  '''
  def checkInactiveEmrClusters(self): 
    try:
      if ( not self.ignorefilters ):
        clusters = self.filter()
      else:
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
        for cluster in clusters[region]:
          if cluster['Id'] not in self.rule_properties['IgnoreResourceList']:
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
    except Exception as e:
      return self.returnFailjson(str(e))
