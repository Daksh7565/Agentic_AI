import streamlit as st
import sqlite3
from datetime import datetime
from main2 import app


# Import your app pipeline here
# from your_project import app   # <-- replace with your pipeline import

st.set_page_config(page_title="E-Commerce AI Agent", page_icon="🛒")

st.title("🛒 E-Commerce Support Chatbot")

# --- Initialize session ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "session_id" not in st.session_state:
    from uuid import uuid4
    st.session_state["session_id"] = "S" + str(uuid4().hex[:6]).upper()

# --- Display existing chat history ---
for role, msg in st.session_state["messages"]:
    if role == "customer":
        st.chat_message("user").write(msg)
    else:
        st.chat_message("assistant").write(msg)

# --- Chat input box ---
if prompt := st.chat_input("Ask me about your orders, returns, or products..."):
    # Log customer message
    st.session_state["messages"].append(("customer", prompt))
    st.chat_message("user").write(prompt)

    # Run your pipeline
    query = {"session_id": st.session_state["session_id"], "question": prompt}
    try:
        answer = app.invoke(query)["final_answer"]
    except Exception as e:
        answer = f"⚠️ Error: {e}"

    # Log agent response
    st.session_state["messages"].append(("agent", answer))
    st.chat_message("assistant").write(answer)


# --- Show saved history button ---
def fetch_conversations(session_id):
    conn = sqlite3.connect("mydb.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, created_at FROM conversations WHERE session_id=? ORDER BY id",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

if st.sidebar.button("📜 Show Conversation History"):
    history = fetch_conversations(st.session_state["session_id"])
    st.sidebar.write(f"### Session {st.session_state['session_id']} History")
    for role, content, created_at in history:
        if role == "customer":
            st.sidebar.write(f"🧑 **Customer** ({created_at}): {content}")
        else:
            st.sidebar.write(f"🤖 **Agent** ({created_at}): {content}")
