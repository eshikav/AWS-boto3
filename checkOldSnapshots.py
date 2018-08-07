import boto3
import collections
from time import gmtime, strftime
from datetime import datetime
from dateutil import parser
import json

class checkOldSnapshots():
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
    print json.dumps(message,indent=3)

  '''
  Description:
  getOlderSnapshots gathers all the snapshot list which are owned by the account passed in the credentials object it also includes
  the objects which are specified in the include filters

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns the default dict object which contains the information about the snapshots in the regions.
  '''
  def getOlderSnapshots(self):
    try:
      snapshots = collections.defaultdict(list)
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in self.regions:
        client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
        if ( not self.ignorefilters ) and len(includeresources.keys()) != 0:
          snapshots[region] = []
          for tag in includeresources.keys():
            filter={"Name": "tag:"+tag,"Values": includeresources[tag]}
            for snapshot in client.describe_snapshots(Filters=[filter])['Snapshots']:
              if ( snapshot['SnapshotId'] not in list(snapshot['SnapshotId'] for snapshot in snapshots[region])):
                 snapshots[region].append(snapshot)
        else:
          for snapshot in client.describe_snapshots()['Snapshots']:
            snapshots[region].append(snapshot)
      return snapshots
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  filter method will filter the resources based on the exclude tag list which is specified in the rule_properties object

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the snapshots in the particular region
  after the exclusion
  '''
  def filter(self):
    try:
      resources = self.getOlderSnapshots()
      object = self.getOlderSnapshots()
      excluderesources = self.rule_properties['Filters'][0]['ExcludeResourcesWithTagEquals']
      includeresources = self.rule_properties['Filters'][0]['TagEquals']
      for region in object.keys():
        count = 0
        for index,resource in enumerate(object[region]):
          if "Tags" in resource.keys():
            for resourcetag in resource['Tags']:
              for tag in excluderesources.keys():
                if tag == resourcetag['Key'] and resourcetag['Value'] in excluderesources[tag]:
                  if len(resources[region]) != 0 and resources[region][index-count]['SnapshotId'] == resource['SnapshotId']:
                    x=resources[region].pop(index-count)
                    count += 1
      return resources
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  getSnapshotAge gets the age( the time elapsed since it was created) of the snapshots which are returned from filter

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a defaultdict object which contains the regions as the keys and the list of the snapshots in the particular region
  with thir ages( the time elapsed since it was created)
  '''
  def getSnapshotAge(self):
    try:
      if ( not self.ignorefilters ):
        snapshots = self.filter()
      else:
        snapshots = self.getOlderSnapshots()
      for region in snapshots.keys():
        for index,snapshot in enumerate(snapshots[region]):
          creationdate=snapshot['StartTime']
          presenttime = datetime.now(creationdate.tzinfo)
          snapshots[region][index]['age'] = (presenttime-creationdate).days
      return snapshots
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  mark, marks all the old snapshots with a timestamp. A mark is basically a tag to the resource with key as Mark and value as the timestamp.

  Arguments:
  It doesnot expets any arguments

  Return:
  It doesnot have any return objects
  '''
  def mark(self):
    try:
      snapshots = self.getSnapshotAge()
      fmt = "%a, %d %b %Y %H:%M:%S"
      for region in snapshots.keys():
        mark_tag = [{
                 'Key': 'Mark',
                 'Value': strftime(fmt,gmtime()),
                 }]
        client = boto3.resource('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])

        for snapshot in snapshots[region]:
          if 'Tags' in snapshot.keys() and 'Mark' in list(tag['Key'] for tag in snapshot['Tags']):
            pass
          else:
            client.Snapshot(snapshot['SnapshotId']).create_tags(Tags=mark_tag)
    except Exception as e:
      return self.returnFailjson(str(e))


  '''
  Description:
  checkOldSnapshots reports all the old AMI which deviates from a specific rule.

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contains the information of the old snapshots
  '''
  def checkOldSnapshots(self):
    try:
      snapshots=self.getSnapshotAge()
      result = True
      failReason = ""
      offenders = []
      scannedresources = sum(list(len(snapshots[region]) for region in snapshots.keys()))
      ignoredresources = 0
      ignored = []
      control = "x.x"
      description = "Ensure there are no Shapshots older than 10 days"
      scored = True
      counter = 0
      for region in snapshots.keys():
        for snapshot in snapshots[region]:
          if snapshot['age'] > 10 and snapshot['SnapshotId'] not in self.rule_properties['IgnoreResourceList']:
            counter += 1
            offenders.append(dict({'region': region,'id': snapshot['SnapshotId']}))
          else:
            if snapshot['SnapshotId'] in self.rule_properties['IgnoreResourceList']:
              ignoredresources += 1
              ignored.append(dict({'region': region,'id': snapshot['SnapshotId']}))
      if counter != 0:
        failReason = "Account has "+str(counter)+" older Snapshots which are older than 30 days"
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources, 'ignored': ignored}
    except Exception as e:
      return self.returnFailjson(str(e))
