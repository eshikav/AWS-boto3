import boto3
import json
import sys

class checkNoUnEncryptedBucket:
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
  checkNoUnEncryptedBucket reports all the unencrypted buckets in the regions specified.

  Arguments:
  It doesnot takes any arguments.

  Return:
  It returns a json object which contains the information of the failed buckets
  '''
  def checkNoUnEncryptedBucket(self):
    try:
      client = boto3.client('s3',
                           aws_access_key_id=self.credentials['access_key'],
                           aws_secret_access_key=self.credentials['secret_key'],
                           aws_session_token=self.credentials['session_token'])
      buckets =  list(bucket['Name'] for bucket in client.list_buckets()['Buckets'])
      scannedresources = len(buckets)
      ignoredresources = 0
      result = True
      failReason = ""
      offenders = []
      control = "x.x"
      description = "Ensure there are no buckets without  SSE/KMS encryption"
      scored = True
      ignored= []
      counter = 0
      for bucket in buckets:
        if bucket not in self.rule_properties['IgnoreResourceList']: 
          try:
            resource=client.get_bucket_encryption(Bucket=bucket)
          except Exception as e:
            if "encryption configuration was not found" in str(e):
              counter += 1
              offenders.append(bucket)
        else:
          if bucket in self.rule_properties['IgnoreResourceList'] :
            ignoredresources += 1 
            ignored.append(bucket)
      if counter != 0:   
        failReason = "There are "+str(counter)+" buckets without  SSE/KMS encryption"
      return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources,'ignored': ignored}
    except Exception as e:
      return self.returnFailjson(str(e))
