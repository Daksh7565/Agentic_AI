# E-Commerce AI Support Agent

This project is an AI-powered chatbot designed to provide customer support for an e-commerce platform. It leverages natural language processing to understand customer queries and interacts with a database to fetch information about orders, returns, and products. The application is built with Python, Streamlit, and the LangChain library, featuring a modular architecture orchestrated by LangGraph.

## Features

*   **Order Status Inquiry**: Customers can ask for the status of their orders.
*   **Product Information**: Provides details about products, such as price and stock availability.
*   **Returns Processing**: Can initiate and provide information about product returns.
*   **Conversation History**: Saves and displays the chat history for each session.
*   **Natural Language Understanding**: Utilizes large language models to interpret user intent and generate human-like responses.
*   **SQL Generation**: Dynamically generates and executes SQL queries to retrieve information from the database.

## How It Works

The application is built around a conversational agent powered by LangChain and Groq's LPU Inference Engine. The agent's workflow is defined and managed using LangGraph, which orchestrates a series of nodes to process a user's request:

1.  **Intent Detection**: The user's query is first analyzed to determine the intent (e.g., `order_status`, `product_details`).
2.  **SQL Generation**: Based on the detected intent, a safe SQL `SELECT` query is generated to fetch the relevant information from the database.
3.  **SQL Validation**: The generated SQL is validated to ensure it's a safe query and does not contain any forbidden keywords.
4.  **SQL Execution**: The validated query is executed against the SQLite database.
5.  **Response Generation**: The results from the database are used to generate a user-friendly and conversational response.
6.  **Conversation Logging**: The entire conversation is logged to a SQLite database for history tracking.

The user interface is created with Streamlit, providing a simple and intuitive chat-based experience.

## Project Structure

├── app.py # Main Streamlit application file
├── main2.py # LangGraph pipeline and agent logic
├── mydb.db # SQLite database for conversations and e-commerce data
├── requirements.txt # Python dependencies
└── README.md # This file

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Daksh7565/Agentic_AI.git
    cd Agentic_AI.git
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your Groq API key:**
    You will need a Groq API key to use the language model. You can get one from the [Groq website](https://console.groq.com/keys). Once you have your key, you can set it as an environment variable:
    ```bash
    export GROQ_API_KEY="your-groq-api-key"
    ```
    Alternatively, you can hardcode it in `main2.py` (not recommended for production).

## Usage

To run the application, use the following command in your terminal:

```bash
streamlit run app.py
