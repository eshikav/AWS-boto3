import boto3
import json
import collections

class checkVPCEndpoints:
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
  getVpcEndpointsWithS3Gateway gathers a list of all the VPC endpoint with a VPC which are of the type S3 Gateway

  Arguments:
  it takes the failmessage as the argument

  Return:
  returns a default dict object which contains the region as the key and the list of VPC's that has S3 Endpoints as the value in a 
  specified region 
  '''
  def getVpcEndpointsWithS3Gateway(self):
    try:
      vpc_endpoints = collections.defaultdict()
      for region in self.regions:
        vpc_endpoints[region]=[]
        client = boto3.client('ec2',region,
                            aws_access_key_id=self.credentials['access_key'],
                            aws_secret_access_key=self.credentials['secret_key'],
                            aws_session_token=self.credentials['session_token'])
        for vpcendpoint in client.describe_vpc_endpoints()['VpcEndpoints']:
          if vpcendpoint['VpcEndpointType'] == 'Gateway' and vpcendpoint['ServiceName'].split('.')[-1] == 's3'\
             and vpcendpoint['VpcId'] not in vpc_endpoints[region]:
            vpc_endpoints[region].append(vpcendpoint['VpcId'])
      return vpc_endpoints
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  getVpcs gathers a list of all the VPC's in a region

  Arguments:
  it takes the failmessage as the argument

  Return:
  returns a default dict object which contains the region as the key and the list of VPC information in the regions specified
  '''
  def getVpcs(self):
    vpcs = collections.defaultdict(list)
    includeresources = self.rule_properties['Filters'][0]['TagEquals']
    for region in self.regions:   
      client = boto3.client('ec2',region,
                            aws_access_key_id=self.credentials['access_key'],
                            aws_secret_access_key=self.credentials['secret_key'],
                            aws_session_token=self.credentials['session_token'])
      if ( not self.ignorefilters ) and len(includeresources.keys()) != 0:
        vpcs[region] = []
        for tag in includeresources.keys():
          filter={"Name": "tag:"+tag,"Values": includeresources[tag]}
          for vpc in client.describe_vpcs(Filters=[filter])['Vpcs']:
            if vpc['VpcId'] not in list(vpc for vpc in vpcs[region]):
              vpcs[region].append(vpc)
      else:
        for vpc in client.describe_vpcs()['Vpcs']:
          vpcs[region].append(vpc)
    return vpcs

  '''
  Description:
  filter method will filter the resources based on the exclude tag list which is specified in the rule_properties object

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the VPC's in the particular region
  after the exclusion
  '''
  def filter(self):
    try:
      resources = self.getVpcs()
      object = self.getVpcs()
      excluderesources = self.rule_properties['Filters'][0]['ExcludeResourcesWithTagEquals']
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in object.keys():
        count = 0
        for index,resource in enumerate(object[region]):
          if "Tags" in resource.keys():
            for resourcetag in resource['Tags']:
              for tag in excluderesources.keys():
                if tag == resourcetag['Key'] and resourcetag['Value'] in excluderesources[tag]:
                  if len(resources[region]) != 0 and resources[region][index-count]['VpcId'] == resource['VpcId']:
                    x=resources[region].pop(index-count)
                    count += 1
      return resources
    except Exception as e:
      return self.returnFailjson(str(e))


  '''
  Description:
  checkVPCEndpoints reports all the VPC's without a S3 gateway

  Arguments:
  it takes the failmessage as the argument

  Return:
  returns a default dict object which contains the region as the key and the list of VPC information in the regions specified
  '''
  def checkVPCEndpoints(self):
    result = True
    failReason = ""
    offenders = []
    control = "x.x"
    description = "There are no VPC's without s3 as vpc gateway"
    ignoredresources = 0
    scannedresources = 0
    ignored = []
    scored = True
    counter = 0
    vpcs = self.getVpcs()
    vpc_endpoints = self.getVpcEndpointsWithS3Gateway()
    for region in vpcs.keys():
      for vpc in vpcs[region]:
        if vpc['VpcId'] not in vpc_endpoints[region] and vpc['VpcId'] not in self.rule_properties['IgnoreResourceList']:
          counter += 1
          offenders.append({"region": region,'vpcid': vpc['VpcId']})
          result = False
          failReason = "There are "+str(counter)+" VPC's without s3 endpoints as gateway"
        else:
          if vpc['VpcId'] in self.rule_properties['IgnoreResourceList']:
            ignored.append({"region": region,'vpcid': vpc['VpcId']})
            ignoredresources += 1
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control, 'IgnoredResources': ignoredresources,"ScannedResources": scannedresources,"ignored": ignored }
