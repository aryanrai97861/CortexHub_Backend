import os
import sys
import json
from dotenv import load_dotenv
from typing import TypedDict,Annotated,List,Union

from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI # For Gemini
from langgraph.graph import StateGraph, END

load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY=os.getenv("TAVILY_API_KEY")

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)

if not TAVILY_API_KEY:
    print("TAVILY_API_KEY not found in .env", file=sys.stderr)
    sys.exit(1)


# --- Define the Agent's Tools ---
# An agent is an LLM that is given tools and a goal.
# This agent will have a web search tool.
tavily_tool = TavilySearchResults(max_results=5) # Web search tool with 5 results
tools = [tavily_tool]


# --- Define the Agent's state ---
# This defines the data that gets passed between the nodes in our graph
class AgentState(TypedDict):
    input:str
    char_history:List[BaseMessage]
    intermediate_steps:Annotated[List[BaseMessage],lambda a,b:a+b]

# --- Define the Agent's Nodes (The building blocks of the workflow) ---

def call_model(state:AgentState):
    """Called when the agent needs to decide what to do next.
    It uses a prompt to decide between a tool or a final answer
    """
    model_with_tools=ChatGoogleGenerativeAI(model="gemini-2.5-pro",google_api_key=GEMINI_API_KEY).bind_tools(tools)
    prompt=ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful AI assistant. You have access to a web search tool to find information."),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{intermediate_steps}"),
        ]
    )
    chain=prompt | model_with_tools
    response=chain.invoke(state)
    return {"intermedate_steps":[response]}

def call_tools(state:AgentState):
    """Calls the tool based on the agent's decision."""
    tool_input=state['intermediate_steps'][-1]
    tool_output=tavily_tool.invoke(tool_input.total_calls[0]['args'])
    return {"intermediate_steps":[tool_output]}

def should_continue(state:AgentState):
    """Decides whether to continue the loop(call a tool) or end the graph"""
    last_message=state['intermediate_steps'][-1]
    # If the last message contains tool calls, we continue to call the tool.
    if "tool_calls" in last_message.additional_kwargs:
        return "continue"
    else:
        # Otherwise, we have a final answer, so we end.
        return "end"
    
# --- Build the Langgraph workflow ---
workflow=StateGraph(AgentState)

workflow.add_node("agent",call_model)
workflow.add_node("action",call_tools)

# Define the start node and conditional edge
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {"continue":"action","end":END}
)

# Define the edge for returning to the agent after the tool is run
workflow.add_edge("action","agent")

# Compile the graph
app_graph=workflow.compile()

# --- Main execution block for when script is called by Node.js ---
if __name__ == "__main__":
    operation = sys.argv[1]

    if operation == "run_agent":
        goal = sys.argv[2]
        
        # This is where you would call the graph with the input
        inputs = {"input": goal, "chat_history": [], "intermediate_steps": []}
        
        # We run the graph and collect the final output
        final_output = app_graph.invoke(inputs)

        # Format the final output into a structured log for the frontend
        # The final answer is in the last message of intermediate_steps
        final_answer_message = final_output['intermediate_steps'][-1]
        
        # We can extract the final text and simulate a simple log
        simulated_log = [
            { "id": "log-1", "type": "goal", "text": f"Goal received: \"{goal}\"", "timestamp": "" },
            { "id": "log-2", "type": "status", "text": "Agent is planning steps...", "timestamp": "" },
            { "id": "log-3", "type": "result", "text": final_answer_message.content, "details": "This is a detailed result from the agent's process.", "timestamp": "" },
        ]
        
        print(json.dumps({ "message": "Agent execution complete.", "log": simulated_log }))
    
    else:
        print(f"Unknown operation: {operation}", file=sys.stderr)
        sys.exit(1)