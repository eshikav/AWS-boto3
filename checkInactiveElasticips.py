import boto3
import json
import sys
import collections
class checkInactiveElasticips:
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

  def getAddresses(self): 
    addresses = collection.defaultdict()
    for region in self.regions:
      client=boto3.client('ec2',region,
                           aws_access_key_id=self.credentials['access_key'],
                           aws_secret_access_key=self.credentials['secret_key'],
                           aws_session_token=self.credentials['session_token'])
      if client.describe_addresses()['Addresses'] != 0:
        addresses[region] = client.describe_addresses()['Addresses'] 
    return addresses 

  def checkInactiveElasticips(self):
    adresses = self.getAddresses()
    scannedresources=sum(len(adresses[region]) for region in adresses.keys())
    ignoredresources = 0
    result = True
    failReason = ""
    offenders = []
    control = "x.x"
    description = "Ensure all the Allocated Elastic ip's are associated with the instances"
    scored = True
    counter = 0
    for region in adresses.keys():
      for eip in adresses[region]:
        if 'AssociationId' not in eip.keys() and eip['PublicIp'] not in self.rule_properties["IgnoreResourceList"]:
          counter += 1
          offenders.append(dict({'region': region,'id': eip['AllocationId']}))
        else:
          if eip['PublicIp'] in self.rule_properties["IgnoreResourceList"]:
            ignoredresources += 1
    if counter != 0:
      failReason = "Account has "+str(counter)+" elastic IP's which are allocated but not being associated"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources, 'Failed': counter}

