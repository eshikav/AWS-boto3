import boto3
import json
import sys
client = boto3.client('s3')

def control_x_x_elastic_ips(event):
   buckets =  list(bucket['Name'] for bucket in client.list_buckets()['Buckets'])
   print buckets
   scannedresources = len(buckets)
   ignoredresources = 0
   result = True
   failReason = ""
   offenders = []
   control = "x.x"
   description = "Ensure there are no buckets without  SSE/KMS encryption"
   scored = True
   counter = 0
   for bucket in buckets:
      if bucket not in event['IgnoreResourceList']: 
         try:
            resource=client.get_bucket_encryption(Bucket=bucket)
            print resource
         except Exception as e:
            if "encryption configuration was not found" in str(e):
               counter += 1
               offenders.append(bucket)
      else: 
        ignoredresources += 1 
   if counter != 0:   
        failReason = "There are "+str(counter)+" buckets without  SSE/KMS encryption"
   return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'Failed': counter,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources}

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

print json.dumps(control_x_x_elastic_ips(event),indent=4)
