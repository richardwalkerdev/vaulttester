## Introduction 

This guide explores getting HashiCorp Vault running in AWS using Podman, enabling the Dynamic AWS secrets feature and using a simple testing application built with Django REST framework. Finally, deploying the same application onto an OpenShift Container platform.

The idea is to test that an application deployed on OpenShift can retrieve AWS IAM credentials from a HashiCorp Vault.

Here is a high-level architecture diagram of the following exercises: 

![Architecture](/images/misc/vault-1.png)

### Prerequisites

This guide uses Amazon Web Servers (AWS) to deploy an OpenShift 4 cluster and two RHEL 8 EC2 instances. One instance will be the management host where the installation of OpenShift will be initiated from. The second will be a HashiCorp Vault instance, external to the Cluster.


### Management EC2 instance & OpenShift 4 Cluster

The steps to provision and install the management EC2 instance in its own VPC and deploy the OpenSHift 4 Cluster are detailed here: https://www.richardwalker.dev/guides/aws_openshift4/

After completing _that_ guide, you should have the core of the target architecture:

![Architecture](/images/misc/vault-2.png)


### Deploy HashiCorp Vault

Continuing on from the previous guide, these steps repeat the AWS exercise of adding a new VPC for the Vault server to live in and provisioning the vault instance.

Create a VPC for the Vault server to live:

``` bash
aws ec2 create-vpc --cidr-block 10.20.0.0/16
```

The output from the previous command provides a `VpcId` which can be used to name the VPC:

``` bash
aws ec2 create-tags --resources vpc-0df2cb717036b98c4 --tags Key=Name,Value=vault-vpc
```

Then, also with the `VpcId`, create a subnet:

``` bash
aws ec2 create-subnet --vpc-id vpc-0df2cb717036b98c4 --cidr-block 10.20.0.0/28
```

The subnet can then be named using the new `subnetId` as output from previous command:

``` bash
aws ec2 create-tags --resources subnet-05f8b78744c97f819 --tags Key=Name,Value=vault-subnet
```

Create an new internet gateway:

``` bash
aws ec2 create-internet-gateway
```

Name the internet gateway using the new `InternetGatewayId` as output from previous command:

``` bash
aws ec2 create-tags --resources igw-0982a0d4b110667e3 --tags Key=Name,Value=vault-igw
```

Attach internet gateway to the vault VPC using `InternetGatewayId` and `VpcId`:

``` bash
aws ec2 attach-internet-gateway --internet-gateway-id igw-0982a0d4b110667e3 --vpc-id vpc-0df2cb717036b98c4
```

Next use the `describe-route-tables` to obtain the new `RouteTableID`. There could be a few but, find the one with the corresponding `DestinationCidrBlock` and `VpcId`:

``` bash
aws ec2 describe-route-tables
```

Create a route for the route table to internet gateway using `RouteTableID` and `InternetGatewayId`:

``` bash
aws ec2 create-route --route-table-id rtb-07e90ee1421b842ea --destination-cidr-block 0.0.0.0/0 --gateway-id igw-0982a0d4b110667e3
```

### Create a Vault EC2 instance

If needed, create a new key-pair, which can also be done via the web console under EC2 KeyPairs:

``` bash
aws ec2 create-key-pair --key-name vaultkey --query 'KeyMaterial' --output text > vaultkey.pem
```

If obtainer from the web console, copy and paste the RSA PRIVATE KEY into a file. Either way, apply the correct file permissions to the file:

``` bash
chmod 600 mgmtkey.pem
```

Using a “Red Hat Enterprise Linux 8 (HVM)” `ami-0a0cb6c7bcb2e4c51`, SSD Volume Type, `t2.micro` (Free tier eligible) with the key-pair just created, a new instance can be spun up within the new subnet and with a public IP address:

``` bash
aws ec2 run-instances --image-id ami-0a0cb6c7bcb2e4c51 --key-name vaultkey --instance-type t2.micro --region eu-west-2 --subnet-id subnet-05f8b78744c97f819  --associate-public-ip-address --count 1
```

Using the `InstanceId` for example `"InstanceId": "i-0666c0f60b87a0bbc"`, name it:

``` bash
aws ec2 create-tags --resources i-0666c0f60b87a0bbc --tags Key=Name,Value=vault-server
```

