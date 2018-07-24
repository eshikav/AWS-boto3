import boto3
import collections
from datetime import datetime,timedelta
from dateutil import parser
from dateutil.tz import tzutc
import json
class checkInactiveAmi:

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

  def getOlderAmis(self):
    sts_client = boto3.client('sts',
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
    Filters=[
           {
             'Name': 'owner-id',
             'Values': [sts_client.get_caller_identity()["Account"]]
            }
            ]
    images = collections.defaultdict()
    for region in self.regions:
      client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
      if len(client.describe_images(Filters=Filters)['Images']) != 0: 
        images[region] = client.describe_images(Filters=Filters)['Images']
    return images

  def getAmiAge(self):
    images=self.getOlderAmis()
    for region in images.keys():
      for index,image in enumerate(images[region]):
        creationdate=parser.parse(image['CreationDate'])
        presenttime = datetime.now(tzutc())
        images[region][index]['age'] = (presenttime-creationdate).days
    return images

  def mark(self):
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
        if (image['age'] > 30 and image['ImageId'] not in self.rule_properties['IgnoreResourceList']):
          if ('Tags' in image.keys() and 'Mark' in list(tag['Key'] for tag in image['Tags'])):
            pass
          else:
            client.Image(image['ImageId']).create_tags(Tags=mark_tag)

  def sweep(self):
    images = self.getAmiAge()
    for region in images.keys():
      client = boto3.resource('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
      for image in images[region]:
        if ('Tags' in image.keys() and 'Mark' in list(tag['Key'] for tag in image['Tags'])):
          print image['ImageId']

  def checkInactiveAmi(self):
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
        if image['age'] > 30 and image['ImageId'] not in self.rule_properties['IgnoreResourceList']:
          counter += 1
          offenders.append(dict({'region': region,'id': image['ImageId']}))
        else:
          if image['ImageId'] in self.rule_properties['IgnoreResourceList']:
            ignoredresources += 1
            ignored.append(dict({'region': region,'id': image['ImageId']}))
    if counter != 0:
      failReason = "Account has "+str(counter)+" older AMI's which are older than 30 days"
    return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources,'ignored': ignored}


