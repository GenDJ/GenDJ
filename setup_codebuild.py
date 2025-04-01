#!/usr/bin/env python3
"""
Automates the setup of an AWS CodeBuild project for GenDJ.

Reads configuration from a .env file and creates:
1. Secrets Manager secret for Docker Hub credentials.
2. IAM Role for CodeBuild service.
3. CodeBuild project configured for GPU builds.
"""

import os
import sys
import time
import boto3
import dotenv
import json
import argparse
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

# --- Configuration Loading ---
def load_env(env_file_path):
    """Load and validate environment variables."""
    print(f"--- Loading configuration from {env_file_path} ---")
    env_path = Path(env_file_path)
    if not env_path.exists():
        print(f"Error: Environment file '{env_path}' not found.")
        sys.exit(1)

    dotenv.load_dotenv(env_path)

    required_vars = [
        'AWS_REGION', 'DOCKERHUB_USERNAME', 'DOCKERHUB_PASSWORD',
        'DOCKERHUB_SECRET_NAME', 'CODEBUILD_PROJECT_NAME',
        'CODEBUILD_SERVICE_ROLE_NAME', 'SOURCE_REPO_URL', 'SOURCE_REPO_TYPE',
        'GPU_COMPUTE_TYPE', 'CODEBUILD_IMAGE', 'IMAGE_REPO_NAME', 'IMAGE_TAG'
    ]
    config = {}
    missing = []
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing.append(var)
        else:
            config[var] = value

    if missing:
        print(f"Error: Missing required environment variables in {env_path}: {', '.join(missing)}")
        sys.exit(1)

    # Optional AWS Profile
    config['AWS_PROFILE'] = os.environ.get('AWS_PROFILE')
    print("Configuration loaded successfully.")
    return config

# --- AWS Helper Functions ---

def get_aws_clients(config):
    """Initialize and return Boto3 clients."""
    print("--- Initializing AWS Clients ---")
    try:
        session_args = {'region_name': config['AWS_REGION']}
        if config.get('AWS_PROFILE'):
            print(f"Using AWS Profile: {config['AWS_PROFILE']}")
            session_args['profile_name'] = config['AWS_PROFILE']
        
        session = boto3.Session(**session_args)
        
        # Verify credentials early
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"AWS Credentials OK. Running as: {identity['Arn']}")

        clients = {
            'iam': session.client('iam'),
            'secretsmanager': session.client('secretsmanager'),
            'codebuild': session.client('codebuild')
        }
        print("AWS Clients initialized.")
        return clients
    except (NoCredentialsError, PartialCredentialsError):
        print("Error: AWS credentials not found. Configure AWS CLI or environment variables.")
        sys.exit(1)
    except ClientError as e:
        print(f"Error initializing AWS clients or checking identity: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during AWS client initialization: {e}")
        sys.exit(1)


def create_or_update_secret(secretsmanager, name, username, password):
    """Create or update a secret in AWS Secrets Manager."""
    print(f"--- Managing Secret: {name} ---")
    secret_value = json.dumps({
        'DOCKERHUB_USERNAME': username,
        'DOCKERHUB_PASSWORD': password
    })
    try:
        secretsmanager.create_secret(
            Name=name,
            Description="Docker Hub credentials for CodeBuild",
            SecretString=secret_value,
            Tags=[{'Key': 'ManagedBy', 'Value': 'GenDJSetupScript'}]
        )
        print(f"Successfully created secret '{name}'.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceExistsException':
            print(f"Secret '{name}' already exists. Updating secret value...")
            try:
                secretsmanager.update_secret(SecretId=name, SecretString=secret_value)
                print(f"Successfully updated secret '{name}'.")
            except ClientError as e_update:
                print(f"Error updating secret '{name}': {e_update}")
                return None
        else:
            print(f"Error creating secret '{name}': {e}")
            return None
    
    # Retrieve ARN after creation/update
    try:
        response = secretsmanager.describe_secret(SecretId=name)
        print(f"Secret ARN: {response['ARN']}")
        return response['ARN']
    except ClientError as e_desc:
        print(f"Error describing secret '{name}' after creation/update: {e_desc}")
        return None


def create_codebuild_role(iam, role_name):
    """Create the IAM service role for CodeBuild."""
    print(f"--- Managing IAM Role: {role_name} ---")
    assume_role_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "codebuild.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    })

    role_arn = None
    try:
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=assume_role_policy,
            Description="Service role for GenDJ CodeBuild project",
            Tags=[{'Key': 'ManagedBy', 'Value': 'GenDJSetupScript'}]
        )
        role_arn = response['Role']['Arn']
        print(f"Successfully created IAM role '{role_name}'. ARN: {role_arn}")
        # IAM roles can take a moment to be fully available for policy attachment
        print("Waiting 10 seconds for IAM role propagation...")
        time.sleep(10) 
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"IAM role '{role_name}' already exists. Retrieving ARN...")
            try:
                response = iam.get_role(RoleName=role_name)
                role_arn = response['Role']['Arn']
                print(f"Using existing role. ARN: {role_arn}")
            except ClientError as e_get:
                print(f"Error retrieving existing role '{role_name}': {e_get}")
                return None
        else:
            print(f"Error creating IAM role '{role_name}': {e}")
            return None
            
    return role_arn


