import boto3
import collections
from time import gmtime, strftime
from datetime import datetime
from dateutil import parser
import json

class checkOldSnapshots():
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

  def getOlderSnapshots(self):
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
    snapshots = collections.defaultdict()
    for region in self.regions:
      client = boto3.client('ec2',region,
                             aws_access_key_id=self.credentials['access_key'],
                             aws_secret_access_key=self.credentials['secret_key'],
                             aws_session_token=self.credentials['session_token'])
      if len(client.describe_snapshots(Filters=Filters)['Snapshots']) != 0: 
        snapshots[region] = client.describe_snapshots(Filters=Filters)['Snapshots']
    return snapshots

  def getSnapshotAge(self):
    snapshots=self.getOlderSnapshots()
    for region in snapshots.keys():
      for index,snapshot in enumerate(snapshots[region]):
        creationdate=snapshot['StartTime']
        presenttime = datetime.now(creationdate.tzinfo)
        snapshots[region][index]['age'] = (presenttime-creationdate).days
    return snapshots

  def mark(self):
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
   
  def checkOldSnapshots(self):
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

