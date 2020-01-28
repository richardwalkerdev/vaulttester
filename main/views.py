from rest_framework.response import Response
from rest_framework.decorators import api_view
import hvac, os, boto.ec2
from django.conf import settings
import time


# Key Value Tester
@api_view(['GET'])
def kv(request):
    # Reusable function for obtaining environment variables
    def get_env_value(env_variable):
        try:
            return os.environ[env_variable]
        except KeyError:
            error_msg = 'Set the {} environment variable'.format(var_name)
            raise ImproperlyConfigured(error_msg)

    # Set environmant variable VAULT_TOKEN & VAULT_URL
    VAULT_TOKEN = get_env_value('VAULT_TOKEN')
    VAULT_URL = get_env_value('VAULT_URL')
    

    # Check connection and authentication to vault server
    try:
        print("Trying to connect and authenticate.")
        client = hvac.Client(url=os.environ['VAULT_URL'], token=os.environ['VAULT_TOKEN'])
        # Test authentication
        auth_bool = client.is_authenticated()
        print("Connected OK. Authenticated:", auth_bool)
    except:
        print("Error: Failed to connect and/or authenticate.")
        return Response("Error: Failed to connect and/or authenticate.")

    # Write a Key/Value under secret/test of foo/bar 
    # Equivalnet of `vault kv put secret/test foo=bar`
    try:
        create_response = client.secrets.kv.v2.create_or_update_secret(
            path='test',
            secret=dict(foo='bar'),
        )
    except:
        print("Error: Failed to write key value secret to vault.")
        return Response("Error: Failed to write key value secret to vault.")

    # Read the Key/Value pair under `test`
    try:
        read_response = client.secrets.kv.read_secret_version(path='test')
        # Print result to console
        print('Value under path "secret/test" / key "foo": {val}'.format(
            val=read_response['data']['data']['foo'],
        ))
        # Set foo_value
        foo_value = read_response['data']['data']['foo']
    except:
        print("Error: Failed to read key value secret to vault.")
        return Response("Error: Failed to read key value secret to vault.")    

    # Return JSON response
    return Response({"Authenticated": auth_bool, "foo": foo_value})

@api_view(['GET'])
def aws(request):
    # Assumes Dynamic AWS enabled in Vault
    # `vault secrets enable -tls-skip-verify -path=aws aws`
    # Add a role & root aws credentials in your vault

    # Reusable function for obtaining environment variables
    def get_env_value(env_variable):
        try:
            return os.environ[env_variable]
        except KeyError:
            error_msg = 'Set the {} environment variable'.format(var_name)
            raise ImproperlyConfigured(error_msg)

    # Set environmant variable VAULT_TOKEN & VAULT_URL
    VAULT_TOKEN = get_env_value('VAULT_TOKEN')
    VAULT_URL = get_env_value('VAULT_URL')
    

    # Check connection and authentication to vault server
    try:
        print("Trying to connect and authenticate.")
        client = hvac.Client(url=os.environ['VAULT_URL'], token=os.environ['VAULT_TOKEN'])
        # Test authentication
        auth_bool = client.is_authenticated()
        print("Connected OK. Authenticated:", auth_bool)
    except:
        print("Error: Failed to connect and/or authenticate.")
        return Response("Error: Failed to connect and/or authenticate.")

    # Generate AWS credentials
    try:
        gen_creds_response = client.secrets.aws.generate_credentials(
            name='ec2-role',
        )
        print('Generated access / secret keys: {access} / {secret}'.format(
            access=gen_creds_response['data']['access_key'],
            secret=gen_creds_response['data']['secret_key'],
        ))

        # Assign variables for API response 
        aws_gen_access_key_value = gen_creds_response['data']['access_key']
        aws_gen_secret_key = gen_creds_response['data']['secret_key']
 
    except:
        print("Error: Failed to generate AWS credentials.")
        return Response("Error: Failed to generate AWS credentials.")  

    return Response({"Authenticated": auth_bool,"AWS_GEN_ACCESS_KEY": aws_gen_access_key_value,"AWS_GEN_SECRET_KEY": aws_gen_secret_key})

