import boto3
import json
import sys
import collections
class checkInactiveElasticips:
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
    if len(rule_properties['RuleProperties'][0]['Filters'][0]['Region']) == 0:
      client = boto3.client('ec2',
                             aws_access_key_id=credentials['access_key'],
                             aws_secret_access_key=credentials['secret_key'],
                             aws_session_token=credentials['session_token'])
      self.regions = list(region['RegionName'] for region in client.describe_regions()['Regions'])
    else:
      self.regions = rule_properties['RuleProperties'][0]['Filters'][0]['Region']
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
  getOlderAmis gathers all the AMI list which are owned by the account passed in the credentials object it also includes
  the objects which are specified in the include filters

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns the default dict object which contains the information about the Elastic Ip adresses in the regions with keys as the regions and the list of
  Elastic ips as the values
  '''
  def getAddresses(self): 
    try:
      addresses = collections.defaultdict(list)
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in self.regions:
        client=boto3.client('ec2',region,
                           aws_access_key_id=self.credentials['access_key'],
                           aws_secret_access_key=self.credentials['secret_key'],
                           aws_session_token=self.credentials['session_token'])
        if ( not self.ignorefilters ) and len(includeresources.keys()) != 0:
          addresses[region]=[]
          for tag in includeresources.keys():
            filter={"Name": "tag:"+tag,"Values": includeresources[tag]}
            for address in client.describe_addresses(Filters=[filter])['Addresses']:
              if address['AllocationId'] not in list(address['AllocationId'] for address in addresses[region]):
                addresses[region].append(address)
        else:
          for address in client.describe_addresses()['Addresses']:
            addresses[region].append(address)
      return addresses 
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  filter method will filter the resources based on the exclude tag list which is specified in the rule_properties object

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the AMI's in the particular region
  after the exclusion
  '''
  def filter(self):
    try:
      resources = self.getAddresses()
      object = self.getAddresses()
      excluderesources = self.rule_properties['Filters'][0]['ExcludeResourcesWithTagEquals']
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in object.keys():
        count = 0
        for index,resource in enumerate(object[region]):
          if "Tags" in resource.keys():
            for resourcetag in resource['Tags']:
              for tag in excluderesources.keys():
                if tag == resourcetag['Key'] and resourcetag['Value'] in excluderesources[tag]:
                  if len(resources[region]) != 0 and resources[region][index-count]['AllocationId'] == resource['AllocationId']:
                    x=resources[region].pop(index-count)
                    count += 1
      return resources
    except Exception as e:
      return self.returnFailjson(str(e))
    
  '''
  Description:
  checkInactiveElasticips reports all the Elastic Ips which are associated but not being used by the account

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contains the information of the Elastic IPs which are not being used but associated with the account
  '''
  def checkInactiveElasticips(self):
    try:
      if ( not self.ignorefilters ):
        adresses = self.filter(adresses)
      else:
        adresses = self.getAddresses()
      scannedresources=sum(len(adresses[region]) for region in adresses.keys())
      ignoredresources = 0
      ignored = []
      result = True
      failReason = ""
      offenders = []
      control = "x.x"
      description = "Ensure all the Allocated Elastic ip's are associated with the instances"
      scored = True
      counter = 0
      for region in adresses.keys():
        for eip in adresses[region]:
          if 'AssociationId' not in eip.keys() and eip['AllocationId'] not in self.rule_properties["IgnoreResourceList"]:
            counter += 1
            offenders.append(dict({'region': region,'id': eip['AllocationId']}))
          else:
            if eip['AllocationId'] in self.rule_properties["IgnoreResourceList"]:
              ignoredresources += 1
              ignored.append(dict({'region': region,'id': eip['AllocationId']}))
      if counter != 0:
        failReason = "Account has "+str(counter)+" elastic IP's which are allocated but not being associated"
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources, 'Failed': counter, 'Ignored': ignored}
    except Exception as e:
      return self.returnFailjson(str(e))
