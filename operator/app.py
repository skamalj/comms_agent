import json
from tools import tool_list
from utils import get_secret
# import requests

from langgraph.graph import StateGraph,  START, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage,  HumanMessage
from langgraph_dynamodb_checkpoint import DynamoDBSaver
from langgraph_utils import call_model, create_tools_json
import os
from langgraph_reducer import PrunableStateFactory
import boto3

model_name = model=os.getenv("MODEL_NAME")
provider_name = os.getenv("PROVIDER_NAME")
profiles_table = os.getenv("PROFILES_DDB_TABLE")
stepfunctions = boto3.client("stepfunctions")

tool_node = ToolNode(tools=tool_list)

    
def should_continue(state) -> str:
    last_message = state['messages'][-1]
    if not last_message.tool_calls:
        return END
    return 'tools'

# Function to call the supervisor model
def call_gw_model(state): 
    with open("agent_prompt.txt", "r", encoding="utf-8") as file:
        system_message = file.read()
        messages = state["messages"]
        system_msg = SystemMessage(content=system_message)

        if isinstance(messages[0], SystemMessage):
            messages[0]=system_msg
        else:
            messages.insert(0, system_msg)

        json_tools = create_tools_json(tool_list)
        response = call_model(model_name, provider_name, messages, json_tools)
        
        return {"messages": [response]}

def init_graph():
    with DynamoDBSaver.from_conn_info(table_name="whatsapp_checkpoint", max_write_request_units=100,max_read_request_units=100, ttl_seconds=86400) as saver:
        graph = StateGraph(PrunableMessagesState)
        
        graph.add_node("agent", call_gw_model)
        graph.add_node("tools", tool_node)
    
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", should_continue, ["tools", END])
        graph.add_edge("tools", "agent")
       
        app = graph.compile(checkpointer=saver)
        return app

min_number_of_messages_to_keep = int(os.environ.get("MSG_HISTORY_TO_KEEP", 20))
max_number_of_messages_to_keep = int(os.environ.get("DELETE_TRIGGER_COUNT", 30))    
PrunableMessagesState = PrunableStateFactory.create_prunable_state(min_number_of_messages_to_keep, max_number_of_messages_to_keep)   

app = init_graph()

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")  # Change region if needed
table = dynamodb.Table(profiles_table)

def get_profile_id(userid):
    """Fetch profile_id from DynamoDB using GSI on userid."""
    response = table.query(
        IndexName="UserIdIndex",
        KeyConditionExpression="userid = :uid",
        ExpressionAttributeValues={":uid": userid}
    )
    items = response.get("Items", [])
    return items[0]["profile_id"] if items else None

def get_all_userids_and_channels(profile_id):
    """Fetch all userids and channels associated with the profile_id."""
    response = table.query(
        KeyConditionExpression="profile_id = :pid",
        ExpressionAttributeValues={":pid": profile_id}
    )
    items = response.get("Items", [])
    return [(item["userid"], item["channel"]) for item in items]

def handle_message(channel_type, recipient, message, from_agent):
    # Step 1: Get profile_id for this user
    profile_id = get_profile_id(recipient)
    if not profile_id:
        print(f"No profile found for user: {recipient}, skipping.")
        return None

    # Step 2: Get all associated userids & channels
    user_profiles = get_all_userids_and_channels(profile_id)

    # Format profiles for the prompt
    profile_info = "\n".join(
        [f"- UserID: {uid}, Channel: {ch}" for uid, ch in user_profiles]
    )

    print(f"User Profiles for {recipient}: \n{profile_info}")

    # Step 3: Construct the prompt for the Comms-Agent
    prompt = (
        f"Send the following message to user {recipient} on the {channel_type} channel:\n"
        f"- Message: {message}\n\n"
        f"Here are all associated user profiles:\n"
        f"{profile_info}\n\n"
    )

    input_message = {
        "messages": [HumanMessage(prompt)],
    }

    config = {"configurable": {"thread_id": profile_id}}
    response = app.invoke(input_message, config)
    print("Response:", response)

    # Step 4: Parse response from Comms-Agent and construct final return response
    comms_agent_response = response["messages"][-1].content

    # Assuming the comms_agent_response is in the format:
    # {"nextagent": "END", "message": "User-facing message delivered"}
    if isinstance(comms_agent_response, str) and comms_agent_response.strip():
        parsed_response = json.loads(comms_agent_response)
    elif isinstance(comms_agent_response, dict):
        parsed_response = comms_agent_response
    else:
        raise ValueError("Invalid response: not JSON or empty")


    # Final return response
    return {
        "fromagent": "comms-agent",  # Identifying this agent
        "nextagent": from_agent if parsed_response.get("nextagent") == "REPLY" else "END",  # If nextagent is REPLY, use from_agent; otherwise, END
        "message": parsed_response.get("message", ""),  # User-facing message or correction for next agent
        "thread_id": profile_id,
        "channel_type": channel_type,
        "from": recipient
    }

def lambda_handler(event, context):
    print("Received event:", json.dumps(event, indent=2))

    # Handle Step Function event with task token
    if "taskToken" in event and "input" in event:
        task_token = event["taskToken"]
        input_data = event["input"]
        channel_type = input_data.get("channel_type")
        from_agent = input_data.get("from_agent")
        recipient = input_data.get("from")
        message = input_data.get("message")

        result = handle_message(channel_type, recipient, message, from_agent)
        if result:
            stepfunctions.send_task_success(
                taskToken=task_token,
                output=json.dumps(result)
            )
        else:
            stepfunctions.send_task_failure(
                taskToken=task_token,
                error="UserProfileError",
                cause="Missing profile or invalid input."
            )
        return

    else:
        print("Incorrect event format. Expected 'taskToken' and 'input'.")
        if "taskToken" in event:
            task_token = event["taskToken"]
            # Send failure response to Step Function
            stepfunctions.send_task_failure(
                    taskToken=task_token,
                    error="IncorrectEventError",
                    cause="Invalid input."
                )
            return
        else:
            print("Incorrect event format. Expected 'taskToken' and 'input'.")
            return
