# backend/python_scripts/langgraph_agent.py

import os
import sys
import json
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List, Union
from datetime import datetime

from langchain_core.tools import tool
from langchain_tavily import TavilySearch # Correct import for TavilySearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

if not TAVILY_API_KEY:
    print("TAVILY_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

# --- Define the Agent's Tools ---
tavily_tool = TavilySearch(max_results=5, api_key=TAVILY_API_KEY)
tools = [tavily_tool]

# --- Define the Agent's state ---
class AgentState(TypedDict):
    input: str
    chat_history: List[BaseMessage]
    intermediate_steps: Annotated[List[Union[AIMessage, ToolMessage]], lambda a, b: a + b] # Corrected type annotation for clarity

# --- Define the Agent's Nodes ---

def call_model(state: AgentState):
    """Called when the agent needs to decide what to do next."""
    model_with_tools = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        google_api_key=GEMINI_API_KEY,
        temperature=0
    ).bind_tools(tools)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant. You have access to a web search tool to find information. Use the chat history to maintain context across the conversation."),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{intermediate_steps}"),
    ])
    
    chain = prompt | model_with_tools
    response = chain.invoke(state)
    return {"intermediate_steps": [response]}

def call_tools(state: AgentState):
    """Calls the tool based on the agent's decision."""
    last_message = state['intermediate_steps'][-1]
    
    # Check if the last message has tool calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        # Assuming only one tool call for simplicity
        tool_call = last_message.tool_calls[0]
        tool_output = tavily_tool.invoke(tool_call['args'])
        
        # Create a tool message
        tool_message = ToolMessage(
            content=str(tool_output),
            tool_call_id=tool_call['id']
        )
        return {"intermediate_steps": [tool_message]}
    else:
        # No tool calls, return empty
        return {"intermediate_steps": []}

def should_continue(state: AgentState):
    """Decides whether to continue the loop or end the graph"""
    last_message = state['intermediate_steps'][-1]
    
    # Check if the last message has tool calls
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue"
    else:
        return "end"

# --- Build the Langgraph workflow ---
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("action", call_tools)

# Define the start node and conditional edge
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"continue": "action", "end": END}
)

# Define the edge for returning to the agent after the tool is run
workflow.add_edge("action", "agent")

# Compile the graph
app_graph = workflow.compile()

# --- History Management Functions ---

def load_history_from_file(session_id: str) -> List[BaseMessage]:
    """Load chat history from a JSON file"""
    history_file = f"chat_history_{session_id}.json"
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                history_data = json.load(f)
                history = []
                for msg in history_data:
                    if msg['type'] == 'human':
                        history.append(HumanMessage(content=msg['content']))
                    elif msg['type'] == 'ai':
                        history.append(AIMessage(content=msg['content']))
                return history
        except Exception as e:
            print(f"Error loading history: {e}", file=sys.stderr)
    return []

def save_history_to_file(session_id: str, history: List[BaseMessage]):
    """Save chat history to a JSON file"""
    history_file = f"chat_history_{session_id}.json"
    try:
        history_data = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                history_data.append({"type": "human", "content": msg.content})
            elif isinstance(msg, AIMessage):
                history_data.append({"type": "ai", "content": msg.content})
        
        with open(history_file, 'w') as f:
            json.dump(history_data, f, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}", file=sys.stderr)

# --- Main execution block ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <operation> [args...]", file=sys.stderr)
        sys.exit(1)
        
    operation = sys.argv[1]

    if operation == "run_agent":
        if len(sys.argv) < 4:
            print("Usage: python script.py run_agent <goal> <session_id>", file=sys.stderr)
            sys.exit(1)
            
        goal = sys.argv[2]
        session_id = sys.argv[3]
        
        try:
            # Load existing chat history
            chat_history = load_history_from_file(session_id)
            
            # Initialize inputs with chat history and new user goal
            inputs = {
                "input": goal,
                "chat_history": chat_history,
                "intermediate_steps": []
            }
            
            # Run the graph
            final_output = app_graph.invoke(inputs)

            # Extract the final answer
            if final_output['intermediate_steps']:
                final_message = final_output['intermediate_steps'][-1]
                final_text = final_message.content if hasattr(final_message, 'content') else str(final_message)
            else:
                final_text = "No response generated"
            
            # Update chat history with new interaction
            updated_history = chat_history + [
                HumanMessage(content=goal),
                AIMessage(content=final_text)
            ]
            
            # Save updated history
            save_history_to_file(session_id, updated_history)
            
            # Create a structured log for the frontend
            current_time = datetime.now().strftime("%H:%M:%S") # My Comment: Use Python's datetime for a timestamp
            
            simulated_log = [
                {"id": "log-1", "type": "goal", "text": f"Goal received: \"{goal}\"", "timestamp": current_time},
                {"id": "log-2", "type": "status", "text": "Agent is processing...", "timestamp": current_time},
                {"id": "log-3", "type": "result", "text": final_text, "details": "Agent execution completed", "timestamp": current_time},
            ]
            
            result = {
                "message": "Agent execution complete.",
                "log": simulated_log,
                "session_id": session_id,
                "history_length": len(updated_history)
            }
            
            print(json.dumps(result))
            
        except Exception as e:
            error_result = {
                "error": str(e),
                "message": "Agent execution failed"
            }
            print(json.dumps(error_result), file=sys.stderr)
            sys.exit(1)
    
    elif operation == "get_history":
        if len(sys.argv) < 3:
            print("Usage: python script.py get_history <session_id>", file=sys.stderr)
            sys.exit(1)
            
        session_id = sys.argv[2]
        history = load_history_from_file(session_id)
        
        history_data = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                history_data.append({"type": "human", "content": msg.content})
            elif isinstance(msg, AIMessage):
                history_data.append({"type": "ai", "content": msg.content})
        
        result = {
            "session_id": session_id,
            "history": history_data
        }
        print(json.dumps(result))
        
    elif operation == "clear_history":
        if len(sys.argv) < 3:
            print("Usage: python script.py clear_history <session_id>", file=sys.stderr)
            sys.exit(1)
            
        session_id = sys.argv[2]
        history_file = f"chat_history_{session_id}.json"
        
        if os.path.exists(history_file):
            os.remove(history_file)
            
        result = {
            "message": f"History cleared for session {session_id}",
            "session_id": session_id
        }
        print(json.dumps(result))
        
    else:
        print(f"Unknown operation: {operation}", file=sys.stderr)
        sys.exit(1)