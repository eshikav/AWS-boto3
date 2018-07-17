import boto3
import json
import sys

client=boto3.client('ec2')

def get_regions():
    """Summary

    Returns:
        TYPE: Description
    """
    try:
       client = boto3.client('ec2')
       region_response = client.describe_regions()
       regions = [region['RegionName'] for region in region_response['Regions']]
       return regions
    except Exception as e:
       if "not able to validate the provided access credentials" in str(e):
         print 'Check your credentials and rerun again'
         sys.exit(300)
    
def get_addresses(regions): 
   try: 
      return dict((region,boto3.client('ec2',region).describe_addresses()['Addresses'])\
             for region in regions if len(boto3.client('ec2',region).describe_addresses()\
             ['Addresses']) != 0)
   except Exception as e:
      if "not able to validate the provided access credentials" in str(e):
         print 'check your credentials'
      sys.exit(300)

def control_x_x_elastic_ips(regions,event):
   adresses = dict((region,boto3.client('ec2',region).describe_addresses()['Addresses'])\
                 for region in regions if len(boto3.client('ec2',region).describe_addresses()\
                 ['Addresses']) != 0)
   scannedresources=sum(len(adresses[region]) for region in adresses.keys())
   ignoredresources = 0
   result = True
   failReason = ""
   offenders = []
   control = "x.x"
   description = "Ensure all the Allocated Elastic ip's are associated with the instances"
   scored = True
   counter = 0
   for region in adresses.keys():
     for eip in adresses[region]:
       if 'AssociationId' not in eip.keys() and eip['PublicIp'] not in event["IgnoreResourceList"]:
         counter += 1
         offenders.append(dict({'region': region,'id': eip['AllocationId']}))
       else:
         ignoredresources += 1
   if counter != 0:
     failReason = "Account has "+str(counter)+" elastic IP's which are allocated but not being associated"
   return {'Result': result, 'failReason': failReason, 'Offenders': offenders, 'ScoredControl': scored, 'Description': description, 'ControlId': control,'ScannedResources': scannedresources,'IgnoredResources': ignoredresources, 'Failed': counter}

event={
        "RuleID": 5,
        "RuleName": "UnusedElasticIPs",
        "Severity": "High",
        "Description": "Find uncrypted EBD volumes",
        "Frequency": "cron(0 12 * * ? *)",
        "Service": "EC2",
        "Default_tz": "et",
        "Ignore": "False",
        "IgnoreResourceList": ["18.209.218.3"],
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



regions=get_regions()
x=control_x_x_elastic_ips(regions,event) 
print json.dumps(x,indent=4)
