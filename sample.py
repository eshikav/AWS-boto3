from checkUnderUtilizedNetworkInstances import checkUnderUtilizedNetworkInstances
import json
import boto3
import collections


client = boto3.client('sts')
cred=client.get_session_token()['Credentials']
credentials={}
credentials['access_key'] = cred['AccessKeyId']
credentials['secret_key'] =  cred['SecretAccessKey']
credentials['session_token'] = cred['SessionToken']
rule_properties={
    "RuleProperties": [
        {
            "Description": "Under utilized EC2 instances less than 10% CPU utilization",
            "IgnoreResourceList": [],
            "ShortDescription": "Under Utilized EC2 instance",
            "IgnoreActionFilters": False,
            "IgnoreFilters": False,
            "Filters": [
                {
                    "Region": ['us-east-1'],
                    "ExcludeResourcesWithTagEquals": {
                        "name" : [],
                        "name1" : []
                    },
                    "TagEquals": {
                        "name" : ["sample","shiva"],
                        "name1" : ["shiva"]
                    }
                }
            ],
            "ActionFilters": [
                {
                    "Action": "Terminate",
                    "ActionTimeInDays": 3
                }
            ],
            "PossibleActions": ["Stop", "Suspend", "Terminate"],
            "Severity": "High",
            "HelpUrl": "www.insisiv.com/cmp/rules/1/help",
            "FixAvailable": False
        }
    ]
}

sample = checkUnderUtilizedNetworkInstances(rule_properties,credentials)
#print json.dumps(sample.mark(),indent=4)
#print sample.getVpcEndpointsWithS3Gateway()
#print json.dumps(sample.checkUnderUtilizedNetworkInstances(),indent=4)
print sample.sweep()
