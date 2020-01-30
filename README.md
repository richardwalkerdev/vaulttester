
## Introduction 

This guide explores getting HashiCorp Vault running in AWS using Podman, enabling the dynamic "AWS Secrets Engine" feature and using a simple testing application built with Django REST framework. Moving onto deploying the same application onto an OpenShift Container platform and finally, OpenShift exploits Vaults "Kubernetes Auth Method" to authenticate to Vault to retrieve AWS credentials.  

Here is a high-level architecture diagram of the following exercises: 

![Architecture](/img/misc/vault-1.png)

Take note that there are three VPC in the equation. VPC peering is required for the OpenShift cluster to access Vault using private addresses. In simple terms the numbers in green circles depict:

1. application authenticates with Vault using Kubernetes auth method
2. application requests to generate AWS credential
3. AWS credential returned to the application
4. application uses AWS credential to do stuff with permitted AWS resources

### Prerequisites

This guide uses Amazon Web Servers (AWS) to deploy an OpenShift 4 cluster and two RHEL 8 EC2 instances. One instance in its VPC is the management host, the second instance in its VPC hots HashiCorp Vault, external to the OpenShift cluster, also deployed into its dedicated VPC.


### Management EC2 instance & OpenShift 4 Cluster

The steps to provision and install the management EC2 instance in its VPC and deploy the OpenSHift 4 Cluster are detailed here: https://www.richardwalker.dev/guides/aws_openshift4/

After completing _that_ guide, you should have the core of the target architecture:

![Architecture](/img/misc/vault-2.png)


### Deploy HashiCorp Vault

These steps essentially repeat the AWS exercise of adding a new VPC for the Vault server to live in and provide the vault EC2 instance.

Create a VPC for the Vault server to live:

``` bash
aws ec2 create-vpc --cidr-block 10.20.0.0/16
```

Use the output from the previous command, which provides a `VpcId` to name the VPC:

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

Create a new internet gateway:

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

If needed, create a new key-pair:

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

You'll need to obtain and make a note of the unseal key, root token and the suggested `export` environment variable for `VAULT_ADDR`. View the beginning of the logs from the running container to obtain this information. Use `podman ps` to obtain the container ID, for example:

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

And refresh your current shell environment:

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

You'll need to log in using the _Root Token_ recorded earlier (I told you to make a note of it! Hint, use `podman logs`)

``` bash
vault login s.riAiCB7QRiVgmRfTE4wl8VJM
```

Once logged in you can start interacting with Vault. The following command adds a Key/Value pair into the path `secret/smoketest`. Note, if you didn't log in to Vault successfully, you'd receive an API error `missing client token`.

Create a Key/Value secret: 

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

And finally, it can be deleted:

``` bash
vault kv delete secret/smoketest
```

Before moving on, enable the AWS Secrets Engine:

``` bash
vault secrets enable aws
```

Ref. https://www.vaultproject.io/docs/secrets/aws/index.html


### Python Client for Hashicorp Vault

The next logical step is to understand how to work with vault via Python code. I've built a simple Django REST framework project helps test and prove interacting with Vault using the `hvac` package.  

Ref. https://pypi.org/project/hvac/

To test the water, it's worth running and testing the code locally on our Vault EC2 instance. Once happy, we can deploy the code in a project on the OpenShift cluster.

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

An essential aspect is to develop code that exploits environment variables, rather than including such values in `settings.py`, we set environment variables and retrieve them.

Look at this extract from my Python code:

``` python 
# Reusable function for obtaining environment variables
    def get_env_value(env_variable):
        try:
            return os.environ[env_variable]
        except KeyError:
            error_msg = 'Set the {} environment variable'.format(env_variable)
            raise ImproperlyConfigured(error_msg)

    # Set environmant variable VAULT_TOKEN & VAULT_URL
    VAULT_TOKEN = get_env_value('VAULT_TOKEN')
    VAULT_URL = get_env_value('VAULT_URL')
```

