import boto3
import collections
from time import gmtime, strftime
from datetime import datetime,timedelta
from dateutil import parser
import json

class checkEmrPublicInstaces():

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

  def getEmrClusters(self):
    clusters = collections.defaultdict(list)
    for region in self.regions:
      client = boto3.client('emr',region)
      for cluster in client.list_clusters()['Clusters']:
        if "terminated" not in cluster['Status']['State'].lower():
          clusters[region].append(cluster)
    return clusters

  def checkEMRPublicInstances(self): 
    clusters = self.getEmrClusters()
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
        if cluster['Id'] not in  self.rule_properties['IgnoreResourceList']:
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

