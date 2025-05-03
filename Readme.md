
# Communication Agent Service

## Overview
This service is a serverless application built using AWS SAM that handles multi-channel communication (WhatsApp and Email) through a unified interface. It uses LangGraph for orchestrating the communication flow and integrates with various AWS services including Lambda, DynamoDB, Step Functions, and SES.

## Prerequisites

### AWS Resources
- AWS Account with appropriate permissions
- AWS SAM CLI installed
- Python 3.10
- AWS CLI configured with appropriate credentials

### Required AWS Secrets
The following secrets need to be configured in AWS Secrets Manager:

1. `WhatsAppAPIToken` - Meta WhatsApp API access token
2. `WhatsappNumberID` - Meta WhatsApp Business Account Number ID
3. `ApiGWKey` - API Gateway key
4. `ApiGWEndpoint` - API Gateway endpoint

### Environment Variables
The following environment variables are used by the application:


PROFILES_DDB_TABLE=UserProfiles
MODEL_NAME=gpt-4o
PROVIDER_NAME=openai
MSG_HISTORY_TO_KEEP=20
DELETE_TRIGGER_COUNT=30
API_GW_URL=[from secrets]
API_GW_KEY=[from secrets]


## Deployment

### Manual Deployment
1. Clone the repository
2. Install dependencies:
   bash
   pip install -r requirements.txt
   
3. Build the SAM application:
   bash
   sam build --use-container
   
4. Deploy the application:
   bash
   sam deploy --guided
   

### Automated Deployment (GitHub Actions)
The repository includes a GitHub Actions workflow that automatically deploys the application when changes are pushed to the main branch.

#### GitHub Actions Setup
1. Configure the following secrets in your GitHub repository:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

2. The workflow will automatically:
   - Set up Python
   - Configure AWS credentials
   - Build and deploy the SAM application

## Infrastructure

### AWS Resources Created
- Lambda Function (CommsAgentFunction)
  - Runtime: Python 3.10
  - Memory: 512MB
  - Timeout: 60 seconds

### IAM Permissions
The Lambda function is granted permissions to:
- Access Secrets Manager
- Send emails via SES
- Access DynamoDB tables
- Interact with Step Functions

## DynamoDB Schema

The application uses a DynamoDB table named 'UserProfiles' with the following structure:
- Primary Key: `profile_id`
- GSI: `UserIdIndex` on `userid`
- Additional attributes:
  - `channel`
  - `userid`

## Communication Channels

### WhatsApp
- Utilizes Meta's WhatsApp Business API
- Requires valid WhatsApp Business Account
- Messages are sent using the WhatsApp API token

### Email
- Uses AWS SES for email communication
- Supports both plain text and HTML formatted emails


## License

This project is licensed under the MIT License - see the LICENSE file for details