It includes a function for retrieving values and kindly prompts you if not set. The application needs the `VAULT_TOKEN` to authenticate with Vault and the `VAULT_URL` to know where the Vault end-point lives.  

In the "development" environment, set them before running the local development python server:

```
export VAULT_TOKEN='s.riAiCB7QRiVgmRfTE4wl8VJM'
export VAULT_URL='http://localhost:8200'
```

And then run the development python server to start up the application:

``` bash
python manage.py runserver
```

Now, you'll need a second SSH session to the vault EC2 instance, open another terminal. The application has three `views` defined. 

The first `view` in my `vaulttester` application, deals with adding a key/value pair secret and reading it back out of Vault, providing a JSON response of both the key and the value:

``` bash
curl http://localhost:8000/vault/kv/
```

```
{"Authenticated":true,"foo":"bar"}
``` 

### Vault AWS Secrets

The second `view`, deals with testing the generation and retrieval of AWS credentials.

The way this works is, we add a privileged AWS credential to Vault which is then used by the AWS secrets engine to generate AWS credentials based on predefined roles. 

Working directly with Vault, make sure the AWS engine is enabled:

``` bash
vault secrets enable aws
```

Then add a valid AWS credential:

``` bash
vault write -tls-skip-verify aws/config/root access_key=AKIASOEJKXREORPFZEZHF secret_key=lCpQtx/3xg38dkNDJSvOMUjw8LzC90Etf/OZn region=eu-west-2
```

The next step is to add an AWS role to Vault. This example role generates AWS credentials that are privileged to access EC2 resources. NOTE: The `Version` is essential, don't change it!

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

View the role:

``` bash
vault read aws/roles/ec2-role
```

With a role in place, new credentials can be now dynamically generated using the role as a reference. 

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

Curling the second `view` in my testing application connects to Vault and generates a new AWS credential based on the pre-defined role.

``` bash
curl http://localhost:8000/vault/aws/
```

Sample output:

```
{"Authenticated":true,"AWS_GEN_ACCESS_KEY":"AKIATNGJKXRYQZDZSXJ7","AWS_GEN_SECRET_KEY":"ow7K7TAAfX2bsxM/Z8OJt1ArwToCAW5LcZ1Wa+Wa"}
```

If you look in your AWS Web console under IAM, you'll see the new credentials appearing:

![Users](/img/misc/vault-users.png)

### Final Smoke test

The third `view` in my `vaulttester` application repeats the previous task and then goes on to create an EC2 instance and prove the generated credentials work. 

There should be nothing more to do at this stage other than test it out:

``` bash
curl http://localhost:8000/vault/ec2/
```

There is a 30-second delay built into this `view` to allow the generated credentials to propagate in AWS. 
All being well, it should complete, and you'll see a new EC2 instance appearing in your AWS Web console. 

### OpenShift 

#### AWS Secrets Engine

The penultimate stage is to deploy the application onto OpenShift and make any necessary configuration changes. At this stage, we'll still use the environment variable `VAULT_TOKEN` with Vaults `Root Token`.   

The OpenShift cluster VPC and Vaults VPC need peering to enable network traffic between the two.

Create a peering connection from cluster-vpc to vault-vpc:

``` bash
aws ec2 create-vpc-peering-connection --vpc-id vpc-0a7aac3645c41d165 --peer-vpc-id vpc-0df2cb717036b98c4
```

Name it:

``` bash
aws ec2 create-tags --resources pcx-0848144bcad633c7b --tags Key=Name,Value=cluster-pcx
```

Accept it:

``` bash
aws ec2 accept-vpc-peering-connection --vpc-peering-connection-id pcx-0848144bcad633c7b
```

Next, the necessary routes need adding.

Add destination CIDR block and target peering connection from vault `rtb` to cluster VPC:

``` bash
aws ec2 create-route --route-table-id rtb-07e90ee1421b842ea --destination-cidr-block 10.0.0.0/16 --vpc-peering-connection-id pcx-0848144bcad633c7b
```

