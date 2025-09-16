# -------------------------------
# Imports
# -------------------------------
import re
import sqlite3
from datetime import datetime
from typing import Any, Annotated, Literal
import uuid

from typing_extensions import TypedDict

# LangChain Core
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# LangChain Community
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase

# LangChain Groq
from langchain_groq import ChatGroq

# LangChain Prompts
from langchain.prompts import ChatPromptTemplate

# LangGraph
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode
import os
from dotenv import load_dotenv
load_dotenv()
# -------------------------------
# Database and Toolkit Setup
# -------------------------------
db = SQLDatabase.from_uri("sqlite:///mydb.db")
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    groq_api_key=os.getenv("key")
)

# -------------------------------
# Tools
# -------------------------------
toolkit = SQLDatabaseToolkit(db=db, llm=llm)
t = toolkit.get_tools()
list_table_tool = next((i for i in t if i.name == "sql_db_list_tables"), None)
db_schema_tool = next((i for i in t if i.name == "sql_db_schema"), None)
db_query_tool_instance = next((i for i in t if i.name == "sql_db_query"), None)
db_query_checker_tool = next((i for i in t if i.name == "sql_db_query_checker"), None)
# c=db_query_tool_instance.invoke("select * from products where name=='Laptop' ;")
# print(c)
@tool
def db_query_tool(query: str) -> str:
    """
    Execute a SQL query against the database and return the result.
    If the query is invalid or returns no result, an error message will be returned.
    In case of an error, the user is advised to rewrite the query and try again.
    """
    result = db.run_no_throw(query)
    if not result:
        return "Error: Query failed. Please rewrite your query and try again."
    return result


# -------------------------------
# Prompts
# -------------------------------
sql_prompt = ChatPromptTemplate.from_template("""
You are a helpful AI assistant that converts natural language into valid SQL queries.
The database schema is:
{schema}

Rules:
- Only output a single SQL statement.
- Do NOT include explanations, only SQL.
- Only query tables and columns that exist in the schema.
- By default, generate safe SELECT queries.
- If user asks for modification (INSERT, UPDATE, DELETE), respond with:
  "I can only run safe SELECT queries."

User Question: {question}
SQL Query:
""")

response_prompt = ChatPromptTemplate.from_template("""
You are a customer support assistant. 
User asked: {question}
Database returned: {results}

Write a clear, friendly response for the customer.
""")

intent_prompt = ChatPromptTemplate.from_template("""
You are an assistant for an e-commerce customer support bot.
Classify the user request into one of these intents:
- order_status
- returns
- product_details
- general_inquiry

User request: {question}
Answer with only the intent.
""")


# -------------------------------
# Intent Detection
# -------------------------------
def detect_intent(state: dict):
    question = state["question"]
    intent = llm.invoke(intent_prompt.format(question=question)).content.strip().lower()
    state["intent"] = intent
    return state

def get_new_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())

