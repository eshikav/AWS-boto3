import boto3
import json
import collections

class checkVPCEndpoints:
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

  def getVpcEndpoints(self):
    vpc_endpoints = collections.defaultdict()
    for region in self.regions:
      client = boto3.client('ec2',region,
                            aws_access_key_id=self.credentials['access_key'],
                            aws_secret_access_key=self.credentials['secret_key'],
                            aws_session_token=self.credentials['session_token'])
      if len(client.describe_vpc_endpoints()['VpcEndpoints']) != 0:
        vpc_endpoints['region'] = client.describe_vpc_endpoints()['VpcEndpoints']
    return vpc_endpoints

  def checkVPCEndpoints(self):
    vpcendpoints = self.getVpcEndpoints()
    result = True
    failReason = ""
    offenders = []
    control = "x.x"
    description = "There are no endpoints without s3 as vpc gateway"
    ignoredresources = 0
    scannedresources = 0
    ignored = []
    scored = True
    counter = 0
    for region in vpcendpoints.keys():
      for endpoint in vpcendpoints[region]:
        if endpoint['VpcId'] not in self.rule_properties['IgnoreResourceList'] and endpoint['ServiceName'].split('.')[-1] != 's3': 
          counter += 1
          offenders.append({"region": region,'endpointid': endpoint['VpcId']})
          result = False
          failReason = "There are "+str(counter)+" vpc endpoints without s3 as gateway"
        else:
          if endpoint['VpcId'] in self.rule_properties['IgnoreResourceList']:
            ignored.append({"region": region,'endpointid': endpoint['VpcId']})
            ignoredresources += 1
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control, 'IgnoredResources': ignoredresources,"ScannedResources": scannedresources,"ignored": ignored }