Add destination CIDR block and target peering connection from cluster VPC to vault VPC: (OpenShift creates a route table explicitly associated with three subnets, e.g. cluster-cbx2t-public)

Add all three:

``` bash
aws ec2 create-route --route-table-id rtb-XYZ --destination-cidr-block 10.20.0.0/16 --vpc-peering-connection-id pcx-XYZ

aws ec2 create-route --route-table-id rtb-XYZ --destination-cidr-block 10.20.0.0/16 --vpc-peering-connection-id pcx-XYZ

aws ec2 create-route --route-table-id rtb-XYZ --destination-cidr-block 10.20.0.0/16 --vpc-peering-connection-id pcx-XYZ

```

We also need an inbound firewall rule to allow requests coming from the `10.0.0.0/16` subnet to vault `8200` port.

Using the Security Group associated with your vault instance:

``` bash
aws ec2 authorize-security-group-ingress --group-id sg-0961bf6b882a75b2d --protocol tcp --port 8200 --cidr 10.0.0.0/16
```

### OpenShift Project

With that in place, it's time to deploy my `vaulttester` on to OpenShift.

Login to your OpenShift cluster, in this case, use `kubeadmin` (not recommended but for demonstration purposes and keeping this guide lean and focused):

``` bash
oc login https://api.cluster.domain.com:6443
```

Create a new project:

``` bash
oc new-project vault-tester-project
```

Add the `python-s2i-base` S2I builder image as an image stream :

``` bash
oc import-image python-s2i-base --from quay.io/richardwalkerdev/mys2i --confirm
```

Which can be check with:

``` bash
oc get is
```

Now, deploy the application, both `VAULT_TOKEN` and `VAULT_URL` need to reflect your values, `VAULT_URL` being the private IP address of your Vault EC2 instance. 

``` bash
oc new-app --name vaulttester-app -e VAULT_TOKEN='s.B6zLfE6FTDfwyAInFxk3l0kN' -e VAULT_URL='http://10.20.0.9:8200' python-s2i-base~https://github.com/richardwalkerdev/vaulttester.git
```

The output from the previous command tells you how to tail the logs, check the status of running pods with:


``` bash
oc get pods
```

Next, expose the service to get a route to the application:

``` bash
oc expose svc vaulttester-app
```

And obtain it with:

``` bash
oc get route/vaulttester-app
```

All being well, test it using the route:


``` bash
curl vault-tester-vaulttester.apps.cluster.domain.com/vault/kv/

curl vault-tester-vaulttester.apps.cluster.domain.com/vault/aws/
```

All the previous steps can be captured into a file for simple re-deployment if repeating this exercise:

Capture OpenShift configurations:

``` bash
oc get -o yaml --export is,bc,dc,svc,route > vaulttester-template.yaml
```

Example Usage:

``` bash
oc new-project vaulttester

oc create -f vaulttester-template.yaml
```

### Kubernetes Auth Method

Finally, let's deal with how OpenShift authenticates with Vault. So far, we've passed the `Root Token` as an environment variable, not ideal. 

A better method is possible using Vaults "Kubernetes Auth Method". The Kubernetes Auth Method enables Vault authentication using an OpenShift Service Account.

Ref. https://www.vaultproject.io/docs/auth/kubernetes/


**OpenShift configuration**

Create a "token reviewer" service account in OpenShift:

``` bash
oc create sa vault-auth
```

As explained on the page https://www.vaultproject.io/docs/auth/kubernetes/, the `vault-auth` service account needs permissions to create `tokenreviews.authentication.k8s.io`.

Create a cluster role binding definition file:

``` bash
vi ClusterRoleBinding.yaml
```

```
apiVersion: rbac.authorization.k8s.io/v1beta1
kind: ClusterRoleBinding
metadata:
  name: role-tokenreview-binding
  namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:auth-delegator
subjects:
  - kind: ServiceAccount
    name: vault-auth
    namespace: default
```

And create it:

``` bash
oc create -f ClusterRoleBinding.yaml
```