# -------------------------------
# Conversation Logging
# -------------------------------
def log_conversation(session_id, role, content):
    conn = sqlite3.connect("mydb.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM conversations")
    next_id = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO conversations (id, session_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (next_id, session_id, role, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()


# -------------------------------
# SQL Generation
# -------------------------------
def generate_sql(state: dict):
    question = state["question"]
    intent = state["intent"]
    schema = db.get_table_info()

    sql_prompt_intent = ChatPromptTemplate.from_template("""
    You are an SQL expert for an e-commerce support chatbot.

    Database Schema:
    {schema}

    Rules:
    - Only output a single SELECT statement.
    - Do NOT include explanations or formatting.
    - Only use tables/columns from the schema.
    - The intent of the query is: {intent}

    Extra rules by intent:
    - For order_status → always select: status, tracking_number, created_at
    - For returns → always select: status, reason, created_at
    - For product_details → always select: name, price, stock

    User asked: {question}
    SQL Query:
    """)

    sql_raw = llm.invoke(sql_prompt_intent.format(
        schema=schema,
        intent=intent,
        question=question
    )).content.strip()

    state["sql"] = clean_sql(sql_raw)
    return state


# -------------------------------
# SQL Execution
# -------------------------------
def execute_sql(state: dict):
    if state.get("safe", True):
        try:
            conn = sqlite3.connect("mydb.db")
            cursor = conn.cursor()
            cursor.execute(state["sql"])
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]

            results = [dict(zip(col_names, row)) for row in rows]
            conn.close()
            state["results"] = results
        except Exception as e:
            state["results"] = f"Error: {e}"

    return state


# -------------------------------
# Response Generation
# -------------------------------
# --- New and Improved generate_response function ---
def generate_response(state: dict):
    results = state.get("results", [])
    question = state["question"]
    session_id = state.get("session_id")

    if not session_id:
        session_id = get_new_session_id()
        state["session_id"] = session_id

    # Handle errors or no results
    if isinstance(results, str) or not results:
        final_answer = "Sorry, I couldn’t find any matching records for your request."
        log_conversation(session_id, "customer", question)
        log_conversation(session_id, "agent", final_answer)
        state["final_answer"] = final_answer
        return state

    # Use the LLM to generate a natural response based on the data
    response_prompt_template = """
    You are a friendly and helpful e-commerce customer support assistant.
    A customer asked the following question:
    "{question}"

    Your database query returned the following results:
    {results}

    Based on these results, please provide a clear, conversational, and helpful answer to the customer's question.
    - If the results are a list of items, format them nicely.
    - If the results are a single number or status, state it clearly.
    - Do not mention the database or SQL. Just answer the question directly.
    """
    
    final_prompt = response_prompt_template.format(
        question=question,
        results=results
    )

    # Invoke the LLM to get the final answer
    final_answer = llm.invoke(final_prompt).content.strip()

    log_conversation(session_id, "customer", question)
    log_conversation(session_id, "agent", final_answer)

    state["final_answer"] = final_answer
    return state


# -------------------------------
# SQL Validation
# -------------------------------
def validate_sql(state: dict):
    sql = state["sql"]
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER"]
    if any(word in sql.upper() for word in forbidden):
        state["results"] = "Error: Unsafe SQL detected. Only SELECT queries are allowed."
        state["safe"] = False
    else:
        state["safe"] = True
    return state


def clean_sql(sql: str) -> str:
    sql = sql.strip()
    if sql.lower().startswith("```sql"):
        sql = sql[6:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip()


# -------------------------------
# Build LangGraph pipeline
# -------------------------------
graph = StateGraph(dict)

graph.add_node("detect_intent", RunnableLambda(detect_intent))
graph.add_node("generate_sql", RunnableLambda(generate_sql))
graph.add_node("validate_sql", RunnableLambda(validate_sql))
graph.add_node("execute_sql", RunnableLambda(execute_sql))
graph.add_node("generate_response", RunnableLambda(generate_response))

graph.add_edge(START, "detect_intent")
graph.add_edge("detect_intent", "generate_sql")
graph.add_edge("generate_sql", "validate_sql")
graph.add_edge("validate_sql", "execute_sql")
graph.add_edge("execute_sql", "generate_response")
graph.add_edge("generate_response", END)

app = graph.compile()
# def app():
#     return ap

# -------------------------------
# Example Runs
# -------------------------------
# query1 = {"question": "i want update about my product O007?"}
# query2 = {"question": "Show me the most expensive product."}
# query3 = {"question": "I want to return my product O005."}
# query4 = {"question": "What is the price of P002?"}

# print("\n--- Query 1 ---")
# print(app.invoke(query1)["final_answer"])

# print("\n--- Query 2 ---")
# print(app.invoke(query2)["final_answer"])

# print("\n--- Query 3 ---")
# print(app.invoke(query3)["final_answer"])

# print("\n--- Query 4 ---")
# print(app.invoke(query4)["final_answer"])