The instance creation also creates a default security group, using the `GroupId` also found in the output from the instance creation for example `"GroupId": "sg-0961bf6b882a75b2d"`, name the new default Security Group:

``` bash
aws ec2 create-tags --resources sg-0961bf6b882a75b2d --tags Key=Name,Value=vault-sg
```

An inbound rule for SSH port 22 needs to be added to the security group:

``` bash
aws ec2 authorize-security-group-ingress --group-id sg-0961bf6b882a75b2d --protocol tcp --port 22 --cidr 0.0.0.0/0
```

After a couple of minutes get the public IP address for the new EC2 instance:

``` bash
aws ec2 describe-instances --instance-ids i-0666c0f60b87a0bbc
```

And SSH to the new instance:

``` bash
ssh -i vaultkey.pem ec2-user@35.178.14.74
```

### Run Vault using Podman

The easiest method of implementing Vault is to pull the vault container image and run it using Podman.

Install `podman`:

``` bash
sudo dnf install podman -y
```

Pull the vault image from `docker.io`:

``` bash
podman pull vault
```

View the image is now available locally:

``` bash
podman images
```

Now run a container using that image using the default port:

``` bash
podman run -d --cap-add=IPC_LOCK -p 8200:8200 -e 'VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200' vault
```

Check the container is running:

``` bash
podman ps
```

You'll need to obtain and make note of the unseal key, root token and the suggested `export` environment variable for `VAULT_ADDR`. View the beginning of the logs from the running container to obtain this information, the container ID is obtained from the previous `podman ps` command:

```
podman logs eb1564fc266a
```

Example:

```
export VAULT_ADDR='http://0.0.0.0:8200'
Unseal Key: 0w2SdqlY1u3I1mV28FWZxmE3UXlCW9HsOOl0wdi7myg=
Root Token: s.riAiCB7QRiVgmRfTE4wl8VJM
```

Do the export:

``` bash
export VAULT_ADDR='http://0.0.0.0:8200'
```

### Install Vault CLI tool

You'll now need the vault CLI tool in your `PATH`, first download it:

``` bash
sudo dnf install wget unzip -y
```

``` bash
wget https://releases.hashicorp.com/vault/1.3.1/vault_1.3.1_linux_amd64.zip
```

Ensure you have a `~/bin` directory:

``` bash
mkdir ~/bin
```

Extract `vault` into `~/bin`:

``` bash
unzip vault_1.3.1_linux_amd64.zip -d ~/bin
```

And regrach your environemnt:

``` bash 
source ~/.bashrc
```

Check you now have the `vault` command:

```
vault version
```

### Working with Vault

All being well, you should be able to use the `vault` command to check the status or your running Vault container service:

``` bash
vault status
```

You'll need to login using the _Root Token_ recorded earlier (I told you to make a note of it!, hint, use `podman logs`)

``` bash
vault login s.riAiCB7QRiVgmRfTE4wl8VJM
```

Once logged in you can start interacting with Vault. The following command adds a Key/Value pair into the path `secret/smoketest`. Note, if you didn't login as described in the previous step you'll receive an API error `missing client token`:

``` bash 
vault kv put secret/smoketest foo=bar
```

And read it back:

``` bash
vault kv get secret/smoketest
```

Get just the secret for `foo`:

``` bash
vault kv get -field=foo secret/smoketest
``` 

And finally it can be deleted:

``` bash
vault kv delete secret/smoketest
```

Before moving on, enable the AWS Secrets Engine:

``` bash
vault secrets enable aws
```

Ref. https://www.vaultproject.io/docs/secrets/aws/index.html


### Python Client for Hashicorp Vault

The next logical step is to understand how to work with vault via Python code. I've built a simple Django REST framework project that will help test and prove interacting with Vault using the `hvac` package.  

Ref. https://pypi.org/project/hvac/

To test the water at this stage it's worth running and testing the code locally on our Vault EC2 instance. Once happy, the code can be deployed to a project on the OpenShift cluster.

Install Python:

``` bash
sudo dnf install python3 python3-pip -y
```

Install `virtualenv`:

``` bash
pip3 install virtualenv --user
```

Create and change to a working directory:

``` bash
mkdir -p ~/code
cd ~/code
```

Install git:

``` bash
sud dnf install git -y
```
And clone my project:

``` bash
git clone https://github.com/richardwalkerdev/vaulttester.git
```

Create and activate a new Python virtual environment:

``` bash
virtualenv venv
source venv/bin/activate
```

Change directory into the Python project:
``` bash
cd ~/code/vaulttester
```

And install the Python packages:

``` bash
pip install -r requirements.txt
```

### Coding for S2I and OpenShift

A really important aspect is to develop code that exploits environment variables, rather than including such values in `settings.py`, we set environment variables and retrieve them.

Look at this extract from my Python code:

``` python 
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
```

It includes a function for retrieving values and kindling prompts you if not set. The application needs the `VAULT_TOKEN` to authenticate with Vault and the `VAULT_URL` to know where the Vault end-point lives.  

In the "development" environment, set them before running the local development python server:

```
export VAULT_TOKEN = 's.riAiCB7QRiVgmRfTE4wl8VJM'
export VAULT_URL = 'http://localhost:8200'
```

And then run the development python server to start up the application:

``` bash
python manage.py runserver
```

Now, you'll need a second SSH session to the vault EC2 instance, open another terminal. The application has three `views` defined. 

The first view in my `vaulttester` application, deals with adding a key value pair secret and reading it back out of vault, providing a JSON response of both the key and the value:

``` bash
curl http://localhost:8000/vault/kv/
```

```
{"Authenticated":true,"foo":"bar"}
``` 

### Vault AWS Secrets

The second view, deals with testing the generation and retrieval of AWS credentials.

The way this works is a privileged AWS credential is added to vault which is then used by the AWS secrets engine to subsequently generate AWS credentials based on predefined roles. 

Working directly with Vault, make sure the AWS engine is enabled:

``` bash
vault secrets enable aws
```

Then add a valid AWS credential:

``` bash
vault write -tls-skip-verify aws/config/root access_key=ALOWDEJ...EXAMPLE secret_key=lCpQtx/3xg38...EXAMPLE region=eu-west-2
```

The next step is to add an AWS role to vault, this example role provides full EC2 access to the credentials that will be generated. NOTE: The `Version` is important, don't change it!

``` bash
vault write -tls-skip-verify aws/roles/ec2-role \
policy_arns=arn:aws:iam::aws:policy/AmazonEC2FullAccess \
credential_type=iam_user \
policy_document=-<<EOF
{
"Version": "2012-10-17",
"Statement": [
  {
    "Effect": "Allow",
    "Action": [
    "ec2:*"
    ],
    "Resource": [
      "*"
      ]
    }
  ]
}
EOF
```

This role can be then viewed:

``` bash
vault read aws/roles/ec2-role
```

With a role in place, new credentials can be now dynamically generated using the the role as a reference. 

From the command line:

``` bash
vault read aws/creds/ec2-role
```

From Python code:

``` python
gen_creds_response = client.secrets.aws.generate_credentials(
        name='ec2-role',
    )

```

Curling the second view in my testing application will connect to vault and generate a new AWS credential based on the pre-defined role.

``` bash
curl http://localhost:8000/vault/aws/
```

Sample output:

```
{"Authenticated":true,"AWS_GEN_ACCESS_KEY":"AKIATNGJKXRYQZDZSXJ7","AWS_GEN_SECRET_KEY":"ow7K7TAAfX2bsxM/Z8OJt1ArwToCAW5LcZ1Wa+Wa"}
```

If you look in your AWS Web console under IAM, you'll see the new credentials appearing:

![Users](/images/misc/vault-users.png)

### Final Smoke test

The third view in my `vaulttester` application repeats the previous task and then goes on to actually create an EC2 instance and prove it works. 

There should be nothing more to do at this stage other than test it out:

``` bash
curl http://localhost:8000/vault/ec2/
```

There is a 30 second delay built in to this `view` to allow the generated credentials to propagate in AWS. 
All being well, it should complete and you'll see a new EC2 instance appearing in your AWS Web console. 


### OpenShift

The final stage is to now deploy the `vaulttester` application onto OpenShift and make any necessary configuration changes so that it can all work. 

The first thing to deal with how to allow OpenShift to authenticate with Vault. This is made possible using Vaults "Kubernetes Auth Method". So far in this guide, we've been using Vaults `Root Token` to access vault. Kubernetes Auth Method enables Vault authentication using an OpenShift Service Account Token.


``` bash
vault auth enable kubernetes
```

Ref. https://www.vaultproject.io/docs/auth/kubernetes/