Notice `system:serviceaccount:vault-tester-project:vault-auth` referes to `system:serviceaccount:<PROJECT_NAME>:<SERVICE_ACCOUNT>`.

Apply it:

``` bash
oc adm policy add-cluster-role-to-user system:auth-delegator system:serviceaccount:vault-tester-project:vault-auth
```

Next, you'll need to obtain the service account token and CA certificate, needed over on the Vault server. 

Get the token for the `vault-auth` service account:

``` bash
svc_jwt=$(oc serviceaccounts get-token vault-auth)
```

Get the name of a running pod:

``` bash
oc get pods
```

And obtain the OpenShift CA certificate from the application pod, example:

``` bash
oc exec vaulttester-app-1-5p5tg -- cat /var/run/secrets/kubernetes.io/serviceaccount/ca.crt >> ca.crt
```

**Vault configuration**

Back on the Vault EC2 instance, export the token and copy the `ca.crt` so they're available for the preceding commands. 

``` bash 
export token_reviewer_jwt=eyJhbGciOiJSUzI1NiIsImtpZCI6IjRqd...
```

Enable the authentication method:

``` bash
vault auth enable kubernetes
```

Configure the "Kubernetes authentication method" to use the `vault-auth` service account token to authenticate with the OpenShift master API:

```
vault write -tls-skip-verify auth/kubernetes/config token_reviewer_jwt=$token_reviewer_jwt kubernetes_host=https://api.cluster.domain.com:6443 kubernetes_ca_cert=@ca.crt 
```

Create a named role policy that allows the client to read our `ec2-role` create earlier:

``` bash
vi aws.hcl
```

```
# Allow a token to generate aws credentials

path "aws/creds/ec2-role" {
  capabilities = ["read", "list"]
}
```
And write the policy

```
vault policy write -tls-skip-verify aws-example aws.hcl
```

Authorization with this back-end is role-based. Add an AWS role in the Kubernetes Auth method:

```
vault write -tls-skip-verify auth/kubernetes/role/aws-example bound_service_account_names=default bound_service_account_namespaces='*' policies=aws-example ttl=1h
```

#### Manual Test

With all that in place, we can test the process manually.

On the OpenShift management instance, get the default service account token from the default namespace:

``` bash
default_account_token=$(oc serviceaccounts get-token default -n default)
```

On the Vault instance, export that `default_account_token`:

```
export default_account_token=eyJhbGciOiJSUzI1NiIsI ...
``` 

And perform a smoke test:

```
vault write -tls-skip-verify auth/kubernetes/login role=aws-example jwt=${default_account_token}
```

The output from the previous command should return a token:

```
Key                                       Value
---                                       -----
token                                     s.aaLpnZwZGUBzITQ1ICdhG0PD
...< omitted output >...
```

The generated token can be used to log into Vault and perform the `vault read aws/creds/ec2-role` because we bound the policy with the Kubernetes role.

Test it out:

```
vault login s.aaLpnZwZGUBzITQ1ICdhG0PD
vault read aws/creds/ec2-role
```


The final view in my `vaulttester` tests this new authentication process, examine the following snippet:

``` python
f = open('/var/run/secrets/kubernetes.io/serviceaccount/token')
jwt = f.read()
client = hvac.Client()
client = hvac.Client(url=os.environ['VAULT_URL'])
client.auth_kubernetes("aws-example", jwt)
```

Unlike the previous `views` this one uses the `jwt` token to authenticate to Vault using the `aws-example` role we added, which in turn is authorised to read `aws/creds/ec2-role` and generate AWS credentials.

``` bash
curl vault-tester-vaulttester.apps.cluster.domain.com/vault/ocp/
``` 

Output:

```
{"Authenticated":true,"AWS_GEN_ACCESS_KEY":"AKIATNGJKXRYSV6V2D4T","AWS_GEN_SECRET_KEY":"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"}
```

### Conclusion

That was quite some effort but hopefully provides enough of a foundation and information to get up and running with Vault integration and OpenShift.  