def attach_role_policies(iam, role_name, secret_arn):
    """Attach necessary policies to the CodeBuild service role."""
    print(f"--- Attaching Policies to Role: {role_name} ---")
    # Basic policy for CodeBuild logs
    cloudwatch_policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess" 
    # Policy to allow reading the specific Docker Hub secret
    secrets_manager_policy_name = f"CodeBuildReadSecret-{role_name}"
    
    # Create a custom inline policy for fine-grained Secrets Manager access
    secrets_policy_doc = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "secretsmanager:GetSecretValue",
                "Resource": secret_arn # Grant access ONLY to the specific secret
            }
        ]
    })

    policies_to_attach = {
        cloudwatch_policy_arn: "ManagedPolicy",
        secrets_manager_policy_name: "InlinePolicy" 
    }
    
    all_attached = True
    for policy_key, policy_type in policies_to_attach.items():
        try:
            if policy_type == "ManagedPolicy":
                 print(f"Attaching managed policy: {policy_key}")
                 iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_key)
            elif policy_type == "InlinePolicy":
                 print(f"Putting inline policy: {policy_key}")
                 iam.put_role_policy(
                     RoleName=role_name,
                     PolicyName=policy_key,
                     PolicyDocument=secrets_policy_doc
                 )
            print(f"Successfully attached/put policy: {policy_key}")
        except ClientError as e:
            # Ignore if policy is already attached/exists
            if e.response['Error']['Code'] not in ['EntityAlreadyExists', 'LimitExceeded']: 
                 print(f"Error attaching/putting policy '{policy_key}': {e}")
                 all_attached = False
            else:
                 print(f"Policy '{policy_key}' already attached/exists.")

    if all_attached:
         print("All required policies attached successfully.")
    else:
         print("Warning: Failed to attach one or more required policies.")
         
    return all_attached


def create_codebuild_project(codebuild, config, service_role_arn):
    """Create the CodeBuild project."""
    print(f"--- Managing CodeBuild Project: {config['CODEBUILD_PROJECT_NAME']} ---")
    
    # Define environment variables for buildspec.yml
    environment_variables = [
        {'name': 'IMAGE_REPO_NAME', 'value': config['IMAGE_REPO_NAME'], 'type': 'PLAINTEXT'},
        {'name': 'IMAGE_TAG', 'value': config['IMAGE_TAG'], 'type': 'PLAINTEXT'},
        # Add other variables if needed by buildspec.yml
    ]

    project_definition = {
        'name': config['CODEBUILD_PROJECT_NAME'],
        'description': 'Builds the GenDJ serverless Docker image using GPU (Manual Trigger Only)',
        'source': {
            'type': config['SOURCE_REPO_TYPE'],
            'location': config['SOURCE_REPO_URL'],
            'buildspec': 'buildspec.yml', # Assumes buildspec.yml in root
            # 'gitCloneDepth': 1, # Optional: for faster clones if history not needed
            # 'reportBuildStatus': True, # Reports status to GitHub/etc. - Keep if desired
            # No 'triggers' key means manual builds only by default
        },
        'artifacts': {'type': 'NO_ARTIFACTS'}, # We push to Docker Hub, no build artifacts needed
        'environment': {
            'type': 'LINUX_GPU_CONTAINER',
            'image': config['CODEBUILD_IMAGE'],
            'computeType': config['GPU_COMPUTE_TYPE'],
            'privilegedMode': True, # Required for Docker builds
            'environmentVariables': environment_variables,
        },
        'serviceRole': service_role_arn,
        'logsConfig': { # Basic logging configuration
            'cloudWatchLogs': {'status': 'ENABLED'},
            's3Logs': {'status': 'DISABLED'}
        },
        'tags': [{'key': 'ManagedBy', 'value': 'GenDJSetupScript'}]
    }

    try:
        response = codebuild.create_project(**project_definition)
        print(f"Successfully submitted request to create CodeBuild project '{config['CODEBUILD_PROJECT_NAME']}'.")
        # print(f"Project ARN: {response['project']['arn']}") # ARN is in response['project']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
            print(f"CodeBuild project '{config['CODEBUILD_PROJECT_NAME']}' already exists. Attempting update...")
            try:
                # Remove name for update, use it as identifier
                update_definition = project_definition.copy()
                del update_definition['name'] 
                del update_definition['tags'] # Tags cannot be updated here
                
                response = codebuild.update_project(**update_definition)
                print(f"Successfully submitted request to update CodeBuild project '{config['CODEBUILD_PROJECT_NAME']}'.")
            except ClientError as e_update:
                 print(f"Error updating CodeBuild project: {e_update}")
                 return False
        else:
            print(f"Error creating CodeBuild project: {e}")
            return False
            
    return True

