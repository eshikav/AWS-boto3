import boto3
import json
import sys
client = boto3.client('s3')

def get_buckets():
   return list(bucket for bucket in client.list_buckets()['Buckets'])

def get_public_buckets(bucketlist):
    public_buckets = dict()
    for bucket in bucketlist:
       acl=client.get_bucket_acl(Bucket=bucket['Name'])
       permissions=(list(type['Permission'] for type in acl['Grants'] if type['Grantee']['Type']\
                     == 'Group' and "AllUsers" in type['Grantee']['URI'] ))
       if len(permissions) != 0:
          public_buckets[bucket['Name']] = permissions
    return public_buckets
       
    
    
def control_x_x_elastic_ips(publicbuckets,event):
   result = True
   failReason = ""
   offenders = []
   control = "x.x"
   description = "Ensure there are no buckets exposed publicly"
   scored = True
   counter = 0
   for bucket in publicbuckets:
      print bucket
      if bucket not in event['IgnoreResourceList']: 
        counter += 1
        offenders.append({bucket: publicbuckets[bucket]})
        result = False
        failReason = "There are "+str(counter)+" buckets which are exposed publicly"
      else:
        pass
   return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control}

event={
        "RuleID": 5,
        "RuleName": "UnusedElasticIPs",
        "Severity": "High",
        "Description": "Find uncrypted EBD volumes",
        "Frequency": "cron(0 12 * * ? *)",
        "Service": "EC2",
        "Default_tz": "et",
        "Ignore": "False",
        "IgnoreResourceList": ["aws-athena-query-results-388603454435-us-east-1"],
        "MetricAggregationType": "Average",
        "ComparisonOperator": "LessThanOrEqualToThreshold",
        "Filters" : [{
          "Period": 1,
          "PeriodUnits": "minutes",
          "Delta": 1,
          "DeltaUnits": "hours",
          "ConsecutiveInterval": 5
        }]
       }

buckets_list=get_buckets()
public_buckets=get_public_buckets(buckets_list)
print json.dumps(control_x_x_elastic_ips(public_buckets,event),indent=4)
