import boto3
import collections
from datetime import datetime,timedelta
from dateutil import parser
from dateutil.tz import tzutc
import json
class checkInactiveAmi:
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
  def returnFailjson(failmessage):
    message={
          "failed": True,
          "reason": failmessage
          }
    print json.dumps(message,indent=3)

  '''
  Description:
  getOlderAmis gathers all the AMI list which are owned by the account passed in the credentials object it also includes
  the objects which are specified in the include filters

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns the default dict object which contains the information about the AMI in the regions.
  '''
  def getOlderAmis(self):
    try:
      images = collections.defaultdict(list)
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      sts_client = boto3.client('sts',
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
      for region in self.regions:
        client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        if ( not self.ignorefilters ) and len(includeresources.keys()) != 0:
          images[region] = []
          for tag in includeresources.keys():
            filter=[{
                   'Name': 'owner-id',
                   'Values': [sts_client.get_caller_identity()["Account"]]
                   },
                   {
                    "Name": "tag:"+tag,
                    "Values": includeresources[tag]
                   }]
            for image in client.describe_images(Filters=filter)['Images']:
              if ( image['ImageId'] not in list(image['ImageId'] for image in images[region])):
                 images[region].append(image)
        else:
          for image in client.describe_images()['Images']:
            images[region].append(image)
      return images
    except Exception as e:
      returnFailjson(str(e))


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
      resources = self.getOlderAmis()
      object = self.getOlderAmis()
      excluderesources = self.rule_properties['Filters'][0]['ExcludeResourcesWithTagEquals']
      for region in object.keys():
        count = 0
        for index,resource in enumerate(object[region]):
          if "Tags" in resource.keys():
            for resourcetag in resource['Tags']:
              for tag in excluderesources.keys():
                if tag == resourcetag['Key'] and resourcetag['Value'] in excluderesources[tag]:
                  if len(resources[region]) != 0 and resources[region][index-count]['ImageId'] == resource['ImageId']:
                    x=resources[region].pop(index-count)
                    count += 1
      return resources
    except Exception as e:
      returnFailjson(str(e))

  '''
  Description:
  getAmiAge calculates the age(time after the creation) of the AMI's returned from the filter or getOlderAmis

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the AMI's in the particular region
  along with the age(time after the creation) of the AMI
  '''
  def getAmiAge(self):
    try:
      if ( not self.ignorefilters ):
        images = self.filter()
      else:
        images = self.getOlderAmis()
      for region in images.keys():
        for index,image in enumerate(images[region]):
          creationdate=parser.parse(image['CreationDate'])
          presenttime = datetime.now(tzutc())
          images[region][index]['age'] = (presenttime-creationdate).days
      return images
    except Exception as e:
      returnFailjson(str(e))

  '''
  Description:
  mark, marks all the old images with a timestamp. A mark is basically a tag to the resource with key as Mark and value as the timestamp.

  Arguments:
  It doesnot expets any arguments

  Return:
  It doesnot have any return objects
  '''
  def mark(self):
    try:
      images = self.getAmiAge()
      for region in images.keys():
        mark_tag = [{
                 'Key': 'Mark',
                 'Value': datetime.now(tzutc()).isoformat(),
                 }]
        client = boto3.resource('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        for image in images[region]:
          if (image['age'] > -1 and image['ImageId'] not in self.rule_properties['IgnoreResourceList']):
            if ('Tags' in image.keys() and 'Mark' in list(tag['Key'] for tag in image['Tags'])):
              pass
            else:
              client.Image(image['ImageId']).create_tags(Tags=mark_tag)
    except Exception as e:
      returnFailjson(str(e)) 

  '''
  Description:
  It takes action on the old AMI specified in the rule_properties.

  Arguments:
  It doesnot expects any arguments

  Return:
  It doesnot returns anything
  '''
  def sweep(self):
    try:
      images = self.getAmiAge()
      for region in images.keys():
        client = boto3.resource('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        for image in images[region]:
          if ('Tags' in image.keys() and 'Mark' in list(tag['Key'] for tag in image['Tags'])):
            print image['ImageId']
    except Exception as e:
      returnFailjson(str(e)) 

  '''
  Description:
  checkInactiveAmi reports all the old AMI which deviates from a specific rule.

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contains the information of the failed volumes
  '''
  def checkInactiveAmi(self):
    try:
      images=self.getAmiAge()
      result = True
      failReason = ""
      offenders = []
      control = 10
      description = "Ensure there are no AMI's older than 30 days"
      scored = True
      counter = 0
      scannedresources = sum(list(len(images[region]) for region in images.keys()))
      ignoredresources = 0
      ignored = []
      for region in images.keys():
        for image in images[region] :
          if image['age'] > -1 and image['ImageId'] not in self.rule_properties['IgnoreResourceList']:
            counter += 1
            offenders.append(dict({'region': region,'id': image['ImageId']}))
          else:
            if image['ImageId'] in self.rule_properties['IgnoreResourceList']:
              ignoredresources += 1
              ignored.append(dict({'region': region,'id': image['ImageId']}))
      if counter != 0:
        failReason = "Account has "+str(counter)+" older AMI's which are older than 30 days"
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources,'ignored': ignored}
    except Exception as e:
      returnFailjson(str(e))
