import os
import requests
from langchain_core.tools import tool
from utils import get_secret
import boto3
import json



@tool
def send_whatsapp_message(recipient, message):
    """
    Sends a WhatsApp message using the Meta API.

    :param recipient: The recipient's phone number.
    :return: The JSON response from the API call.
    """
    access_token = get_secret("WhatsAppAPIToken")  # Fetch token from Secrets Manager
    whatsapp_number_id = get_secret("WhatsappNumberID")  # Fetch WhatsApp number ID from Secrets Manager
    if not access_token:
        print("Failed to retrieve access token.")
        return None
    
    url = f"https://graph.facebook.com/v22.0/{whatsapp_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": message}
    }
    
    response = requests.post(url, headers=headers, json=payload)
    return response.json()


@tool
def send_email_via_ses(email_json: str):
    """
    Sends an email using AWS SES.

    Expected JSON format:
    {
        "to_email": "recipient@example.com",
        "subject": "Subject Line",
        "body": "Email body content",
        "is_html": false  # Set to true to enable HTML formatting for a better-looking report
    }

    Note:
    For visually appealing, well-formatted reports (e.g., tables, styled text), set "is_html" to true and use HTML in the "body".

    :param email_json: JSON string containing email details.
    :return: Response message indicating success or failure.
    """
    try:
        # Parse JSON input
        email_data = json.loads(email_json)
        to_email = email_data.get("to_email")
        subject = email_data.get("subject", "No Subject")
        body = email_data.get("body", "")
        is_html = email_data.get("is_html", False)

        # Ensure required fields are present
        if not to_email or not body:
            return "Error: Missing required fields ('to_email' or 'body')."

        # Construct email body (HTML or plain text)
        message_body = {"Html": {"Data": body}} if is_html else {"Text": {"Data": body}}
        ses_client = boto3.client("ses")
        FROM_EMAIL = os.getenv("EMAIL_FROM", "agent@mockify.com")
        # Send email via AWS SES
        response = ses_client.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": message_body,
            },
        )
        return f"Email sent successfully! Message ID: {response['MessageId']}"

    except Exception as e:
        return f"Error sending email: {str(e)}"


tool_list = [send_email_via_ses, send_whatsapp_message]