@api_view(['GET'])
def ec2(request):
    # Reusable function for obtaining environment variables
    def get_env_value(env_variable):
        try:
            return os.environ[env_variable]
        except KeyError:
            error_msg = 'Set the {} environment variable'.format(var_name)
            raise ImproperlyConfigured(error_msg)

    # Set environmant variable VAULT_TOKEN & VAULT_URL
    VAULT_TOKEN = get_env_value('VAULT_TOKEN')
    VAULT_URL = get_env_value('VAULT_URL')
    
    # Check connection and authentication to vault server
    try:
        print("Trying to connect and authenticate.")
        client = hvac.Client(url=os.environ['VAULT_URL'], token=os.environ['VAULT_TOKEN'])
        # Test authentication
        auth_bool = client.is_authenticated()
        print("Connected OK. Authenticated:", auth_bool)
    except:
        print("Error: Failed to connect and/or authenticate.")
        return Response("Error: Failed to connect and/or authenticate.")

    # Generate AWS credentials
    try:
        gen_creds_response = client.secrets.aws.generate_credentials(
            name='ec2-role',
        )
        print('Generated access / secret keys: {access} / {secret}'.format(
            access=gen_creds_response['data']['access_key'],
            secret=gen_creds_response['data']['secret_key'],
        ))

        # Assign variables for API response 
        aws_gen_access_key_value = gen_creds_response['data']['access_key']
        aws_gen_secret_key = gen_creds_response['data']['secret_key']
    except:
        print("Error: Failed to generate AWS credentials.")
        return Response("Error: Failed to generate AWS credentials.")  

    # Need some time for the AWS credentials to propagate and be effective
    print("Waiting 30 seconds for credentials to propagate.")
    time.sleep(30)

    # Create an EC2 instace using new credentials
    try:
        # Using the new credentails connect to AWS
        connection = boto.ec2.connect_to_region("eu-west-2",
                     aws_access_key_id = aws_gen_access_key_value,
                     aws_secret_access_key = aws_gen_secret_key)
 
        # Create an EC2 instance 
        connection.run_instances('ami-0a0cb6c7bcb2e4c51',
                                  key_name='vaultkey', 
                                  instance_type='t2.micro',
                                  security_groups=['default'])                          
    except:
        print("Error: Failed to create EC2 instance.")
        return Response("Error: Failed to create EC2 instance.")  

    return Response({"Successful, check your AWS console for new instance."})

@api_view(['GET'])
def ocp(request):
   
    def get_env_value(env_variable):
        try:
            return os.environ[env_variable]
        except KeyError:
            error_msg = 'Set the {} environment variable'.format(env_variable)
            raise ImproperlyConfigured(error_msg)



    VAULT_URL = get_env_value('VAULT_URL')


    # f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
    # jwt = f.read()
    # client = hvac.Client()
    # client = hvac.Client(url='https://vault.mydomain.internal')
    # client.auth_kubernetes("default", jwt)
    # print(client.read('secret/pippo/pluto'))

    # client = hvac.Client(url=os.environ['VAULT_URL'], token=os.environ['VAULT_TOKEN'])

 #   try:
        # OpenShift (from pod)
    f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
    jwt = f.read()
    client.auth_kubernetes(aws-example, jwt)

    # Test authentication
    auth_bool = client.is_authenticated()
    #print("Connected OK. Authenticated:", auth_bool)
    print("Authenticated?", auth_bool)
    # except:
    #     print("Error: Failed to connect and/or authenticate.")
    #     return Response("Error: Failed to connect and/or authenticate.")

    # Generate AWS credentials
    try:
        gen_creds_response = client.secrets.aws.generate_credentials(
            name='ec2-role',
        )
        print('Generated access / secret keys: {access} / {secret}'.format(
            access=gen_creds_response['data']['access_key'],
            secret=gen_creds_response['data']['secret_key'],
        ))

        # Assign variables for API response 
        aws_gen_access_key_value = gen_creds_response['data']['access_key']
        aws_gen_secret_key = gen_creds_response['data']['secret_key']
 
    except:
        print("Error: Failed to generate AWS credentials.")
        return Response("Error: Failed to generate AWS credentials.")  

    return Response({"Authenticated": auth_bool,"AWS_GEN_ACCESS_KEY": aws_gen_access_key_value,"AWS_GEN_SECRET_KEY": aws_gen_secret_key})
