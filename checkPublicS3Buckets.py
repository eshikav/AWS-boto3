import boto3
import json
import sys

class checkPublicS3Buckets():
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
    return message

  '''
  Description:
  getBuckets gathers the list of all the buckets.

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a list of buckets 
  '''
  def getBuckets(self):
    try:
      client = boto3.client('s3',
                           aws_access_key_id=self.credentials['access_key'],
                           aws_secret_access_key=self.credentials['secret_key'],
                           aws_session_token=self.credentials['session_token'])

      return list(bucket for bucket in client.list_buckets()['Buckets'])
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  getPublicBuckets gets the properties of the buckets and checks if the permissions of the buckets are open to public

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a dict object of the buckets along with the open permissions
  '''
  def getPublicBuckets(self):
    try:
      bucketlist = self.getBuckets()
      public_buckets = dict()
      client = boto3.client('s3',
                          aws_access_key_id=self.credentials['access_key'],
                          aws_secret_access_key=self.credentials['secret_key'],
                          aws_session_token=self.credentials['session_token'])
 
      for bucket in bucketlist:
        acl=client.get_bucket_acl(Bucket=bucket['Name'])
        permissions=(list(type['Permission'] for type in acl['Grants'] if type['Grantee']['Type']\
                     == 'Group' and "AllUsers" in type['Grantee']['URI'] ))
        if len(permissions) != 0:
          public_buckets[bucket['Name']] = permissions
      return public_buckets
    except Exception as e:
      return self.returnFailjson(str(e))

  '''
  Description:
  checkPublicS3Buckets reports all the buckets which are open to the public

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contains the information about the failed resources if any
  '''
  def checkPublicS3Buckets(self):
    try:
      publicbuckets = self.getPublicBuckets()
      result = True
      failReason = ""
      offenders = []
      control = "x.x"
      description = "Ensure there are no buckets exposed publicly"
      ignoredresources = 0
      scannedresources = 0
      ignored = []
      scored = True
      counter = 0
      for bucket in publicbuckets:
        if bucket not in self.rule_properties['IgnoreResourceList']: 
          counter += 1
          offenders.append({bucket: publicbuckets[bucket]})
          result = False
          failReason = "There are "+str(counter)+" buckets which are exposed publicly"
        else:
          if bucket in self.rule_properties['IgnoreResourceList']:
            ignored.append({bucket: publicbuckets[bucket]})
            ignoredresources += 1
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control, 'IgnoredResources': ignoredresources,"ScannedResources": scannedresources,"ignored": ignored }
    except Exception as e:
      return self.returnFailjson(str(e))