# --- Main Execution ---
def main():
    """Main script execution."""
    start_time = time.time()
    print("=== Starting AWS CodeBuild Setup for GenDJ ===")
    
    parser = argparse.ArgumentParser(description="Automate AWS CodeBuild setup for GenDJ.")
    parser.add_argument("--env-file", default=".env.aws-setup", help="Path to environment file")
    args = parser.parse_args()

    # Check if buildspec exists locally before proceeding
    if not Path("buildspec.yml").exists():
        print("Error: buildspec.yml not found in the current directory.")
        print("Please create the buildspec.yml file before running this script.")
        sys.exit(1)

    config = load_env(args.env_file)
    clients = get_aws_clients(config)

    success = False
    try:
        # 1. Setup Secret
        secret_arn = create_or_update_secret(
            clients['secretsmanager'],
            config['DOCKERHUB_SECRET_NAME'],
            config['DOCKERHUB_USERNAME'],
            config['DOCKERHUB_PASSWORD']
        )
        if not secret_arn: raise Exception("Failed to create/update secret.")

        # 2. Setup IAM Role
        role_arn = create_codebuild_role(clients['iam'], config['CODEBUILD_SERVICE_ROLE_NAME'])
        if not role_arn: raise Exception("Failed to create/get IAM role.")

        # 3. Attach Policies
        policies_ok = attach_role_policies(clients['iam'], config['CODEBUILD_SERVICE_ROLE_NAME'], secret_arn)
        if not policies_ok: raise Exception("Failed to attach necessary IAM policies.")

        # 4. Setup CodeBuild Project
        project_ok = create_codebuild_project(clients['codebuild'], config, role_arn)
        if not project_ok: raise Exception("Failed to create/update CodeBuild project.")

        success = True

    except Exception as e:
        print(f"\n>>> An error occurred during setup: {e}")
        success = False

    finally:
        end_time = time.time()
        print("\n--- Setup Script Finished ---")
        print(f"Total execution time: {end_time - start_time:.2f} seconds")

        if success:
            print("\n-----------------------------------------")
            print("  AWS CodeBuild Setup Successful!        ")
            print("-----------------------------------------")
            print("\nNext Steps (Manual Actions Required):")
            print("1. AWS Console -> CodeBuild -> Build projects -> Select your project.")
            if config['SOURCE_REPO_TYPE'] == 'GITHUB':
                 print("2. Source Section: If using a private GitHub repo or wanting build status checks,")
                 print("   ensure the connection to GitHub is authorized (you might need to click 'Connect using OAuth').")
            elif config['SOURCE_REPO_TYPE'] == 'BITBUCKET':
                 print("2. Source Section: Ensure connection to Bitbucket is authorized.")
            print("3. IAM Console -> Roles -> Find your CodeBuild role:")
            print(f"   '{config['CODEBUILD_SERVICE_ROLE_NAME']}'")
            print("   Review attached policies. Consider replacing 'CloudWatchLogsFullAccess'")
            print("   with a more restrictive policy allowing writes only to the specific log group if desired.")
            print("4. CodeBuild Project -> Build details -> Start build (to trigger the build manually). Builds will ONLY run when started manually.")
            print("\nFor Security: Consider removing DOCKERHUB_PASSWORD from your .env file now.")
            sys.exit(0)
        else:
            print("\n-----------------------------------------")
            print("     >>> AWS CodeBuild Setup FAILED <<<    ")
            print("-----------------------------------------")
            print("Please review the logs above for errors.")
            sys.exit(1)


if __name__ == "__main__":
    # Ensure necessary libraries are installed before running
    try:
        import boto3
        import dotenv
    except ImportError as e:
        print(f"Error: Missing required Python library - {e.name}")
        print("Please install dependencies using: pip install -r requirements-aws.txt")
        sys.exit(1)
        
    # Add pathlib import check if needed, though usually built-in
    from pathlib import Path

    main()
